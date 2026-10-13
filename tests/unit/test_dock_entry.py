"""Starting the contained desktop's own screen from inside its container (spec 22.2, piece 5): the
admin's settings reach Hermes' code, and asking the container to stop stops the desktop too."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from bap_browser.computer import dock_entry
from bap_browser.computer.seams.state import current, work_for


@pytest.fixture(autouse=True)
def the_seams_state_is_left_as_it_was() -> Iterator[None]:
    """`dock_entry.main` sets what the copied code works for and never restores it: it is the
    container's one process. A test must put it back."""
    before = current()
    yield
    work_for(before)


def and_then_stop(monkeypatch: pytest.MonkeyPatch) -> None:
    """Has `main`'s wait loop stop on its first look, by calling the handler it registered
    directly: a real OS signal is not reliable to raise from the same process on every platform a
    test may run on."""
    caught: list[Any] = []
    real_signal = dock_entry.signal.signal

    def signal(sig: int, handler: Any) -> Any:
        caught.append(handler)
        return real_signal(sig, handler)

    monkeypatch.setattr(dock_entry.signal, "signal", signal)
    monkeypatch.setattr(dock_entry.time, "sleep", lambda _: caught[0](dock_entry.signal.SIGTERM, None))


def test_the_admins_settings_reach_hermes_code(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(dock_entry.SETTINGS, '{"geometry": "1024x768", "idle_stop_minutes": 10}')
    seen: dict[str, Any] = {}

    def start() -> str:
        seen["geometry"] = current().computer.base.desktop.geometry
        seen["idle_stop_minutes"] = current().computer.base.desktop.idle_stop_minutes
        and_then_stop(monkeypatch)
        return "started"

    monkeypatch.setattr(dock_entry.runtime, "start", start)
    monkeypatch.setattr(dock_entry.runtime, "stop", lambda: True)

    assert dock_entry.main() == 0
    assert seen == {"geometry": "1024x768", "idle_stop_minutes": 10}


def test_with_no_settings_given_hermes_own_defaults_apply(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(dock_entry.SETTINGS, raising=False)
    and_then_stop(monkeypatch)
    monkeypatch.setattr(dock_entry.runtime, "start", lambda: "started")
    monkeypatch.setattr(dock_entry.runtime, "stop", lambda: True)

    assert dock_entry.main() == 0


def test_a_desktop_that_cannot_start_is_said_plainly(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv(dock_entry.SETTINGS, raising=False)

    def start() -> str:
        raise RuntimeError("Bot Desktop needs tigervnc-standalone-server on the gateway host")

    monkeypatch.setattr(dock_entry.runtime, "start", start)

    assert dock_entry.main() == 1
    assert "tigervnc" in capsys.readouterr().err


def test_asked_to_stop_it_stops_the_desktop_before_it_ends(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(dock_entry.SETTINGS, raising=False)
    stopped = False

    def stop() -> bool:
        nonlocal stopped
        stopped = True
        return True

    and_then_stop(monkeypatch)
    monkeypatch.setattr(dock_entry.runtime, "start", lambda: "started")
    monkeypatch.setattr(dock_entry.runtime, "stop", stop)

    dock_entry.main()

    assert stopped is True
