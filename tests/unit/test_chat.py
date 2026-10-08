"""The chat: a person gives the agent its tasks from the viewer, one after another (spec 9.14)."""

import asyncio
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from fakes import FakeDriver

from bap_browser.agent.command import NOT_RUN, do_task
from bap_browser.agent.models import Message, Reply, Said, ToolCall, ToolOutput
from bap_browser.config import Config
from bap_browser.errors import ModelError
from bap_browser.service.session import ServiceSession
from bap_browser.tools import ToolDefinition

NOW = 1_759_480_000.0


class Replies:
    """A model that gives fixed replies and keeps what it was shown."""

    def __init__(self, *replies: Reply | Exception) -> None:
        self._replies = list(replies)
        self.seen: list[list[Message]] = []

    async def complete(
        self, system: str, messages: Sequence[Message], tools: Sequence[ToolDefinition]
    ) -> Reply:
        self.seen.append(list(messages))
        reply = self._replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


async def chat_session(
    make_config: Callable[..., Config], folder: Path, **sections: Any
) -> tuple[ServiceSession, list[str]]:
    tasks: list[str] = []
    session = ServiceSession(
        make_config(folder, **sections), FakeDriver(), clock=lambda: NOW, on_task=tasks.append
    )
    await session.start()
    return session, tasks


def chat(session: ServiceSession) -> list[dict[str, Any]]:
    events = [item for item in session.hub.subscribe()[0] if isinstance(item, dict)]
    return [event for event in events if event["type"] in ("message", "task_changed")]


async def test_a_session_says_whether_it_has_a_chat(make_config, tmp_path: Path) -> None:
    with_chat, _ = await chat_session(make_config, tmp_path)
    without = ServiceSession(make_config(tmp_path), FakeDriver())
    await without.start()
    try:
        assert with_chat.hub.subscribe()[0][0]["chat"] is True  # type: ignore[index]
        assert "chat" not in without.hub.subscribe()[0][0]  # type: ignore[operator]
        await without.handle({"type": "task", "text": "Open example.com"})
        assert chat(without) == []
    finally:
        await with_chat.close()
        await without.close()


async def test_a_task_from_the_viewer_reaches_the_agent_and_is_shown_to_every_viewer(
    make_config, tmp_path: Path
) -> None:
    session, tasks = await chat_session(make_config, tmp_path)
    try:
        await session.handle({"type": "task", "text": "  Find the opening hours  "})
        assert tasks == ["Find the opening hours"]
        assert chat(session) == [
            {"type": "message", "id": 1, "role": "person", "text": "Find the opening hours", "ts": NOW}
        ]
    finally:
        await session.close()


async def test_what_is_not_a_task_is_not_taken(make_config, tmp_path: Path) -> None:
    session, tasks = await chat_session(make_config, tmp_path, agent={"max_task_chars": 10})
    for text in ("", "   ", None, 7, ["a"], "x" * 11):
        await session.handle({"type": "task", "text": text})
    await session.handle({"type": "task"})
    assert tasks == [] and chat(session) == []
    await session.handle({"type": "task", "text": "x" * 10})
    assert tasks == ["x" * 10]
    await session.close()
    await session.handle({"type": "task", "text": "too late"})
    assert tasks == ["x" * 10]


async def test_a_message_is_redacted(make_config, tmp_path: Path) -> None:
    session, _ = await chat_session(make_config, tmp_path, safety={"redact_patterns": ["tok-[a-z]+"]})
    try:
        session.said("agent", "The key is tok-abc.", failed=True)
        assert chat(session) == [
            {
                "type": "message",
                "id": 1,
                "role": "agent",
                "text": "The key is [REDACTED].",
                "ts": NOW,
                "failed": True,
            }
        ]
    finally:
        await session.close()


async def test_a_task_is_done_and_answered_in_the_chat(make_config, tmp_path: Path) -> None:
    session, _ = await chat_session(make_config, tmp_path)
    read = ToolCall("a", "browser_snapshot", {})
    model = Replies(Reply("I will read the page.", (read,)), Reply("It says Fake."))
    history: list[Message] = []
    try:
        await do_task("What is on the page?", session, model, session.config, history)
        assert [(event["type"], event.get("text", event.get("working"))) for event in chat(session)] == [
            ("task_changed", True),
            ("message", "I will read the page."),
            ("message", "It says Fake."),
            ("task_changed", False),
        ]
    finally:
        await session.close()
    # The page the task read is not kept: the next task pays for none of it.
    assert history == [
        Said("user", "What is on the page?"),
        Said("assistant", "I will read the page.", (read,)),
        ToolOutput(read, "Page: Fake", False),
        Said("assistant", "It says Fake."),
    ]


async def test_the_next_task_goes_on_from_the_conversation_so_far(make_config, tmp_path: Path) -> None:
    session, _ = await chat_session(make_config, tmp_path)
    model = Replies(Reply("Done."), Reply("Done again."))
    history: list[Message] = []
    try:
        await do_task("First", session, model, session.config, history)
        await do_task("Second", session, model, session.config, history)
    finally:
        await session.close()
    assert model.seen[1] == [Said("user", "First"), Said("assistant", "Done."), Said("user", "Second")]


async def test_a_task_that_fails_is_answered_and_the_session_goes_on(make_config, tmp_path: Path) -> None:
    session, _ = await chat_session(make_config, tmp_path, agent={"max_steps": 1})
    first, second = ToolCall("a", "browser_snapshot", {}), ToolCall("b", "browser_snapshot", {})
    model = Replies(
        ModelError("The model provider could not be reached: timed out"),
        Reply("", (first, second)),
        Reply("Fine."),
    )
    history: list[Message] = []
    try:
        await do_task("First", session, model, session.config, history)
        await do_task("Second", session, model, session.config, history)
        messages = [event for event in chat(session) if event["type"] == "message"]
        assert [(message["text"], message.get("failed", False)) for message in messages] == [
            ("The model provider could not be reached: timed out", True),
            ("Stopped after 1 tool calls without finishing the task.", True),
        ]
        assert session.control == "agent"
        # Every call the model made has a result, so the conversation can go on.
        assert history[-1] == ToolOutput(second, NOT_RUN, True)
        await do_task("Third", session, model, session.config, history)
        assert chat(session)[-2]["text"] == "Fine."
    finally:
        await session.close()


async def test_waiting_for_a_task_ends_when_the_session_does(make_config, tmp_path: Path) -> None:
    session, _ = await chat_session(make_config, tmp_path)
    waiting = asyncio.create_task(session.wait_until_ended())
    await asyncio.sleep(0)
    assert not waiting.done()
    await session.handle({"type": "stop"})
    await asyncio.wait_for(waiting, 1)


def messages(session: ServiceSession) -> list[dict[str, Any]]:
    return [event for event in chat(session) if event["type"] == "message"]


async def test_a_person_stops_the_task_and_the_session_goes_on(make_config, tmp_path: Path) -> None:
    session, _ = await chat_session(make_config, tmp_path)
    history: list[Message] = []

    class StoppedWhileThinking(Replies):
        async def complete(
            self, system: str, messages: Sequence[Message], tools: Sequence[ToolDefinition]
        ) -> Reply:
            reply = await super().complete(system, messages, tools)
            if len(self.seen) == 1:
                await session.handle({"type": "stop_task"})
            return reply

    model = StoppedWhileThinking(
        Reply("", (ToolCall("a", "browser_snapshot", {}),)), Reply("The second one is done.")
    )
    try:
        await do_task("First task", session, model, session.config, history)
        said = messages(session)[-1]
        assert (said["role"], said["text"]) == ("agent", "Stopped before the task was finished.")
        assert "failed" not in said, "a task a person stopped has not failed"
        assert len(model.seen) == 1, "the model is not asked again"
        assert not [call for call in session.browser.started_driver.calls if call[0] == "snapshot"]  # type: ignore[union-attr]
        assert session.control == "agent"

        await do_task("Second task", session, model, session.config, history)
        assert messages(session)[-1]["text"] == "The second one is done."
    finally:
        await session.close()


async def test_stopping_does_nothing_when_no_task_is_being_done(make_config, tmp_path: Path) -> None:
    session, _ = await chat_session(make_config, tmp_path)
    try:
        await session.handle({"type": "stop_task"})
        assert session.task_stopped() is False
        session.working(True)
        await session.handle({"type": "stop_task"})
        assert session.task_stopped() is True
        session.working(True)
        assert session.task_stopped() is False, "a new task starts clean"
    finally:
        await session.close()


async def test_stopping_lets_go_of_a_call_that_was_waiting_for_a_person(make_config, tmp_path: Path) -> None:
    session, _ = await chat_session(make_config, tmp_path)
    try:
        session.working(True)
        await session.handle({"type": "pause"})
        held = asyncio.create_task(session.toolkit.call("browser_snapshot", {}))
        for _ in range(8):
            await asyncio.sleep(0)
        assert not held.done()
        await session.handle({"type": "stop_task"})
        result = await asyncio.wait_for(held, 1)
        assert result.text == "A person stopped the task, so nothing was done."
        assert session.control == "paused", "stopping a task changes nothing about who is driving"

        # A request for a person's help that is open is closed with it.
        await session.handle({"type": "resume"})
        session.working(True)
        asking = asyncio.create_task(
            session.toolkit.call("browser_request_human", {"reason": "Sign in", "kind": "login"})
        )
        async with asyncio.timeout(1):
            while session.control != "person_requested":
                await asyncio.sleep(0)
        await session.handle({"type": "stop_task"})
        await asyncio.wait_for(asking, 1)
        assert session.control == "agent"
    finally:
        await session.close()
