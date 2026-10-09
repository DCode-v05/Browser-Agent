"""The driver of computer use (spec 21.4): a contained desktop behind the same seam as a browser.

A session, its live picture, a person's hand on the mouse and the keyboard, and every rule that
holds for a browser hold for a desktop through this. What only a page has (refs, tabs, dialogs, an
address) a desktop has not: those operations say so.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
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
from bap_browser.driver.contained_desktop import App, ContainedDesktop
from bap_browser.errors import BadInput, BapError, BrowserError
from bap_browser.results import Picture

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
NO_PAGE = "A desktop has no web page: this works in a browser only. Look at the screen and act by its pixels."


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


def chord(keys: str) -> str:
    """`Control+Shift+t`, as `bap_browser.keys.normalise` gives it, as the desktop takes it."""
    *held, key = ["+"] if keys == "+" else keys.replace("++", "+plus").split("+")
    named = key_name("+" if key == "plus" else key)
    if named is None or any(part not in HELD for part in held):
        raise BadInput(
            "That key cannot be pressed on the desktop. Use a name such as Enter, Escape, Tab, "
            "ArrowDown or F5, or one character.",
            reason="the key name is not known",
        )
    return "+".join([*(HELD[part] for part in held), named])


class DesktopDriver:
    def __init__(self, config: Config, name: str = "computer") -> None:
        self._config = config
        self._settings = config.computer
        self.desktop = ContainedDesktop(config.computer, config.data_dir, name)
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

    # What the desktop is asked.

    async def windows(self) -> list[str]:
        """The titles of the windows that are open, as the desktop gives them."""
        try:
            out = await self.desktop.run(
                "xdotool", "search", "--onlyvisible", "--name", ".", "getwindowname", "%@"
            )
        except BrowserError:
            if not self.desktop.alive:
                raise
            # With no window open the search finds nothing, and says so as a failure.
            return []
        most, longest = self._settings.windows_listed, self._settings.window_title_chars
        titles = [line.strip()[:longest] for line in out.decode(errors="replace").splitlines()]
        return [title for title in titles if title and title != "Openbox"][:most]

    async def open_app(self, app: App) -> bool:
        """Opens an app. True when a window of it came up in time."""
        before = len(await self.windows())
        await self.desktop.start_app(app)
        waited, pause = 0.0, self._settings.app_poll_ms / 1000
        while waited < self._settings.app_open_wait_s:
            await asyncio.sleep(pause)
            waited += pause
            if len(await self.windows()) > before:
                return True
        return False

    async def _picture(self, *how: str) -> bytes:
        return await self.desktop.run("import", "-window", "root", *how)

    async def _settle(self) -> None:
        await asyncio.sleep(self._settings.settle_ms / 1000)

    async def change_mark(self) -> str | None:
        try:
            small = await self._picture("-resize", f"{self._settings.mark_width}x", "png:-")
        except BrowserError:
            return None
        return hashlib.sha256(small).hexdigest()

    async def screenshot(self, *, full_page: bool, annotate: bool) -> Shot:
        width, height = await self.viewport()
        data = await self._picture("png:-")
        self._last_shot = (width, height)
        return Shot(Picture(data, "image/png"), width, height)

    async def zoom(self, region: tuple[float, float, float, float]) -> Shot:
        width, height = await self.viewport()
        x, y = max(0, int(region[0])), max(0, int(region[1]))
        w, h = min(int(region[2]), width) - x, min(int(region[3]), height) - y
        if w <= 0 or h <= 0:
            raise BadInput(
                f"The region is outside the screen, which is {width} by {height} pixels.",
                reason="the region is outside the screen",
            )
        # A small region is given at twice its size, so that small print can be read.
        data = await self._picture("-crop", f"{w}x{h}+{x}+{y}", "+repage", "-resize", "200%", "png:-")
        return Shot(Picture(data, "image/png"), w * 2, h * 2, scaled=True)

    def page_point(self, x: float, y: float) -> tuple[float, float]:
        return x, y

    # What the agent does.

    def _on_screen(self, x: float, y: float) -> tuple[str, str]:
        width, height = self._settings.screen_width, self._settings.screen_height
        if not (0 <= x < width and 0 <= y < height):
            raise BadInput(
                f"({x:g}, {y:g}) is outside the screen, which is {width} by {height} pixels.",
                reason="the point is outside the screen",
            )
        return str(int(x)), str(int(y))

    async def click_at(
        self, x: float, y: float, *, button: MouseButton, click_count: int, modifiers: Sequence[str]
    ) -> ActionOutcome:
        at = self._on_screen(x, y)
        held = [HELD[name] for name in modifiers if name in HELD]
        command = ["xdotool", "mousemove", *at]
        for name in held:
            command += ["keydown", name]
        command += ["click", "--repeat", str(click_count), BUTTON_NUMBER[button]]
        for name in reversed(held):
            command += ["keyup", name]
        await self.desktop.run(*command)
        await self._settle()
        return ActionOutcome(f"the screen at ({at[0]}, {at[1]})")

    async def hover_at(self, x: float, y: float) -> ActionOutcome:
        at = self._on_screen(x, y)
        await self.desktop.run("xdotool", "mousemove", *at)
        await self._settle()
        return ActionOutcome(f"the screen at ({at[0]}, {at[1]})")

    async def type_text(
        self, ref: str | None, text: str, *, clear: bool, submit: bool, slowly: bool
    ) -> ActionOutcome:
        if ref is not None:
            self._no_page()
        if clear:
            await self.desktop.run("xdotool", "key", "ctrl+a", "key", "Delete")
        # The text goes in on the standard input: it is in no command line, and so in no list of processes.
        await self.desktop.run(
            "xdotool",
            "type",
            "--delay",
            str(self._settings.type_delay_ms),
            "--file",
            "-",
            stdin=text.encode(),
        )
        if submit:
            # A field that completes what is typed takes a moment to settle; an Enter before that is lost.
            await self._settle()
            await self.desktop.run("xdotool", "key", "Return")
        await self._settle()
        return ActionOutcome("")

    async def press_key(self, keys: str, *, repeat: int, ref: str | None) -> ActionOutcome:
        if ref is not None:
            self._no_page()
        await self.desktop.run("xdotool", "key", "--repeat", str(repeat), chord(keys))
        await self._settle()
        return ActionOutcome("")

    async def turn_wheel(self, direction: str, steps: int, at: tuple[float, float] | None) -> None:
        """Turns the mouse wheel, where the pointer is or at a point."""
        command = ["xdotool"]
        if at is not None:
            command += ["mousemove", *self._on_screen(*at)]
        button = {"up": WHEEL_UP, "down": WHEEL_DOWN, "left": WHEEL_LEFT, "right": WHEEL_RIGHT}[direction]
        notches = steps * self._settings.scroll_notches_per_step
        await self.desktop.run(*command, "click", "--repeat", str(notches), button)
        await self._settle()

    async def drag(self, start: Place, end: Place) -> Dragged:
        if isinstance(start, str) or isinstance(end, str):
            self._no_page()
        begin, finish = self._on_screen(*start), self._on_screen(*end)
        pause = str(self._settings.drag_pause_ms / 1000)
        await self.desktop.run(
            "xdotool",
            *("mousemove", *begin, "mousedown", "1", "sleep", pause),
            *("mousemove", *finish, "sleep", pause, "mouseup", "1"),
        )
        await self._settle()
        return Dragged(f"({begin[0]}, {begin[1]})", f"({finish[0]}, {finish[1]})")

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
        how = ["-quality", str(min(level.jpeg_quality, self._settings.frame_jpeg_quality))]
        if level.max_width < self._settings.screen_width:
            how = ["-resize", f"{level.max_width}x", *how]
        pause = max(self._settings.frame_ms / 1000, 1 / level.max_fps)
        last = b""
        while self.desktop.alive:
            try:
                frame = await self._picture(*how, "jpeg:-")
            except BapError:
                await asyncio.sleep(pause)
                continue
            # A screen that stands still is sent once.
            if frame != last:
                last = frame
                on_frame(frame)
            await asyncio.sleep(pause)

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
