"""The contained desktop of computer use (spec 21.3): a small Linux desktop with a virtual screen,
in a container of its own. It is driven from outside with the tools a person would use: the mouse,
the keyboard and a look at the screen.

Nothing is ever put into a command line that an agent or a page wrote: positions are numbers, keys
are names from a table, and typed text goes in on the standard input of the command that types it.
"""

from __future__ import annotations

import asyncio
import hashlib
import shutil
from dataclasses import dataclass
from pathlib import Path

from bap_browser.config_computer import Computer
from bap_browser.errors import BrowserError

# Where the shared folder is inside the desktop.
FILES_INSIDE = "/home/agent/Files"
GONE = ("No such container", "is not running")


@dataclass(frozen=True)
class App:
    """An app the desktop's image holds."""

    id: str
    """Its name in `computer.apps`, where a person allows it or not."""
    name: str
    command: str

    @property
    def program(self) -> str:
        """Where its program is inside the desktop."""
        return f"/usr/bin/{self.command}"


# The apps of the image `deploy/desktop.Dockerfile` builds.
APPS = (
    App("text_editor", "Text editor", "mousepad"),
    App("files", "Files", "pcmanfm"),
    App("calculator", "Calculator", "galculator"),
    App("terminal", "Terminal", "xterm"),
)


def allowed_apps(settings: Computer) -> list[App]:
    """The apps a person lets the agent open."""
    return [app for app in APPS if getattr(settings.apps, app.id)]


class ContainedDesktop:
    def __init__(self, settings: Computer, data_dir: str, name: str) -> None:
        self._settings = settings
        self._folder = Path(settings.folder).expanduser().resolve()
        # One desktop for each data folder and each system: a second start takes the place of the first.
        where = hashlib.sha256(str(Path(data_dir).expanduser().resolve()).encode()).hexdigest()[:8]
        self.container = f"bap-browser-desktop-{name}-{where}"
        self._running = False
        self._channel: asyncio.subprocess.Process | None = None
        # The program that started the container and holds its input open while it is wanted.
        self._owner: asyncio.subprocess.Process | None = None

    @property
    def alive(self) -> bool:
        return self._running

    @property
    def folder(self) -> Path | None:
        """The folder of this machine that the desktop shows as `Files`. None when none is shared."""
        return self._folder if self._settings.share_folder else None

    async def start(self) -> None:
        settings = self._settings
        program = settings.container_command
        if shutil.which(program) is None:
            raise BrowserError(
                f"Computer use needs a program that runs containers, and `{program}` was not found. "
                "Install Docker and start it.",
                reason="no container program",
            )
        # `image ls` answers for an image that is there and for one that is not; `image inspect`
        # does not find every image some container programs list.
        code, out, said = await self._call(program, "image", "ls", "-q", settings.image)
        if code != 0:
            raise BrowserError(
                "The container program is installed but not running. Start Docker and try again.",
                reason="the container program is not running",
            )
        if not out.strip():
            raise BrowserError(
                f"The desktop's image `{settings.image}` is not on this machine. Build it once with: "
                f"{program} build -t {settings.image} -f deploy/desktop.Dockerfile deploy",
                reason="the desktop's image is not built",
            )
        await self._call(program, "rm", "-f", self.container)
        # Not detached: this process holds the container's input open, and the desktop ends when
        # that input closes. However this process ends, its desktop does not outlive it.
        command = [program, "run", "-i", "--rm", "--name", self.container, "-e", "WHILE_INPUT=1"]
        if not settings.network:
            command += ["--network", "none"]
        command += ["-e", f"SCREEN={settings.screen_width}x{settings.screen_height}"]
        # An app a person has not allowed cannot run at all: an empty file stands where its program
        # is, so neither the agent nor a menu of the desktop can start it (spec 21.6).
        allowed = allowed_apps(settings)
        for app in APPS:
            if app not in allowed:
                command += ["-v", f"/dev/null:{app.program}:ro"]
        if settings.share_folder:
            self._folder.mkdir(parents=True, exist_ok=True)
            command += ["-v", f"{self._folder}:{FILES_INSIDE}"]
        self._owner = await asyncio.create_subprocess_exec(
            *command,
            settings.image,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        self._running = True
        waited = 0.0
        pause = settings.app_poll_ms / 1000
        while (await self._call(program, "exec", self.container, "xdpyinfo"))[0] != 0:
            if self._owner.returncode is not None:
                assert self._owner.stderr is not None
                said = (await self._owner.stderr.read()).decode(errors="replace")
                self._running = False
                raise self._not_started(said)
            waited += pause
            if waited > settings.start_wait_s:
                await self.close()
                raise BrowserError(
                    "The desktop's screen did not come up in time.", reason="the desktop did not start"
                )
            await asyncio.sleep(pause)

    def _not_started(self, said: str) -> BrowserError:
        """Why the container did not start, in words a person can act on."""
        if self._settings.share_folder and "operation not permitted" in said:
            return BrowserError(
                f"The container program may not reach the folder {self._folder}. Allow it in this "
                "computer's privacy settings (on a Mac: Privacy & Security, Files and Folders), or "
                "choose another folder for computer.folder.",
                reason="the shared folder cannot be reached",
            )
        return BrowserError(
            f"The desktop could not be started: {_last_line(said)}", reason="the desktop did not start"
        )

    async def close(self) -> None:
        self._running = False
        owner, self._owner = self._owner, None
        if owner is not None and owner.returncode is None:
            assert owner.stdin is not None
            # Its input closes: the desktop ends by itself, and is removed.
            owner.stdin.close()
        channel, self._channel = self._channel, None
        if channel is not None and channel.returncode is None:
            channel.kill()
            await channel.wait()
        await self._call(self._settings.container_command, "rm", "-f", self.container)
        if owner is not None:
            try:
                await asyncio.wait_for(owner.communicate(), self._settings.command_timeout_s)
            except TimeoutError:
                owner.kill()
                await owner.wait()

    async def run(self, *command: str, stdin: bytes | None = None) -> bytes:
        """Runs a program inside the desktop and gives what it wrote. A failure is a BrowserError."""
        if not self._running:
            raise BrowserError("The desktop is not running.", reason="the desktop closed")
        head = [self._settings.container_command, "exec"]
        if stdin is not None:
            head.append("-i")
        code, out, said = await self._call(*head, self.container, *command, stdin=stdin)
        if code != 0:
            if any(sign in said for sign in GONE):
                self._running = False
                raise BrowserError("The desktop closed.", reason="the desktop closed")
            raise BrowserError(
                f"The desktop could not do that: {_last_line(said) or command[0] + ' failed'}",
                reason="the desktop could not do it",
            )
        return out

    async def start_app(self, app: App) -> None:
        """Starts an app and leaves it running."""
        if not self._running:
            raise BrowserError("The desktop is not running.", reason="the desktop closed")
        program = self._settings.container_command
        code, _, said = await self._call(program, "exec", "-d", self.container, app.command)
        if code != 0:
            raise BrowserError(
                f"{app.name} could not be opened: {_last_line(said)}", reason="the app did not open"
            )

    async def send(self, line: str) -> None:
        """One line for the standing input channel: what a person does with the mouse and the
        keyboard goes this way, because it must not wait for a program to start each time."""
        if not self._running:
            return
        channel = self._channel
        if channel is None or channel.returncode is not None:
            channel = self._channel = await asyncio.create_subprocess_exec(
                self._settings.container_command,
                "exec",
                "-i",
                self.container,
                "xdotool",
                "-",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
        assert channel.stdin is not None
        try:
            channel.stdin.write(line.encode() + b"\n")
            await channel.stdin.drain()
        except (BrokenPipeError, ConnectionResetError):
            # The channel went away with the desktop. The next line opens a new one, if there is a desktop.
            self._channel = None

    async def _call(self, *command: str, stdin: bytes | None = None) -> tuple[int, bytes, str]:
        """Runs a program of this machine: its exit code, what it wrote, and what it said went wrong."""
        process = await asyncio.create_subprocess_exec(
            *command,
            stdin=asyncio.subprocess.PIPE if stdin is not None else asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            out, err = await asyncio.wait_for(process.communicate(stdin), self._settings.command_timeout_s)
        except TimeoutError:
            process.kill()
            await process.wait()
            return 1, b"", "it took too long"
        return process.returncode or 0, out, err.decode(errors="replace")


def _last_line(said: str) -> str:
    """What a program said went wrong, in one line: its line that names an error, or else its last."""
    lines = [line.strip() for line in said.splitlines() if line.strip()]
    named = [line for line in lines if "rror" in line]
    return (named or lines or [""])[-1]
