"""The chat: a person gives the agent its tasks from the viewer, one after another (spec 9.14)."""

import asyncio
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from fakes import FakeDriver

from bap_browser.agent.command import NOT_RUN, _do
from bap_browser.agent.models import Message, ModelError, Reply, Said, ToolCall, ToolOutput
from bap_browser.config import Config
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
        await _do("What is on the page?", session, model, session.config, history)
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
        await _do("First", session, model, session.config, history)
        await _do("Second", session, model, session.config, history)
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
        await _do("First", session, model, session.config, history)
        await _do("Second", session, model, session.config, history)
        messages = [event for event in chat(session) if event["type"] == "message"]
        assert [(message["text"], message.get("failed", False)) for message in messages] == [
            ("The model provider could not be reached: timed out", True),
            ("Stopped after 1 tool calls without finishing the task.", True),
        ]
        assert session.control == "agent"
        # Every call the model made has a result, so the conversation can go on.
        assert history[-1] == ToolOutput(second, NOT_RUN, True)
        await _do("Third", session, model, session.config, history)
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
