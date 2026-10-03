import pytest

from bap_browser.driver.base import TabInfo
from bap_browser.driver.playwright_driver import PlaywrightDriver
from bap_browser.errors import BrowserError


async def test_the_driver_is_alive_and_names_its_browser(driver: PlaywrightDriver) -> None:
    assert driver.is_alive()
    assert driver.description().startswith("Chromium ")


async def test_navigate_returns_the_address_and_updates_the_tab(driver: PlaywrightDriver, site: str) -> None:
    assert await driver.navigate(f"{site}/form.html") == f"{site}/form.html"
    assert await driver.tabs() == [TabInfo("t1", f"{site}/form.html", "Sign up", True)]


async def test_a_page_that_cannot_be_reached_is_a_browser_error(driver: PlaywrightDriver) -> None:
    with pytest.raises(BrowserError, match=r"Could not open http://127\.0\.0\.1:9/: .*ERR_"):
        await driver.navigate("http://127.0.0.1:9/")


async def test_a_navigation_straight_after_a_failed_one_is_not_interrupted(
    driver: PlaywrightDriver, site: str
) -> None:
    with pytest.raises(BrowserError):
        await driver.navigate("http://127.0.0.1:9/")
    assert await driver.navigate(f"{site}/form.html") == f"{site}/form.html"


async def test_the_page_script_runs_out_of_the_pages_sight(driver: PlaywrightDriver, site: str) -> None:
    await driver.navigate(f"{site}/form.html")
    assert await driver.page_script.frames_passed(2, 100) is True
    assert await driver.page.evaluate("typeof __bap") == "undefined"


async def test_an_unknown_operation_is_a_browser_error(driver: PlaywrightDriver, site: str) -> None:
    await driver.navigate(f"{site}/form.html")
    with pytest.raises(BrowserError, match="unknown operation nope"):
        await driver.page_script.call("nope", {})


async def test_the_script_is_installed_again_after_a_navigation(driver: PlaywrightDriver, site: str) -> None:
    await driver.navigate(f"{site}/form.html")
    assert await driver.page_script.frames_passed(1, 100) is True
    await driver.navigate(f"{site}/welcome.html")
    assert await driver.page_script.frames_passed(1, 100) is True


async def test_closing_twice_is_harmless(make_config, tmp_path_factory: pytest.TempPathFactory) -> None:
    extra = PlaywrightDriver(make_config(tmp_path_factory.mktemp("data")))
    await extra.start()
    await extra.close()
    await extra.close()
    assert not extra.is_alive()
