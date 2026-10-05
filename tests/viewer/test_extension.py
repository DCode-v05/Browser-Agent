"""The extension in a real browser: its panel shows the chat, and the page the agent works on shows
who is driving, without the agent reading any of it (spec 9.15)."""

import asyncio
import json
import re
from collections.abc import Callable
from pathlib import Path

from bap_browser import browser_extension
from bap_browser.agent.command import chat_with_viewer
from bap_browser.agent.models import ScriptedModel
from bap_browser.config import Config
from bap_browser.driver.playwright_driver import PlaywrightDriver
from bap_browser.service.server import Service
from bap_browser.service.session import ServiceSession

SHOTS = Path(__file__).parents[2] / ".bap-browser" / "viewer-shots"
LOOK = "bap-browser-look"


async def test_the_panel_shows_the_chat_and_the_page_shows_who_is_driving(
    make_config: Callable[..., Config], tmp_path: Path
) -> None:
    folder = browser_extension.install(tmp_path / "state" / "extension")
    kept = {"user_data_dir": str(tmp_path / "profile")}
    hidden = browser_extension.with_extension(make_config(tmp_path, browser=kept), folder)
    # The session believes its browser is on screen, as it is when a person runs it. The browser of
    # this test has no window, because a test machine has no screen.
    shown = hidden.model_copy(update={"browser": hidden.browser.model_copy(update={"headless": False})})
    driver = PlaywrightDriver(hidden)
    session = ServiceSession(shown, driver, agent="Reference agent", on_task=lambda task: None)
    service = Service(shown, {session.name: session}, port=0)
    await session.start()
    try:
        await service.start()
        browser_extension.announce(folder, service.viewer_address)
        tools = session.toolkit
        opened = await tools.call("browser_navigate", {"url": f"{service.address}/demo-site/start.html"})
        assert not opened.is_error, opened.text
        page = driver.page

        # The side panel's page, opened here as a tab: the same page, in the same window.
        panel = await page.context.new_page()
        errors: list[str] = []
        panel.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
        await panel.goto(f"chrome-extension://{browser_extension.EXTENSION_ID}/panel.html")
        chat = panel.frame_locator("#viewer")
        await chat.get_by_role("region", name="Chat").wait_for()
        assert await chat.get_by_role("region", name="Browser").count() == 0, "no picture of the browser"
        assert await chat.get_by_text("Ready for your task").count() > 0

        # While the agent waits for a task, the page is at rest.
        assert await page.locator(f"{LOOK}[data-tone]").count() == 0

        session.working(True)
        clicked = await tools.call(
            "browser_click", {"ref": _ref(opened.text, 'link "Skylark Air: check in online"')}
        )
        assert not clicked.is_error, clicked.text
        await page.locator(f'{LOOK}[data-tone="agent"][data-working]').wait_for(state="attached")
        SHOTS.mkdir(parents=True, exist_ok=True)
        await page.bring_to_front()
        await page.screenshot(path=str(SHOTS / "extension-page-agent.png"))
        await panel.bring_to_front()
        await panel.set_viewport_size({"width": 400, "height": 820})
        await panel.screenshot(path=str(SHOTS / "extension-panel.png"))

        # What is drawn on the page is for the person. The agent reads the page without it.
        read = await tools.call("browser_get_text", {})
        seen = await tools.call("browser_snapshot", {})
        assert "Check in online" in read.text
        for words in ("Agent is working", LOOK):
            assert words not in read.text and words not in seen.text, words
        # And it takes no click: the page under it is still what a click reaches.
        typed = await tools.call(
            "browser_type", {"ref": _ref(seen.text, 'textbox "Last name"'), "text": "Lovelace"}
        )
        assert not typed.is_error, typed.text

        await session.handle({"type": "take_over"})
        await page.locator(f'{LOOK}[data-tone="person"]:not([data-working])').wait_for(state="attached")
        await page.bring_to_front()
        await page.screenshot(path=str(SHOTS / "extension-page-person.png"))

        session.working(False)
        await session.handle({"type": "hand_back"})
        await page.locator(f"{LOOK}:not([data-tone])").wait_for(state="attached")
        assert errors == []
    finally:
        browser_extension.forget(folder)
        await service.stop()
        await session.close()


def _ref(page: str, element: str) -> str:
    from bap_browser.agent.models import ref_of

    return ref_of(page, element)


async def test_the_chat_command_makes_its_session_known_to_the_extension_and_forgets_it_again(
    make_config: Callable[..., Config], tmp_path: Path
) -> None:
    folder = browser_extension.install(tmp_path / "state" / "extension")
    kept = {"user_data_dir": str(tmp_path / "profile")}
    config = browser_extension.with_extension(make_config(tmp_path, browser=kept), folder)
    session_file = folder / "session.json"
    chat = asyncio.create_task(
        chat_with_viewer(
            config, lambda service: ScriptedModel([]), first_task=None, open_viewer=False, extension=folder
        )
    )
    try:
        async with asyncio.timeout(30):
            while not session_file.exists() and not chat.done():
                await asyncio.sleep(0.05)
        assert not chat.done(), chat.exception()
        viewer = json.loads(session_file.read_text(encoding="utf-8"))["viewer"]
        assert re.fullmatch(r"http://127\.0\.0\.1:\d+/\?embed=1#token=[\w-]+", viewer)
        # The browser opens on the page that says how to open the chat.
        log = tmp_path / "events.jsonl"
        async with asyncio.timeout(30):
            while not (log.exists() and "start.html" in log.read_text(encoding="utf-8")):
                await asyncio.sleep(0.05)
    finally:
        chat.cancel()
        await asyncio.gather(chat, return_exceptions=True)
    assert not session_file.exists(), "the address, which carries the token, is not left behind"
