"""The mouse, the keyboard and the screen of a real Mac (spec 21.13), through macOS's own CoreGraphics
and `screencapture`. Nothing is installed for it. It works only after the person has allowed the
program that runs it under Screen Recording and Accessibility, in System Settings.

Points are the screen's own coordinates, top left at (0, 0), in points, not pixels: a picture is
scaled to points, so that x and y of a picture are x and y of the mouse.
"""

from __future__ import annotations

import contextlib
import ctypes
import ctypes.util
import os
import re
import signal
import subprocess
import tempfile
from collections.abc import Sequence
from enum import IntEnum
from pathlib import Path
from typing import Literal, Protocol

Button = Literal["left", "right", "middle"]

# Event types, buttons and fields of CoreGraphics.
DOWN = {"left": 1, "right": 3, "middle": 25}
UP = {"left": 2, "right": 4, "middle": 26}
BUTTON = {"left": 0, "right": 1, "middle": 2}


class Code(IntEnum):
    """Fixed numbers of CoreGraphics: event types, a field, the event tap, the scroll unit."""

    MOVED = 5
    DRAGGED = 6
    CLICK_STATE = 1
    HID_TAP = 0
    LINE_UNITS = 1


FLAGS = {"cmd": 1 << 20, "shift": 1 << 17, "ctrl": 1 << 18, "alt": 1 << 19}
# The keys by name, as the rest of the code writes them (`bap_browser.keys`), and their key codes.
NAMED_CODES = {
    "Enter": 36,
    "Tab": 48,
    "Space": 49,
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
    "F1": 122,
    "F2": 120,
    "F3": 99,
    "F4": 118,
    "F5": 96,
    "F6": 97,
    "F7": 98,
    "F8": 100,
    "F9": 101,
    "F10": 109,
    "F11": 103,
    "F12": 111,
    "Shift": 56,
    "Control": 59,
    "Alt": 58,
    "Meta": 55,
}
# A US keyboard's keys by the character they type unshifted.
CHARACTER_CODES = {
    "a": 0, "s": 1, "d": 2, "f": 3, "h": 4, "g": 5, "z": 6, "x": 7, "c": 8, "v": 9, "b": 11,
    "q": 12, "w": 13, "e": 14, "r": 15, "y": 16, "t": 17, "1": 18, "2": 19, "3": 20, "4": 21,
    "6": 22, "5": 23, "=": 24, "9": 25, "7": 26, "-": 27, "8": 28, "0": 29, "]": 30, "o": 31,
    "u": 32, "[": 33, "i": 34, "p": 35, "l": 37, "j": 38, "'": 39, "k": 40, ";": 41, "\\": 42,
    ",": 43, "/": 44, "n": 45, "m": 46, ".": 47, "`": 50,
}  # fmt: skip
MODIFIERS = {"Control": "ctrl", "Shift": "shift", "Alt": "alt", "Meta": "cmd", "ControlOrMeta": "cmd"}
# Where each app begins in what `lsappinfo list` writes; its name is the first quoted word after.
APP_START = re.compile(r"^\s*\d+\) ", re.MULTILINE)
NAME = re.compile(r'^"([^"]+)"')
PID = re.compile(r"pid = (\d+)")
# The apps of computer use on a Mac, by their name in `computer.apps`.
MAC_APPS = {"text_editor": "TextEdit", "files": "Finder", "calculator": "Calculator", "terminal": "Terminal"}


def flags_of(held: Sequence[str]) -> int:
    """The flags of the modifiers held, by their names in `bap_browser.keys`. KeyError for another."""
    flags = 0
    for name in held:
        flags |= FLAGS[MODIFIERS[name]]
    return flags


def chord(keys: str) -> tuple[int, int]:
    """`Meta+s`, as `bap_browser.keys.normalise` gives it, as a key code and the flags held with it.
    Raises KeyError for a key this keyboard has no code for."""
    *held, key = ["+"] if keys == "+" else keys.replace("++", "+plus").split("+")
    key = "=" if key == "plus" else key
    code = NAMED_CODES.get(key, CHARACTER_CODES.get(key.lower()) if len(key) == 1 else None)
    if code is None:
        raise KeyError(key)
    return code, flags_of(held)


class Hands(Protocol):
    """What the helper does on the Mac. The real one is `MacHands`; a test gives a stand-in."""

    def screen(self) -> tuple[int, int]: ...

    def allowed(self) -> tuple[bool, bool]:
        """Whether Screen Recording and Accessibility are allowed for this program."""
        ...

    def ask_for_access(self) -> None:
        """Has macOS ask the person for what is not allowed yet. It also lists this program under
        Screen Recording and Accessibility, so that the person finds it there to switch on."""
        ...

    def pointer_at(self) -> tuple[float, float]: ...

    def picture(
        self, width: int, jpeg_quality: int | None, region: tuple[int, int, int, int] | None = None
    ) -> bytes:
        """The screen, or a region of it given as x, y, width and height in points, `width` pixels wide."""
        ...

    def click(self, x: float, y: float, button: Button, count: int, flags: int) -> None: ...

    def move(self, x: float, y: float) -> None: ...

    def press(self, x: float, y: float, button: Button, down: bool) -> None: ...

    def drag(self, start: tuple[float, float], end: tuple[float, float]) -> None: ...

    def type_text(self, text: str) -> None: ...

    def key(self, code: int, flags: int, down: bool | None) -> None:
        """A key pressed and let go, or, with `down`, only pressed or only let go."""
        ...

    def scroll(self, lines_x: int, lines_y: int) -> None: ...

    def open_app(self, name: str) -> None: ...

    def front(self) -> str:
        """The name of the app in front."""
        ...

    def running(self) -> dict[str, int]:
        """The apps a person can see running, by name, with their process ids."""
        ...

    def quit_app(self, pid: int) -> None:
        """Ends an app."""
        ...


class Point(ctypes.Structure):
    _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double)]


class Size(ctypes.Structure):
    _fields_ = [("width", ctypes.c_double), ("height", ctypes.c_double)]


class Rect(ctypes.Structure):
    _fields_ = [("origin", Point), ("size", Size)]


def _library(name: str) -> ctypes.CDLL:
    found = ctypes.util.find_library(name)
    return ctypes.cdll.LoadLibrary(found or f"/System/Library/Frameworks/{name}.framework/{name}")


class MacHands:
    def __init__(self) -> None:
        cg = self._cg = _library("CoreGraphics")
        self._cf = _library("CoreFoundation")
        self._ax = _library("ApplicationServices")
        pointer, event = ctypes.c_void_p, ctypes.c_void_p
        cg.CGMainDisplayID.restype = ctypes.c_uint32
        cg.CGDisplayBounds.restype = Rect
        cg.CGDisplayBounds.argtypes = [ctypes.c_uint32]
        cg.CGPreflightScreenCaptureAccess.restype = ctypes.c_bool
        cg.CGRequestScreenCaptureAccess.restype = ctypes.c_bool
        self._ax.AXIsProcessTrustedWithOptions.restype = ctypes.c_bool
        self._ax.AXIsProcessTrustedWithOptions.argtypes = [ctypes.c_void_p]
        self._cf.CFDictionaryCreate.restype = ctypes.c_void_p
        self._cf.CFDictionaryCreate.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.c_long,
            ctypes.c_void_p,
            ctypes.c_void_p,
        ]
        self._ax.AXIsProcessTrusted.restype = ctypes.c_bool
        cg.CGEventCreate.restype = event
        cg.CGEventCreate.argtypes = [pointer]
        cg.CGEventGetLocation.restype = Point
        cg.CGEventGetLocation.argtypes = [event]
        cg.CGEventCreateMouseEvent.restype = event
        cg.CGEventCreateMouseEvent.argtypes = [pointer, ctypes.c_uint32, Point, ctypes.c_uint32]
        cg.CGEventCreateKeyboardEvent.restype = event
        cg.CGEventCreateKeyboardEvent.argtypes = [pointer, ctypes.c_uint16, ctypes.c_bool]
        cg.CGEventKeyboardSetUnicodeString.argtypes = [event, ctypes.c_ulong, ctypes.POINTER(ctypes.c_uint16)]
        cg.CGEventSetFlags.argtypes = [event, ctypes.c_uint64]
        cg.CGEventSetIntegerValueField.argtypes = [event, ctypes.c_uint32, ctypes.c_int64]
        cg.CGEventCreateScrollWheelEvent2.restype = event
        cg.CGEventCreateScrollWheelEvent2.argtypes = [
            pointer,
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.c_int32,
            ctypes.c_int32,
            ctypes.c_int32,
        ]
        cg.CGEventPost.argtypes = [ctypes.c_uint32, event]
        self._cf.CFRelease.argtypes = [pointer]

    def _post(self, event: int | None) -> None:
        self._cg.CGEventPost(Code.HID_TAP, event)
        self._cf.CFRelease(event)

    def screen(self) -> tuple[int, int]:
        bounds = self._cg.CGDisplayBounds(self._cg.CGMainDisplayID())
        return int(bounds.size.width), int(bounds.size.height)

    def allowed(self) -> tuple[bool, bool]:
        return bool(self._cg.CGPreflightScreenCaptureAccess()), bool(self._ax.AXIsProcessTrusted())

    def ask_for_access(self) -> None:
        recording, accessibility = self.allowed()
        if not recording:
            self._cg.CGRequestScreenCaptureAccess()
        if not accessibility:
            self.trusted(prompt=True)

    def trusted(self, *, prompt: bool) -> bool:
        """Whether Accessibility is allowed. With `prompt`, macOS asks the person when it is not."""
        cf, ax = self._cf, self._ax
        key = ctypes.c_void_p.in_dll(ax, "kAXTrustedCheckOptionPrompt")
        value = ctypes.c_void_p.in_dll(cf, "kCFBooleanTrue" if prompt else "kCFBooleanFalse")
        keys, values = (ctypes.c_void_p * 1)(key.value), (ctypes.c_void_p * 1)(value.value)
        key_calls = ctypes.addressof(ctypes.c_char.in_dll(cf, "kCFTypeDictionaryKeyCallBacks"))
        value_calls = ctypes.addressof(ctypes.c_char.in_dll(cf, "kCFTypeDictionaryValueCallBacks"))
        options = cf.CFDictionaryCreate(None, keys, values, 1, key_calls, value_calls)
        try:
            return bool(ax.AXIsProcessTrustedWithOptions(options))
        finally:
            cf.CFRelease(options)

    def pointer_at(self) -> tuple[float, float]:
        event = self._cg.CGEventCreate(None)
        at = self._cg.CGEventGetLocation(event)
        self._cf.CFRelease(event)
        return at.x, at.y

    def picture(
        self, width: int, jpeg_quality: int | None, region: tuple[int, int, int, int] | None = None
    ) -> bytes:
        with tempfile.TemporaryDirectory() as folder:
            shot = Path(folder) / "screen.png"
            part = [f"-R{','.join(str(number) for number in region)}"] if region else []
            subprocess.run(["screencapture", "-x", "-m", *part, "-t", "png", str(shot)], check=True)
            # The picture is made as wide as the screen is in points, so that its pixels are points.
            out = Path(folder) / ("screen.jpg" if jpeg_quality else "screen.png")
            how = ["-s", "format", "jpeg", "-s", "formatOptions", str(jpeg_quality)] if jpeg_quality else []
            subprocess.run(
                ["sips", "--resampleWidth", str(width), *how, str(shot), "--out", str(out)],
                check=True,
                capture_output=True,
            )
            return out.read_bytes()

    def _mouse(self, kind: int, x: float, y: float, button: Button, count: int = 1, flags: int = 0) -> None:
        event = self._cg.CGEventCreateMouseEvent(None, kind, Point(x, y), BUTTON[button])
        self._cg.CGEventSetIntegerValueField(event, Code.CLICK_STATE, count)
        if flags:
            self._cg.CGEventSetFlags(event, flags)
        self._post(event)

    def click(self, x: float, y: float, button: Button, count: int, flags: int) -> None:
        self.move(x, y)
        for number in range(1, count + 1):
            self._mouse(DOWN[button], x, y, button, number, flags)
            self._mouse(UP[button], x, y, button, number, flags)

    def move(self, x: float, y: float) -> None:
        self._mouse(Code.MOVED, x, y, "left")

    def press(self, x: float, y: float, button: Button, down: bool) -> None:
        self._mouse((DOWN if down else UP)[button], x, y, button)

    def drag(self, start: tuple[float, float], end: tuple[float, float]) -> None:
        self._mouse(DOWN["left"], *start, "left")
        self._mouse(Code.DRAGGED, *end, "left")
        self._mouse(UP["left"], *end, "left")

    def type_text(self, text: str) -> None:
        for character in text:
            units = character.encode("utf-16-le")
            codes = (ctypes.c_uint16 * (len(units) // 2)).from_buffer_copy(units)
            for down in (True, False):
                event = self._cg.CGEventCreateKeyboardEvent(None, 0, down)
                self._cg.CGEventKeyboardSetUnicodeString(event, len(codes), codes)
                self._post(event)

    def key(self, code: int, flags: int, down: bool | None) -> None:
        for pressed in (True, False) if down is None else (down,):
            event = self._cg.CGEventCreateKeyboardEvent(None, code, pressed)
            if flags:
                self._cg.CGEventSetFlags(event, flags)
            self._post(event)

    def scroll(self, lines_x: int, lines_y: int) -> None:
        # CoreGraphics counts a wheel turned toward the person as negative.
        self._post(self._cg.CGEventCreateScrollWheelEvent2(None, Code.LINE_UNITS, 2, -lines_y, -lines_x, 0))

    def open_app(self, name: str) -> None:
        subprocess.run(["open", "-a", name], check=True, capture_output=True)

    def running(self) -> dict[str, int]:
        listed = subprocess.run(["lsappinfo", "list"], capture_output=True, text=True, check=False).stdout
        apps: dict[str, int] = {}
        for block in APP_START.split(listed)[1:]:
            name, pid = NAME.match(block), PID.search(block)
            if name and pid and 'type="Foreground"' in block:
                apps[name.group(1)] = int(pid.group(1))
        return apps

    def quit_app(self, pid: int) -> None:
        with contextlib.suppress(ProcessLookupError):
            os.kill(pid, signal.SIGTERM)

    def front(self) -> str:
        front = subprocess.run(["lsappinfo", "front"], capture_output=True, text=True, check=False)
        if front.returncode != 0 or not front.stdout.strip():
            return ""
        asked = subprocess.run(
            ["lsappinfo", "info", "-only", "name", front.stdout.strip()],
            capture_output=True,
            text=True,
            check=False,
        )
        return asked.stdout.split("=", 1)[-1].strip().strip('"') if asked.returncode == 0 else ""
