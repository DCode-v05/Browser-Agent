"""The desktop of computer use on this machine's own virtual screen (spec 21.3), for a machine that is
itself the boundary: the micro VM. The engine starts the screen and the window manager, and runs each
command beside them. Nothing an agent wrote goes into a command line, as in the container.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import shutil
from pathlib import Path

from bap_browser.config_computer import Computer
from bap_browser.driver.contained_desktop import App, allowed_apps
from bap_browser.errors import BrowserError

BACKGROUND = "#3a5a78"
NEEDED = ("Xvfb", "openbox", "xdotool", "import", "xdpyinfo")


class ScreenHere:
    def __init__(self, settings: Computer) -> None:
        self._settings = settings
        self._folder = Path(settings.folder).expanduser().resolve()
        self._env = {**os.environ, "DISPLAY": settings.display}
        self._running = False
        self._kept: list[asyncio.subprocess.Process] = []
        self._channel: asyncio.subprocess.Process | None = None

    @property
    def alive(self) -> bool:
        return self._running

    @property
    def folder(self) -> Path | None:
        return self._folder if self._settings.share_folder else None

    async def start(self) -> None:
        missing = [program for program in NEEDED if shutil.which(program) is None]
        if missing:
            raise BrowserError(
                f"This machine has no {', '.join(missing)}: computer use here needs a virtual screen. "
                "Build the micro VM's image with DESKTOP=true.",
                reason="no virtual screen here",
            )
        settings = self._settings
        if settings.share_folder:
            self._folder.mkdir(parents=True, exist_ok=True)
        screen = f"{settings.screen_width}x{settings.screen_height}x24"
        self._running = True
        await self._keep("Xvfb", settings.display, "-screen", "0", screen, "-nolisten", "tcp")
        waited, pause = 0.0, settings.app_poll_ms / 1000
        while (await self._call("xdpyinfo"))[0] != 0:
            waited += pause
            if waited > settings.start_wait_s:
                await self.close()
                raise BrowserError(
                    "The virtual screen did not come up in time.", reason="the desktop did not start"
                )
            await asyncio.sleep(pause)
        await self._keep("openbox")
        # The window manager paints the background when it starts: the colour is set after it.
        await asyncio.sleep(settings.settle_ms / 1000)
        await self._call("xsetroot", "-solid", BACKGROUND)

    async def close(self) -> None:
        self._running = False
        kept, self._kept = self._kept, []
        if self._channel is not None:
            kept.append(self._channel)
            self._channel = None
        for process in reversed(kept):
            if process.returncode is None:
                with contextlib.suppress(ProcessLookupError):
                    process.terminate()
                await process.wait()

    async def run(self, *command: str, stdin: bytes | None = None) -> bytes:
        if not self._running:
            raise BrowserError("The desktop is not running.", reason="the desktop closed")
        code, out, said = await self._call(*command, stdin=stdin)
        if code != 0:
            lines = [line.strip() for line in said.splitlines() if line.strip()]
            raise BrowserError(
                f"The desktop could not do that: {lines[-1] if lines else command[0] + ' failed'}",
                reason="the desktop could not do it",
            )
        return out

    async def start_app(self, app: App) -> None:
        if not self._running:
            raise BrowserError("The desktop is not running.", reason="the desktop closed")
        # An app a person has not allowed is not started, and an app this machine lacks cannot be.
        if app not in allowed_apps(self._settings) or shutil.which(app.command) is None:
            raise BrowserError(f"{app.name} is not on this desktop.", reason="the app is not here")
        await self._keep(app.command)

    async def send(self, line: str) -> None:
        if not self._running:
            return
        channel = self._channel
        if channel is None or channel.returncode is not None:
            channel = self._channel = await asyncio.create_subprocess_exec(
                "xdotool",
                "-",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
                env=self._env,
            )
        assert channel.stdin is not None
        try:
            channel.stdin.write(line.encode() + b"\n")
            await channel.stdin.drain()
        except (BrokenPipeError, ConnectionResetError):
            self._channel = None

    async def _keep(self, *command: str) -> None:
        """Starts a program that stays: the screen, the window manager, an app."""
        self._kept.append(
            await asyncio.create_subprocess_exec(
                *command,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
                env=self._env,
                cwd=Path.home(),
            )
        )

    async def _call(self, *command: str, stdin: bytes | None = None) -> tuple[int, bytes, str]:
        process = await asyncio.create_subprocess_exec(
            *command,
            stdin=asyncio.subprocess.PIPE if stdin is not None else asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=self._env,
        )
        try:
            out, err = await asyncio.wait_for(process.communicate(stdin), self._settings.command_timeout_s)
        except TimeoutError:
            process.kill()
            await process.wait()
            return 1, b"", "it took too long"
        return process.returncode or 0, out, err.decode(errors="replace")
