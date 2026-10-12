"""Computer use on Hermes' base (spec 22).

`hermes/` is Hermes' own code, taken by `scripts/take_hermes.py` and never edited by hand. `seams/`
answers what that code asks of Hermes. This module is how the rest of the engine uses it.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from bap_browser.computer.hermes.computer_use import cua_backend, tool
from bap_browser.computer.seams import settings
from bap_browser.computer.seams.state import Asker, Working, current, work_for
from bap_browser.config import Config

__all__ = ["ask_with", "base", "computer_use", "driver_environment", "settings_seen"]


@contextmanager
def base(config: Config, home: Path, backend: Callable[[], Any] | None = None) -> Iterator[None]:
    """Computer use for one configuration, with its files in `home`. On the way out every driver it
    started is stopped. `backend` names a backend to use in place of the driver."""
    before = work_for(Working(computer=config.computer, home=home, backend=backend))
    try:
        yield
    finally:
        tool.reset_backend_for_tests()
        work_for(before)


def ask_with(ask: Asker | None) -> None:
    """Who is asked before an action that changes something. With nobody, such an action is refused."""
    current().ask = ask


def computer_use(arguments: dict[str, Any], session: str) -> Any:
    """One call of Hermes' `computer_use` tool. Text as a JSON string, or a dictionary that holds a
    picture."""
    return tool.handle_computer_use(arguments, session_id=session)


def settings_seen() -> dict[str, Any]:
    """The settings as the copied code reads them, in Hermes' names."""
    return settings.load_config()


def driver_environment() -> dict[str, str]:
    """The environment the driver is started with."""
    return cua_backend.sanitized_cua_driver_env()
