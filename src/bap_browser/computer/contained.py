"""The contained desktop on Hermes' base (spec 22.6, arrangement B): the driver is mounted into the
desktop's container at the start, and the dock is named as the driver, so that Hermes' code talks
to it through `docker exec`. The container has no network: the driver is fetched here, by its
checksum, kept on this machine, and mounted in. Copying it into a running container instead broke
under a rootless container program: writing to one path required remounting a read-only bind of
another (an app a person has not allowed), which the rootless program could not do."""

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


def fetch_the_driver(computer: Computer, home: Path) -> Path:
    """The pinned driver for the container's own system, fetched once by its checksum and kept on
    this machine, for the caller to mount into the desktop's container at its start. A container
    run once and thrown away tells the architecture; nothing is written into the real one here."""
    program, wait = computer.container_command, computer.command_timeout_s
    try:
        asked = subprocess.run(
            [program, "run", "--rm", computer.image, "uname", "-m"],
            capture_output=True,
            text=True,
            timeout=wait,
            check=True,
        )
        target = driver.target("linux", asked.stdout.strip())
        kept = home / KEPT_IN
        return driver.installed(kept, target_name=target) or driver.install(
            kept, target_name=target, timeout_s=computer.base.install_timeout_s
        )
    except driver.DriverError as wrong:
        raise BrowserError(str(wrong), reason="the driver could not be installed") from wrong
    except (OSError, subprocess.SubprocessError) as wrong:
        raise BrowserError(
            f"The driver could not be fetched for the desktop's container: {wrong}",
            reason="the driver could not be fetched",
        ) from wrong
