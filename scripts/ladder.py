"""The ladder: what must pass on a system before computer use is offered there (spec 22.10.1).

    uv run python scripts/ladder.py

It runs on the machine it is started on, against that machine's own screen, and says of each rung
whether it passed and what it saw. Rungs 1 to 3 are here: the driver is installed and answers; a capture in each of the three modes
returns something; and through the engine's own session the tool finds a field by its number, types
into it and reads it back. Rungs 4 and 5 are added with the allowed apps and the lease.

It ends with 0 when every rung it ran passed.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import io
import json
import os
import platform
import re
import secrets
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from bap_browser import computer
from bap_browser.computer import commands, driver
from bap_browser.computer.hermes.computer_use import permissions
from bap_browser.config import Config, load_config
from bap_browser.driver.hermes_driver import HermesDriver
from bap_browser.service.session import ServiceSession
from bap_browser.tools.computer_tools import computer_tools_for

MODES = ("som", "vision", "ax")
# An app each system has: how it is started, the name a capture finds it by, and how it is closed
# when ending its process is not enough.
KNOWN: dict[str, tuple[list[str], str, list[str]]] = {
    "win32": (["notepad.exe"], "Notepad", []),
    "linux": (["zenity", "--entry", "--title=Ladder", "--text=A window the ladder knows"], "zenity", []),
    "darwin": (["open", "-a", "TextEdit"], "TextEdit", ["osascript", "-e", 'quit app "TextEdit"']),
}
# A line of a capture that names a field text goes into: its number and its role.
A_FIELD = re.compile(r"#(\d+) (\S*(?:[Tt]ext|[Ee]dit|[Ee]ntry|[Dd]ocument)\S*) ")
OK_BUTTON = re.compile(r"#(\d+) \S*button\S* 'OK'")
TYPED = "ladder 4711"
WAIT_FOR_THE_APP_S = 20.0
LOOK_AGAIN_S = 0.5


def said(result: Any) -> dict[str, Any]:
    """A result of the tool as a dictionary. Text comes as JSON. A capture with a picture comes as a
    dictionary whose `meta` says what the picture is of."""
    if isinstance(result, str):
        answer = json.loads(result)
        if not isinstance(answer, dict):
            return {"error": result}
        # A screen that has not changed is not sent twice: the picture is the one before.
        return {**answer, "picture": bool(answer.get("screen_unchanged"))}
    meta = result.get("meta", {})
    picture = any(part.get("type") == "image_url" for part in result.get("content", []))
    return {
        "width": meta.get("width", 0),
        "height": meta.get("height", 0),
        "total_elements": meta.get("elements", 0),
        "picture": picture,
    }


@contextmanager
def a_known_app() -> Iterator[tuple[str, subprocess.Popen[bytes]]]:
    """Opens an app every such system has, for the ladder to work in, and closes it after. The app
    and its process come out: on Linux the app prints what was typed into it when it is closed."""
    system = next(name for name in KNOWN if sys.platform.startswith(name))
    command, name, closing = KNOWN[system]
    started = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
        yield name, started
    finally:
        if started.poll() is None:
            started.terminate()
        if closing:
            subprocess.run(closing, capture_output=True, check=False)


def capture(mode: str, app: str) -> tuple[bool, str]:
    """A capture of the known app. Its window takes a moment to come up, so it is asked for until it
    is there or the wait is over."""
    asked = {"action": "capture", "mode": mode, "app": app}
    ends = time.monotonic() + WAIT_FOR_THE_APP_S
    answer = said(computer.computer_use(asked, session="ladder"))
    while ("error" in answer or not answer.get("width")) and time.monotonic() < ends:
        time.sleep(LOOK_AGAIN_S)
        answer = said(computer.computer_use(asked, session="ladder"))
    if "error" in answer:
        return False, str(answer["error"])
    width, height = answer.get("width", 0), answer.get("height", 0)
    elements = answer.get("total_elements", len(answer.get("elements", [])))
    seen = (
        f"{width} by {height}, {elements} elements, {'a picture' if answer.get('picture') else 'no picture'}"
    )
    wants_picture, wants_elements = mode != "ax", mode != "vision"
    passed = width > 0 and height > 0
    passed = passed and (not wants_picture or bool(answer.get("picture")))
    passed = passed and (not wants_elements or elements > 0)
    return passed, seen


async def through_the_engine(config: Config) -> list[tuple[str, bool, str]]:
    """Rung 3: the agent's own way in. Through the session and its check, the tool finds a field of
    the known app by its number, types into it, and reads back what it typed."""
    runs = config.computer.runs if config.computer.runs == "remote" else "machine"
    machine = config.model_copy(update={"computer": config.computer.model_copy(update={"runs": runs})})
    watching = HermesDriver(machine)
    session = ServiceSession(
        machine, watching, name="ladder", backend="contained_desktop", tools=computer_tools_for
    )
    rungs: list[tuple[str, bool, str]] = []
    await session.start()
    try:
        with a_known_app() as (app, process):
            ends = time.monotonic() + WAIT_FOR_THE_APP_S
            seen = await session.toolkit.call("computer_use", {"action": "capture", "mode": "ax", "app": app})
            while not A_FIELD.search(seen.text) and time.monotonic() < ends:
                await asyncio.sleep(LOOK_AGAIN_S)
                seen = await session.toolkit.call(
                    "computer_use", {"action": "capture", "mode": "ax", "app": app}
                )
            field = A_FIELD.search(seen.text)
            if seen.is_error or field is None:
                return [(f"3, a field of {app} is found by its number", False, seen.text[:300])]
            number = int(field.group(1))
            rungs.append(
                (f"3, a field of {app} is found by its number", True, f"element {number}, {field.group(2)}")
            )
            # What a person watching would be shown: the machine's whole screen, as it changes.
            frames: list[bytes] = []
            once, twice = asyncio.Event(), asyncio.Event()

            def shown(frame: bytes) -> None:
                frames.append(frame)
                once.set()
                if len(set(frames)) >= 2:
                    twice.set()

            viewer = machine.viewer
            await watching.start_frames(shown, getattr(viewer.quality_levels, viewer.quality))
            # The first picture is of the screen as it is now, before anything is typed.
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(once.wait(), WAIT_FOR_THE_APP_S)
            await session.toolkit.call("computer_use", {"action": "click", "element": number})
            typed = await session.toolkit.call("computer_use", {"action": "type", "text": TYPED})
            rungs.append(
                (
                    "3, typing into it is done and does not come back in the result",
                    not typed.is_error and TYPED not in typed.text,
                    " | ".join(typed.text.splitlines())[:300],
                )
            )
            after = await session.toolkit.call(
                "computer_use", {"action": "capture", "mode": "ax", "app": app}
            )
            rungs.append(await read_back(session, after.text, process))
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(twice.wait(), WAIT_FOR_THE_APP_S)
            await watching.stop_frames()
            pictures = [frame for frame in frames if frame[:2] == b"\xff\xd8" or frame[:4] == b"\x89PNG"]
            rungs.append(
                (
                    "the screen is streamed to whoever watches, and again when it changes",
                    len(pictures) >= 2 and len(set(pictures)) >= 2,
                    f"{len(pictures)} pictures of the whole screen, {len(set(pictures))} of them different, "
                    f"the first of {len(pictures[0]) if pictures else 0} bytes",
                )
            )
    finally:
        await session.close()
    return rungs


async def read_back(
    session: ServiceSession, after: str, process: subprocess.Popen[bytes]
) -> tuple[str, bool, str]:
    """Whether what was typed is in the app, told by the app and not by the driver. A capture names
    a field and not what it holds, so each known app is asked in its own way."""
    name = "3, the app itself holds what was typed"
    told = " | ".join(after.splitlines())[:600]
    if sys.platform == "win32":
        # Notepad marks a document that was changed with a star before its name.
        return (
            name,
            "*Untitled" in after,
            "its title bar says the document was changed" if "*Untitled" in after else told,
        )
    if sys.platform.startswith("linux"):
        # The dialog prints its field when OK is pressed: a click by number, and the text comes out.
        button = OK_BUTTON.search(after)
        if button is None:
            return name, False, told
        await session.toolkit.call("computer_use", {"action": "click", "element": int(button.group(1))})
        try:
            printed = (await asyncio.to_thread(process.communicate, None, WAIT_FOR_THE_APP_S))[0]
        except subprocess.TimeoutExpired:
            return name, False, "OK was clicked by its number, and the dialog did not close"
        said_back = printed.decode("utf-8", errors="replace").strip()
        return (
            name,
            said_back == TYPED,
            f"the dialog printed {said_back!r} after OK was clicked by its number",
        )
    return name, TYPED in after, "it is in the capture" if TYPED in after else told


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("--config", help="path of config.json")
    parser.add_argument("--rungs", type=int, default=3, help="the highest rung to climb: 2 or 3")
    parser.add_argument(
        "--virtual-screen",
        action="store_true",
        help="climb as the engine in the micro VM does: it starts this machine's own virtual screen first",
    )
    parser.add_argument(
        "--through-helper",
        action="store_true",
        help="climb as an engine elsewhere would: through the helper, started here for this machine alone",
    )
    asked = parser.parse_args(arguments)
    # What a screen holds is printed as it is, on a console of any encoding.
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8", errors="replace")
    config = load_config(asked.config)
    if asked.virtual_screen:
        base = config.computer.base.model_copy(update={"virtual_screen": True})
        config = config.model_copy(update={"computer": config.computer.model_copy(update={"base": base})})
    print(
        f"The ladder on {platform.system()} {platform.release()} ({platform.machine()}), Python {platform.python_version()}"
    )
    rungs: list[tuple[str, bool, str]] = []

    binary = driver.installed(computer.home_of(config))
    problem = "it is not installed" if binary is None else commands.not_ready(config, binary)
    rungs.append(("1, the pinned driver is installed and answers", problem is None, problem or str(binary)))
    with contextlib.ExitStack() as held:
        if asked.through_helper and problem is None:
            # The engine reaches this machine as it would reach one elsewhere: through the helper.
            config = held.enter_context(a_helper_here(config))
            rungs.append(
                (
                    "the helper is started, and the engine is given its pairing code",
                    True,
                    config.computer.helper_url,
                )
            )
        climb(config, asked.rungs, problem is None, rungs)

    for name, passed, seen in rungs:
        print(f"Rung {name}: {'passed' if passed else 'FAILED'}. {seen}")
    failed = [name for name, passed, _ in rungs if not passed]
    print(
        "The ladder is passed as far as it goes."
        if not failed
        else f"The ladder stopped: {len(failed)} failed."
    )
    return 1 if failed else 0


@contextmanager
def a_helper_here(config: Config) -> Iterator[Config]:
    """The helper on this machine, for this machine alone, and the settings of an engine that drives
    the machine through it."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    variable, code = config.computer.helper_token_env, secrets.token_urlsafe(18)
    os.environ[variable] = code
    started = subprocess.Popen(
        [sys.executable, "-m", "bap_browser", "computer", "helper", "--this-machine-alone"],
        env={**os.environ, "BAP_BROWSER__COMPUTER__HELPER_PORT": str(port)},
        stdout=subprocess.DEVNULL,
    )
    try:
        ends = time.monotonic() + WAIT_FOR_THE_APP_S
        while time.monotonic() < ends:
            with (
                contextlib.suppress(OSError),
                socket.create_connection(("127.0.0.1", port), timeout=LOOK_AGAIN_S),
            ):
                break
            time.sleep(LOOK_AGAIN_S)
        elsewhere = config.computer.model_copy(
            update={"runs": "remote", "helper_url": f"http://127.0.0.1:{port}"}
        )
        yield config.model_copy(update={"computer": elsewhere})
    finally:
        started.terminate()
        os.environ.pop(variable, None)


def climb(config: Config, highest: int, installed: bool, rungs: list[tuple[str, bool, str]]) -> None:
    """Rungs 2 and 3, added to what was climbed so far."""
    problem = None if installed else "not installed"
    # With a screen the engine starts itself, there is none until its session has begun: the
    # captures of rung 2 are then the ones rung 3 takes.
    if problem is None and not config.computer.base.virtual_screen:
        with computer.base(config):
            status = permissions.computer_use_status()
            if status["can_grant"] and not status["ready"]:
                # Asking for a capture now would only make macOS put its question on the screen.
                waiting = "macOS has not allowed the driver. Run: bap-browser computer permissions grant"
                rungs.append(("2, a capture in each mode", False, waiting))
                modes: tuple[str, ...] = ()
            else:
                modes = MODES
            if modes:
                with a_known_app() as (app, _):
                    for mode in modes:
                        passed, seen = capture(mode, app)
                        rungs.append((f"2, a capture of {app} in the mode {mode}", passed, seen))

    if highest >= 3 and not [name for name, passed, _ in rungs if not passed]:
        rungs += asyncio.run(through_the_engine(config))


if __name__ == "__main__":
    sys.exit(main())
