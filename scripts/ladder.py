"""The ladder: what must pass on a system before computer use is offered there (spec 22.10.1).

    uv run python scripts/ladder.py

It runs on the machine it is started on, against that machine's own screen, and says of each rung
whether it passed and what it saw. Rungs 1 and 2 are here: the driver is installed and answers, and
a capture in each of the three modes returns something. Rungs 3 to 5 need the tools an agent is
given, and are added with them.

It ends with 0 when every rung it ran passed.
"""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from bap_browser import computer
from bap_browser.computer import commands, driver
from bap_browser.computer.hermes.computer_use import permissions
from bap_browser.config import load_config

MODES = ("som", "vision", "ax")
# An app each system has: how it is started, the name a capture finds it by, and how it is closed
# when ending its process is not enough.
KNOWN: dict[str, tuple[list[str], str, list[str]]] = {
    "win32": (["notepad.exe"], "Notepad", []),
    "linux": (["zenity", "--entry", "--title=Ladder", "--text=A window the ladder knows"], "zenity", []),
    "darwin": (["open", "-a", "TextEdit"], "TextEdit", ["osascript", "-e", 'quit app "TextEdit"']),
}
WAIT_FOR_THE_APP_S = 20.0
LOOK_AGAIN_S = 0.5


def said(result: Any) -> dict[str, Any]:
    """A result of the tool as a dictionary. Text comes as JSON. A capture with a picture comes as a
    dictionary whose `meta` says what the picture is of."""
    if isinstance(result, str):
        answer = json.loads(result)
        return answer if isinstance(answer, dict) else {"error": result}
    meta = result.get("meta", {})
    picture = any(part.get("type") == "image_url" for part in result.get("content", []))
    return {
        "width": meta.get("width", 0),
        "height": meta.get("height", 0),
        "total_elements": meta.get("elements", 0),
        "picture": picture,
    }


@contextmanager
def a_known_app() -> Iterator[str]:
    """Opens an app every such system has, for the captures to look at, and closes it after."""
    system = next(name for name in KNOWN if sys.platform.startswith(name))
    command, name, closing = KNOWN[system]
    started = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        yield name
    finally:
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


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("--config", help="path of config.json")
    asked = parser.parse_args(arguments)
    config = load_config(asked.config)
    print(
        f"The ladder on {platform.system()} {platform.release()} ({platform.machine()}), Python {platform.python_version()}"
    )
    rungs: list[tuple[str, bool, str]] = []

    binary = driver.installed(computer.home_of(config))
    problem = "it is not installed" if binary is None else commands.not_ready(config, binary)
    rungs.append(("1, the pinned driver is installed and answers", problem is None, problem or str(binary)))
    if problem is None:
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
                with a_known_app() as app:
                    for mode in modes:
                        passed, seen = capture(mode, app)
                        rungs.append((f"2, a capture of {app} in the mode {mode}", passed, seen))

    for name, passed, seen in rungs:
        print(f"Rung {name}: {'passed' if passed else 'FAILED'}. {seen}")
    failed = [name for name, passed, _ in rungs if not passed]
    print(
        "The ladder is passed as far as it goes."
        if not failed
        else f"The ladder stopped: {len(failed)} failed."
    )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
