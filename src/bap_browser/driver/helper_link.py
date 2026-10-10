"""The way to a helper a person runs on their own machine, over HTTP with its token (spec 21.13 to
21.15). It stands where the desktop of a container would, for the Mac, Windows and Linux drivers alike.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from bap_browser.config import Config
from bap_browser.errors import BrowserError
from bap_browser.private_file import write_json

# The file, in the data folder, where a helper on this machine says where it is.
PAIRING = "helper.json"


class HelperLink:
    """The way to the helper on the person's machine. It stands where the desktop of a container
    would. `machine` names it in the sentences a person reads: "Mac", "PC" or "Linux machine"."""

    def __init__(self, url: str, token: str, timeout_s: float, machine: str) -> None:
        self._url, self._token, self._timeout_s = url.rstrip("/"), token, timeout_s
        self._machine = machine
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
                f"The helper on the {self._machine} does not answer at {self._url}: {lost}. Start it "
                "there with `bap-browser helper`.",
                reason="the helper does not answer",
            ) from None

    async def status(self) -> dict[str, Any]:
        return json.loads((await self.ask("GET", "/status"))[0])

    async def act(self, **asked: Any) -> None:
        await self.ask("POST", "/act", asked)

    async def start(self) -> None:
        if not self._token:
            raise BrowserError(
                f"No helper is paired. Start the helper on this {self._machine} with `uv run "
                "bap-browser helper --allow text_editor,files,calculator`, or give the token of one "
                "elsewhere in BAP_BROWSER_HELPER_TOKEN.",
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
                f"The Mac has not allowed the helper {' and '.join(missing)} yet. macOS has asked: switch "
                "Terminal on under each in System Settings, Privacy & Security. This page connects by itself "
                "once both are allowed.",
                reason="the Mac has not allowed it",
            )
        if told["stopped"]:
            raise BrowserError(
                f"The person stopped the helper. Start it again on the {self._machine}.",
                reason="the helper is stopped",
            )
        self._running = True

    async def close(self) -> None:
        self._running = False

    async def run(self, *command: str, stdin: bytes | None = None) -> bytes:
        raise BrowserError(
            f"Commands are not run on a person's {self._machine}.", reason="not on that machine"
        )

    async def start_app(self, app: Any) -> None:
        await self.act(do="open", app=app.id)

    async def send(self, line: str) -> None:
        """A person's hand on the machine goes through the driver's own pointer, key and wheel."""


def pairing_file(config: Config) -> Path:
    """Where the helper on this machine leaves its address and token, for this user alone (spec 21.13
    to 21.15)."""
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
