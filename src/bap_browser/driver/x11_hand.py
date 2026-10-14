"""A person's hand on a Linux desktop's X screen, through the helper there (spec 22.6.2): what they
do on the engine's picture is given to the screen as xdotool's commands, as a person's hand on the
contained desktop is."""

from __future__ import annotations

import subprocess
from typing import IO, Protocol

from bap_browser.driver.base import KeyAction, MouseButton, PointerAction
from bap_browser.driver.desktop_driver import (
    BUTTON_NUMBER,
    WHEEL_DOWN,
    WHEEL_LEFT,
    WHEEL_RIGHT,
    WHEEL_UP,
    key_name,
)


class Screen(Protocol):
    def size(self) -> tuple[float, float]: ...

    def send(self, line: str) -> None: ...


class X11Hand:
    """What a person does, turned into the lines xdotool reads."""

    def __init__(self, screen: Screen) -> None:
        self._screen = screen

    def pointer(self, action: PointerAction, x: float, y: float, button: MouseButton) -> None:
        line = f"mousemove {int(x)} {int(y)}"
        if action != "move":
            line += f" mouse{action} {BUTTON_NUMBER[button]}"
        self._screen.send(line)

    def key(self, action: KeyAction, key: str) -> None:
        named = key_name(key)
        if named is not None:
            self._screen.send(f"key{action} {named}")

    def wheel(self, dx: float, dy: float) -> None:
        moved, button = (dy, WHEEL_DOWN if dy > 0 else WHEEL_UP)
        if abs(dx) > abs(dy):
            moved, button = (dx, WHEEL_RIGHT if dx > 0 else WHEEL_LEFT)
        if moved:
            self._screen.send(f"click {button}")


class XScreen:
    """The X screen this program's DISPLAY names, driven by one standing xdotool, which reads its
    commands a line at a time: a person's hand must not wait for a program to start each time."""

    def __init__(self) -> None:
        self._channel: subprocess.Popen[str] | None = None

    def size(self) -> tuple[float, float]:
        said = subprocess.run(
            ["xdotool", "getdisplaygeometry"], capture_output=True, text=True, check=True
        ).stdout
        wide, high = said.split()
        return float(wide), float(high)

    def send(self, line: str) -> None:
        channel = self._channel
        if channel is None or channel.poll() is not None:
            channel = self._channel = subprocess.Popen(
                ["xdotool", "-"],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
            )
        given: IO[str] | None = channel.stdin
        if given is not None:
            given.write(line + "\n")
            given.flush()
