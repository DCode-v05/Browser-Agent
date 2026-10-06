"""Frames in a real browser (spec 5.3): what is inside a frame is read under the frame's line, and an
element inside one is acted on like any other, by a ref that begins with the frame's name."""

import re
from collections.abc import Callable
from pathlib import Path

import pytest

from bap_browser.config import Config
from bap_browser.driver import open_session
from bap_browser.driver.playwright_driver import PlaywrightDriver
from bap_browser.driver.snapshot import NOTICE
from bap_browser.errors import StaleRef
from bap_browser.tools import Toolkit


async def read(driver: PlaywrightDriver, mode: str = "interactive", max_chars: int = 20000) -> str:
    return await driver.snapshot(mode=mode, ref=None, max_chars=max_chars, include_bboxes=False)


def ref_of(snapshot: str, element: str, under: str | None = None) -> str:
    """The ref of an element. `under` names the frame it must be in, by the frame's line."""
    text = snapshot[snapshot.index(f"- {under}") :] if under else snapshot
    found = re.search(re.escape(f"- {element}") + r"[^\n]*\[ref=((?:f\d+)?e\d+)\]", text)
    assert found, f"{element!r} not in:\n{snapshot}"
    return found.group(1)


async def open_frames(driver: PlaywrightDriver, site: str) -> str:
    await driver.navigate(f"{site}/frames.html")
    # The frame from the other site is added by the page's script and loads after the page.
    assert await driver.wait_for_load("networkidle", 10)
    return await read(driver)


async def inside(driver: PlaywrightDriver, frame: str, expression: str) -> object:
    """Asks the page inside a frame, by the frame element's id."""
    handle = await driver.page.query_selector(f"#{frame}")
    assert handle is not None
    content = await handle.content_frame()
    assert content is not None
    return await content.evaluate(expression)


async def test_what_is_inside_a_frame_is_read_under_its_line(driver: PlaywrightDriver, site: str) -> None:
    page = await open_frames(driver, site)
    lines = page.splitlines()
    payment = next(index for index, line in enumerate(lines) if line.startswith('- iframe "Payment"'))
    assert re.fullmatch(r'- iframe "Payment" \[ref=e\d+\]', lines[payment])
    # One step in, with refs that begin with the frame's name.
    assert re.fullmatch(r'  - heading "Sign up" \[ref=f\d+e\d+\] \[level=1\]', lines[payment + 1])
    assert re.fullmatch(r'  - textbox "Full name" \[ref=f\d+e\d+\] \[required\]', lines[payment + 2])
    # A frame has no heading of its own: the page's is the only one.
    assert page.count("Page: ") == 1 and page.count("URL: ") == 1
    # A frame is its own space of names, and every ref is still one of a kind.
    refs = re.findall(r"\[ref=([^\]]+)\]", page)
    assert len(refs) == len(set(refs))
    numbers = [int(ref.rsplit("e", 1)[1]) for ref in refs]
    assert len(numbers) == len(set(numbers)), "a number was used in two frames"


async def test_a_frame_from_another_site_is_read_too(driver: PlaywrightDriver, site: str) -> None:
    page = await open_frames(driver, site)
    other = page[page.index('- iframe "Other site"') :]
    assert re.search(r'\n  - heading "Tools" \[ref=f\d+e\d+\]', other)
    # It is another site, in a process of its own, which this page's script cannot look into.
    assert await driver.page.evaluate("document.getElementById('other').contentDocument") is None


async def test_a_frame_inside_a_frame(driver: PlaywrightDriver, site: str) -> None:
    page = await open_frames(driver, site)
    outer = page[page.index('- iframe "Outer"') :].splitlines()
    assert re.fullmatch(r'  - iframe "Inner" \[ref=(f\d+)e\d+\]', outer[1])
    assert re.fullmatch(r'    - heading "Welcome" \[ref=(f\d+)e\d+\] \[level=1\]', outer[2])
    names = [re.search(r"ref=(f\d+)e", line).group(1) for line in outer[1:3]]  # type: ignore[union-attr]
    assert names[0] != names[1], "the frame inside has a name of its own"


async def test_typing_and_clicking_inside_a_frame(driver: PlaywrightDriver, site: str) -> None:
    page = await open_frames(driver, site)
    name = ref_of(page, 'textbox "Full name"', under='iframe "Payment"')
    typed = await driver.type_text(name, "Ada Lovelace")
    assert typed.target == 'textbox "Full name"'
    assert await inside(driver, "same", "document.getElementById('name').value") == "Ada Lovelace"

    terms = ref_of(page, 'checkbox "I accept the terms"', under='iframe "Payment"')
    assert (await driver.set_checked(terms, True)).changed
    assert await inside(driver, "same", "document.querySelector('[name=terms]').checked") is True
    country = ref_of(page, 'combobox "Country"', under='iframe "Payment"')
    assert (await driver.select_option(country, ["India"])).labels == ["India"]

    # The frame goes to another page; the page around it stays.
    clicked = await driver.click(ref_of(page, 'button "Create account"', under='iframe "Payment"'))
    assert clicked.target == 'button "Create account"' and clicked.navigated_to is None
    await driver.wait_for_load("networkidle", 5)
    after = await read(driver)
    assert '  - heading "Welcome, Ada Lovelace"' in after
    assert after.startswith("Page: Frames\n")


async def test_a_click_inside_a_frame_from_another_site_lands_where_the_element_is(
    driver: PlaywrightDriver, site: str
) -> None:
    page = await open_frames(driver, site)
    # Where an element is on the page: inside the frame, which has a border and a padding of its own.
    products = ref_of(page, 'button "Products"', under='iframe "Other site"')
    box = (await driver.locate(products)).box
    frame = await driver.page.evaluate(
        "(() => { const r = document.getElementById('other').getBoundingClientRect(); return [r.x, r.y]; })()"
    )
    within = await inside(
        driver,
        "other",
        "(() => { const r = document.getElementById('opener').getBoundingClientRect(); return [r.x, r.y]; })()",
    )
    assert box is not None and isinstance(within, list)
    assert (box.x, box.y) == pytest.approx((frame[0] + 5 + 10 + within[0], frame[1] + 5 + 10 + within[1]))
    # This one is outside what the frame shows until the frame is scrolled to it.
    spot = ref_of(page, 'button "Spot"', under='iframe "Other site"')
    assert (await driver.click(spot)).target == 'button "Spot"'
    assert await inside(driver, "other", "document.getElementById('spotted').textContent") == (
        "Spotted with 1 click"
    )
    search = ref_of(page, 'textbox "Search"', under='iframe "Other site"')
    await driver.type_text(search, "typed across sites")
    assert await inside(driver, "other", "document.getElementById('search').value") == "typed across sites"
    await driver.press_key("Control+a", ref=search)
    assert "ctrl+a" in str(await inside(driver, "other", "document.getElementById('keys').textContent"))


async def test_a_frame_out_of_sight_is_brought_into_view_for_a_click(
    driver: PlaywrightDriver, site: str
) -> None:
    page = await open_frames(driver, site)
    assert await driver.page.evaluate("scrollY") == 0
    link = ref_of(page, 'link "Back to sign up"', under='iframe "Far down"')
    await driver.click(link)
    assert await driver.page.evaluate("scrollY") > 0
    await driver.wait_for_load("networkidle", 5)
    assert await inside(driver, "far", "document.title") == "Sign up"


async def test_the_text_of_an_element_inside_a_frame(driver: PlaywrightDriver, site: str) -> None:
    page = await open_frames(driver, site)
    heading = ref_of(page, 'heading "Welcome"', under='iframe "Inner"')
    assert await driver.text(heading, 100) == ("Welcome", 0)
    subtree = await driver.snapshot(mode="all", ref=heading, max_chars=20000, include_bboxes=False)
    assert subtree.splitlines()[-1].startswith('- heading "Welcome" [ref=')


async def test_find_reaches_into_frames(driver: PlaywrightDriver, site: str) -> None:
    await open_frames(driver, site)
    found = await driver.find("Create account", 5)
    assert re.fullmatch(r'- button "Create account" \[ref=f\d+e\d+\]', found.lines[0])
    price = await driver.find("42 dollars", 5)
    assert re.fullmatch(r'- text "The price is 42 dollars\." \(in f\d+e\d+\)', price.lines[0])
    # The ref it gives works.
    await driver.click(ref_of(found.lines[0], 'button "Create account"'))


async def test_a_ref_into_a_frame_that_is_gone_is_stale(driver: PlaywrightDriver, site: str) -> None:
    page = await open_frames(driver, site)
    name = ref_of(page, 'textbox "Full name"', under='iframe "Payment"')
    await driver.page.evaluate("document.getElementById('same').remove()")
    with pytest.raises(StaleRef):
        await driver.click(name)
    # After another page was opened, the frames of this one are no frames any more.
    await driver.navigate(f"{site}/welcome.html")
    with pytest.raises(StaleRef):
        await driver.type_text(name, "late")
    with pytest.raises(StaleRef):
        await driver.locate("f99e1")


async def test_frames_stay_within_the_size_of_one_snapshot(driver: PlaywrightDriver, site: str) -> None:
    await open_frames(driver, site)
    small = await read(driver, max_chars=700)
    assert len(small) <= 700
    assert small.rstrip().endswith(NOTICE)
    assert small.startswith("Page: Frames\n")


async def test_frames_can_be_left_unread_and_only_so_deep(
    make_config: Callable[..., Config], tmp_path: Path, site: str
) -> None:
    for snapshot, expected in (
        ({"include_iframes": False}, (False, False)),
        ({"max_frame_depth": 1}, (True, False)),
    ):
        async with open_session(make_config(tmp_path, browser={"snapshot": snapshot})) as session:
            tools = Toolkit(session)
            await tools.call("browser_navigate", {"url": f"{site}/frames.html"})
            await tools.call("browser_wait", {"load_state": "networkidle"})
            page = (await tools.call("browser_snapshot", {})).text
            assert (
                '- iframe "Payment" [ref=' in page and '  - iframe "Inner" [ref=' in page
            ) or not expected[0]
            assert (
                "Full name" in page,
                'heading "Welcome"'
                in page[page.index('- iframe "Outer"') : page.index('- iframe "Far down"')],
            ) == expected, page


async def test_the_tools_work_on_a_ref_inside_a_frame(
    make_config: Callable[..., Config], tmp_path: Path, site: str
) -> None:
    async with open_session(make_config(tmp_path)) as session:
        tools = Toolkit(session)
        await tools.call("browser_navigate", {"url": f"{site}/frames.html"})
        await tools.call("browser_wait", {"load_state": "networkidle"})
        page = (await tools.call("browser_snapshot", {})).text
        name = ref_of(page, 'textbox "Full name"', under='iframe "Payment"')
        email = ref_of(page, 'textbox "Email"', under='iframe "Payment"')
        filled = await tools.call(
            "browser_fill_form",
            {"fields": [{"ref": name, "value": "Ada"}, {"ref": email, "value": "ada@example.com"}]},
        )
        assert filled.text.startswith(f"Filled: {name}, {email}"), filled.text
        typed = await tools.call("browser_type", {"ref": name, "text": "Grace", "submit": True})
        assert typed.text.startswith(f'Typed 5 characters into {name} (textbox "Full name")'), typed.text
        bad = await tools.call("browser_click", {"ref": "f1x2"})
        assert bad.is_error and "bad value for 'ref'" in bad.text
