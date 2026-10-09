"""A contained desktop that keeps what it was asked, with no container, for tests of computer use."""

from pathlib import Path
from typing import Any


class StandIn:
    """What a contained desktop is asked, kept, with no container."""

    def __init__(self, folder: Path | None = None) -> None:
        self.alive = True
        self.folder = folder
        self.ran: list[tuple[tuple[str, ...], bytes | None]] = []
        self.started: list[str] = []

    async def start(self) -> None: ...

    async def close(self) -> None:
        self.alive = False

    async def run(self, *command: str, stdin: bytes | None = None) -> bytes:
        self.ran.append((command, stdin))
        if command[:2] == ("xdotool", "search"):
            return b"Untitled 1 - Mousepad\n" if self.started else b""
        if command[0] == "import":
            return b"\x89PNG\r\n\x1a\n" + bytes(16)
        return b""

    async def start_app(self, app: Any) -> None:
        self.started.append(app.command)

    async def send(self, line: str) -> None: ...
