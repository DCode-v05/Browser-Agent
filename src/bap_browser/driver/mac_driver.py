"""The driver of computer use on a person's real Mac (spec 21.13), through the helper they run there.

Each action is asked of the helper over HTTP with its token. The helper decides what it allows: it
refuses everything once the person has pushed the pointer into the corner of the screen, and it opens
only the apps the person named when they started it.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import os
import urllib.error
import urllib.request
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
from bap_browser.driver.contained_desktop import App
from bap_browser.driver.desktop_driver import DesktopDriver
from bap_browser.driver.mac_hands import MAC_APPS
from bap_browser.errors import BadInput, BrowserError
from bap_browser.private_file import write_json
from bap_browser.results import Picture

# The file, in the data folder, where a helper on this Mac says where it is.
PAIRING = "helper.json"


class MacLink:
    """The way to the helper on the person's Mac. It stands where the desktop of a container would."""

    def __init__(self, url: str, token: str, timeout_s: float) -> None:
        self._url, self._token, self._timeout_s = url.rstrip("/"), token, timeout_s
        self._running = False

    @property
    def url(self) -> str:
        """Where the helper answers."""
        return self._url

    @property
    def alive(self) -> bool:
        return self._running

    @property
    def folder(self) -> Path | None:
        """No folder is shared: the agent works among the person's own files."""
        return None

    async def ask(self, method: str, path: str, body: dict[str, Any] | None = None) -> tuple[bytes, str]:
        """What the helper answered, and its kind. A refusal or a failure is a BrowserError."""

        def call() -> tuple[bytes, str]:
            request = urllib.request.Request(
                self._url + path,
                data=json.dumps(body).encode() if body is not None else None,
                headers={"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"},
                method=method,
            )
            with urllib.request.urlopen(request, timeout=self._timeout_s) as answer:
                return answer.read(), answer.headers.get("Content-Type", "")

        try:
            return await asyncio.to_thread(call)
        except urllib.error.HTTPError as refused:
            said = refused.read().decode(errors="replace")
            with contextlib.suppress(ValueError):
                said = json.loads(said).get("error", said)
            if refused.code == 401:
                said = "The helper did not take the token. Copy the token it printed into BAP_BROWSER_HELPER_TOKEN."
            raise BrowserError(
                said or f"The helper answered {refused.code}.", reason="the helper refused"
            ) from None
        except OSError as lost:
            self._running = False
            raise BrowserError(
                f"The helper on the Mac does not answer at {self._url}: {lost}. Start it there with "
                "`bap-browser helper`.",
                reason="the helper does not answer",
            ) from None

    async def status(self) -> dict[str, Any]:
        return json.loads((await self.ask("GET", "/status"))[0])

    async def act(self, **asked: Any) -> None:
        await self.ask("POST", "/act", asked)

    async def start(self) -> None:
        if not self._token:
            raise BrowserError(
                "No helper is paired. Start the helper on this Mac with `uv run bap-browser helper "
                "--allow text_editor,files,calculator`, or give the token of one elsewhere in "
                "BAP_BROWSER_HELPER_TOKEN.",
                reason="no token for the helper",
            )
        told = await self.status()
        missing = [
            name
            for name, given in (
                ("Screen Recording", told["screen_recording"]),
                ("Accessibility", told["accessibility"]),
            )
            if not given
        ]
        if missing:
            raise BrowserError(
                f"The Mac has not allowed the helper {' and '.join(missing)}. The person allows it in System "
                "Settings, Privacy & Security, for the program that runs the helper.",
                reason="the Mac has not allowed it",
            )
        if told["stopped"]:
            raise BrowserError(
                "The person stopped the helper. Start it again on the Mac.", reason="the helper is stopped"
            )
        self._running = True

    async def close(self) -> None:
        self._running = False

    async def run(self, *command: str, stdin: bytes | None = None) -> bytes:
        raise BrowserError("Commands are not run on a person's Mac.", reason="not on a Mac")

    async def start_app(self, app: App) -> None:
        await self.act(do="open", app=app.id)

    async def send(self, line: str) -> None:
        """A person's hand on a Mac goes through the driver's own pointer, key and wheel."""


def pairing_file(config: Config) -> Path:
    """Where the helper on this Mac leaves its address and token, for this user alone (spec 21.13)."""
    return Path(config.data_dir).expanduser() / PAIRING


def write_pairing(path: Path, url: str, token: str) -> None:
    write_json(path, {"url": url, "token": token})


def read_pairing(path: Path) -> tuple[str, str] | None:
    """The address and the token the helper left. None when no helper is running here."""
    try:
        told = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if (
        not isinstance(told, dict)
        or not isinstance(told.get("url"), str)
        or not isinstance(told.get("token"), str)
    ):
        return None
    return told["url"], told["token"]


class MacDriver(DesktopDriver):
    def __init__(self, config: Config, name: str = "computer") -> None:
        super().__init__(config, name)
        settings = config.computer
        url, token = settings.helper_url, os.environ.get(settings.helper_token_env, "")
        # A helper on this same Mac pairs by itself: nothing is copied by hand.
        paired = read_pairing(pairing_file(config)) if not token else None
        if paired is not None:
            url, token = paired
        self.link = MacLink(url, token, settings.command_timeout_s)
        self.desktop = self.link
        self._screen = (settings.screen_width, settings.screen_height)

    async def start(self) -> None:
        await self.link.start()
        width, height = (await self.link.status())["screen"]
        self._screen = (int(width), int(height))

    def description(self) -> str:
        return f"The person's Mac, {self._screen[0]} by {self._screen[1]}"

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
        waited, pause = 0.0, self._settings.app_poll_ms / 1000
        while waited < self._settings.app_open_wait_s:
            if (await self.link.status()).get("front") == MAC_APPS[app.id]:
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
            await self.link.act(do="key", keys="Meta+a")
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
                await self.link.act(do="move", x=x, y=y)
            else:
                await self.link.act(do="press", x=x, y=y, button=button, down=action == "down")

    async def key(self, action: KeyAction, key: str) -> None:
        with contextlib.suppress(BrowserError):
            await self.link.act(do="key", keys=key, down=action == "down")

    async def wheel(self, x: float, y: float, dx: float, dy: float) -> None:
        with contextlib.suppress(BrowserError):
            line = self._settings.wheel_pixels_per_line
            await self.link.act(do="scroll", x=x, y=y, lines_x=int(dx // line), lines_y=int(dy // line))


def desktop_driver_for(config: Config, name: str = "computer") -> DesktopDriver:
    """The driver of the desktop the configuration names: a container's, this machine's, or a Mac's."""
    return MacDriver(config, name) if config.computer.runs == "mac" else DesktopDriver(config, name)
