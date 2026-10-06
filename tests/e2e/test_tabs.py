"""Tabs in a real browser (spec 5.3): a window a page opens becomes a tab, and the agent moves between them."""

import asyncio
from collections.abc import Callable
from pathlib import Path

from bap_browser.agent.models import ref_of
from bap_browser.config import Config
from bap_browser.driver import BrowserSession, open_session
from bap_browser.driver.playwright_driver import PlaywrightDriver
from bap_browser.tools import Toolkit


async def test_a_link_that_opens_a_new_tab_is_followed_into_it(
    make_config: Callable[..., Config], tmp_path: Path, site: str
) -> None:
    async with open_session(make_config(tmp_path)) as session:
        tools = Toolkit(session)
        first = await tools.call("browser_navigate", {"url": f"{site}/tabs.html"})
        clicked = await tools.call("browser_click", {"ref": ref_of(first.text, 'link "Open the report"')})
        report = f"{site}/welcome.html?name=Report"
        # The result of the click already shows the new tab, which is now the active one.
        assert clicked.text.endswith(
            f"\n[tabs] t1 {site}/tabs.html | t2* {report}"
            f"\n[events] tab t2 opened and is now the active tab: {report}"
        ), clicked.text
        read = await tools.call("browser_snapshot", {})
        assert 'heading "Welcome, Report"' in read.text
        # What happened is told once.
        assert "[events]" not in read.text

        # A ref of one tab is not a ref of another: it can never act on the wrong page.
        elsewhere = await tools.call("browser_click", {"ref": ref_of(first.text, 'button "Open a window"')})
        assert elsewhere.is_error and "is stale or unknown" in elsewhere.text

        listed = await tools.call("browser_tabs", {"action": "list"})
        assert listed.text.startswith(
            f"2 tabs, the active one marked *:\nt1 Tabs | {site}/tabs.html\nt2* Welcome | {report}\n"
        ), listed.text

        back = await tools.call("browser_tabs", {"action": "switch", "tab_id": "t1"})
        assert back.text.startswith("Switched to t1.\nPage: Tabs\n"), back.text
        # Its elements kept their refs while the agent was away.
        assert ref_of(back.text, 'button "Open a window"') == ref_of(first.text, 'button "Open a window"')

        window = await tools.call("browser_click", {"ref": ref_of(back.text, 'button "Open a window"')})
        assert f"t3* {site}/welcome.html?name=Window" in window.text

        closed = await tools.call("browser_tabs", {"action": "close"})
        assert closed.text.startswith("Closed t3. t2 is the active tab.\nPage: Welcome\n"), closed.text
        assert "[events]" not in closed.text, "the agent closed it itself: that is not news"

        # A tab id is never used twice.
        new = await tools.call("browser_tabs", {"action": "new", "url": f"{site}/form.html"})
        assert new.text.startswith(f"Opened tab t4.\nNavigated to {site}/form.html\nPage: Sign up\n"), (
            new.text
        )
        empty = await tools.call("browser_tabs", {"action": "new"})
        assert empty.text.startswith("Opened tab t5. It is empty: open a page in it with browser_navigate.")

        missing = await tools.call("browser_tabs", {"action": "switch", "tab_id": "t3"})
        assert missing.is_error
        assert missing.text.startswith("There is no tab t3. Open tabs: t1, t2, t4, t5.")
        unnamed = await tools.call("browser_tabs", {"action": "switch"})
        assert unnamed.is_error and "Give tab_id" in unnamed.text


async def test_a_new_tab_goes_through_the_address_policy(
    make_config: Callable[..., Config], tmp_path: Path, site: str
) -> None:
    async with open_session(make_config(tmp_path)) as session:
        tools = Toolkit(session)
        await tools.call("browser_navigate", {"url": f"{site}/tabs.html"})
        blocked = await tools.call(
            "browser_tabs", {"action": "new", "url": "http://169.254.169.254/latest/meta-data/"}
        )
        assert blocked.is_error and "cloud metadata address" in blocked.text
        # No tab was opened for it.
        assert blocked.text.endswith(f"[tabs] t1* {site}/tabs.html")


async def test_no_more_tabs_are_open_than_the_limit(
    make_config: Callable[..., Config], tmp_path: Path, site: str
) -> None:
    config = make_config(tmp_path, browser={"tabs": {"max_tabs": 2}})
    async with open_session(config) as session:
        tools = Toolkit(session)
        page = await tools.call("browser_navigate", {"url": f"{site}/tabs.html"})
        await tools.call("browser_tabs", {"action": "new"})
        third = await tools.call("browser_tabs", {"action": "new"})
        assert third.is_error
        assert third.text.startswith("2 tabs are open, which is the most allowed. Close one first.")

        # A window that a page opens beyond the limit is closed at once, and the agent is told.
        await tools.call("browser_tabs", {"action": "switch", "tab_id": "t1"})
        opened = await tools.call("browser_click", {"ref": ref_of(page.text, 'button "Open a window"')})
        assert "[events] a new tab was closed at once: 2 tabs are open" in opened.text, opened.text
        assert opened.text.count(" | ") == 1, "two tabs are still all there is"


async def test_a_new_tab_stays_in_the_background_when_the_setting_says_so(
    make_config: Callable[..., Config], tmp_path: Path, site: str
) -> None:
    config = make_config(tmp_path, browser={"tabs": {"focus_new_tabs": False}})
    async with open_session(config) as session:
        tools = Toolkit(session)
        page = await tools.call("browser_navigate", {"url": f"{site}/tabs.html"})
        clicked = await tools.call("browser_click", {"ref": ref_of(page.text, 'link "Open the report"')})
        report = f"{site}/welcome.html?name=Report"
        assert clicked.text.endswith(
            f"\n[tabs] t1* {site}/tabs.html | t2 {report}\n[events] tab t2 opened: {report}"
        ), clicked.text


async def test_a_tab_that_closes_by_itself_is_told_and_the_agent_goes_on_in_another(
    make_config: Callable[..., Config], tmp_path: Path, site: str
) -> None:
    config = make_config(tmp_path)
    driver = PlaywrightDriver(config)
    async with open_session(config, driver) as session:
        tools = Toolkit(session)
        page = await tools.call("browser_navigate", {"url": f"{site}/tabs.html"})
        await tools.call("browser_click", {"ref": ref_of(page.text, 'button "Open a window"')})
        # The window closes itself, as a sign-in window does when it is done.
        await driver.page.evaluate("setTimeout(() => window.close(), 0)")
        async with asyncio.timeout(5):
            while len(await driver.tabs()) > 1:
                await asyncio.sleep(0.05)
        read = await tools.call("browser_snapshot", {})
        assert read.text.startswith("Page: Tabs\n")
        assert read.text.endswith(
            f"\n[tabs] t1* {site}/tabs.html\n[events] tab t2 closed; t1 is now the active tab"
        ), read.text


async def test_a_click_that_opens_nothing_is_not_kept_waiting_for_a_tab(
    make_config: Callable[..., Config], tmp_path: Path, site: str
) -> None:
    config = make_config(tmp_path, browser={"timeouts": {"popup_adopt_ms": 20000}})
    async with open_session(config) as session:
        tools = Toolkit(session)
        page = await tools.call("browser_navigate", {"url": f"{site}/tabs.html"})
        async with asyncio.timeout(5):
            quiet = await tools.call("browser_click", {"ref": ref_of(page.text, 'button "Do nothing"')})
        assert not quiet.is_error and "[events]" not in quiet.text


async def test_the_live_picture_follows_the_active_tab(
    make_config: Callable[..., Config], tmp_path: Path, site: str
) -> None:
    config = make_config(tmp_path)
    driver = PlaywrightDriver(config)
    session = BrowserSession(config, driver)
    try:
        await session.driver()
        pictures: list[bytes] = []
        await driver.start_frames(pictures.append, config.viewer.quality_levels.standard)
        await driver.navigate(f"{site}/tabs.html")
        await driver.new_tab()
        await driver.navigate(f"{site}/tools.html")
        seen = len(pictures)
        # What changes in the new tab is what a person sees.
        await driver.scroll(0, 400)
        async with asyncio.timeout(5):
            while len(pictures) == seen:
                await asyncio.sleep(0.05)
        await driver.close_tab(None)
        seen = len(pictures)
        await driver.navigate(f"{site}/tools.html")
        async with asyncio.timeout(5):
            while len(pictures) == seen:
                await asyncio.sleep(0.05)
    finally:
        await session.close()
