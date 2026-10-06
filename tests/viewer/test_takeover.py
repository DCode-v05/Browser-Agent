"""Take-over Chrome in a real browser (spec 4.9): the extension in a person's own Chrome dials in to
the core, and the agent's tools drive a tab of that Chrome through it."""

import asyncio
import contextlib
import json
import re
from collections.abc import AsyncIterator, Callable, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from playwright.async_api import BrowserContext, Page, async_playwright

from bap_browser import browser_extension
from bap_browser.agent.command import chat_in_own_chrome
from bap_browser.agent.models import ScriptedModel, ref_of
from bap_browser.config import Config
from bap_browser.driver.playwright_driver import PlaywrightDriver
from bap_browser.errors import BrowserError
from bap_browser.results import ToolResult
from bap_browser.service.server import Service
from bap_browser.service.session import ServiceSession
from bap_browser.tools import Toolkit


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


@dataclass
class TakenOver:
    """A person's Chrome with the extension dialled in, and the agent's session on a tab of it."""

    service: Service
    chrome: BrowserContext
    panel: Page
    session: ServiceSession
    driver: PlaywrightDriver

    @property
    def tools(self) -> Toolkit:
        return self.session.toolkit

    def page_at(self, ending: str) -> Page:
        (found,) = [page for page in self.chrome.pages if page.url.endswith(ending)]
        return found

    async def answer(self, choice: str, site: str = "127.0.0.1") -> None:
        """Presses a button of the extension's question, as the person would."""
        card = self.panel.locator("#question")
        await card.wait_for(timeout=15_000)
        assert await card.locator("#question-site").inner_text() == site
        await card.get_by_role("button", name=choice, exact=True).click()

    async def call_and_answer(self, choice: str, name: str, arguments: Mapping[str, Any]) -> ToolResult:
        """A call that the extension asks the person about, and their answer."""
        call = asyncio.create_task(self.tools.call(name, arguments))
        await self.answer(choice)
        return await asyncio.wait_for(call, 30)


@asynccontextmanager
async def taken_over(
    make_config: Callable[..., Config], tmp_path: Path, **sections: object
) -> AsyncIterator[TakenOver]:
    folder = browser_extension.install(tmp_path / "state" / "extension")
    config = make_config(tmp_path, **sections)
    sessions: dict[str, ServiceSession] = {}
    service = Service(config, sessions, port=0, bridge=True)
    await service.start()
    assert service.bridge is not None
    session: ServiceSession | None = None
    try:
        async with their_chrome(tmp_path / "their-profile", folder) as chrome:
            browser_extension.announce(
                folder, bridge=service.bridge_address, token=service.bridge.pairing_token()
            )
            # The extension's own page, opened here as a tab: where the person answers its questions.
            # The bridge itself is in the extension's background, and dials in by itself.
            panel = await chrome.new_page()
            await panel.goto(f"chrome-extension://{browser_extension.EXTENSION_ID}/panel.html")
            await asyncio.wait_for(service.bridge.wait_connected(), 15)

            browser = config.browser.model_copy(update={"cdp_url": service.bridge_cdp_address})
            attached = config.model_copy(update={"browser": browser})
            driver = PlaywrightDriver(attached, cdp_headers={"Authorization": f"Bearer {service.token}"})
            session = ServiceSession(attached, driver, agent="Reference agent", pictures=False)
            session.browser.ask_site = service.bridge.permit
            session.browser.site_done = service.bridge.permit_done
            await asyncio.wait_for(session.start(), 30)
            sessions[session.name] = session
            yield TakenOver(service, chrome, panel, session, driver)
    finally:
        browser_extension.forget(folder)
        if session is not None:
            await session.close()
        await service.stop()


async def test_the_agent_drives_a_tab_of_the_persons_own_chrome_through_the_extension(
    make_config: Callable[..., Config], tmp_path: Path, site: str
) -> None:
    async with taken_over(make_config, tmp_path) as own:
        assert own.session.hub.subscribe()[0][0]["on_screen"] is True  # type: ignore[index]
        tools = own.tools
        # The first call on a site asks the person, in the extension's own page.
        opened = await own.call_and_answer(
            "Always allow on this site", "browser_navigate", {"url": f"{site}/form.html"}
        )
        assert not opened.is_error, opened.text
        # It is a tab of the person's browser that went there: the one the extension opened for the agent.
        theirs = own.page_at("/form.html")

        typed = await tools.call(
            "browser_type", {"ref": ref_of(opened.text, 'textbox "Full name"'), "text": "Ada Lovelace"}
        )
        assert not typed.is_error, typed.text
        assert await theirs.input_value("#name") == "Ada Lovelace"
        ticked = await tools.call(
            "browser_set_checked",
            {"ref": ref_of(opened.text, 'checkbox "I accept the terms"'), "checked": True},
        )
        assert not ticked.is_error, ticked.text
        assert await theirs.locator('input[name="terms"]').is_checked()
        read = await tools.call("browser_get_text", {})
        assert not read.is_error and "Full name" in read.text

        # The safety policy is the core's here as everywhere.
        blocked = await tools.call("browser_navigate", {"url": "http://169.254.169.254/latest/meta-data/"})
        assert blocked.is_error and "cloud metadata address" in blocked.text

        # The person closes the agent's tab: the agent is told, in words, that its browser is gone.
        await theirs.close()
        # The extension says so, and the driver's end of the bridge is closed with it.
        async with asyncio.timeout(10):
            while own.driver.is_alive():
                await asyncio.sleep(0.05)
        gone = await asyncio.wait_for(tools.call("browser_snapshot", {}), 30)
        assert gone.is_error
        assert "The browser closed" in gone.text


async def test_the_person_decides_site_by_site_what_the_agent_may_do(
    make_config: Callable[..., Config], tmp_path: Path, site: str
) -> None:
    form = {"url": f"{site}/form.html"}
    async with taken_over(make_config, tmp_path) as own:
        # "Don't allow": nothing is opened, and the agent is told not to try another way.
        refused = await own.call_and_answer("Don't allow", "browser_navigate", form)
        assert refused.is_error
        assert refused.text.startswith(
            "The person has not allowed actions on 127.0.0.1. Do not try another way: ask the person, "
            "or choose a different approach."
        )
        assert not [page for page in own.chrome.pages if page.url.endswith("/form.html")]

        # "Allow once" is for the call that asked. The next call on the site asks again.
        opened = await own.call_and_answer("Allow once", "browser_navigate", form)
        assert not opened.is_error, opened.text
        name = ref_of(opened.text, 'textbox "Full name"')
        typed = await own.call_and_answer("Allow once", "browser_type", {"ref": name, "text": "Ada"})
        assert not typed.is_error, typed.text
        assert await own.page_at("/form.html").input_value("#name") == "Ada"

        # "Always allow on this site" is remembered: no question follows.
        always = await own.call_and_answer("Always allow on this site", "browser_snapshot", {})
        assert not always.is_error
        again = await asyncio.wait_for(own.tools.call("browser_type", {"ref": name, "text": "Grace"}), 10)
        assert not again.is_error, again.text
        assert await own.panel.locator("#question").is_hidden()


async def test_the_extension_does_not_rely_on_the_core_for_what_it_allows(
    make_config: Callable[..., Config], tmp_path: Path, site: str
) -> None:
    async with taken_over(make_config, tmp_path) as own:
        opened = await own.call_and_answer("Allow once", "browser_navigate", {"url": f"{site}/form.html"})
        assert not opened.is_error, opened.text
        name = ref_of(opened.text, 'textbox "Full name"')
        # A core that did not ask: the driver is used behind the tool layer's back.
        with pytest.raises(BrowserError, match=re.escape("The person has not allowed actions on 127.0.0.1")):
            await own.driver.click(name)
        with pytest.raises(BrowserError, match="The person has not allowed actions on localhost"):
            await own.driver.navigate(f"{site.replace('127.0.0.1', 'localhost')}/welcome.html")
        assert await own.page_at("/form.html").input_value("#name") == ""


async def test_sites_the_agent_is_never_offered_and_sites_a_deployment_blocks(
    make_config: Callable[..., Config], tmp_path: Path, site: str
) -> None:
    blocked = {"blocked_sites": ["localhost"]}
    async with taken_over(make_config, tmp_path, permissions=blocked) as own:
        # The deployment's list: the person is not even asked.
        other = await asyncio.wait_for(
            own.tools.call(
                "browser_navigate", {"url": f"{site.replace('127.0.0.1', 'localhost')}/form.html"}
            ),
            10,
        )
        assert other.is_error and other.text.startswith("The person has not allowed actions on localhost.")
        # The browser's own pages, whoever asks.
        with pytest.raises(BrowserError, match="has not allowed actions"):
            await own.driver.navigate("chrome://settings/")
        assert await own.panel.locator("#question").is_hidden()


async def test_asking_before_every_action(
    make_config: Callable[..., Config], tmp_path: Path, site: str
) -> None:
    async with taken_over(make_config, tmp_path, permissions={"mode": "ask_before_acting"}) as own:
        opened = await own.call_and_answer(
            "Always allow on this site", "browser_navigate", {"url": f"{site}/form.html"}
        )
        name = ref_of(opened.text, 'textbox "Full name"')
        # Reading an allowed site asks nothing. Acting on it asks each time, with what will be done.
        assert not (await asyncio.wait_for(own.tools.call("browser_snapshot", {}), 10)).is_error
        typing = asyncio.create_task(own.tools.call("browser_type", {"ref": name, "text": "Ada"}))
        card = own.panel.locator("#question")
        await card.wait_for(timeout=15_000)
        assert await card.locator("#question-doing").inner_text() == 'Typing 3 characters into "Full name"'
        # The site is allowed already, so "always" is not offered again.
        assert await card.locator("#always").is_hidden()
        await card.get_by_role("button", name="Allow once", exact=True).click()
        assert not (await asyncio.wait_for(typing, 30)).is_error


async def test_a_question_nobody_answers_is_a_no(
    make_config: Callable[..., Config], tmp_path: Path, site: str
) -> None:
    async with taken_over(make_config, tmp_path, permissions={"preview_timeout_s": 1}) as own:
        unanswered = await asyncio.wait_for(
            own.tools.call("browser_navigate", {"url": f"{site}/form.html"}), 20
        )
        assert unanswered.is_error
        assert unanswered.text.startswith("The person did not answer, so this action was cancelled.")
        await own.panel.locator("#question").wait_for(state="hidden", timeout=5_000)


async def test_the_channel_is_cut_and_restored_and_the_run_continues(
    make_config: Callable[..., Config], tmp_path: Path, site: str
) -> None:
    async with taken_over(make_config, tmp_path) as own:
        bridge = own.service.bridge
        assert bridge is not None
        opened = await own.call_and_answer(
            "Always allow on this site", "browser_navigate", {"url": f"{site}/form.html"}
        )
        name = ref_of(opened.text, 'textbox "Full name"')
        # The connection is cut from the core's side, as a network would cut it.
        extension = bridge._extension  # pyright: ignore[reportPrivateUsage]
        assert extension is not None
        await extension.close()
        async with asyncio.timeout(5):
            while bridge.connected:
                await asyncio.sleep(0.02)
        # A call made while it is cut waits for the bridge, which dials again by itself.
        typed = await asyncio.wait_for(own.tools.call("browser_type", {"ref": name, "text": "Ada"}), 30)
        assert not typed.is_error, typed.text
        assert bridge.connected
        # The tab and its refs are the ones from before.
        assert await own.page_at("/form.html").input_value("#name") == "Ada"
        assert own.driver.is_alive()


async def test_the_persons_own_stop_takes_the_agent_off_every_tab(
    make_config: Callable[..., Config], tmp_path: Path, site: str
) -> None:
    async with taken_over(make_config, tmp_path, bridge={"reconnect_grace_s": 1}) as own:
        opened = await own.call_and_answer(
            "Always allow on this site", "browser_navigate", {"url": f"{site}/form.html"}
        )
        assert not opened.is_error
        await own.panel.get_by_role("button", name="Stop the agent").click()
        await own.panel.locator("#stopped").wait_for(timeout=10_000)
        async with asyncio.timeout(15):
            while own.driver.is_alive():
                await asyncio.sleep(0.05)
        gone = await asyncio.wait_for(own.tools.call("browser_snapshot", {}), 30)
        assert gone.is_error and "The browser on the person's machine is not connected" in gone.text
        # The tab is still the person's, where the agent left it. The bridge does not dial again.
        assert own.page_at("/form.html")
        await asyncio.sleep(1.5)
        assert own.service.bridge is not None and not own.service.bridge.connected


async def test_only_this_products_extension_with_a_pairing_token_may_dial_in(
    make_config: Callable[..., Config], tmp_path: Path
) -> None:
    from websockets.asyncio.client import connect
    from websockets.exceptions import ConnectionClosed, InvalidStatus

    service = Service(make_config(tmp_path), {}, port=0, bridge=True)
    await service.start()
    bridge = service.bridge
    assert bridge is not None
    ours = {"Origin": browser_extension.ORIGIN}

    async def refused(first: dict[str, object]) -> None:
        async with connect(service.bridge_address, additional_headers=ours) as socket:
            await socket.send(json.dumps({"type": "auth", **first}))
            with contextlib.suppress(ConnectionClosed):
                await asyncio.wait_for(socket.recv(), 5)
            assert socket.close_code == 4401, first

    try:
        # A page of another site, or another extension, is turned away before anything is said.
        for origin in ("https://evil.example", "chrome-extension://aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"):
            try:
                async with connect(service.bridge_address, additional_headers={"Origin": origin}) as socket:
                    await asyncio.wait_for(socket.recv(), 5)
                raise AssertionError(f"{origin} was let in")
            except (ConnectionClosed, InvalidStatus):
                pass
        # Neither a made-up token nor the session's own token is a pairing token.
        await refused({"token": "not-the-token"})
        await refused({"token": service.token})
        await refused({"key": "not-a-key"})
        assert not bridge.connected

        # The driver's end is this process's own: without the token nobody is let in there either.
        try:
            async with connect(service.bridge_cdp_address) as socket:
                await asyncio.wait_for(socket.recv(), 5)
            raise AssertionError("the driver's end was open to anyone")
        except (ConnectionClosed, InvalidStatus):
            pass

        pairing = bridge.pairing_token()
        async with connect(service.bridge_address, additional_headers=ours) as socket:
            await socket.send(json.dumps({"type": "auth", "token": pairing}))
            paired = json.loads(await asyncio.wait_for(socket.recv(), 5))
            assert paired["type"] == "paired" and paired["heartbeat_s"] == 15 and paired["mode"]
            assert paired["own_address"] == service.address
            assert bridge.connected
            # The bridge says it is alive, and is answered.
            await socket.send('{"type": "ping"}')
            assert json.loads(await asyncio.wait_for(socket.recv(), 5)) == {"type": "pong"}
        # A pairing token is taken once. The key it gave lets the same bridge come back.
        await refused({"token": pairing})
        async with connect(service.bridge_address, additional_headers=ours) as socket:
            await socket.send(json.dumps({"type": "auth", "key": paired["key"]}))
            assert json.loads(await asyncio.wait_for(socket.recv(), 5))["key"] == paired["key"]
    finally:
        await service.stop()


async def test_a_pairing_token_runs_out_and_a_silent_bridge_is_let_go(
    make_config: Callable[..., Config], tmp_path: Path
) -> None:
    from websockets.asyncio.client import connect
    from websockets.exceptions import ConnectionClosed

    config = make_config(tmp_path, bridge={"pairing_ttl_s": 0, "dead_after_s": 1, "reconnect_grace_s": 1})
    service = Service(config, {}, port=0, bridge=True)
    await service.start()
    bridge = service.bridge
    assert bridge is not None
    ours = {"Origin": browser_extension.ORIGIN}
    try:
        late = bridge.pairing_token()
        async with connect(service.bridge_address, additional_headers=ours) as socket:
            await socket.send(json.dumps({"type": "auth", "token": late}))
            with contextlib.suppress(ConnectionClosed):
                await asyncio.wait_for(socket.recv(), 5)
            assert socket.close_code == 4401

        bridge._settings = bridge._settings.model_copy(update={"pairing_ttl_s": 60})  # pyright: ignore[reportPrivateUsage]
        async with connect(service.bridge_address, additional_headers=ours) as socket:
            await socket.send(json.dumps({"type": "auth", "token": bridge.pairing_token()}))
            assert json.loads(await asyncio.wait_for(socket.recv(), 5))["type"] == "paired"
            # It says nothing more: after `dead_after_s` the core closes the channel.
            with pytest.raises(ConnectionClosed):
                await asyncio.wait_for(socket.recv(), 5)
        assert not bridge.connected
        # With nobody there, what the agent asks for is refused in words, after the wait for a bridge.
        assert await asyncio.wait_for(bridge.permit("act", "https://example.com/", "Clicking"), 5) == (
            "The browser on the person's machine is not connected."
        )
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


async def test_the_driver_hears_what_the_tab_said_in_the_order_the_tab_said_it(
    make_config: Callable[..., Config], tmp_path: Path
) -> None:
    """An event that overtook the answer before it would be about a frame the driver has not heard
    of yet: the driver would drop it, and wait for it for ever."""
    from websockets.asyncio.client import connect

    service = Service(make_config(tmp_path), {}, port=0, bridge=True)
    await service.start()
    bridge = service.bridge
    assert bridge is not None
    try:
        async with (
            connect(
                service.bridge_address, additional_headers={"Origin": browser_extension.ORIGIN}
            ) as extension,
            connect(
                service.bridge_cdp_address, additional_headers={"Authorization": f"Bearer {service.token}"}
            ) as driver,
        ):
            await extension.send(json.dumps({"type": "auth", "token": bridge.pairing_token()}))
            assert json.loads(await extension.recv())["type"] == "paired"
            for round_ in range(50):
                await driver.send(
                    json.dumps({"id": round_, "sessionId": "bap-tab", "method": "Page.getFrameTree"})
                )
                asked = json.loads(await asyncio.wait_for(extension.recv(), 5))
                assert asked["params"]["method"] == "Page.getFrameTree"
                # The answer, and straight after it something the tab said.
                await extension.send(json.dumps({"id": asked["id"], "result": {"frameTree": round_}}))
                event = {"method": "Runtime.executionContextCreated", "params": {"round": round_}}
                await extension.send(json.dumps({"method": "forwardCDPEvent", "params": event}))
                first = json.loads(await asyncio.wait_for(driver.recv(), 5))
                second = json.loads(await asyncio.wait_for(driver.recv(), 5))
                assert first == {"id": round_, "sessionId": "bap-tab", "result": {"frameTree": round_}}
                assert second["method"] == "Runtime.executionContextCreated", second
    finally:
        await service.stop()
