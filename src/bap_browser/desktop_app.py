"""The desktop app (spec 14.3), opened from the window of three browsers (spec 9.16): a button there
starts it as a program of its own, with its own browser, its own agent core and its own chat."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from urllib.parse import quote, urlsplit

from bap_browser.errors import BapError

# An editor built on Electron sets this for the programs it starts. With it, Electron runs as plain
# Node and opens no window.
RUN_AS_NODE = "ELECTRON_RUN_AS_NODE"
STATE_FILE = "BAP_BROWSER__SERVER__STATE_FILE"
# What the chat's own window is told: the address it shows, and how wide it is.
SIDE_CHAT, SIDE_CHAT_WIDTH = "BAP_SIDE_CHAT", "BAP_SIDE_CHAT_WIDTH"


class DesktopApp:
    def __init__(self, folder: Path, state_file: Path, *, close_wait_s: float) -> None:
        """`folder` is the desktop app's own. `state_file` is where its core says where it is: a file
        apart from the one of the service that opens it."""
        self._folder = folder
        self._state_file = state_file
        self._close_wait_s = close_wait_s
        self._running: subprocess.Popen[bytes] | None = None
        self._beside: subprocess.Popen[bytes] | None = None

    def program(self) -> Path | None:
        """Electron, as the app's packages installed it. None when they are not installed."""
        electron = self._folder / "node_modules" / "electron"
        try:
            named = (electron / "path.txt").read_text(encoding="utf-8").strip()
        except OSError:
            return None
        program = electron / "dist" / named
        return program if named and program.is_file() else None

    @property
    def there(self) -> bool:
        """The app can be opened: its packages are installed and its shell is built."""
        return self.program() is not None and (self._folder / "dist" / "index.html").is_file()

    @property
    def open(self) -> bool:
        return self._running is not None and self._running.poll() is None

    def start(self) -> bool:
        """Opens the app's window. False when the one this service opened is still open."""
        if self.open:
            return False
        program = self.program()
        if program is None or not self.there:
            raise BapError(
                "The desktop app is not installed. Run: npm --prefix desktop install, "
                "then npm --prefix desktop run build"
            )
        env = {name: value for name, value in os.environ.items() if name != RUN_AS_NODE}
        env[STATE_FILE] = str(self._state_file)
        try:
            self._running = subprocess.Popen(
                [str(program), str(self._folder)],
                cwd=self._folder,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError as failed:
            raise BapError(f"The desktop app could not be started: {failed}") from failed
        return True

    def chat_beside(self, address: str, width: int) -> bool:
        """Opens the chat of one page in a narrow window that stays above every other app (spec
        22.3.1), at the right edge of the screen. `address` is that chat alone, signed in. False
        when the one this service opened is still open."""
        if self._beside is not None and self._beside.poll() is None:
            return False
        program = self.program()
        if program is None:
            raise BapError("The desktop app is not installed. Run: npm --prefix desktop install")
        env = {name: value for name, value in os.environ.items() if name != RUN_AS_NODE}
        env |= {SIDE_CHAT: address, SIDE_CHAT_WIDTH: str(width)}
        try:
            self._beside = subprocess.Popen(
                [str(program), str(self._folder / "electron" / "side.cjs")],
                cwd=self._folder,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError as failed:
            raise BapError(f"The chat's window could not be opened: {failed}") from failed
        return True

    def chat_beside_until_closed(self, service: str, page: str, width: int) -> int:
        """Opens the chat of one page of a service, by the service's address, in the window that
        stays above every other app, and waits until the person closes it. For a person whose
        engine runs elsewhere, in a micro VM: it is their own machine the window belongs on (spec
        22.6). The viewer's link signs the window in; with no token in it, the page asks them to sign in."""
        at = urlsplit(service)
        if at.scheme not in ("http", "https") or not at.hostname:
            raise BapError("Give the service's address, beginning with http:// or https://.")
        program = self.program()
        if program is None:
            raise BapError("The desktop app is not installed. Run: npm --prefix desktop install")
        chat = f"{at.scheme}://{at.netloc}/?session={quote(page)}&beside"
        if at.fragment.startswith("token="):
            # The viewer's link: its token stays after the #, which no server is sent.
            chat += f"#{at.fragment}"
        env = {name: value for name, value in os.environ.items() if name != RUN_AS_NODE}
        env |= {SIDE_CHAT: chat, SIDE_CHAT_WIDTH: str(width)}
        try:
            return subprocess.run(
                [str(program), str(self._folder / "electron" / "side.cjs")],
                cwd=self._folder,
                env=env,
                check=False,
            ).returncode
        except OSError as failed:
            raise BapError(f"The chat's window could not be opened: {failed}") from failed

    def close(self) -> None:
        """Ends what this service opened: the app, which ends its own core and browser, and the
        chat's own window."""
        running, self._running = self._running, None
        beside, self._beside = self._beside, None
        for one in (running, beside):
            if one is None or one.poll() is not None:
                continue
            one.terminate()
            try:
                one.wait(timeout=self._close_wait_s)
            except subprocess.TimeoutExpired:
                one.kill()
                one.wait()
