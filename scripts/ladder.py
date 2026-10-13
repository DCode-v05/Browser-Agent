"""The ladder: what must pass on a system before computer use is offered there (spec 22.10.1).

    uv run python scripts/ladder.py

It runs on the machine it is started on, against that machine's own screen, and says of each rung
whether it passed and what it saw. Rungs 1 to 3 are here: the driver is installed and answers; a capture in each of the three modes
returns something; and through the engine's own session the tool finds a field by its number, types
into it and reads it back. Rung 4: an app that is not allowed cannot be looked at. Rung 5: while a person has taken over, the
agent can neither act nor look.

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
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from bap_browser import computer
from bap_browser.computer import allowed, commands, driver
from bap_browser.computer.hermes.computer_use import permissions
from bap_browser.config import Config, load_config
from bap_browser.driver.hermes_driver import HermesDriver
from bap_browser.results import ToolResult
from bap_browser.service.session import ServiceSession
from bap_browser.tools.computer_tools import computer_tools_for

MODES = ("som", "vision", "ax")
# An app each system has: how it is started, the name a capture finds it by, and how it is closed
# when ending its process is not enough.
KNOWN: dict[str, tuple[list[str], str, list[str]]] = {
    "win32": (["notepad.exe"], "Notepad", []),
    "linux": (["zenity", "--entry", "--title=Ladder", "--text=A window the ladder knows"], "zenity", []),
    # `-F` opens it afresh: macOS would bring back the windows of its last run, and the driver does
    # not type in the background into an app that has several windows. It is ended by its process:
    # asking it to quit goes through AppleScript, which macOS lets through only after a consent.
    "darwin": (["open", "-F", "-a", "TextEdit"], "TextEdit", ["pkill", "-x", "TextEdit"]),
}
# An app each system has that the settings do not allow: how it is started, the name a capture would
# find it by, and how it is closed.
NOT_ALLOWED: dict[str, tuple[list[str], str, list[str]]] = {
    "win32": (["charmap.exe"], "Character Map", []),
    "linux": (["xmessage", "-name", "Other", "A window that is not allowed"], "xmessage", []),
    "darwin": (["open", "-a", "Stickies"], "Stickies", ["pkill", "-x", "Stickies"]),
}
# An app each system has that is none of the four the settings name: the name it is opened by, and
# what its window is found by.
BY_NAME: dict[str, tuple[str, str]] = {
    "win32": ("Character Map", "Character Map"),
    "linux": ("xclock", "xclock"),
    "darwin": ("Stickies", "Stickies"),
}
# What the driver says when it refuses for the list of allowed apps.
REFUSED_FOR_THE_LIST = re.compile(r"manifest|authoriz|not allowed|denied|outside", re.IGNORECASE)
# A line of a capture that names a field text goes into: its number and its role.
A_FIELD = re.compile(r"#(\d+) (\S*(?:[Tt]ext|[Ee]dit|[Ee]ntry|[Dd]ocument)\S*) ")
A_ROLE_OF_A_FIELD = re.compile(r"text|edit|entry|document", re.IGNORECASE)
OK_BUTTON = re.compile(r"#(\d+) \S*button\S* 'OK'")
TYPED = "ladder 4711"
WAIT_FOR_THE_APP_S = 20.0
WAIT_FOR_THE_OTHER_APP_S = 3.0
# How long a page of a website is given to load before it is read.
WAIT_FOR_THE_PAGE_S = 8.0
# The chord that reaches a browser's address bar.
ADDRESS_BAR = {"darwin": "cmd+l"}
# A line of a capture that names a browser's address bar: its number.
THE_ADDRESS_BAR = re.compile(r"#(\d+) \S+ '[^'\n]*(?:[Aa]ddress|URL)[^'\n]*'")
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
    with tempfile.TemporaryDirectory() as folder:
        if system == "darwin":
            # TextEdit begins with its box for opening a file, and no document. It is given one.
            page = Path(folder) / "ladder.txt"
            page.write_text("", encoding="utf-8")
            command = [*command, str(page)]
        started = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        try:
            yield name, started
        finally:
            if started.poll() is None:
                started.terminate()
            if closing:
                subprocess.run(closing, capture_output=True, check=False)


async def the_windows() -> list[dict[str, Any]]:
    """The windows the driver lists, as it gives them."""
    listed = said(await asyncio.to_thread(computer.computer_use, {"action": "list_windows"}, "ladder"))
    return [row for row in listed.get("windows", []) if isinstance(row, dict)]


async def windows_like(name: str) -> str:
    """What the driver says of the windows and the apps whose row names something, shortly, for a
    rung that failed."""
    rows = [row for row in await the_windows() if name.lower() in json.dumps(row).lower()]
    apps = said(await asyncio.to_thread(computer.computer_use, {"action": "list_apps"}, "ladder"))
    named = [row for row in apps.get("apps", []) if name.lower() in json.dumps(row).lower()]
    return json.dumps({"windows": rows, "apps": named})[:1100]


@contextmanager
def an_app_not_allowed() -> Iterator[tuple[str, int]]:
    """Opens an app the settings do not allow, and closes it after. Its name and its process come out."""
    system = next(name for name in NOT_ALLOWED if sys.platform.startswith(name))
    command, name, closing = NOT_ALLOWED[system]
    with tempfile.TemporaryDirectory() as folder:
        if system == "linux":
            # The same small dialog under another name: to the driver, another program, not allowed.
            other = shutil.copy(shutil.which(KNOWN["linux"][0][0]) or "", Path(folder) / "not-allowed-dialog")
            command, name = (
                [str(other), "--info", "--title=Other", "--text=Not allowed"],
                "not-allowed-dialog",
            )
        started = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            yield name, started.pid
        finally:
            if started.poll() is None:
                started.terminate()
            if closing:
                subprocess.run(closing, capture_output=True, check=False)
            started.wait()


def with_the_known_app_allowed(config: Config) -> Config:
    """The settings with the ladder's own app among the allowed ones, where it is not one already: on
    Linux it is a small dialog and no app of the settings' four."""
    program = shutil.which(KNOWN["linux"][0][0]) if sys.platform.startswith("linux") else None
    if program is None:
        return config
    base = config.computer.base
    base = base.model_copy(update={"also_allowed": [*base.also_allowed, os.path.realpath(program)]})
    return config.model_copy(update={"computer": config.computer.model_copy(update={"base": base})})


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


async def in_the_container(config: Config) -> list[tuple[str, bool, str]]:
    """The ladder on the contained desktop. The engine starts the container, puts the driver in it,
    and through the session opens the text editor, finds its field by number and types into it. The
    editor then marks its own window as changed."""
    inside = config.computer.model_copy(update={"runs": "container", "share_folder": False})
    machine = config.model_copy(update={"computer": inside})
    inside_it = HermesDriver(machine)
    session = ServiceSession(
        machine, inside_it, name="ladder", backend="contained_desktop", tools=computer_tools_for
    )
    rungs: list[tuple[str, bool, str]] = []
    try:
        await session.start()
        opened = await session.toolkit.call("computer_open_app", {"app": "Text editor"})
        rungs.append(
            (
                "1, the desktop is up with the driver inside, and the editor is opened",
                not opened.is_error,
                " | ".join(opened.text.splitlines())[:200],
            )
        )
        look = {"action": "capture", "mode": "ax", "app": "mousepad"}
        ends = time.monotonic() + WAIT_FOR_THE_APP_S
        seen = await session.toolkit.call("computer_use", look)
        while "#" not in seen.text and time.monotonic() < ends:
            await asyncio.sleep(LOOK_AGAIN_S)
            seen = await session.toolkit.call("computer_use", look)
        # An editor has many elements, and a capture's text names only the first of them. The field
        # is looked for among all of them, as the tool itself gives them.
        whole = said(await asyncio.to_thread(computer.computer_use, look, "ladder"))
        every = whole.get("elements", [])
        if whole.get("elements_file"):
            # Past a hundred, the tool keeps the rest in a file and names it.
            kept = await asyncio.to_thread(Path(whole["elements_file"]).read_text, encoding="utf-8")
            every = json.loads(kept)["elements"]
        fields = [one for one in every if A_ROLE_OF_A_FIELD.search(str(one.get("role", "")))]
        rungs.append(
            (
                "2, a capture of the editor numbers its elements",
                bool(fields),
                f"{len(every)} elements; the field is {fields[0] if fields else 'not among them'}; "
                f"roles: {sorted({str(one.get('role')) for one in every})}"[:500],
            )
        )
        if not fields:
            return rungs
        await session.toolkit.call("computer_use", {"action": "click", "element": fields[0]["index"]})
        typed = await session.toolkit.call("computer_use", {"action": "type", "text": TYPED})
        rungs.append(
            (
                "3, typing into its field by number is done",
                not typed.is_error and TYPED not in typed.text,
                " | ".join(typed.text.splitlines())[:300],
            )
        )
        # The editor puts a star before its document's name once the document is changed.
        titles = await inside_it.windows()
        rungs.append(
            ("3, the editor marks its window as changed", any("*" in title for title in titles), str(titles))
        )
        picture = await session.toolkit.call(
            "computer_use", {"action": "capture", "mode": "vision", "app": "mousepad"}
        )
        rungs.append(
            (
                "2, a picture of the editor comes back",
                picture.picture is not None,
                f"{len(picture.picture.data) if picture.picture else 0} bytes",
            )
        )
    finally:
        await session.close()
    return rungs


async def a_window_of(name: str) -> bool:
    """Whether the driver lists a window that names something, once it has had time to open."""
    ends = time.monotonic() + WAIT_FOR_THE_APP_S
    while True:
        if any(name.lower() in json.dumps(row).lower() for row in await the_windows()):
            return True
        if time.monotonic() > ends:
            return False
        await asyncio.sleep(LOOK_AGAIN_S)


def started(program: str) -> int:
    """Starts a program of the system and leaves it open. Its process."""
    return subprocess.Popen([program], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).pid


async def looked_at(session: ServiceSession, pid: int, name: str) -> ToolResult:
    """A capture of one app's window, asked for exactly, by what the driver itself lists: a name
    that matched nothing would prove nothing."""
    ends = time.monotonic() + WAIT_FOR_THE_APP_S
    while True:
        rows = [row for row in await the_windows() if row.get("pid") == pid]
        rows = rows or [row for row in await the_windows() if name.lower() in json.dumps(row).lower()]
        # A window takes a moment to open, and longer on a machine that is busy.
        if rows or time.monotonic() > ends:
            break
        await asyncio.sleep(LOOK_AGAIN_S)
    if not rows:
        return ToolResult(f"its window was not among the driver's: {await windows_like('')}", is_error=True)
    exactly = {"pid": rows[0].get("pid"), "window_id": rows[0].get("window_id")}
    return await session.toolkit.call("computer_use", {"action": "capture", "mode": "ax", **exactly})


async def a_site_is_read(
    session: ServiceSession, browser: str, address: str, expects: str
) -> tuple[str, bool, str]:
    """With any app allowed: the machine's own browser is opened by its name, its address bar is
    clicked by its number, an address is typed, and what the page shows is read. This is how the
    agent reaches a website."""

    async def does(step: dict[str, Any]) -> ToolResult:
        did = await session.toolkit.call("computer_use", step)
        if did.is_error and "foreground" in did.text:
            # The tool says where background delivery is not to be had, and what to do: the agent
            # is told to follow it.
            did = await session.toolkit.call("computer_use", {**step, "delivery_mode": "foreground"})
        return did

    opened = await session.toolkit.call("computer_open_app", {"app": browser})
    # A browser takes a while to show its first window.
    await a_window_of(browser)
    look = {"action": "capture", "mode": "ax", "app": browser}
    first = await session.toolkit.call("computer_use", look)
    bar = THE_ADDRESS_BAR.search(first.text)
    done = [opened, first]
    if bar is not None:
        done.append(await does({"action": "click", "element": int(bar.group(1))}))
    else:
        done.append(await does({"action": "key", "keys": ADDRESS_BAR.get(sys.platform, "ctrl+l")}))
    for step in (
        {"action": "type", "text": address},
        {"action": "key", "keys": "return"},
        {"action": "wait", "seconds": WAIT_FOR_THE_PAGE_S},
    ):
        done.append(await does(step))
    read = await session.toolkit.call("computer_use", look)
    wrong = next((" | ".join(one.text.splitlines())[:200] for one in [*done, read] if one.is_error), None)
    how = f"the address bar was {'element ' + bar.group(1) if bar else 'reached by its key'}; "
    return (
        f"4, any app is allowed, and {address} is opened in {browser} and read",
        wrong is None and expects.lower() in read.text.lower(),
        wrong
        or how + " | ".join(line for line in read.text.splitlines() if expects.lower() in line.lower())[:300]
        or how + "the page read: " + " | ".join(read.text.splitlines())[:600],
    )


async def through_the_engine(
    config: Config, site: tuple[str, str, str] | None = None
) -> list[tuple[str, bool, str]]:
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
                told = f"{seen.text[:300]} || the driver's windows: {await windows_like(app)}"
                return [(f"3, a field of {app} is found by its number", False, told)]
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
            here = machine.computer.model_copy(update={"runs": "machine"})
            if allowed.held(here) or here.any_app:
                # Rung 4: the driver itself refuses an app the person did not allow. Through the
                # helper it is the helper's driver that refuses, with the same settings. Where the
                # person allows any app, the same window is looked at instead.
                with an_app_not_allowed() as (other, its_pid):
                    await asyncio.sleep(WAIT_FOR_THE_OTHER_APP_S)
                    there = await looked_at(session, its_pid, other)
                seen_there = " | ".join(there.text.splitlines())[:300]
                if here.any_app:
                    rungs.append(
                        (
                            f"4, any app is allowed, and {other}, outside the list, is looked at",
                            not there.is_error,
                            seen_there,
                        )
                    )
                else:
                    refused = there.is_error and bool(REFUSED_FOR_THE_LIST.search(there.text))
                    rungs.append(
                        (
                            f"4, {other}, which is not allowed, cannot be looked at or worked in",
                            refused,
                            seen_there,
                        )
                    )
            if here.any_app:
                # An app outside the four the settings name is opened by its name, after a yes.
                system = next(name for name in BY_NAME if sys.platform.startswith(name))
                named, shown_as = BY_NAME[system]
                asked_of_a_person: list[str] = []

                async def yes(question: Any) -> Any:
                    asked_of_a_person.append(question.tool)
                    return "allowed"

                session.browser.ask_approval = yes
                opened = await session.toolkit.call("computer_open_app", {"app": named})
                is_open = await a_window_of(shown_as)
                rungs.append(
                    (
                        f"4, any app is allowed, and {named} is opened by its name after a person's yes",
                        not opened.is_error and is_open and asked_of_a_person == ["computer_open_app"],
                        f"{' | '.join(opened.text.splitlines())[:200]} | asked: {asked_of_a_person} | {(await windows_like(shown_as))[:200]}",
                    )
                )
            if here.any_app and site is not None:
                rungs.append(await a_site_is_read(session, *site))
            if here.any_app and sys.platform == "win32":
                # The two apps of Windows that the list of allowed apps cannot name.
                for program, title in (("explorer.exe", "File Explorer"), ("wt.exe", "")):
                    if shutil.which(program) is None:
                        continue
                    its_pid = await asyncio.to_thread(started, program)
                    await asyncio.sleep(WAIT_FOR_THE_OTHER_APP_S)
                    there = await looked_at(session, its_pid, title or "WindowsTerminal")
                    rungs.append(
                        (
                            f"4, any app is allowed, and {program} is looked at",
                            not there.is_error,
                            " | ".join(there.text.splitlines())[:300],
                        )
                    )
            # Rung 5: while a person holds the screen, nothing is done for the agent, not even a look.
            look = {"action": "capture", "mode": "ax", "app": app}
            await session.handle({"type": "take_over"})
            # The engine's own gate makes a call wait for the person. Hermes' gate is asked directly,
            # as a call that was already on its way would reach it.
            past_the_engine = said(await asyncio.to_thread(computer.computer_use, look, "ladder"))
            await session.handle({"type": "hand_back"})
            after = await session.toolkit.call("computer_use", look)
            kept_out = past_the_engine.get("code") == "human_has_control"
            rungs.append(
                (
                    "5, while a person has taken over, the agent can neither act nor look, and can again after",
                    kept_out and not after.is_error,
                    f"the tool itself answered {past_the_engine.get('code')!r}; after the hand back a capture "
                    f"{'worked' if not after.is_error else 'failed'}",
                )
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
        clicked = await session.toolkit.call(
            "computer_use", {"action": "click", "element": int(button.group(1))}
        )
        try:
            printed = (await asyncio.to_thread(process.communicate, None, WAIT_FOR_THE_APP_S))[0]
        except subprocess.TimeoutExpired:
            said_of_it = " | ".join(clicked.text.splitlines())[:300]
            return name, False, f"OK was clicked by its number, and the dialog did not close: {said_of_it}"
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
        "--contained",
        action="store_true",
        help="climb on the contained desktop: the driver is put inside its container and reached through the dock",
    )
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
    parser.add_argument(
        "--any-app",
        action="store_true",
        help="climb with the person's switch on: the agent is not held to the allowed apps",
    )
    parser.add_argument(
        "--site",
        nargs=3,
        metavar=("BROWSER", "ADDRESS", "EXPECTS"),
        help="with --any-app: open this browser by its name, go to this address, and find this word on the page",
    )
    asked = parser.parse_args(arguments)
    site = (asked.site[0], asked.site[1], asked.site[2]) if asked.site and asked.any_app else None
    # What a screen holds is printed as it is, on a console of any encoding.
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8", errors="replace")
    config = with_the_known_app_allowed(load_config(asked.config))
    if asked.any_app:
        config = config.model_copy(update={"computer": config.computer.model_copy(update={"any_app": True})})
    if asked.virtual_screen:
        base = config.computer.base.model_copy(update={"virtual_screen": True})
        config = config.model_copy(update={"computer": config.computer.model_copy(update={"base": base})})
    print(
        f"The ladder on {platform.system()} {platform.release()} ({platform.machine()}), Python {platform.python_version()}"
    )
    rungs: list[tuple[str, bool, str]] = []

    if asked.contained:
        rungs = asyncio.run(in_the_container(config))
        for name, passed, seen in rungs:
            print(f"Rung {name}: {'passed' if passed else 'FAILED'}. {seen}")
        failed = [name for name, passed, _ in rungs if not passed]
        print(
            "The ladder is passed as far as it goes."
            if not failed
            else f"The ladder stopped: {len(failed)} failed."
        )
        return 1 if failed else 0
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
        climb(config, asked.rungs, problem is None, rungs, site)

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
        env={
            **os.environ,
            "BAP_BROWSER__COMPUTER__HELPER_PORT": str(port),
            # The helper holds the engine to the apps of its own settings: the ladder's app is one.
            "BAP_BROWSER__COMPUTER__BASE__ALSO_ALLOWED": json.dumps(config.computer.base.also_allowed),
        },
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


def climb(
    config: Config,
    highest: int,
    installed: bool,
    rungs: list[tuple[str, bool, str]],
    site: tuple[str, str, str] | None = None,
) -> None:
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
        rungs += asyncio.run(through_the_engine(config, site))


if __name__ == "__main__":
    sys.exit(main())
