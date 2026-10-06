"""The browsers of a window as systems, over HTTP (spec 9.17): each with settings of its own, and a
person's way to manage it, read its log, see what its tasks took, and run its checklist."""

import asyncio
import json
import urllib.error
import urllib.request
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from fakes import FakeDriver

from bap_browser.config import Config
from bap_browser.service.server import Service
from bap_browser.service.session import ServiceSession
from bap_browser.settings import SettingsStore

TOKEN = "a-token-for-the-tests-0123456789abcdef"
NAMES = ("cloud", "builtin")


@dataclass
class Asked:
    """Stands in for whoever runs the browsers: it answers, and remembers what it was asked."""

    asked: list[tuple[Any, ...]] = field(default_factory=list[tuple[Any, ...]])
    why_not: str | None = None

    def described(self) -> list[dict[str, Any]]:
        return [
            {"id": name, "backend": "remote_headless", "state": "agent", "enabled": True} for name in NAMES
        ]

    async def settings_changed(self, system: str) -> None:
        self.asked.append(("settings_changed", system))

    async def manage(self, system: str, action: str) -> str | None:
        self.asked.append(("manage", system, action))
        return self.why_not

    def log(self, system: str) -> dict[str, Any]:
        return {
            "path": f"/logs/{system}.jsonl",
            "lines": [{"tool": "browser_navigate", "ok": True}],
            "size": 40,
        }

    def evals(self, system: str) -> dict[str, Any]:
        return {"system": system, "tasks": {"count": 2}}

    def trace(self, system: str, task: str) -> dict[str, Any] | None:
        return {"id": task, "spans": []} if task == "t1" else None

    def rate(self, system: str, task: str, rating: Any) -> bool:
        self.asked.append(("rate", system, task, rating))
        return task == "t1"

    async def check(self, system: str) -> dict[str, Any] | str:
        self.asked.append(("check", system))
        return self.why_not or {"passed": 9, "failed": 0, "checks": []}


@dataclass
class Window:
    service: Service
    sessions: dict[str, ServiceSession]
    systems: Asked
    config: Config

    def _ask(self, method: str, path: str, body: Any, token: str | None) -> tuple[int, Any]:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(
            f"{self.service.address}{path}", data=data, headers=headers, method=method
        )
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                return response.status, json.loads(response.read() or b"null")
        except urllib.error.HTTPError as refused:
            said = refused.read()
            try:
                return refused.code, json.loads(said or b"null")
            except ValueError:
                # Not an answer of the API: a page of the viewer's own files.
                return refused.code, None

    async def ask(
        self, method: str, path: str, body: Any = None, *, token: str | None = TOKEN
    ) -> tuple[int, Any]:
        return await asyncio.to_thread(self._ask, method, path, body, token)


Open = Callable[..., Any]


@pytest.fixture
async def window(make_config: Callable[..., Config], tmp_path: Path) -> AsyncIterator[Open]:
    opened: list[Window] = []

    async def open_one(**sections: Any) -> Window:
        config = make_config(tmp_path, **sections)
        settings = SettingsStore(config)
        sessions = {
            name: ServiceSession(config, FakeDriver(), name=name, settings=settings) for name in NAMES
        }
        for session in sessions.values():
            await session.start()
        systems = Asked()
        service = Service(
            config,
            sessions,
            token=TOKEN,
            port=0,
            settings=settings,
            rooms=systems.described,
            systems=systems,
        )
        await service.start()
        opened.append(Window(service, sessions, systems, config))
        return opened[-1]

    yield open_one
    for one in opened:
        await one.service.stop()
        for session in one.sessions.values():
            await session.close()


async def test_the_systems_are_for_whoever_holds_the_token(window: Open) -> None:
    one = await window()
    for method, path in (
        ("GET", "/api/systems"),
        ("POST", "/api/systems/cloud/restart"),
        ("GET", "/api/systems/cloud/log"),
        ("GET", "/api/systems/cloud/evals"),
        ("GET", "/api/systems/cloud/evals/t1"),
        ("POST", "/api/systems/cloud/evals/t1/rating"),
        ("POST", "/api/systems/cloud/checks"),
    ):
        assert (await one.ask(method, path, token=None))[0] == 401, path
        assert (await one.ask(method, path, token="wrong"))[0] == 401, path
    assert one.systems.asked == []


async def test_the_window_is_told_its_browsers_are_systems(window: Open) -> None:
    one = await window()
    assert (await one.ask("GET", "/api/sessions"))[1]["systems"] is True
    status, told = await one.ask("GET", "/api/systems")
    assert status == 200 and [system["id"] for system in told["systems"]] == ["cloud", "builtin"]


async def test_a_person_starts_stops_and_restarts_a_system(window: Open) -> None:
    one = await window()
    status, told = await one.ask("POST", "/api/systems/builtin/restart")
    assert status == 200 and len(told["systems"]) == 2
    assert one.systems.asked == [("manage", "builtin", "restart")]
    # What cannot be done is said in a sentence, for the person.
    one.systems.why_not = "This browser is running already."
    assert await one.ask("POST", "/api/systems/cloud/start") == (
        409,
        {"error": "This browser is running already."},
    )
    assert (await one.ask("POST", "/api/systems/no-such-browser/stop"))[0] == 404
    assert (await one.ask("GET", "/api/systems/cloud/stop"))[0] in (404, 405), (
        "a link that is followed stops nothing"
    )


async def test_a_systems_log_and_what_its_tasks_took_are_read(window: Open) -> None:
    one = await window()
    assert await one.ask("GET", "/api/systems/cloud/log") == (
        200,
        {"path": "/logs/cloud.jsonl", "lines": [{"tool": "browser_navigate", "ok": True}], "size": 40},
    )
    assert await one.ask("GET", "/api/systems/builtin/evals") == (
        200,
        {"system": "builtin", "tasks": {"count": 2}},
    )
    assert await one.ask("GET", "/api/systems/cloud/evals/t1") == (200, {"id": "t1", "spans": []})
    assert (await one.ask("GET", "/api/systems/cloud/evals/no-such-task"))[0] == 404
    assert (await one.ask("GET", "/api/systems/no-such-browser/log"))[0] == 404


async def test_a_person_says_whether_an_answer_was_good(window: Open) -> None:
    one = await window()
    rating = "/api/systems/cloud/evals/t1/rating"
    assert await one.ask("POST", rating, {"rating": "good"}) == (200, {"rating": "good"})
    assert await one.ask("POST", rating, {"rating": None}) == (200, {"rating": None})
    assert (await one.ask("POST", rating, {"rating": "excellent"}))[0] == 400
    assert (await one.ask("POST", rating))[0] == 400
    assert (await one.ask("POST", "/api/systems/cloud/evals/t9/rating", {"rating": "bad"}))[0] == 404
    assert [asked for asked in one.systems.asked if asked[0] == "rate"] == [
        ("rate", "cloud", "t1", "good"),
        ("rate", "cloud", "t1", None),
        ("rate", "cloud", "t9", "bad"),
    ]


async def test_the_checklist_is_run_or_says_why_not(window: Open) -> None:
    one = await window()
    assert await one.ask("POST", "/api/systems/cloud/checks") == (
        200,
        {"passed": 9, "failed": 0, "checks": []},
    )
    one.systems.why_not = "This browser is busy. Run the checklist when its task is finished."
    assert await one.ask("POST", "/api/systems/cloud/checks") == (409, {"error": one.systems.why_not})


async def test_a_systems_settings_are_its_own_and_reach_only_its_session(window: Open) -> None:
    one = await window()
    status, shown = await one.ask("GET", "/api/settings?surface=web&system=cloud")
    assert status == 200 and shown["system"] == "cloud"
    ids = [setting["id"] for group in shown["groups"] for setting in group["settings"]]
    assert ids[0] == "system_enabled"
    # A service's own settings, for no system, have no browser to turn off.
    plain = (await one.ask("GET", "/api/settings?surface=web"))[1]
    assert "system_enabled" not in [s["id"] for group in plain["groups"] for s in group["settings"]]

    change = {"surface": "web", "system": "cloud", "changes": {"ask_before": "every_action"}}
    status, after = await one.ask("PATCH", "/api/settings", change)
    assert status == 200 and after["system"] == "cloud"
    assert one.sessions["cloud"].config.safety.ask_before == "every_action"
    assert one.sessions["builtin"].config.safety.ask_before == "risky"
    # Whoever runs the browsers is told, in case one was turned on or off.
    assert one.systems.asked == [("settings_changed", "cloud")]
    assert json.loads(Path(one.config.settings.file).read_text(encoding="utf-8")) == {
        "systems": {"cloud": {"ask_before": "every_action"}}
    }
    # The step that now needs approval is held on the one browser, and done on the other.
    assert (await one.sessions["cloud"].toolkit.call("browser_click", {"ref": "e1"})).is_error
    assert not (await one.sessions["builtin"].toolkit.call("browser_click", {"ref": "e1"})).is_error


async def test_a_system_there_is_none_of_is_refused(window: Open) -> None:
    one = await window()
    assert (await one.ask("GET", "/api/settings?surface=web&system=no-such-browser"))[0] == 400
    change = {"surface": "web", "system": "no-such-browser", "changes": {"colour_mode": "dark"}}
    assert (await one.ask("PATCH", "/api/settings", change))[0] == 400
    assert (await one.ask("PATCH", "/api/settings", {**change, "system": 7}))[0] == 400
    assert one.systems.asked == []


async def test_a_service_with_one_session_has_no_systems(
    make_config: Callable[..., Config], tmp_path: Path
) -> None:
    config = make_config(tmp_path)
    settings = SettingsStore(config)
    session = ServiceSession(config, FakeDriver(), settings=settings)
    await session.start()
    service = Service(config, {"default": session}, token=TOKEN, port=0, settings=settings)
    await service.start()
    one = Window(service, {"default": session}, Asked(), config)
    try:
        assert "systems" not in (await one.ask("GET", "/api/sessions"))[1]
        assert (await one.ask("GET", "/api/systems"))[0] == 404
        assert (await one.ask("GET", "/api/systems/default/evals"))[0] == 404
        assert (await one.ask("POST", "/api/systems/default/checks"))[0] == 404
        assert (await one.ask("GET", "/api/settings?surface=web&system=default"))[0] == 400
    finally:
        await service.stop()
        await session.close()
