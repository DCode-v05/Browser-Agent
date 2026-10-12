"""Hermes can keep the contained desktop inside the sandbox its terminal runs in. This engine has no
such terminal: the desktop is on the machine the engine is on, which in the micro VM is the VM."""

from __future__ import annotations

import threading
from typing import Any

CHROMIUM_SANDBOX_BYPASS_ARGS: tuple[str, ...] = ()
NO_SANDBOX = "This engine keeps no desktop inside a terminal's sandbox."
# Hermes' names for the lock and the lookup of its terminal's sandbox. There is none to find.
_env_lock = threading.Lock()


def get_env_config() -> dict[str, Any]:
    """Where Hermes' terminal runs. `local` is this machine."""
    return {"env_type": "local"}


def _resolve_container_task_id(task: Any) -> str:
    return ""


def _lookup_active_env(task: Any, more: Any) -> None:
    return None


def terminal_tool(*given: Any, **named: Any) -> Any:
    raise RuntimeError(NO_SANDBOX)


class streams:
    """Hermes' pipes into a sandbox. Named as Hermes names it; nothing here opens one."""

    @staticmethod
    def open(*given: Any, **named: Any) -> Any:
        raise RuntimeError(NO_SANDBOX)


def pending() -> None:
    """A change of the sandbox's image that is waiting. There is never one."""
    return None


def chromium_executable() -> str | None:
    return None


def apparmor_restricts_unprivileged_userns() -> bool:
    return False


def needs_chromium_sandbox_bypass() -> bool:
    return False
