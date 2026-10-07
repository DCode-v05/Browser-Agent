import re
import time
from collections.abc import Callable
from pathlib import Path

import pytest

from bap_browser.config import Config
from bap_browser.driver.base import ActionOutcome
from bap_browser.driver.playwright_driver import PlaywrightDriver
from bap_browser.errors import BadInput, BrowserError, StaleRef


async def read(driver: PlaywrightDriver, mode: str = "interactive") -> str:
    return await driver.snapshot(mode=mode, ref=None, max_chars=20000, include_bboxes=False)


def ref_of(snapshot: str, element: str) -> str:
    match = re.search(re.escape(f"- {element}") + r" \[ref=(e\d+)\]", snapshot)
    assert match, f"{element!r} not in:\n{snapshot}"
    return match.group(1)


async def open_form(driver: PlaywrightDriver, site: str) -> str:
    await driver.navigate(f"{site}/form.html")
    return await read(driver)


async def test_typing_fills_a_field(driver: PlaywrightDriver, site: str) -> None:
    page = await open_form(driver, site)
    outcome = await driver.type_text(ref_of(page, 'textbox "Full name"'), "Ada Lovelace")
    assert outcome == ActionOutcome('textbox "Full name"')
    assert 'textbox "Full name" [ref=' in await read(driver)
    assert await driver.page.input_value("#name") == "Ada Lovelace"


async def test_typing_replaces_what_was_there_unless_clear_is_off(
    driver: PlaywrightDriver, site: str
) -> None:
    page = await open_form(driver, site)
    name = ref_of(page, 'textbox "Full name"')
    await driver.type_text(name, "first")
    await driver.type_text(name, "second")
    assert await driver.page.input_value("#name") == "second"
    await driver.type_text(name, " and more", clear=False)
    assert await driver.page.input_value("#name") == "second and more"
    await driver.type_text(name, "")
    assert await driver.page.input_value("#name") == ""


async def test_unusual_characters_arrive_unchanged(driver: PlaywrightDriver, site: str) -> None:
    page = await open_form(driver, site)
    text = "pässwörd 😀 日本語 'quoted' \"double\""
    await driver.type_text(ref_of(page, 'textbox "Full name"'), text)
    assert await driver.page.input_value("#name") == text
    await driver.type_text(ref_of(page, 'textbox "Email"'), "ada@example.com")
    assert await driver.page.input_value("#email") == "ada@example.com"


async def test_typing_slowly_sends_real_key_presses(driver: PlaywrightDriver, site: str) -> None:
    page = await open_form(driver, site)
    await driver.page.evaluate(
        "window.keys = 0; document.getElementById('name').addEventListener('keydown', () => { window.keys++; })"
    )
    await driver.type_text(ref_of(page, 'textbox "Full name"'), "abc", slowly=True)
    assert await driver.page.input_value("#name") == "abc"
    assert await driver.page.evaluate("window.keys") == 3


async def test_typing_without_a_ref_goes_to_the_focused_element(driver: PlaywrightDriver, site: str) -> None:
    await open_form(driver, site)
    await driver.page.focus("#email")
    outcome = await driver.type_text(None, "ada@example.com")
    assert outcome.target == 'textbox "Email"'
    assert await driver.page.input_value("#email") == "ada@example.com"


async def test_typing_with_nothing_focused_asks_for_a_ref(driver: PlaywrightDriver, site: str) -> None:
    await open_form(driver, site)
    with pytest.raises(BadInput, match=r"Nothing is focused. Give the ref of the field to type into."):
        await driver.type_text(None, "x")


async def test_typing_into_something_that_is_not_a_text_field_is_bad_input(
    driver: PlaywrightDriver, site: str
) -> None:
    page = await open_form(driver, site)
    button = ref_of(page, 'button "Create account"')
    with pytest.raises(BadInput, match=rf'{button} \(button "Create account"\) is not a text field'):
        await driver.type_text(button, "x")


async def test_clicking_a_checkbox_and_a_radio_changes_their_state(
    driver: PlaywrightDriver, site: str
) -> None:
    page = await open_form(driver, site)
    outcome = await driver.click(ref_of(page, 'checkbox "I accept the terms"'))
    assert outcome == ActionOutcome('checkbox "I accept the terms"')
    await driver.click(ref_of(page, 'radio "Pro"'))
    after = await read(driver)
    assert 'checkbox "I accept the terms" [ref=' in after
    assert re.search(r'checkbox "I accept the terms" \[ref=e\d+\] \[checked\]', after)
    assert re.search(r'radio "Pro" \[ref=e\d+\] \[checked\]', after)
    assert re.search(r'radio "Free" \[ref=e\d+\] \[unchecked\]', after)


async def test_a_click_that_navigates_says_where_and_the_next_snapshot_is_the_new_page(
    driver: PlaywrightDriver, site: str
) -> None:
    page = await open_form(driver, site)
    await driver.type_text(ref_of(page, 'textbox "Full name"'), "Ada")
    outcome = await driver.click(ref_of(page, 'button "Create account"'))
    assert outcome == ActionOutcome('button "Create account"', f"{site}/welcome.html?name=Ada")
    assert 'heading "Welcome, Ada"' in await read(driver)


async def test_a_link_click_navigates(driver: PlaywrightDriver, site: str) -> None:
    page = await open_form(driver, site)
    outcome = await driver.click(ref_of(page, 'link "Sign in"'))
    assert outcome.navigated_to == f"{site}/welcome.html"


async def test_submit_presses_enter_and_reports_the_navigation(driver: PlaywrightDriver, site: str) -> None:
    page = await open_form(driver, site)
    outcome = await driver.type_text(ref_of(page, 'textbox "Full name"'), "Grace", submit=True)
    assert outcome.navigated_to == f"{site}/welcome.html?name=Grace"


async def test_a_double_click_and_a_modifier_reach_the_page(driver: PlaywrightDriver, site: str) -> None:
    page = await open_form(driver, site)
    await driver.page.evaluate(
        "window.seen = []; document.querySelector('h1').addEventListener('click', (e) => { window.seen.push([e.detail, e.shiftKey]); })"
    )
    await driver.click(ref_of(page, 'heading "Sign up"'), click_count=2, modifiers=["Shift"])
    assert await driver.page.evaluate("window.seen") == [[1, True], [2, True]]


async def test_clickable_things_can_be_clicked(driver: PlaywrightDriver, site: str) -> None:
    await driver.navigate(f"{site}/clickables.html")
    page = await read(driver)
    await driver.click(ref_of(page, 'clickable "Pointer parent"'))
    assert await driver.page.title() == "clicked pointer"


async def test_an_element_off_screen_is_scrolled_into_view_first(driver: PlaywrightDriver, site: str) -> None:
    await driver.navigate(f"{site}/big.html?n=300")
    page = await read(driver)
    await driver.page.evaluate(
        "document.addEventListener('click', (e) => { document.title = e.target.textContent; })"
    )
    await driver.click(ref_of(page, 'button "Item 300"'))
    assert await driver.page.title() == "Item 300"


async def test_a_covered_element_names_what_covers_it(impatient_driver: PlaywrightDriver, site: str) -> None:
    await impatient_driver.navigate(f"{site}/overlay.html")
    pay = ref_of(await read(impatient_driver), 'button "Pay"')
    with pytest.raises(BrowserError) as error:
        await impatient_driver.click(pay)
    assert (
        str(error.value) == f'Could not act on {pay} (button "Pay"): it is covered by dialog "Cookie notice".'
    )


async def test_an_element_that_never_stops_moving_fails_within_the_time_limit(
    impatient_driver: PlaywrightDriver, site: str
) -> None:
    await impatient_driver.navigate(f"{site}/moving.html")
    # A browser that has only just started draws no frame for a moment, and the animation begins
    # with the first frame. The button "never stops moving" only once it has started to move.
    await impatient_driver.page.wait_for_function(
        "document.getAnimations().some((animation) => animation.currentTime > 0)", timeout=10_000
    )
    target = ref_of(await read(impatient_driver), 'button "Catch me"')
    started = time.perf_counter()
    with pytest.raises(BrowserError, match="it is still moving"):
        await impatient_driver.click(target)
    assert time.perf_counter() - started < 3


async def test_a_browser_that_has_just_started_does_not_take_a_moving_element_for_still(
    make_config: Callable[..., Config], tmp_path: Path, site: str
) -> None:
    """The first look at an element can fall inside a frame that is already under way. The wait for
    the next frame then ends within that same frame: the page has not moved on, and finding the
    element where it was says nothing. A browser that has just started draws its first frames far
    apart, which is where this was seen."""
    config = make_config(tmp_path, browser={"timeouts": {"action_ms": 600}})
    for _ in range(3):
        driver = PlaywrightDriver(config)
        await driver.start()
        try:
            await driver.navigate(f"{site}/moving.html")
            await driver.page.wait_for_function(
                "document.getAnimations().some((animation) => animation.currentTime > 0)", timeout=10_000
            )
            target = ref_of(await read(driver), 'button "Catch me"')
            with pytest.raises(BrowserError, match="it is still moving"):
                await driver.click(target)
        finally:
            await driver.close()


async def test_a_disabled_element_is_not_clicked(impatient_driver: PlaywrightDriver, site: str) -> None:
    await impatient_driver.navigate(f"{site}/states.html")
    target = ref_of(await read(impatient_driver), 'button "Disabled button"')
    with pytest.raises(BrowserError, match="it is disabled"):
        await impatient_driver.click(target)


async def test_a_read_only_field_is_not_typed_into(impatient_driver: PlaywrightDriver, site: str) -> None:
    await impatient_driver.navigate(f"{site}/states.html")
    target = ref_of(await read(impatient_driver), 'textbox "Read only"')
    with pytest.raises(BrowserError, match="it is disabled or read-only"):
        await impatient_driver.type_text(target, "x")


async def test_an_element_that_was_removed_is_stale(driver: PlaywrightDriver, site: str) -> None:
    page = await open_form(driver, site)
    target = ref_of(page, 'link "Sign in"')
    await driver.page.evaluate("document.querySelector('a').remove()")
    with pytest.raises(StaleRef, match=f"Ref '{target}' is stale or unknown"):
        await driver.click(target)


async def test_a_ref_from_the_previous_page_is_stale(driver: PlaywrightDriver, site: str) -> None:
    page = await open_form(driver, site)
    old = ref_of(page, 'button "Create account"')
    await driver.navigate(f"{site}/welcome.html")
    with pytest.raises(StaleRef):
        await driver.click(old)
    with pytest.raises(StaleRef):
        await driver.type_text(old, "x")


async def test_rich_text_and_text_areas_take_text(driver: PlaywrightDriver, site: str) -> None:
    await driver.navigate(f"{site}/states.html")
    page = await read(driver)
    await driver.type_text(ref_of(page, 'textbox "Notes"'), "line one\nline two")
    assert await driver.page.input_value("textarea") == "line one\nline two"
    await driver.type_text(ref_of(page, 'textbox "Editor"'), "new text")
    assert await driver.page.inner_text("[contenteditable]") == "new text"


async def test_typing_fails_when_the_page_moves_the_focus_elsewhere(
    driver: PlaywrightDriver, site: str
) -> None:
    await driver.navigate(f"{site}/focus_moves.html")
    password = ref_of(await read(driver), 'textbox "Password"')
    with pytest.raises(BrowserError, match="the page moved the focus to another element"):
        await driver.type_text(password, "hunter2-secret")
    assert await driver.page.input_value("#search") == ""
    assert await driver.page.input_value("#password") == ""


async def test_an_element_inside_a_scrolled_box_is_scrolled_to_and_clicked(
    driver: PlaywrightDriver, site: str
) -> None:
    await driver.navigate(f"{site}/scroll_box.html")
    page = await read(driver)
    for row in (2, 8, 12, 1):
        outcome = await driver.click(ref_of(page, f'button "Row {row}"'))
        assert outcome == ActionOutcome(f'button "Row {row}"')
        assert await driver.page.text_content("#clicked") == f"Clicked row {row}"
