"""The tools beyond navigate, snapshot, click and type, against a real browser."""

import re

import pytest

from bap_browser.driver.playwright_driver import PlaywrightDriver
from bap_browser.errors import BadInput, BrowserError, StaleRef


async def read(driver: PlaywrightDriver, mode: str = "interactive") -> str:
    return await driver.snapshot(mode=mode, ref=None, max_chars=20000, include_bboxes=False)


def ref_of(snapshot: str, element: str) -> str:
    match = re.search(re.escape(f"- {element}") + r"[^\n]*\[ref=(e\d+)\]", snapshot)
    assert match, f"{element!r} not in:\n{snapshot}"
    return match.group(1)


async def open_tools(driver: PlaywrightDriver, site: str) -> str:
    await driver.navigate(f"{site}/tools.html")
    return await read(driver)


async def shown(driver: PlaywrightDriver, element_id: str) -> str:
    return await driver.page.inner_text(f"#{element_id}")


async def test_back_forward_and_reload(driver: PlaywrightDriver, site: str) -> None:
    await driver.navigate(f"{site}/tools.html")
    await driver.navigate(f"{site}/welcome.html")
    assert await driver.back() == f"{site}/tools.html"
    assert "Tools" in await read(driver)
    assert await driver.forward() == f"{site}/welcome.html"
    assert await driver.forward() is None
    assert await driver.reload() == f"{site}/welcome.html"
    assert 'heading "Welcome"' in await read(driver)


async def test_going_back_with_no_earlier_page(make_config, tmp_path) -> None:
    fresh = PlaywrightDriver(make_config(tmp_path))
    await fresh.start()
    try:
        assert await fresh.back() is None
    finally:
        await fresh.close()


async def test_the_text_of_the_page_and_of_one_element(driver: PlaywrightDriver, site: str) -> None:
    page = await open_tools(driver, site)
    text, more = await driver.text(None, 20000)
    assert "The price is 42 dollars." in text and more == 0
    assert "[ref=" not in text
    heading, _ = await driver.text(ref_of(page, 'heading "Tools"'), 20000)
    assert heading == "Tools"
    cut, more = await driver.text(None, 10)
    assert len(cut) == 10 and more == len(text) - 10
    with pytest.raises(StaleRef):
        await driver.text("e99999", 100)


async def test_what_was_typed_is_not_in_the_text(driver: PlaywrightDriver, site: str) -> None:
    page = await open_tools(driver, site)
    await driver.type_text(ref_of(page, 'textbox "Search"'), "hunter2")
    text, _ = await driver.text(None, 20000)
    assert "hunter2" not in text


async def test_find_gives_matching_lines_with_refs_that_work(driver: PlaywrightDriver, site: str) -> None:
    await driver.navigate(f"{site}/big.html?n=300")
    found = await driver.find("item 250", 10)
    assert found.lines[0].startswith('- button "Item 250" [ref=')
    # Every button holds the word "item". Only the one that holds the whole phrase comes first.
    assert found.total >= 300 and len(found.lines) == 10
    ref = ref_of(found.lines[0], 'button "Item 250"')
    assert (await driver.click(ref)).target == 'button "Item 250"'
    assert (await driver.find("no such thing here", 10)).lines == []


async def test_a_ref_is_not_what_an_element_says(driver: PlaywrightDriver, site: str) -> None:
    page = await open_tools(driver, site)
    number = ref_of(page, 'button "Products"').removeprefix("e")
    assert (await driver.find(number, 10)).lines == []


async def test_find_reaches_text_and_says_which_element_it_is_in(driver: PlaywrightDriver, site: str) -> None:
    await open_tools(driver, site)
    found = await driver.find("price", 10)
    assert len(found.lines) == 1
    assert re.fullmatch(r'- text "The price is 42 dollars\." \(in e\d+\)', found.lines[0])


async def test_hover_opens_what_hovering_opens(driver: PlaywrightDriver, site: str) -> None:
    page = await open_tools(driver, site)
    assert "Price list" not in page
    outcome = await driver.hover(ref_of(page, 'button "Products"'))
    assert outcome.target == 'button "Products"'
    assert 'link "Price list"' in await read(driver)


async def test_a_click_and_a_hover_at_a_point(driver: PlaywrightDriver, site: str) -> None:
    await open_tools(driver, site)
    outcome = await driver.click_at(650, 60, click_count=2)
    assert outcome.target == 'button "Spot"'
    assert await shown(driver, "spotted") == "Spotted with 2 click"
    assert (await driver.hover_at(650, 60)).target == 'button "Spot"'
    with pytest.raises(BadInput, match="outside the page"):
        await driver.click_at(5000, 60)


async def test_scrolling_the_page(driver: PlaywrightDriver, site: str) -> None:
    await open_tools(driver, site)
    down = await driver.scroll(0, 400)
    assert (down.y, down.moved, down.inside) == (400, True, False)
    assert down.height > 3000
    up = await driver.scroll(0, -4000)
    assert (up.y, up.moved) == (0, True)
    assert (await driver.scroll(0, -400)).moved is False


async def test_scrolling_a_box_inside_the_page(driver: PlaywrightDriver, site: str) -> None:
    page = await open_tools(driver, site)
    # The button is out of sight at the end of the panel. The wheel turns over the panel, not over
    # where the button would be if the panel did not cut it off.
    inside = await driver.scroll(0, 100, ref=ref_of(page, 'button "Deep in the panel"'))
    assert (inside.y, inside.inside, inside.moved) == (100, True, True)
    assert await driver.page.evaluate("scrollY") == 0


async def test_a_click_lands_after_a_menu_under_the_pointer_has_closed(
    driver: PlaywrightDriver, site: str
) -> None:
    page = await open_tools(driver, site)
    # While the pointer is over "Products" its menu is open and pushes the rest of the page down.
    await driver.hover(ref_of(page, 'button "Products"'))
    await driver.click(ref_of(page, 'checkbox "Send me news"'))
    assert await driver.page.is_checked("#news")


async def test_scrolling_an_element_into_view(driver: PlaywrightDriver, site: str) -> None:
    page = await open_tools(driver, site)
    bottom = ref_of(page, 'button "At the bottom"')
    assert (await driver.locate(bottom)).box is None
    assert (await driver.scroll_to(bottom)).target == 'button "At the bottom"'
    assert (await driver.locate(bottom)).box is not None


async def test_key_presses_reach_the_page(driver: PlaywrightDriver, site: str) -> None:
    page = await open_tools(driver, site)
    search = ref_of(page, 'textbox "Search"')
    await driver.type_text(search, "abc")
    await driver.press_key("Control+a", ref=search)
    await driver.press_key("ArrowDown", repeat=3)
    await driver.press_key("Shift+Tab")
    assert (
        await shown(driver, "keys")
        == "Keys: ctrl+Control ctrl+a ArrowDown ArrowDown ArrowDown shift+Shift shift+Tab"
    )


async def test_enter_in_a_form_reports_where_the_page_went(driver: PlaywrightDriver, site: str) -> None:
    await driver.navigate(f"{site}/form.html")
    page = await read(driver)
    name = ref_of(page, 'textbox "Full name"')
    await driver.type_text(name, "Ada")
    outcome = await driver.press_key("Enter", ref=name)
    assert outcome.target == 'textbox "Full name"'
    assert outcome.navigated_to == f"{site}/welcome.html?name=Ada"


async def test_a_key_the_browser_does_not_have(driver: PlaywrightDriver, site: str) -> None:
    await open_tools(driver, site)
    with pytest.raises(BadInput, match="no key of that name"):
        await driver.press_key("Control+Flarp")
    # Control is not left held down: the click that follows is a plain click.
    page = await read(driver)
    await driver.click(ref_of(page, 'checkbox "Send me news"'))
    assert await driver.page.is_checked("#news")


async def test_choosing_an_option_by_label_or_value(driver: PlaywrightDriver, site: str) -> None:
    page = await open_tools(driver, site)
    colour = ref_of(page, 'combobox "Colour"')
    assert (await driver.select_option(colour, ["Green"])).labels == ["Green"]
    assert await shown(driver, "chosen") == "colour: Green"
    assert (await driver.select_option(colour, ["r"])).labels == ["Red"]
    assert (await driver.select_option(colour, ["green"])).labels == ["Green"]
    assert await driver.page.input_value("#colour") == "g"


async def test_choosing_several_options(driver: PlaywrightDriver, site: str) -> None:
    page = await open_tools(driver, site)
    toppings = ref_of(page, 'listbox "Toppings"')
    assert (await driver.select_option(toppings, ["Cheese", "Onion"])).labels == ["Cheese", "Onion"]
    assert await shown(driver, "chosen") == "toppings: Cheese, Onion"


async def test_an_option_that_cannot_be_chosen(driver: PlaywrightDriver, site: str) -> None:
    page = await open_tools(driver, site)
    colour = ref_of(page, 'combobox "Colour"')
    with pytest.raises(
        BadInput, match=re.escape('has no option "Purple". Its options: "--", "Red", "Green", "Blue".')
    ):
        await driver.select_option(colour, ["Purple"])
    with pytest.raises(BrowserError, match='the option "Blue" is disabled'):
        await driver.select_option(colour, ["Blue"])
    with pytest.raises(BadInput, match="takes one option"):
        await driver.select_option(colour, ["Red", "Green"])
    with pytest.raises(BadInput, match="is not a dropdown"):
        await driver.select_option(ref_of(page, 'button "Products"'), ["Red"])


async def test_checking_and_clearing(driver: PlaywrightDriver, site: str) -> None:
    page = await open_tools(driver, site)
    news = ref_of(page, 'checkbox "Send me news"')
    first = await driver.set_checked(news, True)
    assert (first.target, first.checked, first.changed) == ('checkbox "Send me news"', True, True)
    assert await driver.page.is_checked("#news")
    assert (await driver.set_checked(news, True)).changed is False
    assert (await driver.set_checked(news, False)).changed is True
    assert not await driver.page.is_checked("#news")


async def test_a_switch_that_is_not_a_checkbox_element(driver: PlaywrightDriver, site: str) -> None:
    page = await open_tools(driver, site)
    dark = ref_of(page, 'switch "Dark mode"')
    assert (await driver.set_checked(dark, True)).changed
    assert await driver.page.get_attribute("#dark", "aria-checked") == "true"


async def test_what_cannot_be_checked(driver: PlaywrightDriver, site: str) -> None:
    page = await open_tools(driver, site)
    with pytest.raises(BrowserError, match="it is still not checked"):
        await driver.set_checked(ref_of(page, 'checkbox "Locked"'), True)
    with pytest.raises(BadInput, match="is not a checkbox"):
        await driver.set_checked(ref_of(page, 'button "Products"'), True)
    await driver.navigate(f"{site}/form.html")
    form = await read(driver)
    pro = ref_of(form, 'radio "Pro"')
    assert (await driver.set_checked(pro, True)).checked
    with pytest.raises(BadInput, match="is a radio button"):
        await driver.set_checked(pro, False)


async def test_how_each_field_of_a_form_is_filled(driver: PlaywrightDriver, site: str) -> None:
    await driver.navigate(f"{site}/form.html")
    page = await read(driver)
    kinds = {
        'textbox "Full name"': "text",
        'combobox "Country"': "select",
        'checkbox "I accept the terms"': "check",
        'radio "Pro"': "check",
        'button "Create account"': "other",
    }
    for element, kind in kinds.items():
        assert (await driver.locate(ref_of(page, element))).kind == kind, element


async def test_waiting_for_text_to_appear_and_to_go(driver: PlaywrightDriver, site: str) -> None:
    page = await open_tools(driver, site)
    await driver.click(ref_of(page, 'button "Load results"'))
    assert await driver.wait_for_text("three results", gone=False, timeout_s=5)
    assert await driver.wait_for_text("Loading", gone=True, timeout_s=5)
    assert not await driver.wait_for_text("Nothing says this", gone=False, timeout_s=0.3)
    assert not await driver.wait_for_text("Tools", gone=True, timeout_s=0.3)


async def test_waiting_goes_on_in_the_page_that_replaces_this_one(
    driver: PlaywrightDriver, site: str
) -> None:
    await open_tools(driver, site)
    await driver.page.evaluate("setTimeout(() => { location.href = 'welcome.html?name=Ada'; }, 200)")
    assert await driver.wait_for_text("Welcome, Ada", gone=False, timeout_s=5)


async def test_waiting_for_the_page_to_load(driver: PlaywrightDriver, site: str) -> None:
    await open_tools(driver, site)
    assert await driver.wait_for_load("load", 5)
    assert await driver.wait_for_load("networkidle", 5)
