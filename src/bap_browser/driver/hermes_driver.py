"""The driver of a real machine, on Hermes' base (spec 22.3): this machine's own screen, through
`cua-driver`. It is the same on Windows, macOS and Linux; nothing here asks which.

What the agent does goes through Hermes' `computer_use` tool (`bap_browser.computer`). This class
is what the session, the viewer and the two tools kept from before need of a desktop.
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import json
import os
import sys
from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any

from bap_browser import computer
from bap_browser.config import Config
from bap_browser.config_computer import Computer
from bap_browser.driver.base import KeyAction, MouseButton, PointerAction, QualityLevel, Shot
from bap_browser.driver.contained_desktop import App
from bap_browser.driver.desktop_driver import DesktopDriver
from bap_browser.driver.screen_here import ScreenHere
from bap_browser.errors import BapError, BrowserError
from bap_browser.results import Picture

# What each app the settings can allow is called on each system. On Linux it is the program the
# contained desktop starts.
NAMED = {
    "darwin": {
        "text_editor": "TextEdit",
        "files": "Finder",
        "calculator": "Calculator",
        "terminal": "Terminal",
    },
    "win32": {
        "text_editor": "Notepad",
        "files": "File Explorer",
        "calculator": "Calculator",
        "terminal": "Terminal",
    },
}
A_PICTURE = "data:"
# The whole screen, as Hermes' tool names it: a picture, and no elements.
THE_SCREEN = "screen"


def as_shot(result: Any) -> Shot | None:
    """The picture in a capture's result, with its size. None when the result holds none."""
    if not isinstance(result, dict):
        return None
    for part in result.get("content", []):
        address = part.get("image_url", {}).get("url", "") if part.get("type") == "image_url" else ""
        if address.startswith(A_PICTURE) and ";base64," in address:
            kind, _, data = address.removeprefix(A_PICTURE).partition(";base64,")
            meta = result.get("meta", {})
            return Shot(
                Picture(base64.b64decode(data), kind), int(meta.get("width", 0)), int(meta.get("height", 0))
            )
    return None


async def own_screen(settings: Computer) -> ScreenHere:
    """Starts this machine's own virtual screen, and has the driver work on it. For a machine with
    no screen that is itself the boundary: the micro VM, where the engine runs (spec 22.6)."""
    screen = ScreenHere(settings)
    await screen.start()
    os.environ["DISPLAY"] = settings.display
    return screen


class HermesDriver(DesktopDriver):
    def __init__(
        self, config: Config, name: str = "computer", backend: Callable[[], Any] | None = None
    ) -> None:
        super().__init__(config, name)
        self._name = name
        self._stand_in = backend
        self._base: AbstractContextManager[None] | None = None
        self._last: Shot | None = None
        self._screen: ScreenHere | None = None

    # The session.

    async def start(self) -> None:
        if self._settings.base.virtual_screen:
            self._screen = await own_screen(self._settings)
        self._base = computer.base(self._config, backend=self._stand_in)
        self._base.__enter__()
        # The engine's own check has judged a call, and asked a person where the settings say so,
        # before it reaches the tool (spec 22.3.1). The tool's own question is answered by that.
        computer.ask_with(lambda action, about: True)

    async def close(self) -> None:
        await self.stop_frames()
        base, self._base = self._base, None
        if base is not None:
            # Stopping the driver waits for it, so it is not done on the loop.
            await asyncio.to_thread(base.__exit__, None, None, None)
        screen, self._screen = self._screen, None
        if screen is not None:
            await screen.close()

    def is_alive(self) -> bool:
        return self._base is not None

    def description(self) -> str:
        return "This machine's own screen"

    async def viewport(self) -> tuple[int, int]:
        if self._last is None:
            return self._settings.screen_width, self._settings.screen_height
        return self._last.width, self._last.height

    # What the agent does: one call of Hermes' tool.

    async def use(self, arguments: dict[str, Any], session: str | None = None) -> Any:
        """One call of `computer_use`. Text as a JSON string, or a dictionary that holds a picture."""
        if self._base is None:
            raise BrowserError(
                "The machine's screen is not being driven any more.", reason="the session ended"
            )
        return await asyncio.to_thread(computer.computer_use, arguments, session or self._name)

    # What the two tools kept from before ask.

    async def windows(self) -> list[str]:
        """The titles of the windows that are open."""
        listed = await self.use({"action": "list_windows"})
        answer = json.loads(listed) if isinstance(listed, str) else {}
        titles = [
            str(window.get("title") or window.get("app_name") or "") for window in answer.get("windows", [])
        ]
        kept = [title[: self._settings.window_title_chars] for title in titles if title.strip()]
        return kept[: self._settings.windows_listed]

    async def open_app(self, app: App) -> bool:
        named = NAMED.get(sys.platform, {}).get(app.id, app.command)
        return await self.open_named_app(named)

    async def open_named_app(self, name: str) -> bool:
        if self._base is None:
            return False
        return await asyncio.to_thread(computer.open_app, name, self._name)

    # What a person sees: the whole screen. The viewer has a session of its own with the driver, so
    # that its looking never moves the window the agent is working in.

    async def screenshot(self, *, full_page: bool, annotate: bool) -> Shot:
        seen = await self.use(
            {"action": "capture", "mode": "vision", "app": THE_SCREEN}, f"{self._name}:viewer"
        )
        shot = as_shot(seen)
        if shot is not None:
            self._last = shot
        if self._last is None:
            raise BrowserError("The machine gave no picture of its screen.", reason="no picture")
        return self._last

    async def _send_frames(self, on_frame: Callable[[bytes], None], level: QualityLevel) -> None:
        pause = max(self._settings.frame_ms / 1000, 1 / level.max_fps)
        sent: bytes | None = None
        while self._base is not None:
            with contextlib.suppress(BapError):
                shot = await self.screenshot(full_page=False, annotate=False)
                # A screen that stands still is sent once.
                if shot.picture.data != sent:
                    sent = shot.picture.data
                    on_frame(sent)
            await asyncio.sleep(pause)

    # A person at their own machine has their own mouse and keyboard: nothing is sent for them.

    async def pointer(self, action: PointerAction, x: float, y: float, button: MouseButton) -> None: ...

    async def key(self, action: KeyAction, key: str) -> None: ...

    async def wheel(self, x: float, y: float, dx: float, dy: float) -> None: ...
