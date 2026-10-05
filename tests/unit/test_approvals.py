"""A person allows or denies what the agent may not do by itself (spec 8.2, 8.6)."""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path
from typing import Any

import pytest
from fakes import FakeDriver

from bap_browser.config import Config
from bap_browser.driver import BrowserSession
from bap_browser.results import ToolResult
from bap_browser.service.session import ServiceSession
from bap_browser.tools import Toolkit

CONFIRM_CLICKS = {"action_policies": {"browser_click": "confirm"}}
Watched = Callable[..., Awaitable[tuple[ServiceSession, FakeDriver]]]


@pytest.fixture
async def watched(make_config: Callable[..., Config], tmp_path: Path) -> AsyncIterator[Watched]:
    """A session on a page of shop.example, with a person watching it."""
    sessions: list[ServiceSession] = []

    async def start(*, viewers: int = 1, **sections: Any) -> tuple[ServiceSession, FakeDriver]:
        driver = FakeDriver()
        session = ServiceSession(make_config(tmp_path, **sections), driver)
        sessions.append(session)
        await session.start()
        for _ in range(viewers):
            session.hub.subscribe()
        # The browser is put on the page directly: opening it with a tool would itself be asked about
        # in the tests where every action is.
        driver.url = "https://shop.example/cart"
        return session, driver

    yield start
    for session in sessions:
        await session.close()


def told(session: ServiceSession, kind: str) -> list[dict[str, Any]]:
    events = [item for item in session.hub.subscribe()[0] if isinstance(item, dict)]
    return [event for event in events if event["type"] == kind]


def clicks(driver: FakeDriver) -> int:
    return len([call for call in driver.calls if call[0] == "click"])


async def asked(session: ServiceSession, count: int = 1) -> dict[str, Any]:
    """The approval that is open now, once the session has asked for it."""
    async with asyncio.timeout(2):
        while len(told(session, "approval_requested")) < count:
            await asyncio.sleep(0)
    return told(session, "approval_requested")[-1]


async def answered(
    session: ServiceSession, call: "asyncio.Task[ToolResult]", answer: dict[str, Any], count: int = 1
) -> ToolResult:
    request = await asked(session, count)
    await session.handle({**answer, "id": request["id"]})
    return await asyncio.wait_for(call, 2)


async def test_a_tool_set_to_confirm_waits_for_a_person_and_runs_once_allowed(watched: Watched) -> None:
    session, driver = await watched(safety=CONFIRM_CLICKS)
    call = asyncio.create_task(session.toolkit.call("browser_click", {"ref": "e1"}))
    request = await asked(session)
    assert request["tool"] == "browser_click"
    assert request["summary"] == 'Clicking "Go" on shop.example'
    assert (request["site"], request["expires_in_s"]) == ("shop.example", 180)
    assert "every_time" not in request
    assert clicks(driver) == 0, "nothing is done while the person decides"
    result = await answered(session, call, {"type": "approve", "scope": "once"})
    assert not result.is_error and clicks(driver) == 1
    assert told(session, "approval_closed") == [
        {"type": "approval_closed", "id": request["id"], "outcome": "allowed"}
    ]


async def test_a_denied_action_is_not_done_and_the_agent_is_told_not_to_try_another_way(
    watched: Watched,
) -> None:
    session, driver = await watched(safety=CONFIRM_CLICKS)
    call = asyncio.create_task(session.toolkit.call("browser_click", {"ref": "e1"}))
    result = await answered(session, call, {"type": "deny"})
    assert result.is_error and clicks(driver) == 0
    assert result.text.startswith(
        "The person did not allow this action. Do not try another way: ask the person, or choose a different approach."
    )
    assert told(session, "approval_closed")[-1]["outcome"] == "denied"
    assert (
        told(session, "step_finished")[-1]["summary"] == 'Could not click "Go": the person did not allow it'
    )


async def test_no_answer_in_time_means_no(watched: Watched) -> None:
    session, driver = await watched(safety=CONFIRM_CLICKS, control={"approval_timeout_s": 0})
    result = await asyncio.wait_for(session.toolkit.call("browser_click", {"ref": "e1"}), 2)
    assert result.is_error and clicks(driver) == 0
    assert result.text.startswith("The person did not answer in time, so this action was not done.")
    assert told(session, "approval_closed")[-1]["outcome"] == "expired"


async def test_an_answer_for_another_approval_or_from_nowhere_changes_nothing(watched: Watched) -> None:
    session, driver = await watched(safety=CONFIRM_CLICKS)
    await session.handle({"type": "approve", "id": "a1", "scope": "once"})
    call = asyncio.create_task(session.toolkit.call("browser_click", {"ref": "e1"}))
    await asked(session)
    await session.handle({"type": "approve", "id": "a99", "scope": "once"})
    await session.handle({"type": "approve", "scope": "once"})
    for _ in range(8):
        await asyncio.sleep(0)
    assert not call.done() and clicks(driver) == 0
    await answered(session, call, {"type": "deny"})


async def test_allow_on_this_site_lasts_for_that_tool_on_that_site_for_the_session(watched: Watched) -> None:
    session, driver = await watched(safety=CONFIRM_CLICKS)
    call = asyncio.create_task(session.toolkit.call("browser_click", {"ref": "e1"}))
    assert not (await answered(session, call, {"type": "approve", "scope": "site"})).is_error
    assert told(session, "approval_closed")[-1]["outcome"] == "allowed_site"
    again = await asyncio.wait_for(session.toolkit.call("browser_click", {"ref": "e1"}), 2)
    assert not again.is_error and clicks(driver) == 2
    assert len(told(session, "approval_requested")) == 1, (
        "the same tool on the same site is not asked about again"
    )

    await session.toolkit.call("browser_navigate", {"url": "https://bank.example/"})
    elsewhere = asyncio.create_task(session.toolkit.call("browser_click", {"ref": "e1"}))
    assert (await asked(session, 2))["site"] == "bank.example"
    await answered(session, elsewhere, {"type": "deny"}, 2)


async def test_allow_on_this_site_is_not_remembered_when_the_deployment_says_so(watched: Watched) -> None:
    session, _ = await watched(safety=CONFIRM_CLICKS, control={"site_grant_lifetime": "none"})
    call = asyncio.create_task(session.toolkit.call("browser_click", {"ref": "e1"}))
    await answered(session, call, {"type": "approve", "scope": "site"})
    again = asyncio.create_task(session.toolkit.call("browser_click", {"ref": "e1"}))
    await answered(session, again, {"type": "deny"}, 2)
    assert len(told(session, "approval_requested")) == 2


async def test_a_tool_set_to_deny_is_refused_without_asking_anyone(watched: Watched) -> None:
    session, driver = await watched(safety={"action_policies": {"browser_click": "deny"}})
    result = await asyncio.wait_for(session.toolkit.call("browser_click", {"ref": "e1"}), 2)
    assert result.is_error and clicks(driver) == 0
    assert result.text.startswith("browser_click is not allowed on this deployment.")
    assert told(session, "approval_requested") == []


async def test_with_nobody_watching_it_is_not_done_and_the_next_viewer_is_told(watched: Watched) -> None:
    session, driver = await watched(viewers=0, safety=CONFIRM_CLICKS)
    result = await asyncio.wait_for(session.toolkit.call("browser_click", {"ref": "e1"}), 2)
    assert result.is_error and clicks(driver) == 0
    assert result.text.startswith(
        "This action needs a person's approval and no one is watching, so it was not done."
    )
    assert told(session, "approval_closed")[-1]["outcome"] == "unwatched"


async def test_a_deployment_may_let_such_actions_through_when_nobody_watches(watched: Watched) -> None:
    session, driver = await watched(
        viewers=0, safety=CONFIRM_CLICKS, control={"approval_without_viewer": "allow"}
    )
    result = await asyncio.wait_for(session.toolkit.call("browser_click", {"ref": "e1"}), 2)
    assert not result.is_error and clicks(driver) == 1


async def test_an_action_on_a_control_that_pays_sends_or_deletes_always_asks(watched: Watched) -> None:
    session, driver = await watched()
    plain = await asyncio.wait_for(session.toolkit.call("browser_click", {"ref": "e1"}), 2)
    assert not plain.is_error and told(session, "approval_requested") == [], '"Go" is an ordinary button'

    paying = asyncio.create_task(session.toolkit.call("browser_click", {"ref": "e7"}))
    request = await asked(session)
    assert request["summary"] == 'Clicking "Pay now" on shop.example'
    assert request["every_time"] is True, "the viewer is told not to offer the whole site"
    assert not (await answered(session, paying, {"type": "approve", "scope": "site"})).is_error
    # "Allow on this site" does not cover it: such an action asks every time.
    assert told(session, "approval_closed")[-1]["outcome"] == "allowed"
    again = asyncio.create_task(session.toolkit.call("browser_click", {"ref": "e7"}))
    await answered(session, again, {"type": "deny"}, 2)
    assert clicks(driver) == 2


async def test_typing_is_not_asked_about_by_itself(watched: Watched) -> None:
    session, _ = await watched()
    for ref in ("e3", "e8"):
        typed = await asyncio.wait_for(session.toolkit.call("browser_type", {"ref": ref, "text": "abc"}), 2)
        assert not typed.is_error
    assert told(session, "approval_requested") == []


async def test_a_person_can_ask_to_approve_every_action_but_reading_is_never_asked_about(
    watched: Watched,
) -> None:
    session, _ = await watched(safety={"ask_before": "every_action"})
    read = await asyncio.wait_for(session.toolkit.call("browser_snapshot", {}), 2)
    assert not read.is_error and told(session, "approval_requested") == []
    call = asyncio.create_task(session.toolkit.call("browser_click", {"ref": "e1"}))
    await answered(session, call, {"type": "approve", "scope": "once"})
    moving = asyncio.create_task(session.toolkit.call("browser_navigate", {"url": "https://other.example/"}))
    assert (await asked(session, 2))["site"] == "other.example"
    await answered(session, moving, {"type": "deny"}, 2)


async def test_stopping_lets_go_of_a_call_that_waits_for_an_approval(watched: Watched) -> None:
    session, driver = await watched(safety=CONFIRM_CLICKS)
    session.working(True)
    call = asyncio.create_task(session.toolkit.call("browser_click", {"ref": "e1"}))
    await asked(session)
    await session.handle({"type": "stop_task"})
    assert (await asyncio.wait_for(call, 2)).is_error and clicks(driver) == 0
    assert told(session, "approval_closed")[-1]["outcome"] == "denied"

    session.working(True)
    call = asyncio.create_task(session.toolkit.call("browser_click", {"ref": "e1"}))
    await asked(session, 2)
    await session.handle({"type": "stop"})
    result = await asyncio.wait_for(call, 2)
    assert result.is_error and result.text.startswith("The session was ended by a person.")


async def test_with_no_service_around_it_a_confirm_tool_is_not_run(make_config, tmp_path: Path) -> None:
    driver = FakeDriver()
    tools = Toolkit(BrowserSession(make_config(tmp_path, safety=CONFIRM_CLICKS), driver))
    result = await tools.call("browser_click", {"ref": "e1"})
    assert result.is_error and clicks(driver) == 0
    assert result.text.startswith("This action needs a person's approval and no one is watching")
