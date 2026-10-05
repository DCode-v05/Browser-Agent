"""Take-over Chrome in a real browser (spec 4.9): the extension in a person's own Chrome dials in to
the core, and the agent's tools drive a tab of that Chrome through it."""

import asyncio
import contextlib
import json
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from pathlib import Path

from playwright.async_api import BrowserContext, async_playwright

from bap_browser import browser_extension
from bap_browser.agent.command import chat_in_own_chrome
from bap_browser.agent.models import ScriptedModel, ref_of
from bap_browser.config import Config
from bap_browser.driver.playwright_driver import PlaywrightDriver
from bap_browser.service.server import Service
from bap_browser.service.session import ServiceSession


@asynccontextmanager
async def their_chrome(profile: Path, extension: Path) -> AsyncIterator[BrowserContext]:
    """A browser that stands for the person's own Chrome, with the extension loaded into it."""
    async with async_playwright() as playwright:
        chrome = await playwright.chromium.launch_persistent_context(
            str(profile),
            channel="chromium",
            headless=True,
            args=[f"--disable-extensions-except={extension}", f"--load-extension={extension}"],
        )
        try:
            yield chrome
        finally:
            await chrome.close()


async def test_the_agent_drives_a_tab_of_the_persons_own_chrome_through_the_extension(
    make_config: Callable[..., Config], tmp_path: Path, site: str
) -> None:
    folder = browser_extension.install(tmp_path / "state" / "extension")
    config = make_config(tmp_path)
    sessions: dict[str, ServiceSession] = {}
    service = Service(config, sessions, port=0, bridge=True)
    await service.start()
    assert service.bridge is not None
    session: ServiceSession | None = None
    try:
        async with their_chrome(tmp_path / "their-profile", folder) as chrome:
            browser_extension.announce(folder, bridge=service.bridge_address, token=service.token)
            # The side panel's page, opened here as a tab: it is the bridge, and it dials in by itself.
            panel = await chrome.new_page()
            await panel.goto(f"chrome-extension://{browser_extension.EXTENSION_ID}/panel.html")
            await asyncio.wait_for(service.bridge.wait_connected(), 15)

            browser = config.browser.model_copy(update={"cdp_url": service.bridge_cdp_address})
            attached = config.model_copy(update={"browser": browser})
            driver = PlaywrightDriver(attached, cdp_headers={"Authorization": f"Bearer {service.token}"})
            session = ServiceSession(attached, driver, agent="Reference agent", pictures=False)
            await asyncio.wait_for(session.start(), 30)
            sessions[session.name] = session
            assert session.hub.subscribe()[0][0]["on_screen"] is True  # type: ignore[index]

            tools = session.toolkit
            opened = await asyncio.wait_for(tools.call("browser_navigate", {"url": f"{site}/form.html"}), 30)
            assert not opened.is_error, opened.text
            # It is a tab of the person's browser that went there: the one the extension opened for the agent.
            theirs = [page for page in chrome.pages if page.url.endswith("/form.html")]
            assert len(theirs) == 1

            typed = await tools.call(
                "browser_type", {"ref": ref_of(opened.text, 'textbox "Full name"'), "text": "Ada Lovelace"}
            )
            assert not typed.is_error, typed.text
            assert await theirs[0].input_value("#name") == "Ada Lovelace"
            ticked = await tools.call(
                "browser_set_checked",
                {"ref": ref_of(opened.text, 'checkbox "I accept the terms"'), "checked": True},
            )
            assert not ticked.is_error, ticked.text
            assert await theirs[0].locator('input[name="terms"]').is_checked()
            read = await tools.call("browser_get_text", {})
            assert not read.is_error and "Full name" in read.text

            # The safety policy is the core's here as everywhere.
            blocked = await tools.call(
                "browser_navigate", {"url": "http://169.254.169.254/latest/meta-data/"}
            )
            assert blocked.is_error and "cloud metadata address" in blocked.text

            # The person closes the agent's tab: the agent is told, in words, that its browser is gone.
            await theirs[0].close()
            # The extension says so, and the driver's end of the bridge is closed with it.
            async with asyncio.timeout(10):
                while driver.is_alive():
                    await asyncio.sleep(0.05)
            gone = await asyncio.wait_for(tools.call("browser_snapshot", {}), 30)
            assert gone.is_error
            assert "The browser closed" in gone.text
    finally:
        browser_extension.forget(folder)
        if session is not None:
            await session.close()
        await service.stop()


async def test_only_this_products_extension_with_the_token_may_dial_in(
    make_config: Callable[..., Config], tmp_path: Path
) -> None:
    from websockets.asyncio.client import connect
    from websockets.exceptions import ConnectionClosed, InvalidStatus

    service = Service(make_config(tmp_path), {}, port=0, bridge=True)
    await service.start()
    assert service.bridge is not None
    ours = {"Origin": browser_extension.ORIGIN}
    try:
        # A page of another site, or another extension, is turned away before anything is said.
        for origin in ("https://evil.example", "chrome-extension://aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"):
            try:
                async with connect(service.bridge_address, additional_headers={"Origin": origin}) as socket:
                    await asyncio.wait_for(socket.recv(), 5)
                raise AssertionError(f"{origin} was let in")
            except (ConnectionClosed, InvalidStatus):
                pass
        # The right extension with the wrong token is let go, and the bridge stays free.
        async with connect(service.bridge_address, additional_headers=ours) as socket:
            await socket.send('{"type": "auth", "token": "not-the-token"}')
            with contextlib.suppress(ConnectionClosed):
                await asyncio.wait_for(socket.recv(), 5)
            assert socket.close_code == 4401
        assert not service.bridge.connected

        # The driver's end is this process's own: without the token nobody is let in there either.
        try:
            async with connect(service.bridge_cdp_address) as socket:
                await asyncio.wait_for(socket.recv(), 5)
            raise AssertionError("the driver's end was open to anyone")
        except (ConnectionClosed, InvalidStatus):
            pass

        async with connect(service.bridge_address, additional_headers=ours) as socket:
            await socket.send(f'{{"type": "auth", "token": "{service.token}"}}')
            await asyncio.wait_for(service.bridge.wait_connected(), 5)
            assert service.bridge.connected
    finally:
        await service.stop()


async def test_the_chat_command_waits_for_the_extension_then_opens_the_agents_tab_and_the_chat(
    make_config: Callable[..., Config], tmp_path: Path
) -> None:
    folder = browser_extension.install(tmp_path / "state" / "extension")
    session_file = folder / "session.json"
    chat = asyncio.create_task(
        chat_in_own_chrome(
            make_config(tmp_path), lambda service: ScriptedModel([]), first_task=None, extension=folder
        )
    )
    try:
        # First the extension is told only where to dial in: there is no session to show yet.
        async with asyncio.timeout(30):
            while not session_file.exists() and not chat.done():
                await asyncio.sleep(0.05)
        assert not chat.done(), chat.exception()
        told = json.loads(session_file.read_text(encoding="utf-8"))
        assert sorted(told) == ["bridge", "token"]

        async with their_chrome(tmp_path / "their-profile", folder) as chrome:
            panel = await chrome.new_page()
            await panel.goto(f"chrome-extension://{browser_extension.EXTENSION_ID}/panel.html")
            # Once it has dialled in, the agent's tab opens on the start page, and the panel shows the chat.
            async with asyncio.timeout(60):
                while not any(page.url.endswith("/demo-site/start.html") for page in chrome.pages):
                    assert not chat.done(), chat.exception()
                    await asyncio.sleep(0.1)
            assert "viewer" in json.loads(session_file.read_text(encoding="utf-8"))
            await panel.frame_locator("#viewer").get_by_role("region", name="Chat").wait_for()
            chat.cancel()
            await asyncio.gather(chat, return_exceptions=True)
            # The agent has let go. The person's tab is still there, where it was left.
            assert any(page.url.endswith("/demo-site/start.html") for page in chrome.pages)
    finally:
        chat.cancel()
        await asyncio.gather(chat, return_exceptions=True)
    assert not session_file.exists(), "the token is not left behind"
