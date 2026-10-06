"""The desktop app (spec 14.3), opened from the window of three browsers (spec 9.16): a button there
starts it as a program of its own, with its own browser, its own agent core and its own chat."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from bap_browser.errors import BapError

# An editor built on Electron sets this for the programs it starts. With it, Electron runs as plain
# Node and opens no window.
RUN_AS_NODE = "ELECTRON_RUN_AS_NODE"
STATE_FILE = "BAP_BROWSER__SERVER__STATE_FILE"


class DesktopApp:
    def __init__(self, folder: Path, state_file: Path, *, close_wait_s: float) -> None:
        """`folder` is the desktop app's own. `state_file` is where its core says where it is: a file
        apart from the one of the service that opens it."""
        self._folder = folder
        self._state_file = state_file
        self._close_wait_s = close_wait_s
        self._running: subprocess.Popen[bytes] | None = None

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

    def close(self) -> None:
        """Ends the app this service opened. It ends its own core and browser."""
        running, self._running = self._running, None
        if running is None or running.poll() is not None:
            return
        running.terminate()
        try:
            running.wait(timeout=self._close_wait_s)
        except subprocess.TimeoutExpired:
            running.kill()
            running.wait()
