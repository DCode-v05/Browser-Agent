"""The driver of computer use on a person's real machine (spec 21.13, 21.14: a Mac or a PC), through
the helper they run there.

Each action is asked of the helper over HTTP with its token. The helper decides what it allows: it
refuses everything once the person has pushed the pointer into the corner of the screen, and it opens
only the apps the person named when they started it.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import os
import shlex
import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from bap_browser.config import Config, QualityLevel
from bap_browser.driver.base import (
    ActionOutcome,
    Dragged,
    KeyAction,
    MouseButton,
    Place,
    PointerAction,
    Shot,
)
from bap_browser.driver.contained_desktop import App, allowed_apps
from bap_browser.driver.desktop_driver import DesktopDriver
from bap_browser.driver.helper_link import HelperLink, pairing_file, read_pairing, write_pairing
from bap_browser.driver.mac_hands import MAC_APPS
from bap_browser.driver.windows_hands import WINDOWS_APPS
from bap_browser.errors import BadInput, BrowserError
from bap_browser.results import Picture

__all__ = [
    "MacDriver",
    "WindowsDriver",
    "desktop_driver_for",
    "pairing_file",
    "read_pairing",
    "start_helper_in_terminal",
    "write_pairing",
]

# The script, in the data folder, that Terminal runs to start the helper.
START_SCRIPT = "start-helper.command"


def start_helper_in_terminal(
    config: Config, folder: Path, run: Callable[[list[str]], Any] = subprocess.run
) -> Path:
    """Starts the helper on this Mac in a Terminal window of its own, from the project's `folder`,
    with the apps the admin allows. Terminal is then the program macOS asks the person to allow, and
    the person sees the helper and ends it there with Ctrl+C."""
    apps = [app.id for app in allowed_apps(config.computer)]
    if config.computer.helper_any_app:
        apps.append("any")
    if not apps:
        raise BrowserError(
            "Allow at least one app on the Computer tab's Configuration first.", reason="no app is allowed"
        )
    script = Path(config.data_dir).expanduser().resolve() / START_SCRIPT
    script.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "#!/bin/sh",
        f"cd {shlex.quote(str(folder))} || exit 1",
        f"exec uv run bap-browser helper --allow {','.join(apps)}",
    ]
    handle = os.open(script, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o700)
    with os.fdopen(handle, "w", encoding="utf-8") as file:
        file.write("\n".join(lines) + "\n")
    os.chmod(script, 0o700)
    run(["open", "-a", "Terminal", str(script)])
    return script


class HelperDriver(DesktopDriver):
    """A real machine reached through its own helper (spec 21.13, 21.14): `MacDriver` and
    `WindowsDriver` are this with that machine's own apps and the name it is called by."""

    apps_by_name: dict[str, str]
    machine: str

    def __init__(self, config: Config, name: str = "computer") -> None:
        super().__init__(config, name)
        settings = config.computer
        url, token = settings.helper_url, os.environ.get(settings.helper_token_env, "")
        # A helper on this same machine pairs by itself: nothing is copied by hand.
        paired = read_pairing(pairing_file(config)) if not token else None
        if paired is not None:
            url, token = paired
        self.link = HelperLink(url, token, settings.command_timeout_s, machine=self.machine)
        self.desktop = self.link
        self._screen = (settings.screen_width, settings.screen_height)

    async def start(self) -> None:
        await self.link.start()
        width, height = (await self.link.status())["screen"]
        self._screen = (int(width), int(height))

    def description(self) -> str:
        return f"The person's {self.machine}, {self._screen[0]} by {self._screen[1]}"

    async def viewport(self) -> tuple[int, int]:
        return self._screen

    def _on_screen(self, x: float, y: float) -> tuple[str, str]:
        width, height = self._screen
        if not (0 <= x < width and 0 <= y < height):
            raise BadInput(
                f"({x:g}, {y:g}) is outside the screen, which is {width} by {height} points.",
                reason="the point is outside the screen",
            )
        return str(int(x)), str(int(y))

    async def windows(self) -> list[str]:
        front = (await self.link.status()).get("front", "")
        return [f"{front} (in front)"] if front else []

    async def open_app(self, app: App) -> bool:
        await self.link.start_app(app)
        return await self._in_front(self.apps_by_name[app.id])

    async def open_named_app(self, name: str) -> bool:
        await self.link.act(do="open", name=name)
        return await self._in_front(name)

    async def _in_front(self, name: str) -> bool:
        """Whether the app comes to the front within the wait for an app."""
        waited, pause = 0.0, self._settings.app_poll_ms / 1000
        while waited < self._settings.app_open_wait_s:
            if (await self.link.status()).get("front") == name:
                return True
            await asyncio.sleep(pause)
            waited += pause
        return False

    async def _picture(self, *how: str) -> bytes:
        query = "&".join(how)
        return (await self.link.ask("GET", f"/picture?{query}"))[0]

    async def change_mark(self) -> str | None:
        try:
            small = await self._picture(f"width={self._settings.mark_width}")
        except BrowserError:
            return None
        return hashlib.sha256(small).hexdigest()

    async def screenshot(self, *, full_page: bool, annotate: bool) -> Shot:
        width, height = self._screen
        return Shot(Picture(await self._picture(f"width={width}"), "image/png"), width, height)

    async def zoom(self, region: tuple[float, float, float, float]) -> Shot:
        width, height = self._screen
        x, y = max(0, int(region[0])), max(0, int(region[1]))
        w, h = min(int(region[2]), width) - x, min(int(region[3]), height) - y
        if w <= 0 or h <= 0:
            raise BadInput(
                f"The region is outside the screen, which is {width} by {height} points.",
                reason="the region is outside the screen",
            )
        data = await self._picture(f"width={w * 2}", f"region={x},{y},{w},{h}")
        return Shot(Picture(data, "image/png"), w * 2, h * 2, scaled=True)

    async def click_at(
        self, x: float, y: float, *, button: MouseButton, click_count: int, modifiers: Sequence[str]
    ) -> ActionOutcome:
        at = self._on_screen(x, y)
        await self.link.act(do="click", x=x, y=y, button=button, count=click_count, held=list(modifiers))
        await self._settle()
        return ActionOutcome(f"the screen at ({at[0]}, {at[1]})")

    async def hover_at(self, x: float, y: float) -> ActionOutcome:
        at = self._on_screen(x, y)
        await self.link.act(do="move", x=x, y=y)
        await self._settle()
        return ActionOutcome(f"the screen at ({at[0]}, {at[1]})")

    async def type_text(
        self, ref: str | None, text: str, *, clear: bool, submit: bool, slowly: bool
    ) -> ActionOutcome:
        if ref is not None:
            self._no_page()
        if clear:
            await self.link.act(do="key", keys="ControlOrMeta+a")
            await self.link.act(do="key", keys="Backspace")
        await self.link.act(do="type", text=text)
        if submit:
            await self._settle()
            await self.link.act(do="key", keys="Enter")
        await self._settle()
        return ActionOutcome("")

    async def press_key(self, keys: str, *, repeat: int, ref: str | None) -> ActionOutcome:
        if ref is not None:
            self._no_page()
        await self.link.act(do="key", keys=keys, repeat=repeat)
        await self._settle()
        return ActionOutcome("")

    async def turn_wheel(self, direction: str, steps: int, at: tuple[float, float] | None) -> None:
        lines = steps * self._settings.scroll_notches_per_step
        lines_x = {"left": -lines, "right": lines}.get(direction, 0)
        lines_y = {"up": -lines, "down": lines}.get(direction, 0)
        where = {"x": at[0], "y": at[1]} if at is not None else {}
        if at is not None:
            self._on_screen(*at)
        await self.link.act(do="scroll", lines_x=lines_x, lines_y=lines_y, **where)
        await self._settle()

    async def drag(self, start: Place, end: Place) -> Dragged:
        if isinstance(start, str) or isinstance(end, str):
            self._no_page()
        begin, finish = self._on_screen(*start), self._on_screen(*end)
        await self.link.act(do="drag", **{"from": list(start), "to": list(end)})
        await self._settle()
        return Dragged(f"({begin[0]}, {begin[1]})", f"({finish[0]}, {finish[1]})")

    async def _send_frames(self, on_frame: Callable[[bytes], None], level: QualityLevel) -> None:
        width = min(level.max_width, self._screen[0])
        quality = min(level.jpeg_quality, self._settings.frame_jpeg_quality)
        pause = max(self._settings.frame_ms / 1000, 1 / level.max_fps)
        last = b""
        while self.link.alive:
            try:
                frame = await self._picture(f"width={width}", f"quality={quality}")
            except BrowserError:
                await asyncio.sleep(pause)
                continue
            if frame != last:
                last = frame
                on_frame(frame)
            await asyncio.sleep(pause)

    async def pointer(self, action: PointerAction, x: float, y: float, button: MouseButton) -> None:
        with contextlib.suppress(BrowserError):
            if action == "move":
                await self.link.act(do="move", x=x, y=y, by="person")
            else:
                await self.link.act(do="press", x=x, y=y, button=button, down=action == "down", by="person")

    async def key(self, action: KeyAction, key: str) -> None:
        with contextlib.suppress(BrowserError):
            await self.link.act(do="key", keys=key, down=action == "down", by="person")

    async def wheel(self, x: float, y: float, dx: float, dy: float) -> None:
        with contextlib.suppress(BrowserError):
            line = self._settings.wheel_pixels_per_line
            await self.link.act(
                do="scroll", x=x, y=y, lines_x=int(dx // line), lines_y=int(dy // line), by="person"
            )


class MacDriver(HelperDriver):
    apps_by_name = MAC_APPS
    machine = "Mac"


class WindowsDriver(HelperDriver):
    apps_by_name = WINDOWS_APPS
    machine = "PC"


def desktop_driver_for(config: Config, name: str = "computer") -> DesktopDriver:
    """The driver of the desktop the configuration names: a container's, this machine's, a Mac's or
    a PC's."""
    if config.computer.runs == "mac":
        return MacDriver(config, name)
    if config.computer.runs == "windows":
        return WindowsDriver(config, name)
    return DesktopDriver(config, name)
