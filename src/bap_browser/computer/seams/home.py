"""Hermes' home folder, answered with the folder this engine keeps computer use in."""

from __future__ import annotations

import contextlib
import os
import sys
from pathlib import Path

from bap_browser.computer.seams.state import current


def get_hermes_home() -> Path:
    return current().home


def get_hermes_home_override() -> str | None:
    """Hermes serves several profiles from one process. This engine has one."""
    return None


def hermes_home_key(path: str | Path | None = None) -> str:
    """One name for a folder, however it was written."""
    folder = Path(path) if path is not None else get_hermes_home()
    return os.path.normcase(str(folder.expanduser().resolve(strict=False)))


def get_hermes_dir(new_subpath: str, old_name: str, *, home: Path | None = None) -> Path:
    return (home or get_hermes_home()) / new_subpath


def display_hermes_home(home: Path | None = None) -> str:
    return str(home or get_hermes_home())


def secure_parent_dir(path: Path) -> None:
    """Makes the folder a file is in its owner's alone, when it is a folder of ours."""
    parent = path.parent.resolve()
    if get_hermes_home().resolve() in (parent, *parent.parents):
        with contextlib.suppress(OSError):
            os.chmod(parent, 0o700)


def get_active_profile_name() -> str:
    return "default"


def is_wsl() -> bool:
    """Whether this is Linux inside Windows."""
    if sys.platform != "linux":
        return False
    try:
        return "microsoft" in Path("/proc/version").read_text(encoding="utf-8").lower()
    except OSError:
        return False
