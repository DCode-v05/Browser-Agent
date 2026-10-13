"""The driver of computer use (spec 21.4): a contained desktop behind the same seam as a browser.

A session, its live picture, a person's hand on the mouse and the keyboard, and every rule that
holds for a browser hold for a desktop through this. What only a page has (refs, tabs, dialogs, an
address) a desktop has not: those operations say so.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Callable, Sequence
from typing import Any, NoReturn

from bap_browser.config import Config, QualityLevel
from bap_browser.driver.base import (
    ActionOutcome,
    Checked,
    ConsoleLine,
    Dragged,
    FileGuard,
    Found,
    Guard,
    Happened,
    KeyAction,
    LoadState,
    Located,
    MouseButton,
    NetworkLine,
    PageDialog,
    Place,
    PointerAction,
    SavedFile,
    ScrollPosition,
    Selected,
    Shot,
    TabInfo,
)
from bap_browser.driver.contained_desktop import App, ContainedDesktop, Desktop
from bap_browser.driver.screen_here import ScreenHere
from bap_browser.errors import BadInput

# The one thing a desktop has where a browser has tabs.
SCREEN = "desktop"
BUTTON_NUMBER: dict[MouseButton, str] = {"left": "1", "middle": "2", "right": "3"}
# The wheel, as buttons: up, down, left, right.
WHEEL_UP, WHEEL_DOWN, WHEEL_LEFT, WHEEL_RIGHT = "4", "5", "6", "7"
# Key names as the rest of the code writes them (`bap_browser.keys`), as the desktop takes them.
HELD = {
    "Control": "ctrl",
    "ControlOrMeta": "ctrl",
    "Shift": "shift",
    "Alt": "alt",
    "Meta": "super",
}
NAMED = {
    "Enter": "Return",
    "Tab": "Tab",
    "Space": "space",
    " ": "space",
    "Backspace": "BackSpace",
    "Delete": "Delete",
    "Escape": "Escape",
    "Insert": "Insert",
    "ArrowUp": "Up",
    "ArrowDown": "Down",
    "ArrowLeft": "Left",
    "ArrowRight": "Right",
    "Home": "Home",
    "End": "End",
    "PageUp": "Prior",
    "PageDown": "Next",
    "CapsLock": "Caps_Lock",
    "Control": "Control_L",
    "Shift": "Shift_L",
    "Alt": "Alt_L",
    "Meta": "Super_L",
}
# The characters that are a key by a name of their own.
SIGNS = {
    "+": "plus",
    "-": "minus",
    "=": "equal",
    ".": "period",
    ",": "comma",
    "/": "slash",
    "\\": "backslash",
    ";": "semicolon",
    ":": "colon",
    "'": "apostrophe",
    '"': "quotedbl",
    "[": "bracketleft",
    "]": "bracketright",
    "(": "parenleft",
    ")": "parenright",
    "{": "braceleft",
    "}": "braceright",
    "<": "less",
    ">": "greater",
    "?": "question",
    "!": "exclam",
    "@": "at",
    "#": "numbersign",
    "$": "dollar",
    "%": "percent",
    "^": "asciicircum",
    "&": "ampersand",
    "*": "asterisk",
    "_": "underscore",
    "|": "bar",
    "`": "grave",
    "~": "asciitilde",
}
NO_PAGE = "A desktop has no web page: this works in a browser only. Work on the desktop with computer_use."


def key_name(key: str) -> str | None:
    """One key as the desktop names it. None for what is no key the desktop knows."""
    if key in NAMED:
        return NAMED[key]
    if key in SIGNS:
        return SIGNS[key]
    if len(key) == 1 and key.isascii() and key.isalnum():
        return key
    if len(key) >= 2 and key[0] == "F" and key[1:].isdigit() and 1 <= int(key[1:]) <= 24:
        return key
    return None


class DesktopDriver:
    def __init__(self, config: Config, name: str = "computer") -> None:
        self._config = config
        self._settings = config.computer
        settings = config.computer
        self.desktop: Desktop = (
            ScreenHere(settings)
            if settings.runs == "here"
            else ContainedDesktop(settings, config.data_dir, name)
        )
        self._frames: asyncio.Task[None] | None = None
        self._last_shot: tuple[int, int] | None = None

    # The session.

    async def start(self) -> None:
        await self.desktop.start()

    async def close(self) -> None:
        await self.stop_frames()
        await self.desktop.close()

    def is_alive(self) -> bool:
        return self.desktop.alive

    def description(self) -> str:
        width, height = self._settings.screen_width, self._settings.screen_height
        return f"Contained desktop, {width} by {height}"

    async def tabs(self) -> list[TabInfo]:
        return [TabInfo(SCREEN, "", "Desktop", True)]

    async def viewport(self) -> tuple[int, int]:
        return self._settings.screen_width, self._settings.screen_height

    def where(self) -> tuple[str, str]:
        return SCREEN, ""

    def listen(self, on_event: Callable[[Happened], None]) -> None:
        """Nothing happens on a desktop that it tells of by itself."""

    def guard(self, judge: Guard) -> None:
        """A desktop loads no address. Whether it has a network at all is `computer.network`."""

    def guard_files(self, judge: FileGuard) -> None:
        """No file arrives from a site. What the desktop writes stays in its one shared folder."""

    # What the driver of a real desktop gives: `driver/hermes_driver.py`.

    async def windows(self) -> list[str]:
        raise NotImplementedError

    async def open_named_app(self, name: str) -> bool:
        raise NotImplementedError

    async def open_app(self, app: App) -> bool:
        raise NotImplementedError

    async def change_mark(self) -> str | None:
        return None

    async def screenshot(self, *, full_page: bool, annotate: bool) -> Shot:
        raise NotImplementedError

    def page_point(self, x: float, y: float) -> tuple[float, float]:
        return x, y

    # What an agent does on a desktop goes through the tool `computer_use`, never through these.

    async def zoom(self, region: tuple[float, float, float, float]) -> Shot:
        self._no_page()

    async def click_at(
        self, x: float, y: float, *, button: MouseButton, click_count: int, modifiers: Sequence[str]
    ) -> ActionOutcome:
        self._no_page()

    async def hover_at(self, x: float, y: float) -> ActionOutcome:
        self._no_page()

    async def type_text(
        self, ref: str | None, text: str, *, clear: bool, submit: bool, slowly: bool
    ) -> ActionOutcome:
        self._no_page()

    async def press_key(self, keys: str, *, repeat: int, ref: str | None) -> ActionOutcome:
        self._no_page()

    async def turn_wheel(self, direction: str, steps: int, at: tuple[float, float] | None) -> None:
        self._no_page()

    async def drag(self, start: Place, end: Place) -> Dragged:
        self._no_page()

    # The live picture.

    async def start_frames(self, on_frame: Callable[[bytes], None], level: QualityLevel) -> None:
        await self.stop_frames()
        self._frames = asyncio.create_task(self._send_frames(on_frame, level))

    async def stop_frames(self) -> None:
        frames, self._frames = self._frames, None
        if frames is not None:
            frames.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await frames

    async def _send_frames(self, on_frame: Callable[[bytes], None], level: QualityLevel) -> None:
        raise NotImplementedError

    # What a person does with the mouse and the keyboard while they are in control.

    async def pointer(self, action: PointerAction, x: float, y: float, button: MouseButton) -> None:
        line = f"mousemove {int(x)} {int(y)}"
        if action != "move":
            line += f" mouse{action} {BUTTON_NUMBER[button]}"
        await self.desktop.send(line)

    async def key(self, action: KeyAction, key: str) -> None:
        named = key_name(key)
        if named is not None:
            await self.desktop.send(f"key{action} {named}")

    async def wheel(self, x: float, y: float, dx: float, dy: float) -> None:
        moved, button = (dy, WHEEL_DOWN if dy > 0 else WHEEL_UP)
        if abs(dx) > abs(dy):
            moved, button = (dx, WHEEL_RIGHT if dx > 0 else WHEEL_LEFT)
        if moved:
            await self.desktop.send(f"mousemove {int(x)} {int(y)} click {button}")

    # What only a page has.

    def _no_page(self) -> NoReturn:
        raise BadInput(NO_PAGE, reason="a desktop has no page")

    async def navigate(self, url: str) -> str:
        self._no_page()

    async def locate(self, ref: str, *, press: bool = False) -> Located:
        self._no_page()

    async def locate_point(self, x: float, y: float) -> Located | None:
        return None

    async def locate_focus(self) -> Located | None:
        return None

    def on_screen(self) -> list[Located]:
        """The controls the newest capture named that have a place on the screen."""
        return []

    async def gist(self) -> list[str]:
        return []

    def unseen(self) -> list[str]:
        return []

    async def snapshot(self, *, mode: str, ref: str | None, max_chars: int, include_bboxes: bool) -> str:
        self._no_page()

    async def click(
        self, ref: str, *, button: MouseButton, click_count: int, modifiers: Sequence[str]
    ) -> ActionOutcome:
        self._no_page()

    async def back(self) -> str | None:
        self._no_page()

    async def forward(self) -> str | None:
        self._no_page()

    async def reload(self) -> str:
        self._no_page()

    async def text(self, ref: str | None, max_chars: int) -> tuple[str, int]:
        self._no_page()

    async def find(self, query: str, limit: int) -> Found:
        self._no_page()

    async def hover(self, ref: str) -> ActionOutcome:
        self._no_page()

    async def scroll(
        self, dx: float, dy: float, *, ref: str | None, at: tuple[float, float] | None
    ) -> ScrollPosition:
        self._no_page()

    async def scroll_to(self, ref: str) -> ActionOutcome:
        self._no_page()

    async def select_option(self, ref: str, values: Sequence[str]) -> Selected:
        self._no_page()

    async def set_checked(self, ref: str, checked: bool) -> Checked:
        self._no_page()

    async def wait_for_text(self, text: str, *, gone: bool, timeout_s: float) -> bool:
        self._no_page()

    async def wait_for_load(self, state: LoadState, timeout_s: float) -> bool:
        self._no_page()

    async def new_tab(self) -> str:
        self._no_page()

    async def switch_tab(self, tab_id: str) -> None:
        self._no_page()

    async def close_tab(self, tab_id: str | None) -> str:
        self._no_page()

    def pending_dialog(self) -> PageDialog | None:
        return None

    async def dialog_opened(self) -> None:
        # No page opens a dialog here: whoever waits for one waits until they stop waiting.
        await asyncio.Event().wait()

    async def answer_dialog(self, accept: bool, text: str | None) -> PageDialog:
        self._no_page()

    def console(self, *, clear: bool) -> list[ConsoleLine]:
        return []

    def network(self, *, clear: bool) -> list[NetworkLine]:
        return []

    async def evaluate(self, expression: str) -> Any:
        self._no_page()

    async def upload(self, ref: str, paths: Sequence[str]) -> ActionOutcome:
        self._no_page()

    def downloads(self) -> list[SavedFile]:
        return []

    async def settle_download(self, name: str, keep: bool, reason: str = "") -> None:
        """No file is ever held here."""
