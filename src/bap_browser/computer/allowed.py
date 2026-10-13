"""The apps an agent may work in on a real machine, as the driver itself enforces them (spec 22.7).

The settings name the apps a person allows. Here that list becomes the file the driver is started
with in its `bounded` mode: its capability manifest. The driver then refuses, by itself, to read
the elements of any other app's window or to act in it, whatever the agent asks. It may still see
the screen as a whole and the names of its windows. An app is named as its system names it: by its
bundle on macOS, by its program's full path on Windows and Linux.
"""

from __future__ import annotations

import os
import shutil
import sys
from collections.abc import Callable
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from bap_browser import private_file
from bap_browser.config_computer import Computer

FILE = "allowed.json"
# What each app the settings can allow is on each system, as the driver itself names it: a bundle on
# macOS, the identity the driver lists on Windows, a program on Linux. On Windows the text editor and
# the calculator are the ones the driver was seen to allow by these names (Windows Server 2025). The
# names it lists for File Explorer and Windows Terminal did not let it read their windows, so those
# two are not here: they are added with `computer.base.also_allowed` once their names are known.
APPS: dict[str, dict[str, str]] = {
    "text_editor": {
        "darwin": "com.apple.TextEdit",
        "win32": "%windir%\\system32\\notepad.exe",
        "linux": "mousepad",
    },
    "files": {"darwin": "com.apple.finder", "linux": "pcmanfm"},
    "calculator": {
        "darwin": "com.apple.calculator",
        "win32": "%windir%\\system32\\win32calc.exe",
        "linux": "galculator",
    },
    "terminal": {"darwin": "com.apple.Terminal", "linux": "xterm"},
}
# The driver's own tools that Hermes' backend calls. None of them updates the driver, changes its
# settings for good, runs a command or reads the clipboard.
TOOLS = (
    "start_session",
    "end_session",
    "check_permissions",
    "health_report",
    "get_config",
    "set_config",
    "set_agent_cursor_enabled",
    "list_apps",
    "list_windows",
    "get_window_state",
    "get_desktop_state",
    "click",
    "double_click",
    "drag",
    "scroll",
    "type_text",
    "press_key",
    "hotkey",
    "set_value",
    "launch_app",
    "bring_to_front",
)


def system_of(platform: str) -> str:
    return next((name for name in ("darwin", "win32", "linux") if platform.startswith(name)), "linux")


def held(computer: Computer) -> bool:
    """Whether the driver is to hold the agent to the allowed apps: on this machine, in `bounded`
    mode, and not where the person lets the agent open any app."""
    return (
        computer.runs == "machine" and computer.base.permission_mode == "bounded" and not computer.mac_any_app
    )


def is_a_program(named: str) -> bool:
    """Whether an app is named by its program's full path, on any system. Otherwise it is a bundle."""
    return PurePosixPath(named).is_absolute() or PureWindowsPath(named).is_absolute()


def an_app(named: str) -> dict[str, Any]:
    """One app as the driver's file names it."""
    return {"executable" if is_a_program(named) else "bundle_id": named, "launch": True}


def manifest(
    computer: Computer, platform: str | None = None, find: Callable[[str], str | None] = shutil.which
) -> dict[str, Any]:
    """The driver's capability manifest for the apps the settings allow, on one system. An app this
    machine does not have is left out: there is nothing of it to work in."""
    system = system_of(platform or sys.platform)
    apps: list[dict[str, Any]] = []
    for name, on in computer.apps.model_dump().items():
        if not on:
            continue
        named = APPS[name].get(system)
        # An identity is its own name. A program is named by where it is, with every link followed.
        full = find(named) if named and system == "linux" else named
        if full:
            apps.append(an_app(os.path.realpath(full) if os.path.exists(full) else full))
    apps += [an_app(more) for more in computer.base.also_allowed]
    return {
        "version": 3,
        "expires_after": computer.base.allowed_for,
        "idle_timeout": computer.base.allowed_idle,
        # The display may be looked at as a whole: the driver lists the windows before every capture,
        # and the person's live picture is of the whole screen. A window is read, and acted in, only
        # when its app is among `apps`.
        "resources": {"apps": apps, "desktop": {"display": True}},
        "allow": {"tools": list(TOOLS)},
    }


def write(home: Path, computer: Computer) -> Path:
    """Writes the file the driver is started with, for the engine's user alone to read."""
    private_file.write_json(home / FILE, manifest(computer), indent=1)
    return home / FILE
