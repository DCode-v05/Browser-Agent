"""Computer use on Hermes' base (spec 22).

`hermes/` is Hermes' own code, taken by `scripts/take_hermes.py` and never edited by hand. `seams/`
answers what that code asks of Hermes. This module is how the rest of the engine uses it.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from bap_browser.computer import allowed, contained, driver, remote
from bap_browser.computer.hermes.bot_desktop import lease
from bap_browser.computer.hermes.computer_use import cua_backend, permissions, tool
from bap_browser.computer.hermes.computer_use.backend import CaptureResult
from bap_browser.computer.seams import settings
from bap_browser.computer.seams.state import Asker, Working, current, work_for
from bap_browser.config import Config

# The whole screen, as Hermes' tool names it, and who holds it when a person takes over in the viewer.
THE_SCREEN = "screen"
THE_VIEWER = "viewer"
__all__ = [
    "ask_with",
    "base",
    "computer_use",
    "driver_environment",
    "home_of",
    "manual",
    "open_app",
    "settings_seen",
]


def home_of(config: Config) -> Path:
    """The folder computer use keeps its files in."""
    return Path(config.computer.base.home).expanduser()


@contextmanager
def base(
    config: Config,
    home: Path | None = None,
    backend: Callable[[], Any] | None = None,
    container: str | None = None,
) -> Iterator[None]:
    """Computer use for one configuration, with its files in `home` (the configuration's, unless
    another is given). On the way out every driver it started is stopped. `backend` names a backend
    to use in place of the driver."""
    home = home or home_of(config)
    elsewhere = config.computer.runs in ("mac", "remote")
    settings = remote.through_the_link(config.computer, home) if elsewhere else config.computer
    if container is not None:
        # The desktop is in a container, and so is its driver: the dock reaches it (spec 22.6).
        settings = contained.through_the_dock(settings, container)
    if allowed.held(settings) and backend is None:
        # The driver itself holds the agent to the apps the person allowed (spec 22.7).
        listed = str(allowed.write(home, settings))
        settings = settings.model_copy(
            update={"base": settings.base.model_copy(update={"capability_manifest": listed})}
        )
    before = work_for(Working(computer=settings, home=home, backend=backend))
    # A session that ended while a person held the screen must not hold the next one.
    lease.release()
    try:
        yield
    finally:
        tool.reset_backend_for_tests()
        work_for(before)
        if elsewhere:
            remote.forget(home)
        if container is not None:
            contained.forget()


def ask_with(ask: Asker | None) -> None:
    """Who is asked before an action that changes something. With nobody, such an action is refused."""
    current().ask = ask


def computer_use(arguments: dict[str, Any], session: str) -> Any:
    """One call of Hermes' `computer_use` tool. Text as a JSON string, or a dictionary that holds a
    picture."""
    return tool.handle_computer_use(arguments, session_id=session)


def open_app(name: str, session: str) -> bool:
    """Opens an app by its name, or brings it to the front. False when the backend opens none."""
    with tool._backend_for_call(session) as backend:
        launch = getattr(backend, "launch_app", None)
        if launch is None:
            return False
        launch(name=name)
        return True


def manual() -> str:
    """The manual Hermes gives a model for the tool, without the heading that files it among
    Hermes' skills."""
    text = (Path(__file__).parent / "hermes" / "skill" / "SKILL.md").read_text(encoding="utf-8")
    _, _, body = text.removeprefix("---").partition("\n---\n")
    return body.strip() if text.startswith("---") and body else text.strip()


@dataclass(frozen=True)
class Lacks:
    """What a machine still lacks before an agent can work on it, and how a person is told."""

    what: Literal["driver", "permission", "code"]
    said: str


def lacks(config: Config) -> Lacks | None:
    """What stands between this configuration and a session on the machine. None when nothing does.
    It is asked before a session begins, never during one."""
    settings = config.computer
    if settings.runs == "container":
        # The driver is put into the desktop's container when it starts. Nothing here is needed.
        return None
    if settings.runs == "remote":
        if os.environ.get(settings.helper_token_env):
            return None
        return Lacks(
            "code",
            f"The pairing code of the helper on the other machine is not set in {settings.helper_token_env}.",
        )
    if not settings.base.driver_command and driver.installed(home_of(config)) is None:
        return Lacks("driver", "The driver of computer use is not installed on this machine.")
    if sys.platform != "darwin":
        return None
    with base(config):
        status = permissions.computer_use_status()
    # Only a plain no counts. With the driver not yet running macOS gives no answer, and the first
    # capture will tell.
    missing = [
        name
        for field, name in (("accessibility", "Accessibility"), ("screen_recording", "Screen Recording"))
        if status.get(field) is False
    ]
    if missing:
        return Lacks(
            "permission", f"macOS has not allowed the driver, CuaDriver, under {' and '.join(missing)}."
        )
    return None


def person_holds(holds: bool) -> None:
    """A person has taken the screen, or given it back. While they hold it, Hermes' tool does
    nothing for the agent, not even a capture (spec 22.2.1)."""
    if holds:
        lease.acquire(THE_VIEWER, reason="A person has taken over in the viewer.")
    else:
        lease.release(THE_VIEWER)


def screen(session: str) -> CaptureResult:
    """The whole screen, for the person who watches. It is theirs to see whoever holds the screen,
    so it does not pass the gate the agent's own captures pass."""
    with tool._backend_for_call(session) as backend:
        return backend.capture(mode="vision", app=THE_SCREEN)


def settings_seen() -> dict[str, Any]:
    """The settings as the copied code reads them, in Hermes' names."""
    return settings.load_config()


def driver_environment() -> dict[str, str]:
    """The environment the driver is started with."""
    return cua_backend.sanitized_cua_driver_env()
