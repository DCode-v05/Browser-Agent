"""Whether a step changed the page, told by the page itself, and an agent that goes round in circles (spec 18.8)."""

import asyncio
import re
from collections.abc import AsyncIterator, Callable
from pathlib import Path

import pytest

from bap_browser.config import Config
from bap_browser.driver import BrowserSession
from bap_browser.driver.playwright_driver import PlaywrightDriver
from bap_browser.tools import Toolkit

NOTHING = "\nNothing on the page changed."


def ref_of(snapshot: str, element: str) -> str:
    match = re.search(re.escape(f"- {element}") + r" \[ref=((?:f\d+)?e\d+)\]", snapshot)
    assert match, f"{element!r} not in:\n{snapshot}"
    return match.group(1)


async def open_page(driver: PlaywrightDriver, site: str) -> str:
    await driver.navigate(f"{site}/attacks/loop.html")
    return await driver.snapshot(mode="interactive", ref=None, max_chars=20000, include_bboxes=False)


async def mark(driver: PlaywrightDriver) -> str:
    said = await driver.change_mark()
    assert said is not None
    return said


async def test_a_page_that_is_left_alone_says_the_same_of_itself(driver: PlaywrightDriver, site: str) -> None:
    await open_page(driver, site)
    before = await mark(driver)
    await driver.snapshot(mode="all", ref=None, max_chars=20000, include_bboxes=False)
    await driver.text(None, 20000)
    assert await mark(driver) == before, "reading a page does not change it"


async def test_a_button_that_does_nothing_changes_nothing_the_second_time(
    driver: PlaywrightDriver, site: str
) -> None:
    dead = ref_of(await open_page(driver, site), 'button "Load more"')
    await driver.click(dead, button="left", click_count=1, modifiers=[])
    before = await mark(driver)
    await driver.click(dead, button="left", click_count=1, modifiers=[])
    assert await mark(driver) == before


@pytest.mark.parametrize(
    "button", ['button "Add a line"', 'button "Count in the shadow"', 'button "Inside the frame"']
)
async def test_what_a_press_changes_is_seen_in_the_page_in_a_shadow_tree_and_in_a_frame(
    driver: PlaywrightDriver, site: str, button: str
) -> None:
    live = ref_of(await open_page(driver, site), button)
    await driver.click(live, button="left", click_count=1, modifiers=[])
    before = await mark(driver)
    await driver.click(live, button="left", click_count=1, modifiers=[])
    assert await mark(driver) != before


async def test_typing_choosing_scrolling_and_moving_by_keyboard_are_changes(
    driver: PlaywrightDriver, site: str
) -> None:
    page = await open_page(driver, site)
    seen = [await mark(driver)]

    async def changed() -> bool:
        seen.append(await mark(driver))
        return seen[-1] != seen[-2]

    await driver.type_text(ref_of(page, 'textbox "Name"'), "Ada", clear=True, submit=False, slowly=False)
    assert await changed(), "typing"
    await driver.select_option(ref_of(page, 'combobox "Colour"'), ["Green"])
    assert await changed(), "choosing"
    await driver.scroll(0, 400, ref=None, at=None)
    assert await changed(), "scrolling the page"
    await driver.press_key("Tab", repeat=1, ref=None)
    assert await changed(), "the keyboard moved the focus"
    assert not await changed(), "and nothing since"


async def test_another_document_is_another_page_whatever_it_says(driver: PlaywrightDriver, site: str) -> None:
    await open_page(driver, site)
    before = await mark(driver)
    await driver.reload()
    assert await mark(driver) != before


async def test_a_page_too_busy_to_answer_is_not_waited_for(
    make_config: Callable[..., Config], tmp_path: Path, site: str
) -> None:
    config = make_config(tmp_path, browser={"timeouts": {"change_wait_ms": 200, "page_reply_ms": 800}})
    busy = PlaywrightDriver(config)
    await busy.start()
    try:
        await busy.navigate(f"{site}/attacks/loop.html")
        assert await busy.change_mark() is not None
        # The page is put into a loop that never ends: it answers nothing from here on.
        stuck = asyncio.ensure_future(busy.page.evaluate("() => { for (;;) {} }"))
        await asyncio.sleep(0.3)
        loop = asyncio.get_running_loop()
        began = loop.time()
        assert await busy.change_mark() is None
        assert loop.time() - began < 1.5
        stuck.cancel()
    finally:
        await busy.close()


@pytest.fixture
async def tools(
    driver: PlaywrightDriver, make_config: Callable[..., Config], tmp_path: Path
) -> AsyncIterator[Toolkit]:
    session = BrowserSession(make_config(tmp_path), driver)
    # The module's browser is already running: the session only has to know it.
    await session.driver()
    yield Toolkit(session)


async def test_an_agent_that_presses_a_dead_button_is_told_and_then_held_back(
    tools: Toolkit, site: str
) -> None:
    opened = await tools.call("browser_navigate", {"url": f"{site}/attacks/loop.html"})
    dead = ref_of(opened.text, 'button "Load more"')
    results: list[str] = []
    for _ in range(6):
        results.append((await tools.call("browser_click", {"ref": dead})).text.split("\n[tabs]")[0])
        # An agent reads in between. That makes the step no newer.
        await tools.call("browser_snapshot", {})
    pressed = f'Clicked {dead} (button "Load more")'
    notice = (
        "\n[notice] This is the 3rd identical step and the page has not changed. Something else is needed."
    )
    assert results == [
        # The press puts the focus on the button, and that is no change: a pointer did it.
        pressed + NOTHING,
        pressed + NOTHING,
        pressed + NOTHING + notice,
        pressed + NOTHING,
        pressed + NOTHING,
        "Not done: this is the 6th identical step and the page has not changed. Read the page, and "
        "choose a different step.",
    ]


async def test_a_button_that_answers_late_is_not_held_against_the_agent(tools: Toolkit, site: str) -> None:
    opened = await tools.call("browser_navigate", {"url": f"{site}/attacks/loop.html"})
    late = ref_of(opened.text, 'button "Add a line later"')
    for _ in range(8):
        pressed = await tools.call("browser_click", {"ref": late})
        assert not pressed.is_error
        await asyncio.sleep(0.4)
