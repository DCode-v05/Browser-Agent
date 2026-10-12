"""Hermes' settings file, answered from this engine's configuration (spec 22.8)."""

from __future__ import annotations

import contextlib
import os
from pathlib import Path
from typing import Any

from bap_browser.computer.seams.state import current

# `auto` leaves the choice to the copied code, which decides by the system.
OVERLAY = {"auto": None, "on": False, "off": True}


def load_config() -> dict[str, Any]:
    """The two blocks of Hermes' settings the copied code reads, in Hermes' names."""
    base = current().computer.base
    return {
        "computer_use": {
            "backend": "cua",
            "cua_telemetry": base.driver_telemetry,
            "autostart": base.autostart,
            "native_wayland": base.native_wayland,
            "max_image_dimension": base.max_image_dimension,
            "capture_after_mode": base.capture_after_mode,
            "ax_max_elements": base.ax_max_elements,
            "no_overlay": OVERLAY[base.no_overlay],
            "permission_mode": base.permission_mode if base.capability_manifest else "standard",
            "capability_manifest": base.capability_manifest or None,
            "allow_unsigned_driver": base.allow_unsigned_driver,
        },
        "bot_desktop": {
            "geometry": base.desktop.geometry,
            "auto_start": base.desktop.auto_start,
            "min_free_memory_mb": base.desktop.min_free_memory_mb,
            "idle_stop_minutes": base.desktop.idle_stop_minutes,
            "placement": base.desktop.placement,
        },
    }


load_config_readonly = load_config


def is_managed() -> bool:
    """Whether another program owns the folders' permissions. Here, none does."""
    return False


def secure_dir(path: Path) -> None:
    """Makes a folder its owner's alone."""
    with contextlib.suppress(OSError):
        os.chmod(path, 0o700)
