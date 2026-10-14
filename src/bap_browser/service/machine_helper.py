"""The helper a person runs on their own machine, so that an engine elsewhere can drive it (spec
22.6.2). The same program on Windows, macOS and Linux.

The driver of computer use speaks over a pipe and listens on no network. The helper is the one new
part: it starts the driver on this machine and carries the engine's conversation with it. It
listens on this machine's own address only; `tailscale serve` shows it to the person's tailnet and
to nothing else. Three things stand before anything is done: the tailnet's own grant, who Tailscale
says the caller is, and a pairing code the person read from the helper. It tells the person what
is being done, and never what is typed.
"""

from __future__ import annotations

import asyncio
import contextlib
import hmac
import json
import math
import os
import secrets
import subprocess
import sys
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from http import HTTPStatus
from pathlib import Path
from typing import IO, Any

import uvicorn
from starlette import status
from starlette.applications import Starlette
from starlette.requests import HTTPConnection, Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route, WebSocketRoute
from starlette.websockets import WebSocket, WebSocketDisconnect

from bap_browser import computer
from bap_browser.computer import allowed, driver
from bap_browser.computer.hermes.computer_use.cua_backend_daemon import EmbeddedCuaDaemon
from bap_browser.computer.seams.process import sanitize_subprocess_env, windows_hide_flags
from bap_browser.config import Config
from bap_browser.driver.mac_hand import MacHand, MacOS

# What an engine may have the driver do besides the conversation itself: what it is, whether it is
# ready, and single calls. Nothing that updates the driver, changes its settings or installs more.
RUNS = frozenset({"manifest", "--help", "--version", "status", "doctor", "call", "stop"})
PERMISSIONS = ("permissions", frozenset({"status", "grant"}))
THE_CONVERSATION = "mcp"
WITH_IT = frozenset({"--no-overlay"})
STOPS_IT = "stop"
# What is asked of a driver that is running, and so of the one that holds the engine.
OF_THE_RUNNING_ONE = frozenset({"status", "call"})
THIS_MACHINE = frozenset({"127.0.0.1", "::1", "localhost"})
# Sent by the link when the engine has no more to say.
NO_MORE = ""
STOPPED, NO_CODE, NOT_ALLOWED, BAD = (
    HTTPStatus.LOCKED,
    HTTPStatus.UNAUTHORIZED,
    HTTPStatus.FORBIDDEN,
    HTTPStatus.BAD_REQUEST,
)
REFUSED_AT_THE_DOOR = status.WS_1008_POLICY_VIOLATION


def tailnet_names(address: str, timeout_s: float) -> set[str]:
    """Who Tailscale says an address of the tailnet is: the node's tags and its owner's login.
    Nobody, when Tailscale is not here or does not know the address."""
    try:
        asked = subprocess.run(
            ["tailscale", "whois", "--json", address],
            capture_output=True,
            text=True,
            timeout=timeout_s,
            creationflags=windows_hide_flags(),
            check=False,
        )
        known = json.loads(asked.stdout) if asked.returncode == 0 else {}
    except (OSError, subprocess.SubprocessError, ValueError):
        return set()
    tags = known.get("Node", {}).get("Tags") or []
    login = known.get("UserProfile", {}).get("LoginName")
    return {str(tag) for tag in tags} | ({str(login)} if login else set())


class RemoteHand:
    """A person's mouse and keyboard, from the engine's page, on this machine's own screen (spec
    22.6.2). Where on the picture is given as a share of it, and made a place on this screen here.
    Anything else that comes is dropped: the engine is elsewhere, and what it sends is checked."""

    def __init__(self, macos: Any, hand: MacHand, *, key_chars: int) -> None:
        self._macos = macos
        self._hand = hand
        self._key_chars = key_chars

    def given(self, said: Any) -> None:
        if not isinstance(said, dict):
            return
        kind = said.get("kind")
        place = self._place(said)
        if kind == "pointer" and place is not None:
            action, button = said.get("action"), said.get("button")
            if action in ("move", "down", "up") and button in ("left", "right", "middle"):
                self._hand.pointer(action, *place, button)
        elif kind == "key":
            action, key = said.get("action"), said.get("key")
            if action in ("down", "up") and isinstance(key, str) and 0 < len(key) <= self._key_chars:
                self._hand.key(action, key)
        elif kind == "wheel" and place is not None:
            dx, dy = finite(said.get("dx")), finite(said.get("dy"))
            if dx is not None and dy is not None:
                self._hand.pointer("move", *place, "left")
                self._hand.wheel(dx, dy)

    def _place(self, said: dict[str, Any]) -> tuple[float, float] | None:
        x, y = finite(said.get("x")), finite(said.get("y"))
        if x is None or y is None:
            return None
        wide, high = self._macos.size()
        return min(max(x, 0.0), 1.0) * wide, min(max(y, 0.0), 1.0) * high


def finite(value: object) -> float | None:
    """A number that is one: not a word, not true or false, not infinite."""
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        return None
    return float(value)


@dataclass
class Helper:
    driver: Sequence[str]
    """The driver's program on this machine, as it is started."""
    code: str
    allowed: tuple[str, ...]
    tailnet: bool
    """Whether calls come through the tailnet. When not, only this machine itself is let in."""
    who: Callable[[str], set[str]]
    say: Callable[[str], None]
    run_timeout_s: float
    message_bytes: int
    endpoint: str = ""
    """The driver this helper started with the list of allowed apps, by its own private endpoint.
    Every way to the driver then goes to that one. Empty where the person allows any app."""
    renew: Callable[[], str] | None = None
    """Starts that driver afresh and gives its new endpoint. A driver that has run a while refuses
    an app that was closed and opened again (seen on macOS), so each session of an engine gets one."""
    hand: RemoteHand | None = None
    """A person's mouse and keyboard from the engine's page, where this machine's person allows it."""
    stopped: bool = False
    running: list[subprocess.Popen[bytes]] = field(default_factory=list)

    def refusal(self, caller: HTTPConnection) -> int | None:
        """Why a caller is not let in, as a status. None when it is."""
        if self.stopped:
            return STOPPED
        scheme, _, given = caller.headers.get("authorization", "").partition(" ")
        if scheme.lower() != "bearer" or not hmac.compare_digest(given.encode(), self.code.encode()):
            return NO_CODE
        # `tailscale serve` passes a call on from this machine, and says where it came from.
        came_from = caller.headers.get("x-forwarded-for", "").split(",")[0].strip()
        if not self.tailnet:
            here = caller.client is not None and caller.client.host in THIS_MACHINE
            return None if here and not came_from else NOT_ALLOWED
        if not came_from or not (self.who(came_from) & set(self.allowed)):
            return NOT_ALLOWED
        return None

    def environment(self) -> dict[str, str]:
        return {**sanitize_subprocess_env(os.environ), "CUA_DRIVER_RS_TELEMETRY_ENABLED": "0"}

    def start_driver(self, with_it: Sequence[str]) -> subprocess.Popen[bytes]:
        """Starts the driver for one conversation with an engine."""
        driver = subprocess.Popen(
            [*self.driver, THE_CONVERSATION, *with_it, *self.held(THE_CONVERSATION)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            env=self.environment(),
            creationflags=windows_hide_flags(),
        )
        self.running.append(driver)
        return driver

    def held(self, asked: str) -> list[str]:
        """What is added to a start of the driver so that it reaches the one that holds the engine."""
        if not self.endpoint:
            return []
        return [*(["--embedded"] if asked == THE_CONVERSATION else []), "--socket", self.endpoint]

    def note(self, line: str) -> None:
        """Tells the person of a step the engine takes: its kind, and how much is typed, never what."""
        try:
            sent = json.loads(line)
        except ValueError:
            return
        if not isinstance(sent, dict) or sent.get("method") != "tools/call":
            return
        given = sent.get("params")
        params: dict[str, Any] = given if isinstance(given, dict) else {}
        arguments = params.get("arguments")
        typed = arguments.get("text") if isinstance(arguments, dict) else None
        how_much = f" ({len(typed)} characters)" if isinstance(typed, str) else ""
        self.say(f"The engine: {params.get('name', 'a step')}{how_much}")

    def stop(self) -> None:
        """Ends it for good: what is running is ended, and every later call is refused."""
        self.stopped = True
        for process in self.running:
            if process.poll() is None:
                process.kill()


def pass_on(to: IO[bytes], line: str) -> None:
    """One line of the engine's, to the driver."""
    to.write(line.encode("utf-8") + (b"" if line.endswith("\n") else b"\n"))
    to.flush()


def end(driver: subprocess.Popen[bytes]) -> None:
    """Ends the driver and closes its pipes, without waiting on anything but the process itself."""
    if driver.poll() is None:
        driver.kill()
    driver.wait()
    for pipe in (driver.stdin, driver.stdout):
        if pipe is not None:
            with contextlib.suppress(OSError):
                pipe.close()


def allowed_to_run(asked: Any) -> list[str] | None:
    """What the engine asked the driver to run, when the helper runs that. None when it does not."""
    if not isinstance(asked, list) or not asked or not all(isinstance(part, str) for part in asked):
        return None
    argv = [str(part) for part in asked]
    if argv[0] == PERMISSIONS[0]:
        return argv if len(argv) >= 2 and argv[1] in PERMISSIONS[1] else None
    return argv if argv[0] in RUNS else None


def helper_app(helper: Helper) -> Starlette:
    async def run(request: Request) -> Response:
        refused = helper.refusal(request)
        if refused is not None:
            return Response(status_code=refused)
        try:
            argv = allowed_to_run((await request.json()).get("argv"))
        except (ValueError, AttributeError):
            argv = None
        if argv is not None and helper.endpoint and argv[0] == STOPS_IT:
            # The driver that holds the engine is the helper's to stop, and the person's.
            argv = None
        if argv is None:
            return JSONResponse({"error": "The helper does not run that of the driver."}, status_code=BAD)
        helper.say(f"The engine asked the driver: {' '.join(argv[:2] if argv[0] == 'call' else argv[:1])}")
        try:
            done = await asyncio.to_thread(
                subprocess.run,
                [*helper.driver, *argv, *(helper.held(argv[0]) if argv[0] in OF_THE_RUNNING_ONE else [])],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                stdin=subprocess.DEVNULL,
                timeout=helper.run_timeout_s,
                env=helper.environment(),
                creationflags=windows_hide_flags(),
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as wrong:
            return JSONResponse({"returncode": 1, "stdout": "", "stderr": f"The driver did not run: {wrong}"})
        return JSONResponse({"returncode": done.returncode, "stdout": done.stdout, "stderr": done.stderr})

    async def converse(socket: WebSocket) -> None:
        refused = helper.refusal(socket)
        try:
            with_it = json.loads(socket.query_params.get("argv", "[]"))
        except ValueError:
            with_it = None
        if refused is not None or not isinstance(with_it, list) or not set(with_it) <= WITH_IT:
            await socket.close(REFUSED_AT_THE_DOOR)
            return
        await socket.accept()
        helper.say("An engine has started working on this machine.")
        # An ordinary process with its pipes, read on a thread: it is ended at once and for certain
        # when the engine goes away, whatever the loop is doing.
        if helper.renew is not None and not helper.running:
            # No conversation is under way: this one begins a session, which gets a fresh driver. A
            # second conversation of the session, the viewer's beside the agent's, shares it.
            helper.endpoint = await asyncio.to_thread(helper.renew)
        driver = await asyncio.to_thread(helper.start_driver, with_it)
        assert driver.stdin is not None and driver.stdout is not None
        said, heard = driver.stdout, driver.stdin

        async def answers() -> None:
            while line := await asyncio.to_thread(said.readline):
                await socket.send_text(line.decode("utf-8", errors="replace").rstrip("\r\n"))

        async def requests() -> None:
            async for line in socket.iter_text():
                if line == NO_MORE:
                    heard.close()
                    return
                helper.note(line)
                await asyncio.to_thread(pass_on, heard, line)

        outward, inward = asyncio.create_task(answers()), asyncio.create_task(requests())
        try:
            # The driver ending ends the conversation. So does the engine going away.
            await asyncio.wait({outward, inward}, return_when=asyncio.FIRST_EXCEPTION)
            await outward
        except (WebSocketDisconnect, ConnectionError, RuntimeError, OSError):
            pass
        finally:
            inward.cancel()
            outward.cancel()
            end(driver)
            helper.running.remove(driver)
            helper.say("The engine has stopped working on this machine.")
            with contextlib.suppress(RuntimeError):
                await socket.close()

    async def lend_a_hand(socket: WebSocket) -> None:
        """A person on the engine's page who has taken over: their mouse and keyboard, here."""
        hand = helper.hand
        if helper.refusal(socket) is not None or hand is None:
            await socket.close(REFUSED_AT_THE_DOOR)
            return
        await socket.accept()
        helper.say("A person on the engine's page has this machine's mouse and keyboard.")
        try:
            async for line in socket.iter_text():
                with contextlib.suppress(ValueError):
                    hand.given(json.loads(line))
        except WebSocketDisconnect:
            pass
        finally:
            helper.say("The person on the engine's page has let go of this machine's mouse and keyboard.")

    return Starlette(
        routes=[
            Route("/run", run, methods=["POST"]),
            WebSocketRoute("/mcp", converse),
            WebSocketRoute("/hand", lend_a_hand),
        ]
    )


@contextmanager
def holding_to_the_allowed_apps(config: Config, binary: Path) -> Iterator[Callable[[], str] | None]:
    """The driver started with the list of apps this machine's person allows (spec 22.7): a way to
    start it afresh, which gives its private endpoint. None where the settings do not hold the
    agent to a list. The engine is elsewhere and is not trusted to hold itself, so the driver is
    started here. The one that runs when the helper ends is stopped."""
    here = config.model_copy(update={"computer": config.computer.model_copy(update={"runs": "machine"})})
    if not allowed.held(here.computer):
        yield None
        return
    with computer.base(here):
        listed = computer.settings_seen()["computer_use"]["capability_manifest"]
        held: list[EmbeddedCuaDaemon] = []

        def afresh() -> str:
            for before in held:
                before.stop()
            held[:] = [EmbeddedCuaDaemon(str(binary), "bounded", capability_manifest=listed)]
            held[0].start()
            return held[0].socket_path

        try:
            yield afresh
        finally:
            for last in held:
                last.stop()


NO_HAND_HERE = (
    "it is built for macOS, where the program that runs the helper is allowed under System Settings, "
    "Privacy & Security, Accessibility."
)


def a_hand_here(config: Config) -> RemoteHand | None:
    """A person's mouse and keyboard from the engine's page, where this machine's settings allow it
    and macOS takes them from this program."""
    computer_settings = config.computer
    if not computer_settings.base.helper_hands or sys.platform != "darwin":
        return None
    macos = MacOS()
    if not macos.allowed():
        return None
    hand = MacHand(
        macos,
        again_within_s=computer_settings.double_press_ms / 1000,
        again_within_points=computer_settings.double_press_points,
    )
    return RemoteHand(macos, hand, key_chars=config.control.key_name_max_chars)


def run_helper(config: Config, this_machine_alone: bool) -> int:
    """Runs the helper on this machine until the person ends it (spec 22.6.2). It listens on this
    machine's own address only; `tailscale serve` is what shows it to the tailnet."""
    binary = driver.installed(computer.home_of(config))
    if binary is None:
        print("The driver of computer use is not installed. Run: bap-browser computer install")
        return 1
    base, port = config.computer.base, config.computer.helper_port
    given = os.environ.get(config.computer.helper_token_env, "")
    code = given or secrets.token_urlsafe(base.pairing_bytes)
    tailnet = base.helper_tailnet and not this_machine_alone
    it = Helper(
        driver=[str(binary)],
        code=code,
        allowed=tuple(base.helper_allow),
        tailnet=tailnet,
        who=lambda address: tailnet_names(address, base.whois_timeout_s),
        say=print,
        run_timeout_s=base.helper_run_timeout_s,
        message_bytes=base.helper_message_bytes,
        hand=a_hand_here(config),
    )
    here = f"http://127.0.0.1:{port}"
    print(f"The helper is on this machine at {here}. An engine that has the pairing code can drive this")
    print("machine through it. It tells you here what is done. Press Ctrl+C to end it.")
    if not given:
        # The code is for the person at this machine to read, here and nowhere else.
        print(f"Pairing code: {code}")
        print(f"Give it to the engine as {config.computer.helper_token_env}.")
    if it.hand is not None:
        print("A person who takes over on the engine's page may use this machine's mouse and keyboard.")
    elif base.helper_hands:
        print("A person on the engine's page cannot use this machine's mouse and keyboard: " + NO_HAND_HERE)
    if tailnet:
        print(f"It lets in, from your tailnet: {', '.join(base.helper_allow)}.")
        print(f"To show it to your tailnet and to nothing else: tailscale serve --bg --https={port} {here}")
    else:
        print("It takes calls from this machine alone.")
    try:
        with holding_to_the_allowed_apps(config, binary) as afresh:
            it.renew = afresh
            if afresh is not None:
                # Started now, so that a driver that cannot be started is known before an engine calls.
                it.endpoint = afresh()
            print(
                "The engine is held to the apps you allow in the settings."
                if afresh is not None
                else "The engine is not held to a list of apps."
            )
            uvicorn.run(
                helper_app(it),
                host="127.0.0.1",
                port=port,
                log_level="warning",
                ws_max_size=base.helper_message_bytes,
            )
    except RuntimeError as wrong:
        print(f"The driver could not be started with the list of allowed apps: {wrong}")
        return 1
    finally:
        it.stop()
    return 0
