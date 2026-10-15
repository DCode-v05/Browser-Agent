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

from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import WebSocketException

from bap_browser import computer
from bap_browser.computer import contained, remote
from bap_browser.config import Config
from bap_browser.config_computer import Computer
from bap_browser.driver.base import KeyAction, Located, MouseButton, PointerAction, QualityLevel, Shot
from bap_browser.driver.contained_desktop import App, ContainedDesktop
from bap_browser.driver.desktop_driver import DesktopDriver
from bap_browser.driver.mac_hand import MacHand, MacOS
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
# The driver's own program. Among the windows it is named `cua-driver.exe` on Windows and
# `Cua Driver` on macOS: with what is no letter taken out, both begin alike.
THE_DRIVER = "cua-driver"
# The program the driver pictures a window with on Linux (ImageMagick's).
ITS_PICTURES = "import"
NOT_A_LETTER = re.compile(r"[^a-z]")
ITS_OWN = "cuadriver"
# A role of a page, and what a desktop's own name for it holds. A box that is ticked and a field that
# is typed into are not judged as a button is (spec 18.4).
ROLES = {
    "checkbox": ("checkbox", "togglebutton", "switch"),
    "radio": ("radio",),
    "textbox": ("text", "entry", "edit", "document", "combobox", "searchfield", "password"),
    "link": ("link",),
}
# The roles of a field what is typed into is hidden in, and of one that holds many lines.
SECRET = ("secure", "password")
MANY_LINES = ("textarea", "textview", "document")
# How the desktop's own pointer does each press: the button, and how many times.
PRESSED = {"click": (1, 1), "double_click": (1, 2), "right_click": (3, 1), "middle_click": (2, 1)}
A_PICTURE = "data:"
PNG = b"\x89PNG"
# The states of a session in which a person is at the screen.
A_PERSON_IS_AT_THE_SCREEN = ("person", "person_requested")


def as_a_page_names(role: str) -> str:
    """What an element of a desktop is, in the words the check knows from a page. Each system has
    its own: `AXCheckBox`, `check box`, `CheckBox`. What is none of these is a button: it is pressed."""
    plain = NOT_A_LETTER.sub("", role.lower()).removeprefix("ax")
    return next((known for known, signs in ROLES.items() if any(sign in plain for sign in signs)), "button")


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
        self,
        config: Config,
        name: str = "computer",
        backend: Callable[[], Any] | None = None,
        macos: Callable[[], Any] | None = None,
    ) -> None:
        super().__init__(config, name)
        self._name = name
        self._stand_in = backend
        self._base: AbstractContextManager[None] | None = None
        self._last: Shot | None = None
        self._screen: ScreenHere | None = None
        self._placed: dict[int, tuple[int, int, int, int]] = {}
        self._named: dict[int, tuple[str, str]] = {}
        # How many times the driver's session was lost and begun afresh: each is a session of its own.
        self._afresh = 0
        # The element the agent last pressed by its number, which has the focus, and the app it
        # last named: what a key, typing and watch mode are judged by (spec 22.7).
        self._focus: int | None = None
        self.working_in = ""
        # On a Mac's own screen a person's hand on the picture is posted to macOS itself.
        self._macos: Any = None
        self._hand: MacHand | None = None
        # On a machine elsewhere, the way to its helper's hand while a person has taken over.
        self.far_hand: ClientConnection | None = None
        # The size the page was first told, which it measures where a person points in.
        self.page_size: tuple[int, int] | None = None
        # The system of the machine driven: this one's, or what a machine elsewhere says it runs.
        self.system_driven = sys.platform
        # The same, where it is known: a machine elsewhere that does not say has none, and a desktop
        # of its own (a container, the micro VM's screen) is Linux whatever runs the engine.
        self.system_known: str | None = (
            None
            if self._settings.runs == "remote"
            else "linux"
            if self._settings.runs in ("container", "here")
            else sys.platform
        )
        if self._settings.runs == "machine" and (macos is not None or sys.platform == "darwin"):
            self._macos = (macos or MacOS)()
            self._hand = MacHand(
                self._macos,
                again_within_s=self._settings.double_press_ms / 1000,
                again_within_points=self._settings.double_press_points,
            )

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
            driver_path = None
            if self._stand_in is None:
                await self.desktop.image_ready()
                home = computer.home_of(self._config)
                driver_path = await asyncio.to_thread(contained.fetch_the_driver, self._settings, home)
            await self.desktop.start(driver_path)
            container = self.desktop.container
        self._base = computer.base(self._config, backend=self._stand_in, container=container)
        self._base.__enter__()
        # The engine's own check has judged a call, and asked a person where the settings say so,
        # before it reaches the tool (spec 22.3.1). The tool's own question is answered by that.
        computer.ask_with(lambda action, about: True)
        if self._settings.runs == "remote":
            code = os.environ.get(self._settings.helper_token_env, "")
            said = await asyncio.to_thread(
                remote.system_of_the_machine,
                self._settings.helper_url,
                code,
                self._settings.base.helper_run_timeout_s,
            )
            self.system_driven = said or self.system_driven
            self.system_known = said

    async def close(self) -> None:
        await self.stop_frames()
        await self.let_go()
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
        if self._settings.runs == "container":
            return super().description()
        return "A machine elsewhere" if self._settings.runs == "remote" else "This machine's own screen"

    async def viewport(self) -> tuple[int, int]:
        if self._hand is not None:
            # A Mac's screen in the points its events are placed by: the page works in them, so
            # that a place on the picture is that place on the screen.
            across, down = self._macos.size()
            return int(across), int(down)
        if self.page_size is None:
            # The page works in the size it is told at the start, whatever size a later picture is:
            # what a person does on the picture is measured against it.
            self.page_size = (
                (self._settings.screen_width, self._settings.screen_height)
                if self._last is None
                else (self._last.width, self._last.height)
            )
        return self.page_size

    # What the agent does: one call of Hermes' tool.

    async def use(self, arguments: dict[str, Any], session: str | None = None) -> Any:
        """One call of `computer_use`. Text as a JSON string, or a dictionary that holds a picture."""
        if self._base is None:
            raise BrowserError(
                "The machine's screen is not being driven any more.", reason="the session ended"
            )
        return await asyncio.to_thread(computer.computer_use, arguments, session or self.session_name)

    # Where things are, on a desktop this engine itself started (spec 22.5).

    def saw(self, elements: list[dict[str, Any]]) -> None:
        """Keeps where each element of the newest capture is on the screen, by its number."""
        self._placed = {
            int(one["index"]): (int(x), int(y), int(wide), int(high))
            for one in elements
            for x, y, wide, high in [one.get("bounds") or (0, 0, 0, 0)]
        }
        self._named = {
            int(one["index"]): (str(one.get("role", "")), str(one.get("label", ""))) for one in elements
        }

    def pressed_on(self, element: int | None) -> None:
        """The element a press went to, which then has the focus. None for a press by its place."""
        self._focus = element

    async def locate_focus(self) -> Located | None:
        if self._focus is None or self._focus not in self._named:
            return None
        role, name = self._named[self._focus]
        plain = NOT_A_LETTER.sub("", role.lower()).removeprefix("ax")
        return Located(
            as_a_page_names(role),
            name,
            None,
            secret=any(sign in plain for sign in SECRET),
            multiline=any(sign in plain for sign in MANY_LINES),
            kind="text" if as_a_page_names(role) == "textbox" else "other",
        )

    async def locate(self, ref: str, *, press: bool = False) -> Located:
        """An element of the newest capture, by its number, as the check judges a press (spec 18.4):
        by what it is and what it is called."""
        named = self._named.get(int(ref)) if ref.isdigit() else None
        if named is None:
            self._no_page()
        role, name = named
        return Located(as_a_page_names(role), name, None)

    def on_screen(self) -> list[Located]:
        return [
            Located(as_a_page_names(role), name, None)
            for number, (role, name) in self._named.items()
            if all(self._placed.get(number, (0, 0, 0, 0))[2:])
        ]

    async def press(self, element: int, action: str) -> Literal["pressed", "nowhere"] | None:
        """Presses an element with the desktop's own pointer, at its middle on the screen. "nowhere"
        for one with no size: an item of a menu that is not open, or a hidden button. None where the
        press is left to the driver: the element is not known, the desktop is not this engine's own,
        or the app does not say where the element is. An app of GTK 4 gives every element the corner
        of its window, so a corner that another element has too is nobody's place."""
        own = self._screen or (self.desktop if self._settings.runs in ("container", "here") else None)
        if own is None or element not in self._placed:
            return None
        x, y, wide, high = self._placed[element]
        if not wide or not high:
            return "nowhere"
        shared = [
            other
            for number, other in self._placed.items()
            if number != element and other[:2] == (x, y) and other[2] and other[3]
        ]
        if shared:
            return None
        button, times = PRESSED[action]
        await own.send(f"mousemove {x + wide // 2} {y + high // 2} click --repeat {times} {button}")
        return "pressed"

    async def typed(self, text: str) -> bool:
        """Types text with the desktop's own keyboard, where this engine itself started the desktop.
        As a person's typing does, it takes the place of what is selected; the driver's own typing
        puts text in beside a selection. That keyboard has the letters of plain text on one line:
        False for any other text, and where the keyboard could not type, and the driver types it."""
        own = self._screen or (self.desktop if self._settings.runs in ("container", "here") else None)
        if own is None or not (text.isascii() and text.isprintable()):
            return False
        gap = str(self._settings.key_gap_ms)
        try:
            # The text is the program's input and no word of its command: a command can be listed.
            await own.run("xdotool", "type", "--delay", gap, "--file", "-", stdin=text.encode())
        except BapError:
            return False
        return True

    @property
    def session_name(self) -> str:
        """The name the base knows the agent's session with the driver by."""
        return f"{self._name}.{self._afresh}" if self._afresh else self._name

    async def started_again(self) -> bool:
        """Puts right a desktop that has stopped answering. The next call goes to a session of its
        own: one that is gone, as over a link whose new process does not know it, is not revived.
        Where this engine itself started the desktop, more is done. On Linux the driver pictures a
        window with a program of its own, and when the window has gone that program waits for ever
        with the screen held: nothing else is answered, a fresh driver neither. It is ended, and the
        driver with it. The desktop's apps are left as they are. On a person's own machine nothing
        is ended: what runs there is theirs."""
        self._afresh += 1
        own = self._screen or (self.desktop if self._settings.runs in ("container", "here") else None)
        if own is None:
            return True
        for program in (ITS_PICTURES, THE_DRIVER):
            with contextlib.suppress(BapError):
                # It answers nothing, so it is not asked: it is ended. None left to end is no failure.
                await own.run("pkill", "-9", "-x", program)
        return True

    # What the two tools kept from before ask.

    async def windows(self) -> list[str]:
        """The titles of the windows that are open."""
        listed = await self.use({"action": "list_windows"})
        answer = json.loads(listed) if isinstance(listed, str) else {}
        titles = [
            str(window.get("title") or window.get("app_name") or "")
            for window in answer.get("windows", [])
            # The driver draws the agent's pointer in windows of its own: nothing to work in.
            if not NOT_A_LETTER.sub("", str(window.get("app_name", "")).lower()).startswith(ITS_OWN)
        ]
        kept = [title[: self._settings.window_title_chars] for title in titles if title.strip()]
        return kept[: self._settings.windows_listed]

    async def open_app(self, app: App) -> bool:
        if isinstance(self.desktop, ContainedDesktop) and self._settings.runs == "container":
            # In its container the desktop starts its own apps, and only those a person allowed.
            await self.desktop.start_app(app)
            return True
        named = NAMED.get(self.system_driven, {}).get(app.id, app.command)
        return await self.open_named_app(named)

    async def open_named_app(self, name: str) -> bool:
        if self._base is None:
            return False
        return await asyncio.to_thread(computer.open_app, name, self.session_name)

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
        if self._settings.runs == "remote":
            if state in A_PERSON_IS_AT_THE_SCREEN:
                await self.reach_out()
            else:
                await self.let_go()

    # A machine elsewhere: a person who has taken over on this engine's page uses its mouse and
    # keyboard through the helper there, where that machine's person allows it (spec 22.6.2).

    async def reach_out(self) -> None:
        if self.far_hand is not None:
            return
        code = os.environ.get(self._settings.helper_token_env, "")
        there = self._settings.helper_url.rstrip("/").replace("http", "ws", 1) + "/hand"
        try:
            self.far_hand = await connect(there, additional_headers={"Authorization": f"Bearer {code}"})
        except (OSError, WebSocketException, TimeoutError):
            # That machine's person has not allowed it: the page says to use that machine's own.
            self.far_hand = None

    async def let_go(self) -> None:
        hand, self.far_hand = self.far_hand, None
        if hand is not None:
            with contextlib.suppress(OSError, WebSocketException):
                await hand.close()

    async def hand_over(self, what: dict[str, Any]) -> None:
        """One thing a person did, sent to the machine elsewhere. Where on the picture is sent as a
        share of it: that machine knows its own screen's size."""
        hand = self.far_hand
        if hand is None:
            return
        if "x" in what:
            wide, high = await self.viewport()
            what = {**what, "x": what["x"] / wide, "y": what["y"] / high}
        try:
            await hand.send(json.dumps(what))
        except (OSError, WebSocketException):
            self.far_hand = None

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

    # What a person does on the picture while they are in control. On a desktop nobody sits at, the
    # contained one and the micro VM's, it is sent to that desktop. On a Mac's own screen it is
    # posted to macOS, where the person allowed that. Anywhere else the person has the machine's own
    # mouse and keyboard, and nothing is sent.

    def is_its_own(self) -> bool:
        return self._settings.runs in ("container", "here") or self._screen is not None

    def takes_a_hand(self) -> bool:
        """Whether what a person does on the picture reaches the screen."""
        return (
            self.is_its_own()
            or self.far_hand is not None
            or (self._hand is not None and bool(self._macos.allowed()))
        )

    async def pointer(self, action: PointerAction, x: float, y: float, button: MouseButton) -> None:
        if self.is_its_own():
            await super().pointer(action, x, y, button)
        elif self.far_hand is not None:
            await self.hand_over({"kind": "pointer", "action": action, "x": x, "y": y, "button": button})
        elif self._hand is not None and self.takes_a_hand():
            self._hand.pointer(action, x, y, button)

    async def key(self, action: KeyAction, key: str) -> None:
        if self.is_its_own():
            await super().key(action, key)
        elif self.far_hand is not None:
            await self.hand_over({"kind": "key", "action": action, "key": key})
        elif self._hand is not None and self.takes_a_hand():
            self._hand.key(action, key)

    async def wheel(self, x: float, y: float, dx: float, dy: float) -> None:
        if self.is_its_own():
            await super().wheel(x, y, dx, dy)
        elif self.far_hand is not None:
            await self.hand_over({"kind": "wheel", "x": x, "y": y, "dx": dx, "dy": dy})
        elif self._hand is not None and self.takes_a_hand():
            self._hand.pointer("move", x, y, "left")
            self._hand.wheel(dx, dy)

    async def change_mark(self) -> str | None:
        """Whether the screen changed is told by the tool's own results, not by a mark of ours."""
        return None


def desktop_driver_for(config: Config, name: str = "computer") -> DesktopDriver:
    """The driver of the desktop the configuration names: a container's, or a real machine's, driven
    here, on a person's own Mac, or on a machine elsewhere, all through Hermes' base (spec 22.3)."""
    return HermesDriver(config, name)
