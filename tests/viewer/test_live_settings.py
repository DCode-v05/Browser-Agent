"""The settings screen of a live session, in a real browser (spec 9.12, 10.2): it is drawn from what the
service answers, a change is saved by the service and holds for the agent's next call, and a change a
person may not make is refused where they made it."""

import asyncio
import json
from collections.abc import Callable
from pathlib import Path

from fakes import FakeDriver
from playwright.async_api import Browser

from bap_browser.config import Config
from bap_browser.service.server import Service
from bap_browser.service.session import ServiceSession
from bap_browser.settings import SettingsStore

GROUPS = [
    "Browser",
    "Agent",
    "Approvals",
    "Safety",
    "Sites",
    "Files",
    "Limits",
    "Privacy",
    "Live view",
    "Appearance",
    "Advanced",
]
IS_DARK = "document.documentElement.getAttribute('data-theme') === 'dark'"


async def test_a_person_changes_settings_and_the_service_keeps_them(
    browser: Browser, make_config: Callable[..., Config], tmp_path: Path
) -> None:
    config = make_config(
        tmp_path,
        safety={"blocked_domains": ["*.internal.example"]},
        # What config.json locks is nobody's to change from a screen, the admin's included.
        settings={"locked": ["page_scripts"]},
    )
    settings = SettingsStore(config)
    driver = FakeDriver()
    session = ServiceSession(config, driver, agent="Test agent", settings=settings)
    await session.start()
    service = Service(config, {session.name: session}, port=0, settings=settings)
    await service.start()
    page = await browser.new_page(viewport={"width": 1360, "height": 850})
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    try:
        await page.goto(service.viewer_address)
        await page.get_by_role("button", name="Open settings").click()
        dialog = page.get_by_role("dialog", name="Settings")
        await dialog.get_by_role("tab", name="Browser").wait_for()
        # The screen is the service's own: the groups of this build, and no setting it has not.
        assert [await tab.inner_text() for tab in await dialog.get_by_role("tab").all()] == GROUPS
        assert await dialog.get_by_text("My Chrome", exact=True).count() == 0

        # A change is saved as it is made, and holds for the agent's next call.
        await dialog.get_by_role("tab", name="Approvals").click()
        # The choice shows as taken once the service has saved it.
        await dialog.get_by_role("radio", name="Every action").click()
        await dialog.get_by_text("Saved", exact=True).wait_for()
        assert session.config.safety.ask_before == "every_action"
        click = asyncio.create_task(session.toolkit.call("browser_click", {"ref": "e1"}))
        # The settings screen keeps the pop-up back. Once it is closed, the approval asks.
        await dialog.get_by_role("button", name="Close", exact=True).click()
        popup = page.get_by_role("dialog", name="The agent needs your approval")
        await popup.get_by_role("button", name="Deny").click()
        assert (await asyncio.wait_for(click, 10)).is_error
        assert [call for call in driver.calls if call[0] == "click"] == []
        await page.get_by_role("button", name="Open settings").click()
        # Back to what the deployment has is no loosening.
        await dialog.get_by_role("tab", name="Approvals").click()
        await dialog.get_by_role("radio", name="Risky actions").click()
        await dialog.get_by_text("Saved", exact=True).wait_for()
        assert session.config.safety.ask_before == "risky"

        # What the deployment requires is shown, and is not the person's to change.
        await dialog.get_by_role("tab", name="Advanced").click()
        scripts = dialog.get_by_role("switch", name="Let the agent run scripts in pages")
        assert await scripts.is_disabled()
        await dialog.get_by_text("Set by your organisation").first.wait_for()
        # About this deployment comes from the service too.
        await dialog.get_by_text("0.1.0").wait_for()
        await dialog.get_by_text("safety.blocked_domains").wait_for()

        # A site list: the deployment's entry stays, the person's is added, a bad one is refused in its row.
        await dialog.get_by_role("tab", name="Sites").click()
        await dialog.get_by_text("*.internal.example").wait_for()
        blocked = dialog.get_by_role("textbox", name="Blocked sites")
        await blocked.fill("ads.example\nnot a site")
        await blocked.blur()
        await dialog.get_by_text("That doesn't look like a site. Use a name such as example.com.").wait_for()
        assert session.config.safety.blocked_domains == ["*.internal.example"]
        await blocked.fill("ads.example")
        await blocked.blur()
        await dialog.get_by_text("Saved", exact=True).wait_for()
        assert session.config.safety.blocked_domains == ["*.internal.example", "ads.example"]
        refused = await session.toolkit.call("browser_navigate", {"url": "https://ads.example/"})
        assert refused.is_error and "blocked" in refused.text

        # The colour mode changes the page at once, and is still there after the page is loaded again.
        await dialog.get_by_role("tab", name="Appearance").click()
        await dialog.get_by_role("radio", name="Dark").click()
        await page.wait_for_function(IS_DARK)
        await page.reload()
        await page.get_by_role("button", name="Open settings").wait_for()
        await page.wait_for_function(IS_DARK)
        assert json.loads(Path(config.settings.file).read_text(encoding="utf-8")) == {
            "ask_before": "risky",
            "blocked_sites": ["ads.example"],
            "colour_mode": "dark",
        }
        assert errors == []
    finally:
        # The service first: a page closed while it is connected leaves its socket open.
        await service.stop()
        await session.close()
        await page.close()


async def test_a_person_clears_the_browsing_data_and_the_session_ends(
    browser: Browser, make_config: Callable[..., Config], tmp_path: Path
) -> None:
    profile = tmp_path / "kept-profile"
    (profile / "Default").mkdir(parents=True)
    (profile / "Default" / "Cookies").write_text("signed in", encoding="utf-8")
    config = make_config(tmp_path, browser={"user_data_dir": str(profile)})
    settings = SettingsStore(config)
    session = ServiceSession(config, FakeDriver(), agent="Test agent", settings=settings)
    await session.start()
    service = Service(config, {session.name: session}, port=0, settings=settings)
    await service.start()
    page = await browser.new_page(viewport={"width": 1360, "height": 850})
    try:
        await page.goto(service.viewer_address)
        await page.get_by_role("button", name="Open settings").click()
        dialog = page.get_by_role("dialog", name="Settings")
        await dialog.get_by_role("tab", name="Privacy").click()
        await dialog.get_by_role("button", name="Clear data").click()
        # It asks first, in words that say what will be lost.
        asks = page.get_by_role("alertdialog")
        await asks.get_by_text("Clear cookies and site data in the cloud browser?").wait_for()
        await asks.get_by_text("You'll be signed out of sites there, and open sessions will end.").wait_for()
        assert profile.exists() and session.control == "agent", "nothing is done before the answer"
        await asks.get_by_role("button", name="Clear data").click()
        await page.get_by_text("Browsing data cleared.").wait_for()
        assert not profile.exists() and session.control == "ended"
        await dialog.get_by_role("button", name="Close", exact=True).click()
        await page.get_by_text("It was ended to clear the browsing data.").wait_for()
    finally:
        await service.stop()
        await session.close()
        await page.close()
