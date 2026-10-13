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
import re
import sys
from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any, Literal

from bap_browser import computer
from bap_browser.computer import contained
from bap_browser.config import Config
from bap_browser.config_computer import Computer
from bap_browser.driver.base import KeyAction, MouseButton, PointerAction, QualityLevel, Shot
from bap_browser.driver.contained_desktop import App, ContainedDesktop, Desktop
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
# What `xwininfo` says of a window: its corner on the screen and its size.
ITS_PLACE = re.compile(r"(Absolute upper-left [XY]|Width|Height):\s+(-?\d+)")
# How the desktop's own pointer does each press: the button, and how many times.
PRESSED = {"click": (1, 1), "double_click": (1, 2), "right_click": (3, 1), "middle_click": (2, 1)}
A_PICTURE = "data:"
PNG = b"\x89PNG"
# The states of a session in which a person is at the screen.
A_PERSON_IS_AT_THE_SCREEN = ("person", "person_requested")


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
        self._placed: dict[int, tuple[int, int, int, int]] = {}
        self._inside = False
        self._captured = ("", 0, 0)

    # The session.

    async def start(self) -> None:
        # With a backend named in the driver's place there is no driver to lack.
        lacking = None if self._stand_in else await asyncio.to_thread(computer.lacks, self._config)
        if lacking is not None:
            raise BrowserError(lacking.said, reason=f"the machine lacks: {lacking.what}")
        if self._settings.base.virtual_screen or self._settings.runs == "here":
            self._screen = await own_screen(self._settings)
        container = None
        if isinstance(self.desktop, ContainedDesktop) and self._settings.runs == "container":
            # The desktop is started as before; its driver is then put inside it.
            await self.desktop.start()
            container = self.desktop.container
            if self._stand_in is None:
                home = computer.home_of(self._config)
                await asyncio.to_thread(contained.put_the_driver_in, self._settings, home, container)
        self._base = computer.base(self._config, backend=self._stand_in, container=container)
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
        if isinstance(self.desktop, ContainedDesktop) and self.desktop.alive:
            await self.desktop.close()

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

    # Where things are, on a desktop this engine itself started (spec 22.5).

    def saw(self, elements: list[dict[str, Any]], app: str, size: tuple[int, int]) -> None:
        """Keeps where each element of the newest capture is, by its number, and whether the app gave
        the places on the screen or inside its own window. An app of GTK 4 gives them inside its
        window, and then nothing reaches past the window's own size; others give them on the screen."""
        self._placed = {
            int(one["index"]): (int(x), int(y), int(wide), int(high))
            for one in elements
            for x, y, wide, high in [one.get("bounds") or (0, 0, 0, 0)]
        }
        sized = [place for place in self._placed.values() if place[2] and place[3]]
        wide, high = size
        self._inside = bool(sized and wide and high) and all(
            x >= 0 and y >= 0 and x + its_width <= wide and y + its_height <= high
            for x, y, its_width, its_height in sized
        )
        self._captured = (app, wide, high)

    async def _corner(self, own: Desktop) -> tuple[int, int]:
        """Where the captured window is on the screen: the window of that app that has that size."""
        app, wide, high = self._captured
        listed = await self.use({"action": "list_windows"})
        rows = json.loads(listed).get("windows", []) if isinstance(listed, str) else []
        of_the_app = [row for row in rows if str(row.get("app_name", "")).lower() == app.lower()] or rows
        first: tuple[int, int] | None = None
        for row in of_the_app:
            said = (await own.run("xwininfo", "-id", str(int(row["window_id"])))).decode()
            at = {name: int(number) for name, number in ITS_PLACE.findall(said)}
            corner = at.get("Absolute upper-left X", 0), at.get("Absolute upper-left Y", 0)
            first = first or corner
            if (at.get("Width"), at.get("Height")) == (wide, high):
                return corner
        return first or (0, 0)

    async def press(self, element: int, action: str) -> Literal["pressed", "nowhere"] | None:
        """Presses an element with the desktop's own pointer, at its middle on the screen. "nowhere"
        for one with no size: an item of a menu that is not open, or a hidden button. None where the
        element is not known, or the desktop is not this engine's own: then nothing was done."""
        own = self._screen or (self.desktop if self._settings.runs in ("container", "here") else None)
        if own is None or element not in self._placed:
            return None
        x, y, wide, high = self._placed[element]
        if not wide or not high:
            return "nowhere"
        left, top = await self._corner(own) if self._inside else (0, 0)
        button, times = PRESSED[action]
        await own.send(
            f"mousemove {left + x + wide // 2} {top + y + high // 2} click --repeat {times} {button}"
        )
        return "pressed"

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
        if isinstance(self.desktop, ContainedDesktop) and self._settings.runs == "container":
            # In its container the desktop starts its own apps, and only those a person allowed.
            await self.desktop.start_app(app)
            return True
        named = NAMED.get(sys.platform, {}).get(app.id, app.command)
        return await self.open_named_app(named)

    async def open_named_app(self, name: str) -> bool:
        if self._base is None:
            return False
        return await asyncio.to_thread(computer.open_app, name, self._name)

    # What a person sees: the whole screen. The viewer has a session of its own with the driver, so
    # that its looking never moves the window the agent is working in.

    async def screenshot(self, *, full_page: bool, annotate: bool) -> Shot:
        if self._base is None:
            raise BrowserError(
                "The machine's screen is not being driven any more.", reason="the session ended"
            )
        seen = await asyncio.to_thread(computer.screen, f"{self._name}:viewer")
        if seen.png_b64:
            data = base64.b64decode(seen.png_b64)
            kind = seen.image_mime_type or ("image/png" if data.startswith(PNG) else "image/jpeg")
            self._last = Shot(Picture(data, kind), seen.width, seen.height)
        if self._last is None:
            raise BrowserError("The machine gave no picture of its screen.", reason="no picture")
        return self._last

    async def control_is(self, state: str) -> None:
        """Who has the session now. While a person is at the screen, Hermes' own gate keeps the agent
        from it: on a real machine that gate follows the person's hand (spec 22.3.1)."""
        if self._base is not None:
            await asyncio.to_thread(computer.person_holds, state in A_PERSON_IS_AT_THE_SCREEN)

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

    # A person at their own machine has their own mouse and keyboard: nothing is sent for them. On a
    # desktop nobody sits at, the contained one and the micro VM's, their hand in the viewer is sent.

    def _has_a_hand_to_send(self) -> bool:
        return self._settings.runs in ("container", "here") or self._screen is not None

    async def pointer(self, action: PointerAction, x: float, y: float, button: MouseButton) -> None:
        if self._has_a_hand_to_send():
            await super().pointer(action, x, y, button)

    async def key(self, action: KeyAction, key: str) -> None:
        if self._has_a_hand_to_send():
            await super().key(action, key)

    async def wheel(self, x: float, y: float, dx: float, dy: float) -> None:
        if self._has_a_hand_to_send():
            await super().wheel(x, y, dx, dy)

    async def change_mark(self) -> str | None:
        """Whether the screen changed is told by the tool's own results, not by a mark of ours."""
        return None


def desktop_driver_for(config: Config, name: str = "computer") -> DesktopDriver:
    """The driver of the desktop the configuration names: a container's, or a real machine's, driven
    here, on a person's own Mac, or on a machine elsewhere, all through Hermes' base (spec 22.3)."""
    return HermesDriver(config, name)
