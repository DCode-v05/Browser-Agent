"""Writes the file that holds the agent to the allowed apps (spec 22.7).

`bounded` is the driver's own mode: given this file, it refuses an action outside what the file
names. The file is written here, from the allowed apps in the settings, one app named the way the
driver expects it on this system: a bundle id on macOS, an executable's path on Windows and Linux.
The schema is the driver's own (cua-driver, trycua/cua): https://cua.ai/docs/how-to-guides/driver/write-a-bounded-manifest

Full-screen capture is left open (`resources.desktop.display`), for the person's own live view
(spec 22.2, piece 11). Whether that also lets an action reach a window outside the allowed apps is
not yet proven against the real driver: see docs/status.md and remaining piece 3.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from bap_browser.config_computer import AllowedApps, Base

# The id of each app the settings can allow, in the order the manifest lists them.
APP_IDS = ("text_editor", "files", "calculator", "terminal")

# What each app is called to the driver on macOS: its bundle id.
BUNDLE_IDS: dict[str, str] = {
    "text_editor": "com.apple.TextEdit",
    "files": "com.apple.finder",
    "calculator": "com.apple.calculator",
    "terminal": "com.apple.Terminal",
}

# What each app is called to the driver on Windows and Linux: its executable's absolute path. The
# Linux paths are the contained desktop's own apps (`driver/contained_desktop.py`); neither they nor
# the Windows Calculator's path are yet proven on a person's own machine (remaining piece 8).
EXECUTABLES: dict[str, dict[str, str]] = {
    "win32": {
        "text_editor": r"C:\Windows\System32\notepad.exe",
        "files": r"C:\Windows\explorer.exe",
        "calculator": r"C:\Windows\System32\calc.exe",
        "terminal": r"C:\Windows\System32\cmd.exe",
    },
    "linux": {
        "text_editor": "/usr/bin/mousepad",
        "files": "/usr/bin/pcmanfm",
        "calculator": "/usr/bin/galculator",
        "terminal": "/usr/bin/xterm",
    },
}

# The driver tools the engine calls on an allowed app. One left out is refused before it is asked.
TOOLS = (
    "click",
    "double_click",
    "drag",
    "scroll",
    "type_text",
    "press_key",
    "hotkey",
    "set_value",
    "launch_app",
    "list_apps",
    "list_windows",
    "screenshot",
    "get_window_state",
    "bring_to_front",
    "get_config",
)

FILE_NAME = "capability-manifest.json"


def resource_for(app_id: str, platform: str) -> dict[str, Any] | None:
    """One allowed app, named as the driver on `platform` expects it. None where `platform` or
    `app_id` is not known."""
    if platform == "darwin":
        bundle_id = BUNDLE_IDS.get(app_id)
        return {"bundle_id": bundle_id, "launch": True, "windows": "all"} if bundle_id else None
    executable = EXECUTABLES.get(platform, {}).get(app_id)
    return {"executable": executable, "launch": True, "windows": "all"} if executable else None


def allowed_app_ids(apps: AllowedApps) -> list[str]:
    """The ids of the apps the settings allow, in `APP_IDS` order."""
    return [app_id for app_id in APP_IDS if getattr(apps, app_id)]


def build(apps: AllowedApps, base: Base, platform: str) -> dict[str, Any]:
    """The manifest `bounded` mode reads, for the allowed apps named on `platform`."""
    resources = [
        resource
        for app_id in allowed_app_ids(apps)
        if (resource := resource_for(app_id, platform)) is not None
    ]
    return {
        "version": 3,
        "expires_after": base.capability_expires_after,
        "idle_timeout": base.capability_idle_timeout,
        "allow": {"tools": list(TOOLS)},
        "resources": {"apps": resources, "desktop": {"display": True}},
    }


def write(home: Path, apps: AllowedApps, base: Base, platform: str) -> Path:
    """Writes the manifest under `home`, and returns its path."""
    home.mkdir(parents=True, exist_ok=True)
    path = home / FILE_NAME
    path.write_text(json.dumps(build(apps, base, platform)), encoding="utf-8")
    return path
