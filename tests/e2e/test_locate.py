import re

import pytest

from bap_browser.driver.base import Box, Located
from bap_browser.driver.playwright_driver import PlaywrightDriver
from bap_browser.errors import StaleRef


def ref_of(snapshot: str, element: str) -> str:
    match = re.search(re.escape(f"- {element}") + r" \[ref=(e\d+)\]", snapshot)
    assert match, f"{element!r} not in:\n{snapshot}"
    return match.group(1)


async def read(driver: PlaywrightDriver) -> str:
    return await driver.snapshot(mode="interactive", ref=None, max_chars=20000, include_bboxes=False)


async def test_an_element_is_found_with_its_role_its_name_and_where_it_is(
    driver: PlaywrightDriver, site: str
) -> None:
    await driver.navigate(f"{site}/form.html")
    located = await driver.locate(ref_of(await read(driver), 'button "Create account"'))
    box = await driver.page.locator("button").bounding_box()
    assert box is not None
    assert located == Located(
        "button", "Create account", Box(box["x"], box["y"], box["width"], box["height"])
    )


async def test_finding_an_element_does_not_move_the_page(driver: PlaywrightDriver, site: str) -> None:
    await driver.navigate(f"{site}/big.html?n=300")
    last = ref_of(await read(driver), 'button "Item 300"')
    located = await driver.locate(last)
    assert (located.role, located.name) == ("button", "Item 300")
    # It is below what the picture shows, so there is nothing to outline yet.
    assert located.box is None
    assert await driver.page.evaluate("scrollY") == 0


async def test_an_element_that_is_gone_is_stale(driver: PlaywrightDriver, site: str) -> None:
    await driver.navigate(f"{site}/form.html")
    button = ref_of(await read(driver), 'button "Create account"')
    await driver.navigate(f"{site}/welcome.html")
    with pytest.raises(StaleRef):
        await driver.locate(button)


async def test_a_password_field_is_known_as_one(driver: PlaywrightDriver, site: str) -> None:
    await driver.navigate(f"{site}/form.html")
    page = await read(driver)
    assert (await driver.locate(ref_of(page, 'textbox "Password"'))).secret is True
    assert (await driver.locate(ref_of(page, 'textbox "Full name"'))).secret is False
