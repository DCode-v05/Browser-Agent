"""The window of three pages in a real browser (spec 9.16): the cloud browser, the person's own Chrome
and the built-in browser, each with its own session; the pop-up that asks a person to do a step; and
a new session on a page whose session was stopped."""

import asyncio
import json
import urllib.request
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from playwright.async_api import Browser, Page, async_playwright

from bap_browser import browser_extension
from bap_browser.agent.models import Reply, ScriptedModel, ToolCall
from bap_browser.agent.studio import run_studio
from bap_browser.config import Config

ASK = ToolCall("a", "browser_request_human", {"reason": "Sign in to Northfield for me", "kind": "login"})


def asks_then_answers() -> ScriptedModel:
    """An agent that asks the person to sign in, and says so when they have."""
    return ScriptedModel([lambda page: Reply("", (ASK,)), lambda page: Reply("You are signed in.")])


@dataclass
class Window:
    viewer: str
    token: str
    folder: Path
    page: Page
    running: asyncio.Task[None]

    @property
    def service(self) -> str:
        return self.viewer.split("/#")[0]

    def rooms(self) -> list[dict[str, Any]]:
        asked = urllib.request.Request(
            f"{self.service}/api/sessions", headers={"Authorization": f"Bearer {self.token}"}
        )
        with urllib.request.urlopen(asked, timeout=10) as answer:
            return json.loads(answer.read())["rooms"]

    async def room(self, name: str, state: str) -> dict[str, Any]:
        """Waits until a page of the window is in a state, and gives what the service says of it."""
        async with asyncio.timeout(30):
            while True:
                # A window whose service has stopped says why, instead of being asked for ever.
                assert not self.running.done(), self.running.exception()
                found = next(room for room in await asyncio.to_thread(self.rooms) if room["id"] == name)
                if found["state"] == state:
                    return found
                await asyncio.sleep(0.1)

    async def open(self, tab: str) -> None:
        await self.page.get_by_role("tab", name=tab).click()

    async def tab(self, tab: str) -> str:
        return " ".join((await self.page.get_by_role("tab", name=tab).inner_text()).split())


@asynccontextmanager
async def window(
    make_config: Callable[..., Config], tmp_path: Path, browser: Browser, model: Callable[[], Any]
) -> AsyncIterator[Window]:
    folder = browser_extension.install(tmp_path / "state" / "extension")
    # The file that says where the service is stays in the test's own folder, apart from a service
    # the developer may have running.
    config = make_config(tmp_path, server={"state_file": str(tmp_path / "service.json")})
    running = asyncio.create_task(
        run_studio(config, lambda service: model(), open_viewer=False, extension=folder)
    )
    state = Path(config.server.state_file)
    try:
        async with asyncio.timeout(30):
            while not state.exists():
                assert not running.done(), running.exception()
                await asyncio.sleep(0.05)
        viewer = json.loads(state.read_text(encoding="utf-8"))["viewer"]
        page = await browser.new_page(viewport={"width": 1360, "height": 850})
        opened = Window(viewer, viewer.split("#token=")[1], folder, page, running)
        await opened.room("cloud", "agent")
        await opened.room("builtin", "agent")
        await page.goto(viewer)
        await page.get_by_role("tablist", name="Where the agent works").wait_for()
        yield opened
        await page.close()
    finally:
        running.cancel()
        await asyncio.gather(running, return_exceptions=True)


async def test_the_window_has_a_page_for_each_browser(
    make_config: Callable[..., Config], tmp_path: Path, browser: Browser
) -> None:
    async with window(make_config, tmp_path, browser, lambda: ScriptedModel([])) as opened:
        # Asked from another thread: the service answers on this one.
        rooms = await asyncio.to_thread(opened.rooms)
        assert [(room["id"], room["backend"]) for room in rooms] == [
            ("cloud", "remote_headless"),
            ("chrome", "takeover_chrome"),
            ("builtin", "bundled_chromium"),
        ]
        # The person's own Chrome is not there until its extension dials in.
        assert rooms[1]["state"] == "waiting" and rooms[1]["extension"] == str(opened.folder)
        page = opened.page
        assert [
            " ".join((await tab.inner_text()).split()) for tab in await page.locator(".studio-tab").all()
        ] == [
            "Cloud browser Ready",
            "My Chrome Not connected",
            "Built-in browser Ready",
        ]
        # The cloud browser's page: its picture, and its own chat.
        await page.get_by_label("Your task").wait_for()
        await page.get_by_role("img", name="Live browser view: BAP Browser,").wait_for()
        assert await page.get_by_title("Session").inner_text() == "Session\ncloud"

        await opened.open("My Chrome")
        await page.get_by_role("heading", name="Connect your Chrome").wait_for()
        assert await page.locator(".studio-folder code").inner_text() == str(opened.folder)
        assert await page.get_by_label("Your task").count() == 0

        # The built-in browser is another browser with another session, and keeps its sign-ins.
        await opened.open("Built-in browser")
        await page.get_by_label("Your task").wait_for()
        assert await page.get_by_title("Session").inner_text() == "Session\nbuiltin"
        assert (tmp_path / "built-in-browser").is_dir(), "the built-in browser keeps a profile of its own"
        assert await page.evaluate("document.documentElement.scrollWidth <= innerWidth")


async def test_a_page_that_needs_a_person_pops_up_and_says_so_on_its_tab(
    make_config: Callable[..., Config], tmp_path: Path, browser: Browser
) -> None:
    async with window(make_config, tmp_path, browser, asks_then_answers) as opened:
        page = opened.page
        await opened.open("Built-in browser")
        task = page.get_by_label("Your task")
        await task.fill("Open my account")
        await task.press("Enter")

        popup = page.get_by_role("dialog", name="The agent needs you to sign in")
        await popup.wait_for()
        assert "Sign in to Northfield for me" in await popup.inner_text()
        # The pop-up holds the answers: they are not offered a second time behind it.
        assert await page.get_by_role("button", name="Take over").count() == 1
        # Seen from any other page of the window.
        await popup.get_by_role("button", name="Look first").click()
        await popup.wait_for(state="hidden")
        await opened.open("Cloud browser")
        async with asyncio.timeout(10):
            while await opened.tab("Built-in browser") != "Built-in browser Needs you":
                await asyncio.sleep(0.1)

        # Back on its page the pop-up asks again, and the person does the step.
        await opened.open("Built-in browser")
        await popup.wait_for()
        await popup.get_by_role("button", name="Take over").click()
        await popup.wait_for(state="hidden")
        await page.get_by_role("button", name="Done").first.click()
        await page.get_by_text("You are signed in.").wait_for()
        async with asyncio.timeout(10):
            while await opened.tab("Built-in browser") != "Built-in browser Ready":
                await asyncio.sleep(0.1)


async def test_a_stopped_session_is_started_again_from_its_page(
    make_config: Callable[..., Config], tmp_path: Path, browser: Browser
) -> None:
    async with window(
        make_config, tmp_path, browser, lambda: ScriptedModel([lambda page: Reply("Done.")])
    ) as opened:
        page = opened.page
        task = page.get_by_label("Your task")
        await task.fill("Say done")
        await task.press("Enter")
        await page.get_by_text("Done.", exact=True).wait_for()

        await page.get_by_role("button", name="Stop session").click()
        await page.get_by_role("alertdialog").get_by_role("button", name="Stop session").click()
        await opened.room("cloud", "ended")
        assert await opened.tab("Cloud browser") in ("Cloud browser Stopped", "Cloud browser Ready")
        await page.get_by_role("button", name="Start a new session").click()

        # A new browser and a new conversation on the same page of the window.
        await opened.room("cloud", "agent")
        await page.get_by_text("Tell the agent what to do in the browser.").wait_for()
        assert await page.get_by_text("Done.", exact=True).count() == 0
        await task.fill("Say done again")
        await task.press("Enter")
        await page.get_by_text("Done.", exact=True).wait_for()
        # The other pages were not touched.
        assert (await opened.room("builtin", "agent"))["state"] == "agent"


async def test_the_persons_own_chrome_becomes_a_page_once_its_extension_dials_in(
    make_config: Callable[..., Config], tmp_path: Path, browser: Browser
) -> None:
    async with window(make_config, tmp_path, browser, lambda: ScriptedModel([])) as opened:
        page = opened.page
        await opened.open("My Chrome")
        await page.get_by_role("heading", name="Connect your Chrome").wait_for()
        async with async_playwright() as playwright:
            chrome = await playwright.chromium.launch_persistent_context(
                str(tmp_path / "their-profile"),
                channel="chromium",
                headless=True,
                args=[f"--disable-extensions-except={opened.folder}", f"--load-extension={opened.folder}"],
            )
            try:
                # The extension's own page, as the person would open its side panel.
                panel = await chrome.new_page()
                await panel.goto(f"chrome-extension://{browser_extension.EXTENSION_ID}/panel.html")
                room = await opened.room("chrome", "agent")
                assert room["backend"] == "takeover_chrome"
                # The window's page turns from "connect" into the chat for that Chrome.
                await page.get_by_label("Your task").wait_for(timeout=20_000)
                assert await opened.tab("My Chrome") == "My Chrome Ready"
                # The agent's tab in that Chrome is on the start page, and its side panel shows the same chat.
                async with asyncio.timeout(20):
                    while not any(tab.url.endswith("/demo-site/start.html") for tab in chrome.pages):
                        await asyncio.sleep(0.1)
                await panel.frame_locator("#viewer").get_by_label("Your task").wait_for(timeout=20_000)
            finally:
                await chrome.close()
