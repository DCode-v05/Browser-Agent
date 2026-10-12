"""Hermes' package manager, answered for the one package the copied code asks for: the driver."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from bap_browser.computer import driver
from bap_browser.computer.seams.state import current

NOT_INSTALLED = "The driver of computer use is not installed. Run `bap-browser computer install`."


@dataclass(frozen=True)
class Installed:
    binary: Path


def installed_package(name: str) -> Installed | None:
    """The driver that is installed, or None. It installs nothing. Another driver named in the
    settings, for development, comes before the pinned one."""
    command = current().computer.base.driver_command
    if command:
        found = shutil.which(command)
        return Installed(Path(found)) if found else None
    binary = driver.installed(current().home)
    return Installed(binary) if binary else None


def ensure(name: str) -> None:
    if installed_package(name) is None:
        raise RuntimeError(NOT_INSTALLED)


def ensure_import(name: str) -> None:
    """Hermes installs the MCP client when it is first needed. Here it is a dependency of the engine."""
