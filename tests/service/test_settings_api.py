"""The settings API (spec 10.2): the settings screen is drawn from it, a person's change is saved
through it, and a change applies to the agent's next tool call."""

import asyncio
import json
import urllib.error
import urllib.request
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from fakes import FakeDriver

from bap_browser.config import Config
from bap_browser.service.server import Service
from bap_browser.service.session import ServiceSession
from bap_browser.settings import SettingsStore

TOKEN = "a-token-for-the-tests-0123456789abcdef"


@dataclass
class Served:
    service: Service
    session: ServiceSession
    driver: FakeDriver
    config: Config

    def _ask(self, method: str, path: str, body: Any, token: str | None) -> tuple[int, Any]:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        data = None
        if body is not None:
            data = body if isinstance(body, bytes) else json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            f"{self.service.address}{path}", data=data, headers=headers, method=method
        )
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                return response.status, json.loads(response.read() or b"null")
        except urllib.error.HTTPError as refused:
            return refused.code, json.loads(refused.read() or b"null")

    async def ask(
        self, method: str, path: str, body: Any = None, *, token: str | None = TOKEN
    ) -> tuple[int, Any]:
        # Asked from another thread: the service answers on this one.
        return await asyncio.to_thread(self._ask, method, path, body, token)

    async def change(self, **changes: Any) -> tuple[int, Any]:
        return await self.ask("PATCH", "/api/settings", {"surface": "web", "changes": changes})

    async def setting(self, name: str) -> dict[str, Any]:
        status, answer = await self.ask("GET", "/api/settings?surface=web")
        assert status == 200
        return next(s for group in answer["groups"] for s in group["settings"] if s["id"] == name)

    def told(self) -> list[dict[str, Any]]:
        return [item for item in self.session.hub.subscribe()[0] if isinstance(item, dict)]


Serve = Callable[..., Any]


@pytest.fixture
async def serve(make_config: Callable[..., Config], tmp_path: Path) -> AsyncIterator[Serve]:
    started: list[Served] = []

    async def start(*, with_settings: bool = True, **sections: Any) -> Served:
        config = make_config(tmp_path, **sections)
        settings = SettingsStore(config, {"data_dir": "config.json"}) if with_settings else None
        driver = FakeDriver()
        session = ServiceSession(config, driver, agent="Test agent", settings=settings)
        await session.start()
        service = Service(config, {"default": session}, token=TOKEN, port=0, settings=settings)
        await service.start()
        started.append(Served(service, session, driver, config))
        return started[-1]

    yield start
    for served in started:
        await served.service.stop()
        await served.session.close()


async def test_the_settings_are_for_whoever_holds_the_token(serve: Serve) -> None:
    served = await serve()
    for method, path, body in (
        ("GET", "/api/settings?surface=web", None),
        ("PATCH", "/api/settings", {"surface": "web", "changes": {"colour_mode": "dark"}}),
        ("GET", "/api/config", None),
    ):
        assert (await served.ask(method, path, body, token=None))[0] == 401
        assert (await served.ask(method, path, body, token="wrong"))[0] == 401
    assert (await served.setting("colour_mode"))["value"] == "system", "nothing was changed"


async def test_the_screen_is_drawn_from_the_answer(serve: Serve) -> None:
    served = await serve()
    status, answer = await served.ask("GET", "/api/settings?surface=mobile")
    assert status == 200 and answer["surface"] == "mobile"
    assert "advanced" not in [group["id"] for group in answer["groups"]]
    # With no surface named, it is the web's.
    assert (await served.ask("GET", "/api/settings"))[1]["surface"] == "web"
    assert (await served.ask("GET", "/api/settings?surface=watch"))[0] == 400


async def test_a_change_is_saved_answered_and_announced(serve: Serve) -> None:
    served = await serve()
    status, answer = await served.change(colour_mode="dark", approval_wait="60")
    assert status == 200
    values = {s["id"]: s["value"] for group in answer["groups"] for s in group["settings"]}
    assert values["colour_mode"] == "dark" and values["approval_wait"] == "60"
    assert json.loads(Path(served.config.settings.file).read_text(encoding="utf-8")) == {
        "colour_mode": "dark",
        "approval_wait": "60",
    }
    # Every open viewer is told, so that its settings screen reads them again.
    assert served.told()[-1] == {
        "type": "settings_changed",
        "changes": {"colour_mode": "dark", "approval_wait": "60"},
    }
    assert served.session.config.control.approval_timeout_s == 60


async def test_a_refused_change_says_which_setting_and_why_and_changes_nothing(serve: Serve) -> None:
    served = await serve(settings={"locked": ["activity_log"]})
    before = len(served.told())
    assert await served.change(colour_mode="dark", activity_log=False) == (
        409,
        {"setting": "activity_log", "reason": "locked"},
    )
    assert await served.change(picture_quality="finest") == (
        409,
        {"setting": "picture_quality", "reason": "not_a_choice"},
    )
    assert await served.change(blocked_sites=["not a site"]) == (
        409,
        {"setting": "blocked_sites", "reason": "bad_site"},
    )
    assert (await served.setting("colour_mode"))["value"] == "system"
    assert len(served.told()) == before, "nothing changed, so nothing is announced"


@pytest.mark.parametrize(
    "body",
    [
        b"{not json",
        b"[]",
        {"surface": "web"},
        {"surface": "watch", "changes": {}},
        {"surface": "web", "changes": ["colour_mode"]},
        b'{"surface": "web", "changes": {"blocked_sites": ["' + b"a" * 70_000 + b'.example"]}}',
    ],
)
async def test_a_request_that_is_not_a_change_is_refused(serve: Serve, body: Any) -> None:
    served = await serve()
    assert (await served.ask("PATCH", "/api/settings", body))[0] == 400


async def test_a_site_a_person_blocks_is_refused_at_the_agents_next_call(serve: Serve) -> None:
    served = await serve()
    assert not (
        await served.session.toolkit.call("browser_navigate", {"url": "https://ads.example/"})
    ).is_error
    assert (await served.change(blocked_sites=["ads.example"]))[0] == 200
    refused = await served.session.toolkit.call("browser_navigate", {"url": "https://ads.example/"})
    assert refused.is_error and "blocked" in refused.text
    # And is opened again once the person has taken it off the list.
    assert (await served.change(blocked_sites=[]))[0] == 200
    assert not (
        await served.session.toolkit.call("browser_navigate", {"url": "https://ads.example/"})
    ).is_error


async def test_asking_before_every_action_holds_from_the_next_call(serve: Serve) -> None:
    served = await serve()
    assert not (await served.session.toolkit.call("browser_click", {"ref": "e1"})).is_error
    assert (await served.change(ask_before="every_action"))[0] == 200
    # Nobody is watching this session, so the approval it now needs cannot be given.
    held = await served.session.toolkit.call("browser_click", {"ref": "e1"})
    assert held.is_error and "approval" in held.text
    assert len([call for call in served.driver.calls if call[0] == "click"]) == 1, (
        "the second click was not done"
    )


async def test_a_tool_a_person_turns_off_is_no_longer_offered(serve: Serve) -> None:
    served = await serve(browser={"javascript": {"allow_evaluate": True}})
    offered = lambda: {tool.name for tool in served.session.toolkit.definitions()}  # noqa: E731
    assert {"browser_evaluate", "browser_downloads"} <= offered()
    assert (await served.change(page_scripts=False, allow_downloads=False))[0] == 200
    assert not {"browser_evaluate", "browser_downloads"} & offered()
    assert (await served.session.toolkit.call("browser_evaluate", {"expression": "1"})).is_error
    assert (await served.change(page_scripts=True))[0] == 200
    assert "browser_evaluate" in offered()


async def test_the_log_stops_when_a_person_turns_it_off(serve: Serve) -> None:
    served = await serve()
    log = Path(served.config.logging.event_log or "")
    await served.session.toolkit.call("browser_navigate", {"url": "https://example.com/"})
    lines = len(log.read_text(encoding="utf-8").splitlines())
    assert (await served.change(activity_log=False))[0] == 200
    await served.session.toolkit.call("browser_navigate", {"url": "https://example.com/again"})
    assert len(log.read_text(encoding="utf-8").splitlines()) == lines


async def test_the_picture_changes_quality_while_the_session_runs(serve: Serve) -> None:
    served = await serve()
    standard = served.config.viewer.quality_levels.standard
    assert served.driver.level == standard
    assert (await served.change(picture_quality="data_saver"))[0] == 200
    assert served.driver.level == served.config.viewer.quality_levels.data_saver != standard


async def test_a_session_starts_with_what_a_person_saved(
    make_config: Callable[..., Config], tmp_path: Path
) -> None:
    config = make_config(tmp_path)
    SettingsStore(config).change("web", {"ask_before": "every_action", "blocked_sites": ["ads.example"]})
    session = ServiceSession(config, FakeDriver(), settings=SettingsStore(config))
    await session.start()
    try:
        assert session.config.safety.ask_before == "every_action"
        assert (await session.toolkit.call("browser_navigate", {"url": "https://ads.example/"})).is_error
    finally:
        await session.close()


async def test_about_says_the_version_the_browser_and_what_differs(serve: Serve) -> None:
    served = await serve()
    status, about = await served.ask("GET", "/api/config")
    assert status == 200
    assert about["version"] and about["browser"] == "Fake 1.0"
    assert {"key": "data_dir", "value": json.dumps(served.config.data_dir), "source": "config.json"} in about[
        "changed"
    ]
    # The token is never part of it.
    assert TOKEN not in json.dumps(about)


async def test_the_window_is_told_whether_there_are_settings_to_ask_for(serve: Serve) -> None:
    """The viewer asks this first, so that it never asks for settings a service does not have."""
    assert (await (await serve()).ask("GET", "/api/sessions"))[1]["settings"] is True
    assert "settings" not in (await (await serve(with_settings=False)).ask("GET", "/api/sessions"))[1]


async def test_a_service_without_settings_has_no_such_api(serve: Serve) -> None:
    served = await serve(with_settings=False)
    assert (await served.ask("GET", "/api/settings?surface=web"))[0] == 404
    assert (await served.change(colour_mode="dark"))[0] == 404
    assert (await served.ask("GET", "/api/config"))[0] == 404
