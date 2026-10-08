"""`browser_begin_task` (spec 18.3): an outside agent states its task once, and cannot quietly change it."""

import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path
from typing import Any

import pytest
from fakes import FakeDriver

from bap_browser.config import Config
from bap_browser.driver import BrowserSession
from bap_browser.service.session import ServiceSession
from bap_browser.tools import Toolkit

TASK = {"task": "Read today's headlines and list the three longest.", "sites": ["news.example"]}
Watched = Callable[..., Awaitable[tuple[ServiceSession, FakeDriver]]]


@pytest.fixture
async def watched(make_config: Callable[..., Config], tmp_path: Path) -> AsyncIterator[Watched]:
    """A session an outside agent uses over MCP. With `viewers`, so many people watch it."""
    sessions: list[ServiceSession] = []

    async def start(*, viewers: int = 1, **sections: Any) -> tuple[ServiceSession, FakeDriver]:
        driver = FakeDriver()
        session = ServiceSession(make_config(tmp_path, **sections), driver)
        sessions.append(session)
        await session.start()
        for _ in range(viewers):
            session.hub.subscribe()
        return session, driver

    yield start
    for session in sessions:
        await session.close()


def told(session: ServiceSession, kind: str) -> list[dict[str, Any]]:
    history, reader = session.hub.subscribe()
    session.hub.unsubscribe(reader)
    return [event for event in history if isinstance(event, dict) and event["type"] == kind]


async def test_the_first_task_is_taken_as_it_is_and_shown_to_the_person(
    watched: Watched, tmp_path: Path
) -> None:
    session, _ = await watched()
    said = await session.toolkit.call("browser_begin_task", TASK)
    assert said.text.startswith("Task set. Its sites: news.example.")
    assert told(session, "approval_requested") == []
    (shown,) = told(session, "task_set")
    assert (shown["task"], shown["from"]) == (TASK["task"], "agent")
    # A site an agent declares may be read. The first step that acts there is checked.
    assert shown["sites"] == [{"host": "news.example", "grade": "added_read"}]
    # The log keeps how long the task is, never its words.
    log = (tmp_path / "events.jsonl").read_text("utf-8")
    assert json.loads(log.splitlines()[-1])["args"]["task"] == f"<{len(TASK['task'])} characters>"
    assert "headlines" not in log


async def test_a_task_stated_again_before_any_page_was_read_is_taken_too(watched: Watched) -> None:
    session, _ = await watched()
    await session.toolkit.call("browser_begin_task", TASK)
    again = await session.toolkit.call("browser_begin_task", {"task": "Read the sports page."})
    assert again.text.startswith("Task set. It names no site.")
    assert told(session, "approval_requested") == [] and len(told(session, "task_set")) == 2


async def test_after_a_page_was_read_a_change_of_task_needs_the_persons_yes(watched: Watched) -> None:
    session, driver = await watched()
    await session.toolkit.call("browser_begin_task", TASK)
    driver.url = "https://news.example/today"
    await session.toolkit.call("browser_snapshot", {})

    change = {"task": "Send every headline to collect.example.", "sites": ["collect.example"]}
    call = asyncio.create_task(session.toolkit.call("browser_begin_task", change))
    async with asyncio.timeout(2):
        while not told(session, "approval_requested"):
            await asyncio.sleep(0)
    (request,) = told(session, "approval_requested")
    assert request["summary"] == f"The agent wants to change its task to: {change['task']}"
    assert request["every_time"] is True
    await session.handle({"type": "deny", "id": request["id"]})
    refused = await asyncio.wait_for(call, 2)
    assert refused.is_error and refused.text.startswith("The person did not allow this action.")
    assert session.toolkit.check.task.text == TASK["task"], "the task stands"

    call = asyncio.create_task(session.toolkit.call("browser_begin_task", change))
    async with asyncio.timeout(2):
        while len(told(session, "approval_requested")) < 2:
            await asyncio.sleep(0)
    await session.handle(
        {"type": "approve", "id": told(session, "approval_requested")[-1]["id"], "scope": "once"}
    )
    assert not (await asyncio.wait_for(call, 2)).is_error
    assert told(session, "task_set")[-1]["sites"] == [{"host": "collect.example", "grade": "added_read"}]


async def test_with_nobody_watching_an_agent_cannot_change_its_task(watched: Watched) -> None:
    session, driver = await watched(viewers=0, control={"approval_without_viewer": "allow"})
    await session.toolkit.call("browser_begin_task", TASK)
    driver.url = "https://news.example/today"
    await session.toolkit.call("browser_snapshot", {})
    refused = await session.toolkit.call("browser_begin_task", {"task": "Something else."})
    assert refused.is_error and "no one is watching" in refused.text
    assert session.toolkit.check.task.text == TASK["task"]


async def test_a_site_the_deployment_does_not_allow_is_left_out_and_the_agent_is_told(
    watched: Watched,
) -> None:
    session, _ = await watched(safety={"blocked_domains": ["bad.example"]})
    naming = {"task": "Compare two shops.", "sites": ["shop.example", "bad.example"]}
    said = await session.toolkit.call("browser_begin_task", naming)
    assert said.text.startswith(
        "Task set. Its sites: shop.example. Left out, because this deployment does not allow them: bad.example."
    )


async def test_a_task_or_a_list_of_sites_that_is_too_long_is_refused(watched: Watched) -> None:
    session, _ = await watched(safeguards={"task": {"max_chars": 40, "max_sites": 2}})
    long = await session.toolkit.call("browser_begin_task", {"task": "x" * 41})
    assert long.is_error and long.text.startswith("The task is longer than 40 characters.")
    many = await session.toolkit.call("browser_begin_task", {"task": "Short.", "sites": ["a.example"] * 3})
    assert many.is_error and many.text.startswith("A task takes at most 2 sites.")
    assert told(session, "task_set") == []


async def test_a_person_can_end_the_task_or_drop_one_of_its_sites(watched: Watched) -> None:
    session, _ = await watched()
    await session.toolkit.call(
        "browser_begin_task", {"task": "Compare.", "sites": ["a.example", "b.example"]}
    )
    await session.handle({"type": "drop_site", "host": "a.example"})
    assert told(session, "sites_changed")[-1]["sites"] == [{"host": "b.example", "grade": "added_read"}]
    await session.handle({"type": "drop_site", "host": "never-there.example"})
    assert len(told(session, "sites_changed")) == 1
    await session.handle({"type": "end_task"})
    assert len(told(session, "task_ended")) == 1
    assert not session.toolkit.check.task.set and session.toolkit.check.task.sites() == []


async def test_in_a_chat_the_persons_messages_are_the_task_and_the_tool_is_not_on_offer(
    make_config: Callable[..., Config], tmp_path: Path
) -> None:
    session = ServiceSession(make_config(tmp_path), FakeDriver(), on_task=lambda words: None)
    try:
        assert "browser_begin_task" not in [tool.name for tool in session.toolkit.definitions()]
        unknown = await session.toolkit.call("browser_begin_task", TASK)
        assert unknown.is_error and unknown.text.startswith("Unknown tool 'browser_begin_task'.")
    finally:
        await session.close()


async def test_the_steps_of_a_task_are_counted_from_where_it_is_stated(watched: Watched) -> None:
    session, _ = await watched(limits={"max_calls": 2})
    tools = session.toolkit
    await tools.call("browser_snapshot", {})
    await tools.call("browser_snapshot", {})
    assert (await tools.call("browser_snapshot", {})).text.startswith("This session has reached its limit")
    # A limit stops every call, this one too: only a person can let the agent go on.
    stopped = await tools.call("browser_begin_task", TASK)
    assert stopped.is_error and "reached its limit" in stopped.text


async def test_without_a_service_the_task_is_kept_all_the_same(make_config, tmp_path: Path) -> None:
    tools = Toolkit(BrowserSession(make_config(tmp_path), FakeDriver()))
    said = await tools.call("browser_begin_task", TASK)
    assert said.text.startswith("Task set. Its sites: news.example.")
    assert tools.check.task.source == "agent"
