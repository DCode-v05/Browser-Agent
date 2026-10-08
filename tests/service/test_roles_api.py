"""The admin and the user, over HTTP (spec 4.11): two ways to sign in, what each may ask for, and how
the admin's policy decides what a user may use, change and see."""

import asyncio
import json
import urllib.error
import urllib.request
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from fakes import FakeDriver
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

from bap_browser.config import Config
from bap_browser.service.accounts import Accounts
from bap_browser.service.server import Service
from bap_browser.service.session import ServiceSession
from bap_browser.settings import SettingsStore

OPERATOR = "the-services-own-token-0123456789abcdef"
ADMINS, USERS = "the admin's own words", "what users sign in with"
NAMES = ("cloud", "chrome", "builtin")
TASK = {"id": "t1", "task": "Find a fare", "outcome": "answered", "cost_usd": 0.02, "steps": 3}
EVALS = {
    "tasks": {"count": 1},
    "cost": {"usd": 0.02, "input_tokens": 900, "output_tokens": 40},
    "recent": [TASK],
    "checklist": {"passed": 11, "failed": 0, "checks": []},
}


@dataclass
class Running:
    """Stands in for whoever runs the browsers, and remembers what it was asked to do."""

    asked: list[tuple[Any, ...]] = field(default_factory=list[tuple[Any, ...]])

    def described(self) -> list[dict[str, Any]]:
        return [
            {
                "id": name,
                "state": "agent",
                "enabled": True,
                "log": f"/logs/{name}.jsonl",
                "records": f"/evals/{name}",
            }
            for name in NAMES
        ]

    async def settings_changed(self, system: str) -> None:
        self.asked.append(("settings_changed", system))

    async def manage(self, system: str, action: str) -> str | None:
        self.asked.append((action, system))
        return None

    def log(self, system: str) -> dict[str, Any]:
        return {"path": f"/logs/{system}.jsonl", "lines": [], "size": 0}

    def evals(self, system: str) -> dict[str, Any]:
        return {"system": system, **EVALS}

    def overall(self) -> dict[str, Any]:
        return {"tasks": {"count": 3}, "systems": [{"system": name, "tasks": 1} for name in NAMES]}

    def trace(self, system: str, task: str) -> dict[str, Any] | None:
        return {**TASK, "spans": []} if task == "t1" else None

    def rate(self, system: str, task: str, rating: Any) -> bool:
        self.asked.append(("rate", system, task, rating))
        return True

    async def check(self, system: str) -> dict[str, Any] | str:
        self.asked.append(("check", system))
        return {"passed": 11, "failed": 0, "checks": []}

    def suite(self, system: str) -> dict[str, Any]:
        return {"system": system, "sets": [], "running": None}

    def suite_overall(self) -> dict[str, Any]:
        return {"sets": [], "systems": []}

    def start_suite(self, system: str, name: str, trials: int, mode: Any) -> str | None:
        self.asked.append(("start_suite", system, name, trials, mode))
        return None

    async def stop_suite(self, system: str) -> bool:
        return False


@dataclass
class Window:
    service: Service
    sessions: dict[str, ServiceSession]
    settings: SettingsStore
    accounts: Accounts
    running: Running
    config: Config

    def _ask(self, method: str, path: str, body: Any, token: str | None) -> tuple[int, Any]:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(
            f"{self.service.address}{path}", data=data, headers=headers, method=method
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                said = response.read()
                status = response.status
        except urllib.error.HTTPError as refused:
            said, status = refused.read(), refused.code
        try:
            return status, json.loads(said or b"null")
        except ValueError:
            # Not an answer of the API: a page of the viewer's own files.
            return status, said.decode(errors="replace")

    async def ask(
        self, method: str, path: str, body: Any = None, *, token: str | None = OPERATOR
    ) -> tuple[int, Any]:
        return await asyncio.to_thread(self._ask, method, path, body, token)

    async def signed_in(self, role: str) -> str:
        """Sets both passwords, as the admin would, and signs in as `role`."""
        for whose, password in (("admin", ADMINS), ("user", USERS)):
            if not self.accounts.has(whose):  # type: ignore[arg-type]
                assert (await self.ask("POST", "/api/auth/password", {"role": whose, "password": password}))[
                    0
                ] == 200
        password = ADMINS if role == "admin" else USERS
        status, said = await self.ask(
            "POST", "/api/auth/sign-in", {"role": role, "password": password}, token=None
        )
        assert status == 200 and said["role"] == role
        return said["token"]

    async def socket_closes_with(self, name: str, token: str) -> int | None:
        """Opens a viewer's socket. None when it is let in; otherwise the code it was closed with."""
        address = self.service.address.replace("http://", "ws://") + f"/api/sessions/{name}/ws"
        async with connect(address) as socket:
            await socket.send(json.dumps({"type": "auth", "token": token}))
            try:
                async with asyncio.timeout(5):
                    await socket.recv()
            except ConnectionClosed as closed:
                return closed.rcvd.code if closed.rcvd else 1006
            return None

    async def closes_after(
        self, name: str, token: str, then: Callable[[], Awaitable[Any]], *, says: str | None = None
    ) -> int | None:
        """A viewer that was let in, and the code its connection is closed with once `then` is
        done, and once it has said `says` where it says something. None when it stays."""
        address = self.service.address.replace("http://", "ws://") + f"/api/sessions/{name}/ws"
        async with connect(address) as socket:
            await socket.send(json.dumps({"type": "auth", "token": token}))
            async with asyncio.timeout(5):
                while True:
                    heard = await socket.recv()
                    if isinstance(heard, str) and json.loads(heard)["type"] == "caught_up":
                        break
            await then()
            try:
                if says is not None:
                    await socket.send(json.dumps({"type": says}))
                async with asyncio.timeout(1):
                    while True:
                        await socket.recv()
            except ConnectionClosed as closed:
                return closed.rcvd.code if closed.rcvd else 1006
            except TimeoutError:
                return None


Open = Callable[..., Any]


@pytest.fixture
async def window(make_config: Callable[..., Config], tmp_path: Path) -> AsyncIterator[Open]:
    opened: list[Window] = []

    async def open_one(
        *, with_accounts: bool = True, clock: Callable[[], float] | None = None, **sections: Any
    ) -> Window:
        config = make_config(tmp_path, **sections)
        settings = SettingsStore(config)
        settings.systems = NAMES
        accounts = Accounts(config.auth, clock) if clock else Accounts(config.auth)
        sessions = {
            name: ServiceSession(config, FakeDriver(), name=name, settings=settings) for name in NAMES
        }
        for session in sessions.values():
            await session.start()
        running = Running()
        service = Service(
            config,
            sessions,
            token=OPERATOR,
            port=0,
            settings=settings,
            rooms=running.described,
            systems=running,
            accounts=accounts if with_accounts else None,
        )
        await service.start()
        opened.append(Window(service, sessions, settings, accounts, running, config))
        return opened[-1]

    yield open_one
    for one in opened:
        await one.service.stop()
        for session in one.sessions.values():
            await session.close()


async def test_the_first_time_the_admins_password_is_made_with_the_services_own_link(window: Open) -> None:
    one = await window()
    # A sign-in page asks this before anyone has signed in.
    assert await one.ask("GET", "/api/auth", token=None) == (
        200,
        {"accounts": True, "admin_set": False, "user_set": False, "role": None, "operator": False},
    )
    assert (await one.ask("GET", "/api/auth"))[1] == {
        "accounts": True,
        "admin_set": False,
        "user_set": False,
        "role": "admin",
        "operator": True,
    }
    # Nobody else makes a password, and nobody signs in before there is one.
    assert (await one.ask("POST", "/api/auth/password", {"role": "admin", "password": ADMINS}, token=None))[
        0
    ] == 401
    assert await one.ask("POST", "/api/auth/sign-in", {"role": "admin", "password": ADMINS}, token=None) == (
        409,
        {"error": "not_set"},
    )
    assert await one.ask("POST", "/api/auth/password", {"role": "admin", "password": "short"}) == (
        400,
        {"error": "Use at least 8 characters."},
    )
    assert await one.ask("POST", "/api/auth/password", {"role": "admin", "password": ADMINS}) == (
        200,
        {"admin_set": True, "user_set": False},
    )
    for not_a_request in ({"role": "owner", "password": ADMINS}, {"password": ADMINS}, None):
        assert (await one.ask("POST", "/api/auth/password", not_a_request))[0] == 400
        assert (await one.ask("POST", "/api/auth/sign-in", not_a_request, token=None))[0] == 400


async def test_the_admin_and_the_user_each_sign_in_their_own_way(window: Open) -> None:
    one = await window()
    admin, user = await one.signed_in("admin"), await one.signed_in("user")
    assert await one.ask("POST", "/api/auth/sign-in", {"role": "admin", "password": USERS}, token=None) == (
        401,
        {"error": "wrong"},
    )
    assert (await one.ask("GET", "/api/auth", token=admin))[1]["role"] == "admin"
    assert (await one.ask("GET", "/api/auth", token=user))[1] == {
        "accounts": True,
        "admin_set": True,
        "user_set": True,
        "role": "user",
        "operator": False,
    }
    # The page of each: one address for users, another for the admin, the same page behind both.
    for page in ("/", "/admin"):
        status, said = await one.ask("GET", page, token=None)
        assert status == 200 and "<!doctype html>" in said.lower()
    # Signed out, the token opens nothing more.
    assert (await one.ask("POST", "/api/auth/sign-out", token=user))[0] == 200
    assert (await one.ask("GET", "/api/sessions", token=user))[0] == 401
    assert (await one.ask("GET", "/api/sessions", token=admin))[0] == 200


async def test_wrong_passwords_in_a_row_hold_sign_in_back(window: Open) -> None:
    one = await window(auth={"max_failures": 2, "lock_s": 60})
    await one.signed_in("admin")
    wrong = {"role": "admin", "password": "a guess at it"}
    assert [(await one.ask("POST", "/api/auth/sign-in", wrong, token=None))[0] for _ in range(2)] == [
        401,
        401,
    ]
    status, said = await one.ask(
        "POST", "/api/auth/sign-in", {"role": "admin", "password": ADMINS}, token=None
    )
    assert status == 429 and said["error"] == "locked" and 0 < said["wait_s"] <= 60


async def test_what_is_the_admins_alone_is_refused_to_a_user(window: Open) -> None:
    one = await window()
    user, admin = await one.signed_in("user"), await one.signed_in("admin")
    admins_alone = [
        ("GET", "/api/admin/policy", None),
        ("PATCH", "/api/admin/policy", {"sees": {"cost": False}}),
        ("POST", "/api/auth/password", {"role": "user", "password": "one they chose themselves"}),
        ("GET", "/api/config", None),
        ("GET", "/api/evals", None),
        ("GET", "/api/suite", None),
        ("POST", "/api/browsing-data/clear", None),
        ("POST", "/api/desktop", None),
        ("POST", "/api/systems/cloud/stop", None),
        ("POST", "/api/systems/cloud/restart", None),
        ("GET", "/api/systems/cloud/log", None),
    ]
    for method, path, body in admins_alone:
        assert (await one.ask(method, path, body, token=user))[0] == 403, path
        assert (await one.ask(method, path, body, token=None))[0] == 401, path
    assert one.running.asked == [] and one.settings.user_sees("cost")
    assert one.accounts.sign_in("user", USERS), "the users' password is still the one the admin set"
    # The admin may. So may whoever holds the service's own token.
    for token in (admin, OPERATOR):
        assert (await one.ask("GET", "/api/admin/policy", token=token))[0] == 200
        assert (await one.ask("GET", "/api/evals", token=token))[1]["tasks"] == {"count": 3}
        assert (await one.ask("GET", "/api/systems/cloud/log", token=token))[0] == 200


async def test_a_user_is_shown_the_browsers_the_admin_lets_users_use(window: Open) -> None:
    one = await window()
    user, admin = await one.signed_in("user"), await one.signed_in("admin")
    told = (await one.ask("GET", "/api/sessions", token=user))[1]
    assert told["role"] == "user" and [room["id"] for room in told["rooms"]] == list(NAMES)
    assert (await one.ask("GET", "/api/me", token=user))[1] == {
        "role": "user",
        "systems": list(NAMES),
        "preferred": "cloud",
        "sees": {"evaluations": True, "cost": True, "traces": True, "checklist": True, "log": False},
    }
    assert await one.socket_closes_with("builtin", user) is None

    status, policy = await one.ask("PATCH", "/api/admin/policy", {"systems": {"builtin": False}}, token=admin)
    assert status == 200 and {"id": "builtin", "allowed": False} in policy["systems"]
    # For a user that browser is now not there: not on a tab, not behind an address, not on a socket.
    told = (await one.ask("GET", "/api/sessions", token=user))[1]
    assert [room["id"] for room in told["rooms"]] == ["cloud", "chrome"]
    assert [session["id"] for session in told["sessions"]] == ["cloud", "chrome"]
    assert (await one.ask("GET", "/api/me", token=user))[1]["systems"] == ["cloud", "chrome"]
    assert [s["id"] for s in (await one.ask("GET", "/api/systems", token=user))[1]["systems"]] == [
        "cloud",
        "chrome",
    ]
    assert (await one.ask("GET", "/api/systems/builtin/evals", token=user))[0] == 404
    assert (await one.ask("GET", "/api/settings?surface=web&system=builtin", token=user))[0] == 400
    assert await one.socket_closes_with("builtin", user) == 4404
    assert await one.socket_closes_with("cloud", "not a token") == 4401
    # The admin still has all three.
    told = (await one.ask("GET", "/api/sessions", token=admin))[1]
    assert told["role"] == "admin" and [room["id"] for room in told["rooms"]] == list(NAMES)
    assert await one.socket_closes_with("builtin", admin) is None


async def test_a_viewer_that_may_no_longer_be_on_a_browser_is_shown_out(window: Open) -> None:
    now = [1000.0]
    one = await window(clock=lambda: now[0], auth={"session_hours": 1})
    admin = await one.signed_in("admin")

    async def nothing() -> None:
        return None

    async def keep_users_out_of(name: str, out: bool = True) -> None:
        asked = {"systems": {name: not out}}
        assert (await one.ask("PATCH", "/api/admin/policy", asked, token=admin))[0] == 200

    # While nothing changes, a viewer stays where it is.
    user = await one.signed_in("user")
    assert await one.closes_after("builtin", user, nothing) is None
    # The admin keeps users out of a browser: a user on it is no longer on it, as if it were not there.
    assert await one.closes_after("builtin", user, lambda: keep_users_out_of("builtin")) == 4404
    # A user on another browser is left where they are, and so is the admin on that one.
    await keep_users_out_of("builtin", out=False)
    assert await one.closes_after("cloud", user, lambda: keep_users_out_of("builtin")) is None
    await keep_users_out_of("builtin", out=False)
    assert await one.closes_after("builtin", admin, lambda: keep_users_out_of("builtin")) is None
    await keep_users_out_of("builtin", out=False)

    # Signing out ends the visit on every page it was open on.
    assert (
        await one.closes_after("cloud", user, lambda: one.ask("POST", "/api/auth/sign-out", token=user))
        == 4401
    )

    # A new password for users: whoever signed in with the old one signs in again.
    user = await one.signed_in("user")

    def new_password_for(whose: str) -> Callable[[], Awaitable[Any]]:
        asked = {"role": whose, "password": "another one altogether"}
        return lambda: one.ask("POST", "/api/auth/password", asked, token=admin)

    assert await one.closes_after("cloud", user, new_password_for("user")) == 4401
    # The admin who changes their own password stays where they are.
    assert await one.closes_after("cloud", admin, new_password_for("admin")) is None

    # A visit ends by itself when its time is up. Nothing it asks for after that is done.
    async def an_hour_passes() -> None:
        now[0] += 3601

    late = one.accounts.visit("user")
    assert await one.closes_after("cloud", late, an_hour_passes, says="pause") == 4401
    assert one.sessions["cloud"].control == "agent"
    # The service's own token has no end.
    assert await one.closes_after("cloud", OPERATOR, an_hour_passes, says="resume") is None


async def test_a_user_prefers_a_browser_and_starts_it_when_it_has_stopped(window: Open) -> None:
    one = await window()
    user, admin = await one.signed_in("user"), await one.signed_in("admin")
    status, me = await one.ask("PATCH", "/api/me", {"preferred": "builtin"}, token=user)
    assert status == 200 and me["preferred"] == "builtin"
    assert (await one.ask("GET", "/api/me", token=user))[1]["preferred"] == "builtin"
    # A user starts the browser they prefer. Stopping one is the admin's.
    assert (await one.ask("POST", "/api/systems/builtin/start", token=user))[0] == 200
    assert one.running.asked == [("start", "builtin")]
    # A browser that is not theirs to use is not theirs to prefer.
    await one.ask("PATCH", "/api/admin/policy", {"systems": {"chrome": False}}, token=admin)
    assert await one.ask("PATCH", "/api/me", {"preferred": "chrome"}, token=user) == (
        409,
        {"setting": "preferred_browser", "reason": "not_a_choice"},
    )
    assert (await one.ask("PATCH", "/api/me", {"favourite": "cloud"}, token=user))[0] == 400
    assert (await one.ask("POST", "/api/systems/chrome/start", token=user))[0] == 404


async def test_a_users_settings_are_theirs_and_held_inside_the_admins(window: Open) -> None:
    one = await window()
    user, admin = await one.signed_in("user"), await one.signed_in("admin")
    status, shown = await one.ask("GET", "/api/settings?surface=web&system=cloud", token=user)
    ids = [setting["id"] for group in shown["groups"] for setting in group["settings"]]
    assert status == 200 and shown["role"] == "user" and "ask_before" in ids
    assert not {"page_scripts", "allow_downloads", "system_enabled", "agent_model"} & set(ids)

    change = {"surface": "web", "system": "cloud", "changes": {"ask_before": "every_action"}}
    assert (await one.ask("PATCH", "/api/settings", change, token=user))[0] == 200
    assert one.sessions["cloud"].config.safety.ask_before == "every_action"
    assert one.sessions["builtin"].config.safety.ask_before == "risky"
    # What the agent may do is not a user's to change.
    for admins_setting in ({"page_scripts": True}, {"system_enabled": False}, {"allow_downloads": False}):
        refused = await one.ask("PATCH", "/api/settings", {**change, "changes": admins_setting}, token=user)
        assert refused[0] == 409 and refused[1]["reason"] == "not_on_this_surface"
    assert one.running.asked == [("settings_changed", "cloud")]

    # The admin takes the setting out of the users' hands: the user's value no longer holds, at once.
    assert (await one.ask("PATCH", "/api/admin/policy", {"may_change": {"ask_before": False}}, token=admin))[
        0
    ] == 200
    assert one.sessions["cloud"].config.safety.ask_before == "risky"
    assert await one.ask("PATCH", "/api/settings", change, token=user) == (
        409,
        {"setting": "ask_before", "reason": "locked"},
    )
    # The admin turns on what only the admin may, and it holds for that browser's session.
    admins = {"surface": "web", "system": "cloud", "changes": {"page_scripts": True}}
    assert (await one.ask("PATCH", "/api/settings", admins, token=admin))[0] == 200
    assert "browser_evaluate" in {tool.name for tool in one.sessions["cloud"].toolkit.definitions()}
    assert "browser_evaluate" not in {tool.name for tool in one.sessions["builtin"].toolkit.definitions()}


async def test_a_user_sees_of_the_evaluations_what_the_admin_lets_users_see(window: Open) -> None:
    one = await window()
    user, admin = await one.signed_in("user"), await one.signed_in("admin")
    status, evals = await one.ask("GET", "/api/systems/cloud/evals", token=user)
    assert status == 200 and evals["cost"]["usd"] == 0.02 and evals["recent"] == [TASK]
    assert evals["may"] == {"cost": True, "traces": True, "checklist": True}
    assert (await one.ask("GET", "/api/systems/cloud/evals/t1", token=user))[1]["cost_usd"] == 0.02
    assert (await one.ask("POST", "/api/systems/cloud/checks", token=user))[0] == 200
    # The task sets go with the checklist: who may run the one may run the other.
    run = {"set": "short", "trials": 1, "mode": "reference"}
    assert (await one.ask("GET", "/api/systems/cloud/suite", token=user))[0] == 200
    assert (await one.ask("POST", "/api/systems/cloud/suite", run, token=user))[0] == 202
    # Where a system's files are is the admin's to know.
    listed = (await one.ask("GET", "/api/systems", token=user))[1]["systems"][0]
    assert "log" not in listed and "records" not in listed

    await one.ask("PATCH", "/api/admin/policy", {"sees": {"cost": False}}, token=admin)
    evals = (await one.ask("GET", "/api/systems/cloud/evals", token=user))[1]
    # Taken out of the answer, not merely left undrawn by the page.
    assert evals["cost"] is None and evals["recent"] == [{**TASK, "cost_usd": None}]
    assert evals["may"]["cost"] is False and evals["tasks"] == {"count": 1}
    assert (await one.ask("GET", "/api/systems/cloud/evals/t1", token=user))[1]["cost_usd"] is None

    await one.ask("PATCH", "/api/admin/policy", {"sees": {"traces": False, "checklist": False}}, token=admin)
    evals = (await one.ask("GET", "/api/systems/cloud/evals", token=user))[1]
    assert evals["recent"] == [] and evals["checklist"] is None
    assert (await one.ask("GET", "/api/systems/cloud/evals/t1", token=user))[0] == 403
    assert (await one.ask("POST", "/api/systems/cloud/evals/t1/rating", {"rating": "good"}, token=user))[
        0
    ] == 403
    assert (await one.ask("POST", "/api/systems/cloud/checks", token=user))[0] == 403
    assert (await one.ask("GET", "/api/systems/cloud/suite", token=user))[0] == 403
    assert (await one.ask("POST", "/api/systems/cloud/suite", run, token=user))[0] == 403
    assert (await one.ask("POST", "/api/systems/cloud/suite/stop", token=user))[0] == 403

    await one.ask("PATCH", "/api/admin/policy", {"sees": {"evaluations": False, "log": True}}, token=admin)
    assert (await one.ask("GET", "/api/systems/cloud/evals", token=user))[0] == 403
    status, log = await one.ask("GET", "/api/systems/cloud/log", token=user)
    assert status == 200 and log["path"] == "/logs/cloud.jsonl"
    assert "log" in (await one.ask("GET", "/api/systems", token=user))[1]["systems"][0]
    # The admin sees all of it whatever the policy says, and the whole as one.
    evals = (await one.ask("GET", "/api/systems/cloud/evals", token=admin))[1]
    assert evals["cost"]["usd"] == 0.02 and evals["recent"] == [TASK] and evals["checklist"]["passed"] == 11
    assert evals["may"] == {"cost": True, "traces": True, "checklist": True}
    assert (await one.ask("GET", "/api/evals", token=admin))[1]["systems"][0] == {
        "system": "cloud",
        "tasks": 1,
    }


async def test_a_policy_that_is_not_one_is_refused(window: Open) -> None:
    one = await window()
    admin = await one.signed_in("admin")
    assert await one.ask("PATCH", "/api/admin/policy", {"sees": {"salaries": True}}, token=admin) == (
        409,
        {"setting": "sees.salaries", "reason": "not_a_choice"},
    )
    assert (await one.ask("PATCH", "/api/admin/policy", None, token=admin))[0] == 400
    told = (await one.ask("GET", "/api/admin/policy", token=admin))[1]
    assert [line["id"] for line in told["sees"]] == ["evaluations", "cost", "traces", "checklist", "log"]
    cost = told["sees"][1]
    assert (cost["id"], cost["title"], cost["allowed"]) == ("cost", "What the tasks cost", True)
    assert "what they cost" in cost["description"]


async def test_a_service_nobody_signs_in_to_has_its_own_token_and_nothing_else(window: Open) -> None:
    one = await window(with_accounts=False)
    # It says so, rather than refuse the question: the page that asks shows no error for it.
    assert await one.ask("GET", "/api/auth", token=None) == (200, {"accounts": False})
    assert (await one.ask("POST", "/api/auth/sign-in", {"role": "admin", "password": ADMINS}, token=None))[
        0
    ] == 404
    told = (await one.ask("GET", "/api/sessions"))[1]
    assert "role" not in told and [room["id"] for room in told["rooms"]] == list(NAMES)
    assert (await one.ask("GET", "/api/sessions", token=None))[0] == 401
