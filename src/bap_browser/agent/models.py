"""The model behind the reference agent loop: the conversation and the tools go in, text and tool calls come out."""

from __future__ import annotations

import asyncio
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from bap_browser.tools import ToolDefinition


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class Reply:
    text: str
    tool_calls: tuple[ToolCall, ...] = ()


@dataclass(frozen=True)
class Said:
    """What the person asked for, or what the model answered."""

    role: Literal["user", "assistant"]
    text: str
    tool_calls: tuple[ToolCall, ...] = ()


@dataclass(frozen=True)
class ToolOutput:
    call: ToolCall
    text: str
    is_error: bool


Message = Said | ToolOutput


class ModelError(Exception):
    """The model could not answer. The message is written for the person who ran the command."""


class Model(Protocol):
    async def complete(
        self, system: str, messages: Sequence[Message], tools: Sequence[ToolDefinition]
    ) -> Reply: ...


Step = Callable[[str], Reply]
"""One scripted reply. It is given the page as the model last saw it, to take refs from."""

NO_MORE_STEPS = "The script has no more steps."


class ScriptedModel:
    """Replays fixed replies, so that the whole path can run in tests and demonstrations with no key."""

    def __init__(self, steps: Sequence[Step], pause_s: float = 0) -> None:
        self._steps = list(steps)
        self._pause_s = pause_s

    async def complete(
        self, system: str, messages: Sequence[Message], tools: Sequence[ToolDefinition]
    ) -> Reply:
        if not self._steps:
            return Reply(NO_MORE_STEPS)
        if self._pause_s:
            # A person watching a demonstration needs time to see each step.
            await asyncio.sleep(self._pause_s)
        return self._steps.pop(0)(last_page(messages))


def last_page(messages: Sequence[Message]) -> str:
    """The newest result that holds a page. A result of a click or of typing holds none."""
    for message in reversed(messages):
        if isinstance(message, ToolOutput) and "[ref=" in message.text:
            return message.text
    return ""


def ref_of(page: str, element: str) -> str:
    """The ref of an element as a snapshot names it: `textbox "Email"`. Empty when it is not on the page."""
    found = re.search(re.escape(f"- {element}") + r" \[ref=((?:f\d+)?e\d+)\]", page)
    return found.group(1) if found else ""
