"""Hermes' `computer_use` tool behind this engine's session (spec 22.4): what an agent is offered
on a machine, and what the check, the log and the timeline make of each action."""

from __future__ import annotations

import asyncio
import base64
import shutil
from pathlib import Path
from typing import Any

import pytest

from bap_browser.agent.loop import instructions_for
from bap_browser.computer.hermes.computer_use.backend import (
    ActionResult,
    CaptureResult,
    ComputerUseBackend,
    UIElement,
)
from bap_browser.computer.hermes.computer_use.schema import COMPUTER_USE_SCHEMA
from bap_browser.driver.hermes_driver import HermesDriver
from bap_browser.service.session import ServiceSession
from bap_browser.tools.computer_tools import computer_tools_for
from bap_browser.tools.computer_use_tool import ComputerUseArgs
from bap_browser.tools.event_log import masked
from bap_browser.tools.sentences import label_for, summary_for


class Desk(ComputerUseBackend):
    """A backend with one window, Notes, that holds a Save button and a field."""

    def __init__(self) -> None:
        self.done: list[tuple[str, dict[str, Any]]] = []

    def start(self) -> None: ...

    def stop(self) -> None:
        self.done.append(("stop", {}))

    def is_available(self) -> bool:
        return True

    def capture(
        self, mode: str = "som", app: str | None = None, pid: int | None = None, window_id: int | None = None
    ) -> CaptureResult:
        self.done.append(("capture", {"mode": mode, "app": app}))
        elements = [
            UIElement(index=1, role="AXButton", label="Save", bounds=(10, 10, 80, 24)),
            UIElement(index=2, role="AXTextField", label="Title", bounds=(10, 50, 200, 24)),
        ]
        return CaptureResult(
            mode=mode, width=800, height=600, elements=elements, app="Notes", window_title="My note"
        )

    def click(self, **how: Any) -> ActionResult:
        self.done.append(("click", how))
        return ActionResult(ok=True, action="click", effect="confirmed")

    def drag(self, **how: Any) -> ActionResult:
        return ActionResult(ok=True, action="drag")

    def scroll(self, **how: Any) -> ActionResult:
        return ActionResult(ok=True, action="scroll")

    def type_text(self, text: str, **how: Any) -> ActionResult:
        self.done.append(("type", {"text": text}))
        return ActionResult(ok=True, action="type")

    def key(self, keys: str, **how: Any) -> ActionResult:
        self.done.append(("key", {"keys": keys}))
        return ActionResult(ok=True, action="key")

    def set_value(self, value: str, element: int | None = None) -> ActionResult:
        return ActionResult(ok=True, action="set_value")

    def list_apps(self) -> list[dict[str, Any]]:
        return [{"name": "Notes", "pid": 7}]

    def focus_app(self, app: str, raise_window: bool = False) -> ActionResult:
        return ActionResult(ok=True, action="focus_app")


def on_a_machine(make_config, tmp_path: Path, **sections: Any) -> tuple[ServiceSession, Desk]:
    computer = {"runs": "machine", "base": {"home": str(tmp_path / "home")}}
    config = make_config(tmp_path, computer=computer, **sections)
    desk = Desk()
    driver = HermesDriver(config, backend=lambda: desk)
    session = ServiceSession(
        config, driver, name="computer", backend="contained_desktop", tools=computer_tools_for
    )
    return session, desk


def did(desk: Desk, name: str) -> list[dict[str, Any]]:
    return [how for done, how in desk.done if done == name]


def test_on_a_machine_the_agent_is_offered_hermes_tool_and_two_of_ours(make_config, tmp_path: Path) -> None:
    config = make_config(tmp_path, computer={"runs": "machine"})

    offered = [tool.name for tool in computer_tools_for(config)]

    assert sorted(offered) == ["computer_open_app", "computer_request_human", "computer_use"]


def test_the_tool_takes_what_hermes_tool_takes() -> None:
    theirs = COMPUTER_USE_SCHEMA["parameters"]["properties"]
    ours = ComputerUseArgs.model_json_schema()["properties"]

    assert set(ours) == set(theirs)
    assert ours["action"]["enum"] == theirs["action"]["enum"]
    assert ComputerUseArgs.model_json_schema()["required"] == ["action"]


async def test_a_capture_is_plain_text_that_numbers_the_elements(make_config, tmp_path: Path) -> None:
    session, _ = on_a_machine(make_config, tmp_path)
    await session.start()
    try:
        seen = await session.toolkit.call("computer_use", {"action": "capture", "mode": "ax"})
    finally:
        await session.close()

    assert not seen.is_error, seen.text
    assert not seen.text.lstrip().startswith("{")
    assert "#1" in seen.text and "Save" in seen.text
    assert "#2" in seen.text and "Title" in seen.text


async def test_a_click_on_an_element_reaches_the_machine_and_says_what_to_do_next(
    make_config, tmp_path: Path
) -> None:
    session, desk = on_a_machine(make_config, tmp_path)
    await session.start()
    try:
        await session.toolkit.call("computer_use", {"action": "capture", "mode": "ax"})
        clicked = await session.toolkit.call("computer_use", {"action": "click", "element": 1})
    finally:
        await session.close()

    assert not clicked.is_error, clicked.text
    assert [how["element"] for how in did(desk, "click")] == [1]
    assert not clicked.text.lstrip().startswith("{")
    assert "click" in clicked.text.lower()


async def test_what_is_typed_reaches_the_machine_and_no_result(make_config, tmp_path: Path) -> None:
    session, desk = on_a_machine(make_config, tmp_path)
    await session.start()
    try:
        await session.toolkit.call("computer_use", {"action": "capture", "mode": "ax"})
        typed = await session.toolkit.call("computer_use", {"action": "type", "text": "hunter2 is mine"})
    finally:
        await session.close()

    assert did(desk, "type") == [{"text": "hunter2 is mine"}]
    assert "hunter2" not in typed.text


def test_the_timeline_says_what_was_done_on_the_machine_and_never_what_was_typed() -> None:
    assert label_for("computer_use", {"action": "capture"}, None) == "Looking at the screen"
    assert summary_for("computer_use", {"action": "click", "element": 4}, None, None) == "Clicked element 4"
    assert summary_for("computer_use", {"action": "click", "coordinate": [120, 48]}, None, None) == (
        "Clicked at 120, 48"
    )
    assert summary_for("computer_use", {"action": "type", "text": "my secret"}, None, None) == (
        "Typed 9 characters"
    )
    assert summary_for("computer_use", {"action": "key", "keys": "cmd+s"}, None, None) == "Pressed cmd+s"
    assert summary_for("computer_use", {"action": "key", "keys": "x"}, None, None) == "Pressed a key"
    assert summary_for("computer_use", {"action": "set_value", "value": "Blue"}, None, None) == "Set a value"
    # The log keeps the length of what is typed or set, never the text.
    assert masked({"action": "type", "text": "my secret"}, lambda text: text) == {
        "action": "type",
        "text": "<9 characters>",
    }
    assert masked({"action": "set_value", "value": "Blue"}, lambda text: text)["value"] == "<4 characters>"


async def test_a_hard_blocked_key_comes_back_as_a_failure(make_config, tmp_path: Path) -> None:
    session, desk = on_a_machine(make_config, tmp_path)
    await session.start()
    try:
        pressed = await session.toolkit.call("computer_use", {"action": "key", "keys": "cmd+shift+q"})
    finally:
        await session.close()

    assert pressed.is_error
    assert "blocked" in pressed.text
    assert did(desk, "key") == []


async def test_with_ask_before_every_action_a_capture_runs_and_a_click_waits_for_a_person(
    make_config, tmp_path: Path
) -> None:
    session, desk = on_a_machine(make_config, tmp_path, safety={"ask_before": "every_action"})
    await session.start()
    try:
        seen = await session.toolkit.call("computer_use", {"action": "capture", "mode": "ax"})
        clicked = await session.toolkit.call("computer_use", {"action": "click", "element": 1})
    finally:
        await session.close()

    assert not seen.is_error, seen.text
    assert clicked.is_error
    assert did(desk, "click") == []


async def test_a_deployment_that_denies_the_tool_runs_none_of_it(make_config, tmp_path: Path) -> None:
    session, desk = on_a_machine(make_config, tmp_path, safety={"action_policies": {"computer_use": "deny"}})
    await session.start()
    try:
        seen = await session.toolkit.call("computer_use", {"action": "capture", "mode": "ax"})
    finally:
        await session.close()

    assert seen.is_error
    # The viewer may look at the whole screen. The agent's own capture, of a window, did not run.
    assert [how for how in did(desk, "capture") if how["mode"] == "ax"] == []


async def test_the_driver_is_stopped_when_the_session_ends(make_config, tmp_path: Path) -> None:
    session, desk = on_a_machine(make_config, tmp_path)
    await session.start()
    await session.toolkit.call("computer_use", {"action": "capture", "mode": "ax"})

    await session.close()

    assert did(desk, "stop") == [{}]


@pytest.mark.parametrize("action", ["capture", "wait", "list_apps", "list_windows"])
async def test_an_action_that_only_looks_is_never_counted_as_acting(
    action: str, make_config, tmp_path: Path
) -> None:
    session, _ = on_a_machine(make_config, tmp_path, safety={"ask_before": "every_action"})
    await session.start()
    try:
        looked = await session.toolkit.call("computer_use", {"action": action, "seconds": 0.01})
    finally:
        await session.close()

    assert not looked.is_error, looked.text


def test_the_model_is_given_this_engines_rules_and_then_hermes_own_manual(
    make_config, tmp_path: Path
) -> None:
    told = instructions_for(make_config(tmp_path, computer={"runs": "machine"}))

    ours, theirs = told.index("computer_request_human"), told.index("The verify → escalate ladder")
    assert ours < theirs
    assert "Capture first" in told
    # The manual's own heading for a skill of Hermes is not an instruction to this model.
    assert not told.lstrip().startswith("---")


def test_the_manual_can_be_left_out(make_config, tmp_path: Path) -> None:
    told = instructions_for(make_config(tmp_path, computer={"runs": "machine", "base": {"manual": False}}))

    assert "computer_request_human" in told
    assert "The verify → escalate ladder" not in told


@pytest.mark.skipif(shutil.which("Xvfb") is not None, reason="this machine has a virtual screen to start")
async def test_a_machine_that_is_to_start_its_own_screen_and_has_none_says_what_it_lacks(
    make_config, tmp_path: Path
) -> None:
    computer = {"runs": "machine", "base": {"home": str(tmp_path / "home"), "virtual_screen": True}}
    config = make_config(tmp_path, computer=computer)
    session = ServiceSession(
        config,
        HermesDriver(config, backend=Desk),
        name="computer",
        backend="contained_desktop",
        tools=computer_tools_for,
    )

    seen = await session.toolkit.call("computer_use", {"action": "capture", "mode": "ax"})
    await session.close()

    assert seen.is_error
    assert "virtual screen" in seen.text


class Screen(Desk):
    """A machine whose whole screen is one picture, which a test can change."""

    def __init__(self) -> None:
        super().__init__()
        self.showing = b"first"

    def capture(
        self, mode: str = "som", app: str | None = None, pid: int | None = None, window_id: int | None = None
    ) -> CaptureResult:
        # A real PNG's first bytes and size, then what the test says is on the screen.
        png = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + (64).to_bytes(4, "big") * 2 + self.showing
        return CaptureResult(
            mode=mode, width=64, height=64, png_b64=base64.b64encode(png).decode(), app="screen"
        )


async def test_a_screen_that_stands_still_is_shown_once_and_again_when_it_changes(
    make_config, tmp_path: Path
) -> None:
    computer = {"runs": "machine", "frame_ms": 1, "base": {"home": str(tmp_path / "home")}}
    config = make_config(tmp_path, computer=computer)
    screen = Screen()
    driver = HermesDriver(config, backend=lambda: screen)
    frames: list[bytes] = []
    first, changed = asyncio.Event(), asyncio.Event()

    def shown(frame: bytes) -> None:
        frames.append(frame)
        first.set()
        if len(frames) == 2:
            changed.set()

    await driver.start()
    try:
        await driver.start_frames(shown, config.viewer.quality_levels.standard)
        await asyncio.wait_for(first.wait(), 10)
        # Long enough for many more looks at a screen that does not change.
        for _ in range(20):
            await asyncio.sleep(0.01)
        still = len(frames)
        screen.showing = b"second"
        await asyncio.wait_for(changed.wait(), 10)
    finally:
        await driver.close()

    assert still == 1
    assert len(frames) == 2 and frames[0] != frames[1]
