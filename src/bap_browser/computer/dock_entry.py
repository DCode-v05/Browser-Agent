"""Starts the contained desktop's own screen from inside its container, on Hermes' code (spec 22.2,
piece 5). Hermes' `bot_desktop` only knows how to start a desktop on the machine it runs on; run from
in here, the container is that machine. The admin's desktop settings are given in
`BAP_BROWSER_DESKTOP_SETTINGS`, a JSON object of `DesktopOfTheBase`'s own fields.
"""

from __future__ import annotations

import json
import os
import signal
import sys
import time
from pathlib import Path
from types import FrameType

from bap_browser.computer.hermes.bot_desktop import runtime
from bap_browser.computer.seams.state import Working, work_for
from bap_browser.config_computer import Base, Computer, DesktopOfTheBase

SETTINGS = "BAP_BROWSER_DESKTOP_SETTINGS"
HOME = Path("/home/agent/.bap-browser-desktop")


def desktop_settings() -> DesktopOfTheBase:
    """The admin's desktop settings, as the container was given them. Hermes' own defaults where
    none were given."""
    given = os.environ.get(SETTINGS, "")
    return DesktopOfTheBase.model_validate(json.loads(given) if given else {})


def main() -> int:
    """Brings up the desktop and stays until asked to stop. The container's own process is this
    one: when it ends, so does the desktop."""
    work_for(Working(computer=Computer(base=Base(desktop=desktop_settings())), home=HOME))
    try:
        status = runtime.start()
    except RuntimeError as wrong:
        print(f"The desktop could not start: {wrong}", file=sys.stderr)
        return 1
    print(f"The desktop is up: {status}", file=sys.stderr)

    stopping = False

    def asked_to_stop(signum: int, frame: FrameType | None) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, asked_to_stop)
    while not stopping:
        time.sleep(1)
    runtime.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
