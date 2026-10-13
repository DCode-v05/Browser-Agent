"""A person's hand on a Mac's own screen, through the page's picture (spec 22.3.1).

The driver of computer use presses inside a window it is told of, and does not say where windows
are on the screen: it cannot press where a person points on a picture of the whole screen. macOS
itself can. What the person does on the picture is posted to the system as the events a mouse and
a keyboard make. macOS takes them only from a program the person allowed under Accessibility.
"""

from __future__ import annotations

import ctypes
import time
from typing import Protocol

from bap_browser.driver.base import KeyAction, MouseButton, PointerAction

# macOS's own numbers, which are fixed: the event of a pointer that moved; where an event is posted
# so that it is taken as the machine's own; the field that counts presses; a wheel told in pixels.
MOVED, AS_THE_MACHINES_OWN, THE_PRESS_COUNT, IN_PIXELS = 5, 0, 1, 0
# The kinds of event a mouse makes, as macOS numbers them, by button: down, up, moved while held.
OF_A_BUTTON: dict[MouseButton, tuple[int, int, int]] = {
    "left": (1, 2, 6),
    "right": (3, 4, 7),
    "middle": (25, 26, 27),
}
BUTTON_NUMBER: dict[MouseButton, int] = {"left": 0, "right": 1, "middle": 2}
# The keys that change what another key means, and the flag each sets on the events after it.
HOLDING = {"Shift": (56, 0x20000), "Control": (59, 0x40000), "Alt": (58, 0x80000), "Meta": (55, 0x100000)}
# With one of these held, a letter is a command (cmd+c), and is sent as its key, not as a character.
COMMANDING = 0x40000 | 0x100000
# The keys with a name, by the number of the key on a Mac's keyboard.
NAMED = {
    "Enter": 36,
    "Tab": 48,
    " ": 49,
    "Backspace": 51,
    "Escape": 53,
    "Delete": 117,
    "Home": 115,
    "End": 119,
    "PageUp": 116,
    "PageDown": 121,
    "ArrowLeft": 123,
    "ArrowRight": 124,
    "ArrowDown": 125,
    "ArrowUp": 126,
}
# The keys of letters, digits and signs, on the keyboard macOS takes commands by.
LETTERS = dict(
    zip(
        "asdfhgzxcv" + "bqweryt123465=97-80]ou[ip" + "lj'k;\\,/nm.`",
        [*range(10), *range(11, 36), *range(37, 48), 50],
        strict=True,
    )
)


class Posts(Protocol):
    """What takes the events: macOS, or in a test what keeps them."""

    def mouse(self, kind: int, x: float, y: float, button: int, clicks: int) -> None: ...

    def key(self, code: int, down: bool, flags: int, text: str) -> None: ...

    def scroll(self, down: int, right: int) -> None: ...


class MacHand:
    """What a person does on the picture, turned into the events of a Mac's mouse and keyboard."""

    def __init__(self, posts: Posts, *, again_within_s: float, again_within_points: float) -> None:
        self._posts = posts
        self._again_within_s = again_within_s
        self._again_within_points = again_within_points
        self._held: set[MouseButton] = set()
        self._flags = 0
        self._last_press: tuple[float, float, float, int] = (0.0, 0.0, 0.0, 0)

    def pointer(self, action: PointerAction, x: float, y: float, button: MouseButton) -> None:
        if action == "move":
            # A move with a button held drags what was pressed.
            held = next(iter(self._held), None)
            self._posts.mouse(OF_A_BUTTON[held][2] if held else MOVED, x, y, BUTTON_NUMBER[held or "left"], 0)
            return
        down, up, _ = OF_A_BUTTON[button]
        if action == "down":
            self._held.add(button)
            self._last_press = (time.monotonic(), x, y, self._presses_in_a_row(x, y))
        else:
            self._held.discard(button)
        # macOS tells a double press by a count on the events, not by their times.
        self._posts.mouse(down if action == "down" else up, x, y, BUTTON_NUMBER[button], self._last_press[3])

    def _presses_in_a_row(self, x: float, y: float) -> int:
        when, last_x, last_y, count = self._last_press
        near = max(abs(x - last_x), abs(y - last_y)) <= self._again_within_points
        return count + 1 if near and time.monotonic() - when <= self._again_within_s else 1

    def key(self, action: KeyAction, key: str) -> None:
        down = action == "down"
        if key in HOLDING:
            code, flag = HOLDING[key]
            self._flags = self._flags | flag if down else self._flags & ~flag
            self._posts.key(code, down, self._flags, "")
        elif key in NAMED:
            self._posts.key(NAMED[key], down, self._flags, "")
        elif len(key) == 1 and self._flags & COMMANDING and key.lower() in LETTERS:
            self._posts.key(LETTERS[key.lower()], down, self._flags, "")
        elif len(key) == 1:
            # A character, whatever keyboard the Mac has: the system is given the character itself.
            self._posts.key(0, down, self._flags, key)

    def wheel(self, dx: float, dy: float) -> None:
        # A page's wheel counts down and right; macOS counts up and left.
        if dx or dy:
            self._posts.scroll(-int(dy), -int(dx))


class Point(ctypes.Structure):
    _fields_ = (("x", ctypes.c_double), ("y", ctypes.c_double))


class Rect(ctypes.Structure):
    _fields_ = (
        ("x", ctypes.c_double),
        ("y", ctypes.c_double),
        ("wide", ctypes.c_double),
        ("high", ctypes.c_double),
    )


SERVICES = "/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices"


class MacOS:
    """macOS itself, asked through the system's own library: no package is added for it."""

    def __init__(self) -> None:
        its = self._its = ctypes.CDLL(SERVICES)
        ref = ctypes.c_void_p
        its.AXIsProcessTrusted.restype = ctypes.c_bool
        its.CGMainDisplayID.restype = ctypes.c_uint32
        its.CGDisplayBounds.restype, its.CGDisplayBounds.argtypes = Rect, (ctypes.c_uint32,)
        its.CGEventCreate.restype, its.CGEventCreate.argtypes = ref, (ref,)
        its.CGEventGetLocation.restype, its.CGEventGetLocation.argtypes = Point, (ref,)
        its.CGEventCreateMouseEvent.restype = ref
        its.CGEventCreateMouseEvent.argtypes = (ref, ctypes.c_uint32, Point, ctypes.c_uint32)
        its.CGEventCreateKeyboardEvent.restype = ref
        its.CGEventCreateKeyboardEvent.argtypes = (ref, ctypes.c_uint16, ctypes.c_bool)
        its.CGEventCreateScrollWheelEvent2.restype = ref
        its.CGEventCreateScrollWheelEvent2.argtypes = (
            ref,
            ctypes.c_uint32,
            ctypes.c_uint32,
            *(ctypes.c_int32,) * 3,
        )
        its.CGEventSetIntegerValueField.argtypes = (ref, ctypes.c_uint32, ctypes.c_int64)
        its.CGEventSetFlags.argtypes = (ref, ctypes.c_uint64)
        # The characters go as UTF-16, which is what the system's own strings are.
        its.CGEventKeyboardSetUnicodeString.argtypes = (ref, ctypes.c_ulong, ctypes.c_char_p)
        its.CGEventPost.argtypes = (ctypes.c_uint32, ref)
        its.CFRelease.argtypes = (ref,)

    def allowed(self) -> bool:
        """Whether the person allowed this program under Accessibility. Without it macOS drops
        every event this program posts."""
        return bool(self._its.AXIsProcessTrusted())

    def size(self) -> tuple[float, float]:
        """The main screen's size, in the points its events are placed by."""
        screen = self._its.CGDisplayBounds(self._its.CGMainDisplayID())
        return screen.wide, screen.high

    def pointer_at(self) -> tuple[float, float]:
        event = self._its.CGEventCreate(None)
        at = self._its.CGEventGetLocation(event)
        self._its.CFRelease(event)
        return at.x, at.y

    def _post(self, event: int | None) -> None:
        if event:
            self._its.CGEventPost(AS_THE_MACHINES_OWN, event)
            self._its.CFRelease(event)

    def mouse(self, kind: int, x: float, y: float, button: int, clicks: int) -> None:
        event = self._its.CGEventCreateMouseEvent(None, kind, Point(x, y), button)
        if event and clicks:
            self._its.CGEventSetIntegerValueField(event, THE_PRESS_COUNT, clicks)
        self._post(event)

    def key(self, code: int, down: bool, flags: int, text: str) -> None:
        event = self._its.CGEventCreateKeyboardEvent(None, code, down)
        if event:
            self._its.CGEventSetFlags(event, flags)
            if text:
                units = text.encode("utf-16-le")
                self._its.CGEventKeyboardSetUnicodeString(event, len(units) // 2, units)
        self._post(event)

    def scroll(self, down: int, right: int) -> None:
        self._post(self._its.CGEventCreateScrollWheelEvent2(None, IN_PIXELS, 2, down, right, 0))
