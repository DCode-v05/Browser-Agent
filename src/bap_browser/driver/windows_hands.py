"""The mouse, the keyboard and the screen of a real Windows PC (spec 21.14), through Windows's own
`user32.dll` and `gdi32.dll`. Nothing is installed for that; resizing and encoding a picture, which
macOS's `sips` does for the Mac helper, uses Pillow, since Windows has no built-in tool for it.

Points are the screen's own pixels, top left at (0, 0): there is no separate notion of points and
pixels on Windows, unlike a Mac's screen.
"""

from __future__ import annotations

import ctypes
import io
import subprocess
from collections.abc import Sequence
from enum import IntEnum
from typing import Literal

from PIL import Image

from bap_browser.keys import resolve_chord, resolve_flags

Button = Literal["left", "right", "middle"]

user32 = ctypes.windll.user32  # type: ignore[attr-defined]
gdi32 = ctypes.windll.gdi32  # type: ignore[attr-defined]


class Code(IntEnum):
    """Fixed numbers of the Windows API: mouse event flags, key event flags, the wheel's own unit."""

    MOUSEEVENTF_MOVE = 0x0001
    MOUSEEVENTF_ABSOLUTE = 0x8000
    MOUSEEVENTF_WHEEL = 0x0800
    MOUSEEVENTF_HWHEEL = 0x01000
    KEYEVENTF_KEYUP = 0x0002
    KEYEVENTF_UNICODE = 0x0004
    INPUT_MOUSE = 0
    INPUT_KEYBOARD = 1
    SM_CXSCREEN = 0
    SM_CYSCREEN = 1
    WHEEL_DELTA = 120


DOWN_FLAG = {"left": 0x0002, "right": 0x0008, "middle": 0x0020}
UP_FLAG = {"left": 0x0004, "right": 0x0010, "middle": 0x0040}
# Modifiers held before a key, as the bits of `flags_of`'s own result: this machine's, not another's.
FLAGS = {"ctrl": 1, "shift": 2, "alt": 4, "win": 8}
VK_MODIFIER = {"ctrl": 0x11, "shift": 0x10, "alt": 0x12, "win": 0x5B}
# The keys by name, as the rest of the code writes them (`bap_browser.keys`), and their virtual-key codes.
NAMED_CODES = {
    "Enter": 0x0D,
    "Tab": 0x09,
    "Space": 0x20,
    " ": 0x20,
    "Backspace": 0x08,
    "Escape": 0x1B,
    "Delete": 0x2E,
    "Home": 0x24,
    "End": 0x23,
    "PageUp": 0x21,
    "PageDown": 0x22,
    "ArrowLeft": 0x25,
    "ArrowRight": 0x27,
    "ArrowDown": 0x28,
    "ArrowUp": 0x26,
    "F1": 0x70,
    "F2": 0x71,
    "F3": 0x72,
    "F4": 0x73,
    "F5": 0x74,
    "F6": 0x75,
    "F7": 0x76,
    "F8": 0x77,
    "F9": 0x78,
    "F10": 0x79,
    "F11": 0x7A,
    "F12": 0x7B,
    "Shift": 0x10,
    "Control": 0x11,
    "Alt": 0x12,
    "Meta": 0x5B,
}
# A US keyboard's keys by the character they type unshifted. Letters and digits are their own ASCII
# codes on Windows; the rest are the OEM virtual-key codes of a US layout.
CHARACTER_CODES = {
    **{chr(ch): ch for ch in range(0x30, 0x3A)},  # '0'-'9'
    **{chr(ch): ch - 0x20 for ch in range(0x61, 0x7B)},  # 'a'-'z', by the letter's own VK code
    ";": 0xBA, "=": 0xBB, ",": 0xBC, "-": 0xBD, ".": 0xBE, "/": 0xBF,
    "`": 0xC0, "[": 0xDB, "\\": 0xDC, "]": 0xDD, "'": 0xDE,
}  # fmt: skip
MODIFIERS = {"Control": "ctrl", "Shift": "shift", "Alt": "alt", "Meta": "win", "ControlOrMeta": "ctrl"}
# The apps of computer use on a Windows PC, by their name in `computer.apps`.
WINDOWS_APPS = {
    "text_editor": "Notepad",
    "files": "File Explorer",
    "calculator": "Calculator",
    "terminal": "Terminal",
}
_OPEN_COMMAND = {
    "Notepad": "notepad.exe",
    "File Explorer": "explorer.exe",
    "Calculator": "calc.exe",
    "Terminal": "wt.exe",
}


def flags_of(held: Sequence[str]) -> int:
    """The flags of the modifiers held, by their names in `bap_browser.keys`. KeyError for another."""
    return resolve_flags(held, FLAGS, MODIFIERS)


def chord(keys: str) -> tuple[int, int]:
    """`Control+s`, as `bap_browser.keys.normalise` gives it, as a key code and the flags held with
    it. Raises KeyError for a key this keyboard has no code for."""
    held, code = resolve_chord(keys, NAMED_CODES, CHARACTER_CODES)
    return code, flags_of(held)


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_uint32),
        ("dwFlags", ctypes.c_uint32),
        ("time", ctypes.c_uint32),
        ("dwExtraInfo", ctypes.c_void_p),
    ]


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_uint16),
        ("wScan", ctypes.c_uint16),
        ("dwFlags", ctypes.c_uint32),
        ("time", ctypes.c_uint32),
        ("dwExtraInfo", ctypes.c_void_p),
    ]


class _INPUT_UNION(ctypes.Union):
    _fields_ = [("mi", _MOUSEINPUT), ("ki", _KEYBDINPUT)]


class _INPUT(ctypes.Structure):
    _fields_ = [("type", ctypes.c_uint32), ("union", _INPUT_UNION)]


class _POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class _BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", ctypes.c_uint32),
        ("biWidth", ctypes.c_long),
        ("biHeight", ctypes.c_long),
        ("biPlanes", ctypes.c_uint16),
        ("biBitCount", ctypes.c_uint16),
        ("biCompression", ctypes.c_uint32),
        ("biSizeImage", ctypes.c_uint32),
        ("biXPelsPerMeter", ctypes.c_long),
        ("biYPelsPerMeter", ctypes.c_long),
        ("biClrUsed", ctypes.c_uint32),
        ("biClrImportant", ctypes.c_uint32),
    ]


class _BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", _BITMAPINFOHEADER), ("bmiColors", ctypes.c_uint32 * 3)]


def _send(*inputs: _INPUT) -> None:
    array = (_INPUT * len(inputs))(*inputs)
    user32.SendInput(len(inputs), array, ctypes.sizeof(_INPUT))


def _mouse_input(flags: int, dx: int = 0, dy: int = 0, data: int = 0) -> _INPUT:
    given = _INPUT(type=Code.INPUT_MOUSE, union=_INPUT_UNION(mi=_MOUSEINPUT(dx, dy, data, flags, 0, None)))
    return given


def _key_input(vk: int, *, up: bool) -> _INPUT:
    flags = Code.KEYEVENTF_KEYUP if up else 0
    return _INPUT(type=Code.INPUT_KEYBOARD, union=_INPUT_UNION(ki=_KEYBDINPUT(vk, 0, flags, 0, None)))


def _unicode_input(unit: int, *, up: bool) -> _INPUT:
    flags = Code.KEYEVENTF_UNICODE | (Code.KEYEVENTF_KEYUP if up else 0)
    return _INPUT(type=Code.INPUT_KEYBOARD, union=_INPUT_UNION(ki=_KEYBDINPUT(0, unit, flags, 0, None)))


class WindowsHands:
    """Structurally the same `Hands` protocol `bap_browser.driver.mac_hands` defines: nothing here
    imports it, since a Windows helper never needs a Mac's own code, but every method below answers
    what that protocol asks."""

    def screen(self) -> tuple[int, int]:
        return user32.GetSystemMetrics(Code.SM_CXSCREEN), user32.GetSystemMetrics(Code.SM_CYSCREEN)

    def allowed(self) -> tuple[bool, bool]:
        # Windows has no Screen Recording or Accessibility gate to ask for (spec 21.14): a program
        # already sees its own user's screen and sends it input.
        return True, True

    def ask_for_access(self) -> None:
        """Nothing to ask: see `allowed`."""

    def pointer_at(self) -> tuple[float, float]:
        at = _POINT()
        user32.GetCursorPos(ctypes.byref(at))
        return float(at.x), float(at.y)

    def picture(
        self, width: int, jpeg_quality: int | None, region: tuple[int, int, int, int] | None = None
    ) -> bytes:
        screen_width, screen_height = self.screen()
        x, y, w, h = region or (0, 0, screen_width, screen_height)
        screen_dc = user32.GetDC(0)
        memory_dc = gdi32.CreateCompatibleDC(screen_dc)
        bitmap = gdi32.CreateCompatibleBitmap(screen_dc, w, h)
        chosen = gdi32.SelectObject(memory_dc, bitmap)
        gdi32.BitBlt(memory_dc, 0, 0, w, h, screen_dc, x, y, 0x00CC0020)  # SRCCOPY
        info = _BITMAPINFO()
        info.bmiHeader.biSize = ctypes.sizeof(_BITMAPINFOHEADER)
        info.bmiHeader.biWidth, info.bmiHeader.biHeight = w, -h  # top-down
        info.bmiHeader.biPlanes, info.bmiHeader.biBitCount, info.bmiHeader.biCompression = 1, 32, 0
        buffer = ctypes.create_string_buffer(w * h * 4)
        gdi32.GetDIBits(memory_dc, bitmap, 0, h, buffer, ctypes.byref(info), 0)  # DIB_RGB_COLORS
        gdi32.SelectObject(memory_dc, chosen)
        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(memory_dc)
        user32.ReleaseDC(0, screen_dc)
        image = Image.frombuffer("RGBA", (w, h), buffer.raw, "raw", "BGRA", 0, 1).convert("RGB")
        if width != w:
            image = image.resize((width, max(1, round(h * width / w))))
        out = io.BytesIO()
        image.save(out, format="JPEG" if jpeg_quality else "PNG", quality=jpeg_quality or 95)
        return out.getvalue()

    def _held(self, flags: int) -> list[int]:
        return [vk for name, bit in FLAGS.items() if flags & bit for vk in (VK_MODIFIER[name],)]

    def click(self, x: float, y: float, button: Button, count: int, flags: int) -> None:
        self.move(x, y)
        held = self._held(flags)
        _send(*(_key_input(vk, up=False) for vk in held))
        for _ in range(count):
            _send(_mouse_input(DOWN_FLAG[button]))
            _send(_mouse_input(UP_FLAG[button]))
        _send(*(_key_input(vk, up=True) for vk in reversed(held)))

    def move(self, x: float, y: float) -> None:
        width, height = self.screen()
        norm_x, norm_y = round(x * 65535 / max(1, width - 1)), round(y * 65535 / max(1, height - 1))
        _send(_mouse_input(Code.MOUSEEVENTF_MOVE | Code.MOUSEEVENTF_ABSOLUTE, norm_x, norm_y))

    def press(self, x: float, y: float, button: Button, down: bool) -> None:
        self.move(x, y)
        _send(_mouse_input(DOWN_FLAG[button] if down else UP_FLAG[button]))

    def drag(self, start: tuple[float, float], end: tuple[float, float]) -> None:
        self.move(*start)
        _send(_mouse_input(DOWN_FLAG["left"]))
        self.move(*end)
        _send(_mouse_input(UP_FLAG["left"]))

    def type_text(self, text: str) -> None:
        for character in text:
            units = character.encode("utf-16-le")
            for offset in range(0, len(units), 2):
                unit = int.from_bytes(units[offset : offset + 2], "little")
                _send(_unicode_input(unit, up=False))
                _send(_unicode_input(unit, up=True))

    def key(self, code: int, flags: int, down: bool | None) -> None:
        held = self._held(flags)
        if down is None:
            _send(*(_key_input(vk, up=False) for vk in held), _key_input(code, up=False))
            _send(_key_input(code, up=True), *(_key_input(vk, up=True) for vk in reversed(held)))
        else:
            _send(*(_key_input(vk, up=not down) for vk in held), _key_input(code, up=not down))

    def scroll(self, lines_x: int, lines_y: int) -> None:
        # Windows counts a wheel rotated away from the person (a scroll up) as positive, the same
        # shape as CoreGraphics counting a wheel turned toward the person as negative.
        if lines_y:
            _send(_mouse_input(Code.MOUSEEVENTF_WHEEL, data=int(-lines_y * Code.WHEEL_DELTA) & 0xFFFFFFFF))
        if lines_x:
            _send(_mouse_input(Code.MOUSEEVENTF_HWHEEL, data=int(lines_x * Code.WHEEL_DELTA) & 0xFFFFFFFF))

    def open_app(self, name: str) -> None:
        command = _OPEN_COMMAND.get(name, name)
        subprocess.Popen([command])

    def running(self) -> dict[str, int]:
        found: dict[str, int] = {}

        @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        def each(hwnd: int, _: int) -> bool:
            if not user32.IsWindowVisible(hwnd) or user32.GetWindowTextLengthW(hwnd) == 0:
                return True
            buffer = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(hwnd, buffer, 256)
            pid = ctypes.c_uint32()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            found[buffer.value] = pid.value
            return True

        user32.EnumWindows(each, 0)
        return found

    def quit_app(self, pid: int) -> None:
        handle = ctypes.windll.kernel32.OpenProcess(0x0001, False, pid)  # PROCESS_TERMINATE
        if handle:
            ctypes.windll.kernel32.TerminateProcess(handle, 0)
            ctypes.windll.kernel32.CloseHandle(handle)

    def front(self) -> str:
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return ""
        buffer = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(hwnd, buffer, 256)
        return buffer.value
