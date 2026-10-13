"""The contained desktop on Hermes' base (spec 22.6, arrangement B): the driver is put inside the
desktop's container, and the dock is named as the driver, so that Hermes' code talks to it through
`docker exec`. The container has no network: the driver is fetched here, by its checksum, and
copied in."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from bap_browser.computer import driver
from bap_browser.computer.dock import CONTAINER
from bap_browser.config_computer import Computer
from bap_browser.errors import BrowserError

DOCK = "bap-browser-driver-dock"
INSIDE = "/usr/local/bin/cua-driver"
# Where the driver for a desktop's container is kept on this machine, apart from this machine's own.
KEPT_IN = "contained"


def through_the_dock(computer: Computer, container: str) -> Computer:
    """The settings of computer use with the dock in the driver's place, told its container."""
    dock = shutil.which(DOCK, path=str(Path(sys.executable).parent)) or shutil.which(DOCK)
    if dock is None:
        raise BrowserError(f"{DOCK} is not installed beside the engine. Run `uv sync`.", reason="no dock")
    os.environ[CONTAINER] = container
    return computer.model_copy(update={"base": computer.base.model_copy(update={"driver_command": dock})})


def forget() -> None:
    os.environ.pop(CONTAINER, None)


def put_the_driver_in(computer: Computer, home: Path, container: str) -> None:
    """Puts the pinned driver for the container's own system inside it. Fetched once, by its
    checksum, and kept on this machine."""
    program, wait = computer.container_command, computer.command_timeout_s
    try:
        asked = subprocess.run(
            [program, "exec", container, "uname", "-m"],
            capture_output=True,
            text=True,
            timeout=wait,
            check=True,
        )
        target = driver.target("linux", asked.stdout.strip())
        kept = home / KEPT_IN
        binary = driver.installed(kept, target_name=target) or driver.install(
            kept, target_name=target, timeout_s=computer.base.install_timeout_s
        )
        subprocess.run(
            [program, "cp", str(binary), f"{container}:{INSIDE}"],
            capture_output=True,
            timeout=wait,
            check=True,
        )
    except driver.DriverError as wrong:
        raise BrowserError(str(wrong), reason="the driver could not be installed") from wrong
    except (OSError, subprocess.SubprocessError) as wrong:
        raise BrowserError(
            f"The driver could not be put into the desktop's container: {wrong}",
            reason="the driver could not be put in",
        ) from wrong
