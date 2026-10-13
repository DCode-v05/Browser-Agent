"""A real machine in the window (spec 22.3.1, 22.10.1): the person's Take over and Stop reach
Hermes' own gate on the screen, and the page says what the machine still lacks."""

from __future__ import annotations

import base64
import json
import sys
from pathlib import Path
from typing import Any

import pytest

from bap_browser import computer
from bap_browser.agent import machine_setup
from bap_browser.agent.studio import ACTIONS
from bap_browser.computer import commands, driver
from bap_browser.computer.hermes.computer_use.backend import ActionResult, CaptureResult, ComputerUseBackend
from bap_browser.driver.hermes_driver import HermesDriver
from bap_browser.errors import BrowserError
from bap_browser.service.session import ServiceSession
from bap_browser.settings.catalogue import CATALOGUE
from bap_browser.settings.kinds import Choice
from bap_browser.tools.computer_tools import computer_tools_for

A_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + (64).to_bytes(4, "big") * 2 + b"the screen"


class Desk(ComputerUseBackend):
    def __init__(self) -> None:
        self.done: list[str] = []

    def start(self) -> None: ...

    def stop(self) -> None: ...

    def is_available(self) -> bool:
        return True

    def capture(
        self, mode: str = "som", app: str | None = None, pid: int | None = None, window_id: int | None = None
    ) -> CaptureResult:
        self.done.append(f"capture {app or 'window'}")
        whole = app == "screen"
        return CaptureResult(
            mode=mode,
            width=64,
            height=64,
            png_b64=base64.b64encode(A_PNG).decode() if whole else None,
            app="Notes",
        )

    def click(self, **how: Any) -> ActionResult:
        self.done.append("click")
        return ActionResult(ok=True, action="click")

    def drag(self, **how: Any) -> ActionResult:
        return ActionResult(ok=True, action="drag")

    def scroll(self, **how: Any) -> ActionResult:
        return ActionResult(ok=True, action="scroll")

    def type_text(self, text: str, **how: Any) -> ActionResult:
        return ActionResult(ok=True, action="type")

    def key(self, keys: str, **how: Any) -> ActionResult:
        return ActionResult(ok=True, action="key")

    def set_value(self, value: str, element: int | None = None) -> ActionResult:
        return ActionResult(ok=True, action="set_value")

    def list_apps(self) -> list[dict[str, Any]]:
        return []

    def focus_app(self, app: str, raise_window: bool = False) -> ActionResult:
        return ActionResult(ok=True, action="focus_app")


def on_a_machine(make_config, tmp_path: Path) -> tuple[ServiceSession, HermesDriver, Desk]:
    config = make_config(tmp_path, computer={"runs": "machine", "base": {"home": str(tmp_path / "home")}})
    desk = Desk()
    driver = HermesDriver(config, backend=lambda: desk)
    session = ServiceSession(
        config, driver, name="computer", backend="contained_desktop", tools=computer_tools_for
    )
    return session, driver, desk


def refused_by_the_tool_itself(action: str) -> str | None:
    """Hermes' tool called past this engine's own gate, as a call already on its way would reach it.
    The code of its refusal, or None when it ran."""
    answer = json.loads(
        computer.computer_use({"action": action, "mode": "ax", "element": 1}, session="computer")
    )
    return answer.get("code") if "error" in answer else None


async def test_while_a_person_has_taken_over_the_tool_itself_does_nothing_not_even_look(
    make_config, tmp_path: Path
) -> None:
    session, _, desk = on_a_machine(make_config, tmp_path)
    await session.start()
    try:
        await session.toolkit.call("computer_use", {"action": "capture", "mode": "ax"})
        await session.handle({"type": "take_over"})
        looked, acted = refused_by_the_tool_itself("capture"), refused_by_the_tool_itself("click")
        seen_meanwhile = list(desk.done)
        await session.handle({"type": "hand_back"})
        after = refused_by_the_tool_itself("capture")
    finally:
        await session.close()

    assert (looked, acted) == ("human_has_control", "human_has_control")
    assert "click" not in seen_meanwhile
    assert after is None


async def test_the_person_who_has_taken_over_still_sees_the_screen(make_config, tmp_path: Path) -> None:
    session, driver, _ = on_a_machine(make_config, tmp_path)
    await session.start()
    try:
        await session.handle({"type": "take_over"})
        shot = await driver.screenshot(full_page=False, annotate=False)
    finally:
        await session.close()

    assert shot.picture.data == A_PNG
    assert (shot.width, shot.height) == (64, 64)


async def test_a_take_over_left_behind_by_a_session_that_ended_does_not_hold_the_next_one(
    make_config, tmp_path: Path
) -> None:
    first, _, _ = on_a_machine(make_config, tmp_path)
    await first.start()
    await first.handle({"type": "take_over"})
    await first.close()

    second, _, _ = on_a_machine(make_config, tmp_path)
    await second.start()
    try:
        seen = await second.toolkit.call("computer_use", {"action": "capture", "mode": "ax"})
    finally:
        await second.close()

    assert not seen.is_error, seen.text


async def test_after_stop_nothing_more_reaches_the_machine(make_config, tmp_path: Path) -> None:
    session, _, desk = on_a_machine(make_config, tmp_path)
    await session.start()
    await session.toolkit.call("computer_use", {"action": "capture", "mode": "ax"})
    await session.handle({"type": "stop"})
    before = list(desk.done)

    clicked = await session.toolkit.call("computer_use", {"action": "click", "element": 1})

    assert clicked.is_error or "ended" in clicked.text.lower()
    assert desk.done == before


async def test_a_machine_with_no_driver_does_not_start_and_says_what_to_do(
    make_config, tmp_path: Path
) -> None:
    config = make_config(tmp_path, computer={"runs": "machine", "base": {"home": str(tmp_path / "empty")}})
    session = ServiceSession(
        config, HermesDriver(config), name="computer", backend="contained_desktop", tools=computer_tools_for
    )

    with pytest.raises(BrowserError, match="not installed"):
        await session.start()
    await session.close()


def test_the_settings_offer_this_machine_and_a_machine_elsewhere() -> None:
    runs = next(entry for entry in CATALOGUE if isinstance(entry, Choice) and entry.id == "computer_runs")

    assert [option.value for option in runs.options] == ["container", "machine", "remote"]


def test_what_a_machine_lacks_is_said_in_words_a_person_can_act_on(make_config, tmp_path: Path) -> None:
    config = make_config(tmp_path, computer={"runs": "machine", "base": {"home": str(tmp_path / "empty")}})

    lacks = computer.lacks(config)

    assert lacks is not None and lacks.what == "driver"
    assert "not installed" in lacks.said


# What the page's two buttons do (the admin's, in the window).


def a_config(make_config, tmp_path: Path, runs: str = "machine"):
    return make_config(tmp_path, computer={"runs": runs, "base": {"home": str(tmp_path / "home")}})


def test_the_buttons_are_for_a_page_set_to_this_machine(make_config, tmp_path: Path) -> None:
    assert {"install", "allow"} <= set(ACTIONS)

    why_not = machine_setup.make_ready(a_config(make_config, tmp_path, "container"), "install")

    assert why_not is not None and "This machine" in why_not


def test_install_fetches_the_driver_into_the_machines_folder(
    make_config, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fetched: list[Path] = []
    monkeypatch.setattr(driver, "install", lambda home, **how: fetched.append(home) or home / "cua-driver")
    monkeypatch.setattr(commands, "not_ready", lambda config, binary: None)

    why_not = machine_setup.make_ready(a_config(make_config, tmp_path), "install")

    assert why_not is None
    assert fetched == [tmp_path / "home"]


def test_a_download_that_fails_is_said_and_does_not_raise(
    make_config, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fails(home: Path, **how: Any) -> Path:
        raise driver.DriverError("The driver could not be downloaded.")

    monkeypatch.setattr(driver, "install", fails)

    why_not = machine_setup.make_ready(a_config(make_config, tmp_path), "install")

    assert why_not == "The driver could not be downloaded."


@pytest.mark.skipif(sys.platform == "darwin", reason="on macOS the button has the system ask")
def test_where_nothing_needs_allowing_the_button_says_so(make_config, tmp_path: Path) -> None:
    why_not = machine_setup.make_ready(a_config(make_config, tmp_path), "allow")

    assert why_not is not None and "Only macOS" in why_not
