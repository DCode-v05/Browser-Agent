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
import sys
from typing import Any

from bap_browser import computer
from bap_browser.computer import commands, driver
from bap_browser.computer.hermes.computer_use import permissions
from bap_browser.config import load_config

MODES = ("som", "vision", "ax")


def said(result: Any) -> dict[str, Any]:
    """A result of the tool as a dictionary, whether it came as text or with a picture."""
    if isinstance(result, str):
        answer = json.loads(result)
        return answer if isinstance(answer, dict) else {"error": result}
    text = result.get("text_summary") or ""
    picture = any(part.get("type") == "image_url" for part in result.get("content", []))
    try:
        answer = json.loads(text)
    except ValueError:
        answer = {"summary": text}
    return {**(answer if isinstance(answer, dict) else {}), "picture": picture}


def capture(mode: str) -> tuple[bool, str]:
    answer = said(computer.computer_use({"action": "capture", "mode": mode}, session="ladder"))
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
    return passed, f"{seen}, in {answer.get('app') or 'no app'}"


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
            for mode in modes:
                passed, seen = capture(mode)
                rungs.append((f"2, a capture in the mode {mode}", passed, seen))

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
