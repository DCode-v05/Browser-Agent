"""Computer use on Hermes' base (spec 22.2, 22.3): the copied tool, called as the engine calls it."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from bap_browser import computer
from bap_browser.computer.hermes.computer_use.backend import (
    ActionResult,
    CaptureResult,
    ComputerUseBackend,
    UIElement,
)
from bap_browser.config import Config

TAKEN = Path(computer.__file__).parent / "hermes"


class StandIn(ComputerUseBackend):
    """A backend with one window that holds one button. It records what it is asked to do."""

    def __init__(self) -> None:
        self.done: list[tuple[str, dict[str, Any]]] = []

    def start(self) -> None:
        self.done.append(("start", {}))

    def stop(self) -> None:
        self.done.append(("stop", {}))

    def is_available(self) -> bool:
        return True

    def capture(
        self, mode: str = "som", app: str | None = None, pid: int | None = None, window_id: int | None = None
    ) -> CaptureResult:
        self.done.append(("capture", {"mode": mode, "app": app}))
        save = UIElement(index=1, role="AXButton", label="Save", bounds=(10, 10, 80, 24))
        return CaptureResult(
            mode=mode, width=800, height=600, png_b64=None, elements=[save], app="Notes", window_title="Note"
        )

    def click(self, **how: Any) -> ActionResult:
        self.done.append(("click", how))
        return ActionResult(ok=True, action="click")

    def drag(self, **how: Any) -> ActionResult:
        return ActionResult(ok=True, action="drag")

    def scroll(self, **how: Any) -> ActionResult:
        return ActionResult(ok=True, action="scroll")

    def type_text(self, text: str, **how: Any) -> ActionResult:
        self.done.append(("type", {"characters": len(text)}))
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


@pytest.fixture
def desk(tmp_path: Path) -> Iterator[StandIn]:
    backend = StandIn()
    with computer.base(Config(), home=tmp_path, backend=lambda: backend):
        yield backend


def said(result: Any) -> dict[str, Any]:
    assert isinstance(result, str), result
    answer = json.loads(result)
    assert isinstance(answer, dict)
    return answer


def test_a_capture_names_each_element_by_a_number(desk: StandIn) -> None:
    answer = said(computer.computer_use({"action": "capture", "mode": "ax"}, session="one"))

    assert answer["app"] == "Notes"
    assert [(element["index"], element["label"]) for element in answer["elements"]] == [(1, "Save")]


def test_a_hard_blocked_key_is_refused_before_anybody_is_asked(desk: StandIn) -> None:
    asked: list[str] = []
    computer.ask_with(lambda action, about: asked.append(action) or True)

    answer = said(computer.computer_use({"action": "key", "keys": "ctrl-alt-delete"}, session="one"))

    assert "blocked key combo" in answer["error"]
    assert asked == []
    assert ("key", {"keys": "ctrl-alt-delete"}) not in desk.done


def test_an_action_that_changes_something_is_refused_when_nobody_can_be_asked(desk: StandIn) -> None:
    answer = said(computer.computer_use({"action": "click", "element": 1}, session="one"))

    assert "error" in answer
    assert not [name for name, _ in desk.done if name == "click"]


def test_an_action_the_person_allows_reaches_the_backend(desk: StandIn) -> None:
    asked: list[str] = []
    computer.ask_with(lambda action, about: asked.append(action) or True)

    computer.computer_use({"action": "capture", "mode": "ax"}, session="one")
    answer = said(computer.computer_use({"action": "click", "element": 1}, session="one"))

    assert answer["ok"] is True
    assert asked == ["click"]
    assert [how["element"] for name, how in desk.done if name == "click"] == [1]


def test_an_action_the_person_refuses_does_not_reach_the_backend(desk: StandIn) -> None:
    computer.ask_with(lambda action, about: False)

    answer = said(computer.computer_use({"action": "type", "text": "hello"}, session="one"))

    assert "error" in answer
    assert not [name for name, _ in desk.done if name == "type"]


def test_what_is_typed_is_not_in_the_question_put_to_the_person(desk: StandIn) -> None:
    put: list[str] = []
    computer.ask_with(lambda action, about: put.append(about) or True)

    computer.computer_use({"action": "capture", "mode": "ax"}, session="one")
    computer.computer_use({"action": "type", "text": "my secret words"}, session="one")

    assert put, "the person was not asked"
    assert all("my secret words" not in about for about in put)


def test_the_settings_of_the_configuration_reach_the_copied_code(tmp_path: Path) -> None:
    config = Config.model_validate(
        {"computer": {"base": {"max_image_dimension": 900, "ax_max_elements": 50}}}
    )
    with computer.base(config, home=tmp_path, backend=StandIn):
        seen = computer.settings_seen()

    assert seen["computer_use"]["max_image_dimension"] == 900
    assert seen["computer_use"]["ax_max_elements"] == 50
    assert seen["computer_use"]["cua_telemetry"] is False


def test_the_driver_is_started_without_keys_and_with_its_telemetry_off(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-not-for-the-driver")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-not-for-the-driver")
    monkeypatch.setenv("BAP_BROWSER_SERVICE_TOKEN", "a-service-token")
    monkeypatch.setenv("TS_AUTHKEY", "tskey-auth-not-for-the-driver")
    monkeypatch.setenv("EDITOR_OF_CHOICE", "kept")

    with computer.base(Config(), home=tmp_path, backend=StandIn):
        environment = computer.driver_environment()

    assert "OPENAI_API_KEY" not in environment
    assert "ANTHROPIC_API_KEY" not in environment
    assert "BAP_BROWSER_SERVICE_TOKEN" not in environment
    assert "TS_AUTHKEY" not in environment
    assert environment["EDITOR_OF_CHOICE"] == "kept"
    assert environment["CUA_DRIVER_RS_TELEMETRY_ENABLED"] == "0"


def test_every_copied_file_is_as_it_was_taken_and_says_where_it_is_from() -> None:
    taken = json.loads((TAKEN / "TAKEN.json").read_text(encoding="utf-8"))

    assert taken["commit"]
    assert len(taken["files"]) > 15
    for name, record in taken["files"].items():
        data = (TAKEN / name).read_bytes()
        assert hashlib.sha256(data).hexdigest() == record["sha256"], f"{name} was changed by hand"
        if name.endswith(".py"):
            assert data.startswith(b"# Taken from NousResearch/hermes-agent"), name
    assert "MIT License" in (TAKEN / "LICENSE").read_text(encoding="utf-8")
