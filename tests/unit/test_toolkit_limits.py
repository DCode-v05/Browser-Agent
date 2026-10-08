"""The limits of a task and steps that go round in circles, as an agent and a person meet them (spec 18.8)."""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path
from typing import Any

import pytest
from fakes import SNAPSHOT, FakeDriver

from bap_browser.config import Config
from bap_browser.driver import BrowserSession
from bap_browser.errors import BrowserError
from bap_browser.service.session import ServiceSession
from bap_browser.tools import Toolkit
from bap_browser.tools.toolkit import OUTCOME_UNKNOWN

TABS = "\n[tabs] t1* about:blank"
CLICKED = 'Clicked e1 (button "Go")'
NOTHING = "\nNothing on the page changed."
THIRD = "\n[notice] This is the 3rd identical step and the page has not changed. Something else is needed."
Watched = Callable[..., Awaitable[tuple[ServiceSession, FakeDriver]]]


def kit(make_config: Callable[..., Config], folder: Path, **sections: Any) -> tuple[Toolkit, FakeDriver]:
    driver = FakeDriver()
    return Toolkit(BrowserSession(make_config(folder, **sections), driver)), driver


async def on_a_page(make_config: Callable[..., Config], folder: Path) -> tuple[Toolkit, FakeDriver]:
    """A toolkit whose browser is open on a page that says of itself that it does not change."""
    tools, driver = kit(make_config, folder)
    driver.mark = "the page as it is"
    await tools.call("browser_snapshot", {})
    return tools, driver


@pytest.fixture
async def watched(make_config: Callable[..., Config], tmp_path: Path) -> AsyncIterator[Watched]:
    sessions: list[ServiceSession] = []

    async def start(**sections: Any) -> tuple[ServiceSession, FakeDriver]:
        driver = FakeDriver()
        session = ServiceSession(make_config(tmp_path, **sections), driver, on_task=lambda task: None)
        sessions.append(session)
        await session.start()
        session.hub.subscribe()
        return session, driver

    yield start
    for session in sessions:
        await session.close()


def told(session: ServiceSession, kind: str) -> list[dict[str, Any]]:
    events = [item for item in session.hub.subscribe()[0] if isinstance(item, dict)]
    return [event for event in events if event["type"] == kind]


async def test_a_session_stops_at_its_limit_of_steps(make_config, tmp_path: Path) -> None:
    tools, driver = kit(make_config, tmp_path, limits={"max_calls": 2})
    assert not (await tools.call("browser_snapshot", {})).is_error
    assert not (await tools.call("browser_click", {"ref": "e1"})).is_error
    stopped = await tools.call("browser_click", {"ref": "e1"})
    assert stopped.is_error
    assert stopped.text == (
        "This session has reached its limit of 2 steps. Stop, and tell the person what is done and "
        f"what is left.{TABS}"
    )
    assert [call[0] for call in driver.calls] == ["snapshot", "click"], "the third call did not run"


async def test_a_step_that_changes_nothing_is_told_so_and_the_sixth_is_not_run(make_config, tmp_path) -> None:
    tools, driver = await on_a_page(make_config, tmp_path)
    results = [(await tools.call("browser_click", {"ref": "e1"})).text for _ in range(6)]
    assert results[:5] == [
        CLICKED + NOTHING + TABS,
        CLICKED + NOTHING + TABS,
        CLICKED + NOTHING + THIRD + TABS,
        CLICKED + NOTHING + TABS,
        CLICKED + NOTHING + TABS,
    ]
    assert results[5] == (
        "Not done: this is the 6th identical step and the page has not changed. Read the page, and "
        f"choose a different step.{TABS}"
    )
    assert len([call for call in driver.calls if call[0] == "click"]) == 5


async def test_reading_in_between_does_not_make_the_same_step_new(make_config, tmp_path: Path) -> None:
    tools, _ = await on_a_page(make_config, tmp_path)
    for _ in range(5):
        await tools.call("browser_click", {"ref": "e1"})
        await tools.call("browser_snapshot", {})
    refused = await tools.call("browser_click", {"ref": "e1"})
    assert refused.is_error and refused.text.startswith("Not done: this is the 6th identical step")


async def test_a_step_on_a_page_that_changes_is_never_held_back(make_config, tmp_path: Path) -> None:
    tools, driver = kit(make_config, tmp_path)
    for turn in range(12):
        driver.mark = f"page {turn}"
        result = await tools.call("browser_click", {"ref": "e1"})
        assert result.text == CLICKED + TABS


async def test_a_page_that_changed_by_itself_lets_the_step_run_again(make_config, tmp_path: Path) -> None:
    tools, driver = await on_a_page(make_config, tmp_path)
    for _ in range(5):
        await tools.call("browser_click", {"ref": "e1"})
    driver.mark = "loaded"
    again = await tools.call("browser_click", {"ref": "e1"})
    assert again.text == CLICKED + NOTHING + TABS


async def test_a_page_that_cannot_say_whether_it_changed_is_taken_to_have_changed(
    make_config, tmp_path
) -> None:
    tools, driver = kit(make_config, tmp_path)
    assert driver.mark is None
    results = {(await tools.call("browser_click", {"ref": "e1"})).text for _ in range(8)}
    assert results == {CLICKED + TABS}


async def test_a_step_that_failed_counts_but_is_not_told_that_nothing_changed(make_config, tmp_path) -> None:
    tools, driver = await on_a_page(make_config, tmp_path)
    driver.fail_with = BrowserError("Something covers the button.", reason="it is covered")
    covered = [(await tools.call("browser_click", {"ref": "e1"})).text for _ in range(3)]
    assert covered == [
        "Something covers the button." + TABS,
        "Something covers the button." + TABS,
        "Something covers the button." + THIRD + TABS,
    ]


async def test_a_hover_is_not_told_that_nothing_changed(make_config, tmp_path: Path) -> None:
    tools, _ = await on_a_page(make_config, tmp_path)
    hovered = await tools.call("browser_hover", {"ref": "e1"})
    assert NOTHING not in hovered.text and not hovered.is_error


async def test_the_same_reading_three_times_is_told_and_goes_on(make_config, tmp_path: Path) -> None:
    tools, _ = kit(make_config, tmp_path)
    read = [(await tools.call("browser_snapshot", {})).text for _ in range(4)]
    notice = "\n[notice] This is the 3rd identical call with the same result. Something else is needed."
    assert read == [SNAPSHOT + TABS, SNAPSHOT + TABS, SNAPSHOT + notice + TABS, SNAPSHOT + TABS]


@pytest.mark.parametrize("lost", [ConnectionResetError("cut"), OSError("gone"), EOFError()])
async def test_an_acting_step_whose_answer_was_lost_says_that_its_outcome_is_not_known(
    make_config, tmp_path: Path, lost: Exception, caplog: pytest.LogCaptureFixture
) -> None:
    tools, driver = kit(make_config, tmp_path)
    driver.fail_with = lost
    result = await tools.call("browser_click", {"ref": "e1"})
    assert result.is_error and result.text == OUTCOME_UNKNOWN + TABS
    assert "browser_click failed unexpectedly" in caplog.text


async def test_a_failure_that_is_the_engines_own_fault_does_not_blame_the_connection(
    make_config, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    tools, driver = kit(make_config, tmp_path)
    driver.fail_with = KeyError("a bug")
    result = await tools.call("browser_click", {"ref": "e1"})
    assert result.text.startswith("browser_click failed unexpectedly (KeyError).")
    assert "failed unexpectedly" in caplog.text


async def test_a_person_is_told_of_the_limit_once_and_can_allow_more(watched: Watched) -> None:
    session, _ = await watched(limits={"max_calls": 1, "extend_calls": 2})
    tools = session.toolkit
    assert not (await tools.call("browser_click", {"ref": "e1"})).is_error
    for _ in range(3):
        assert (await tools.call("browser_click", {"ref": "e1"})).is_error
    (reached,) = told(session, "limit_reached")
    assert {key: reached[key] for key in ("kind", "limit", "scope", "more")} == {
        "kind": "calls",
        "limit": 1,
        "scope": "session",
        "more": 2,
    }
    await session.handle({"type": "extend_limit"})
    assert len(told(session, "limit_lifted")) == 1
    assert not (await tools.call("browser_click", {"ref": "e1"})).is_error
    assert not (await tools.call("browser_click", {"ref": "e1"})).is_error
    assert (await tools.call("browser_click", {"ref": "e1"})).is_error
    again = told(session, "limit_reached")
    assert len(again) == 2 and again[-1]["limit"] == 3
    # With nothing to lift, "Allow more" says nothing.
    await session.handle({"type": "extend_limit"})
    await session.handle({"type": "extend_limit"})
    assert len(told(session, "limit_lifted")) == 2


async def test_each_task_of_the_chat_has_its_own_count_of_steps(watched: Watched) -> None:
    session, _ = await watched(limits={"max_calls": 1})
    tools = session.toolkit
    session.working(True)
    assert not (await tools.call("browser_snapshot", {})).is_error
    stopped = await tools.call("browser_snapshot", {})
    assert stopped.text.startswith("This task has reached its limit of 1 steps.")
    assert told(session, "limit_reached")[-1]["scope"] == "task"
    session.working(False)
    assert len(told(session, "limit_lifted")) == 1
    session.working(True)
    assert not (await tools.call("browser_snapshot", {})).is_error


async def test_after_questions_nobody_answered_further_ones_are_not_waited_for(watched: Watched) -> None:
    session, _ = await watched(
        safety={"action_policies": {"browser_click": "confirm"}},
        control={"approval_timeout_s": 0},
        limits={"unanswered_in_a_row": 2},
    )
    tools = session.toolkit
    for _ in range(2):
        unanswered = await tools.call("browser_click", {"ref": "e1"})
        assert unanswered.text.startswith("The person did not answer in time")
    assert [event["count"] for event in told(session, "questions_unanswered")] == [2]
    assert len(told(session, "approval_requested")) == 2
    refused = await tools.call("browser_click", {"ref": "e1"})
    assert refused.text.startswith("The person did not answer in time")
    assert len(told(session, "approval_requested")) == 2, "the third question was not put to anybody"
    # A person is back: anything they do in the viewer makes their questions worth waiting for again.
    await session.handle({"type": "pause"})
    await session.handle({"type": "resume"})
    call = asyncio.create_task(tools.call("browser_click", {"ref": "e1"}))
    async with asyncio.timeout(2):
        await call
    assert len(told(session, "approval_requested")) == 3
