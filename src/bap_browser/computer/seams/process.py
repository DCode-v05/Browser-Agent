"""How the copied code starts another program: with a clean environment and no window."""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import sys
from collections.abc import Coroutine, Mapping
from concurrent.futures import Future
from typing import Any

# A variable whose name has one of these words in it holds something the driver must not be given:
# a model's key, the service's token, a Tailscale key.
SECRET_WORDS = frozenset(
    {"KEY", "KEYS", "APIKEY", "AUTHKEY", "TOKEN", "TOKENS", "SECRET", "SECRETS", "PASSWORD", "PASSWD"}
    | {"CREDENTIAL", "CREDENTIALS", "AUTH"}
)
log = logging.getLogger(__name__)


def is_secret(name: str) -> bool:
    return any(word in SECRET_WORDS for word in name.upper().replace("-", "_").split("_"))


def sanitize_subprocess_env(
    base_env: Mapping[str, str] | None, extra_env: Mapping[str, str] | None = None
) -> dict[str, str]:
    """The environment for a program that is not ours, such as the driver: nothing secret in it.
    What the caller adds itself (`extra_env`) is kept."""
    kept = {name: value for name, value in (base_env or {}).items() if not is_secret(name)}
    return {**kept, **(extra_env or {})}


def served_profile_child_env(
    base: Mapping[str, str] | None = None, *, inherit_credentials: bool = False, **more: Any
) -> dict[str, str]:
    """The environment for the contained desktop's own programs."""
    environment = sanitize_subprocess_env(os.environ if base is None else base)
    environment["HERMES_REAL_HOME"] = os.path.expanduser("~")
    return environment


def windows_hide_flags() -> int:
    """On Windows, the flag that keeps a console window from flashing up. Nothing elsewhere."""
    return subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


def safe_schedule_threadsafe(
    coro: Coroutine[Any, Any, Any], loop: asyncio.AbstractEventLoop | None, **more: Any
) -> Future[Any] | None:
    """Hands a coroutine to a loop that runs on another thread. None, with the coroutine closed,
    when the loop is not there."""
    if loop is None or loop.is_closed():
        coro.close()
        return None
    try:
        return asyncio.run_coroutine_threadsafe(coro, loop)
    except RuntimeError as wrong:
        coro.close()
        log.debug("The loop took no coroutine: %s", wrong)
        return None
