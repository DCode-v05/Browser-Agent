"""The model and the tools of one task, timed for its record (spec 12.6): each reply and each step
is told to the task's trace, with when it began and how it went."""

from __future__ import annotations

import time
from collections.abc import Mapping, Sequence
from typing import Any

from bap_browser.agent.loop import Tools
from bap_browser.agent.models import Message, Model, Reply
from bap_browser.errors import ModelError
from bap_browser.evals.record import Trace
from bap_browser.results import ToolResult
from bap_browser.tools import ToolDefinition


class TimedModel:
    def __init__(self, inner: Model, trace: Trace) -> None:
        self._inner = inner
        self._trace = trace

    async def complete(
        self, system: str, messages: Sequence[Message], tools: Sequence[ToolDefinition]
    ) -> Reply:
        began = time.perf_counter()
        try:
            reply = await self._inner.complete(system, messages, tools)
        except ModelError:
            self._trace.replied(began, ok=False)
            raise
        used = reply.usage
        self._trace.replied(
            began, ok=True, tokens=(used.input_tokens, used.output_tokens) if used is not None else None
        )
        return reply


class TimedTools:
    def __init__(self, inner: Tools, trace: Trace) -> None:
        self._inner = inner
        self._trace = trace

    def definitions(self) -> list[ToolDefinition]:
        return self._inner.definitions()

    async def call(self, name: str, arguments: Mapping[str, Any] | None = None) -> ToolResult:
        began, waited = time.perf_counter(), self._trace.waited_s()
        result = await self._inner.call(name, arguments)
        self._trace.stepped(began, waited, name, result)
        return result
