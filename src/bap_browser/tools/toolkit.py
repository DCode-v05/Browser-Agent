"""Runs a tool call: validate, act, add the state block, redact, log, and tell whoever is watching."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import ValidationError

from bap_browser.driver.base import Located, TabInfo
from bap_browser.driver.session import BrowserSession
from bap_browser.errors import BapError, PolicyBlocked
from bap_browser.results import ToolResult
from bap_browser.tools.browser_tools import TOOLS
from bap_browser.tools.event_log import EventLog
from bap_browser.tools.observer import StepObserver
from bap_browser.tools.registry import ToolDefinition, describe_problem
from bap_browser.tools.sentences import label_for, summary_for

logger = logging.getLogger(__name__)


class Toolkit:
    def __init__(
        self,
        session: BrowserSession,
        tools: Sequence[ToolDefinition] = TOOLS,
        observer: StepObserver | None = None,
    ) -> None:
        self._session = session
        self._tools = {tool.name: tool for tool in tools}
        self._observer = observer
        self._turn = asyncio.Lock()
        self._log = EventLog(session.config.logging, session.redact)
        self._steps = 0

    def definitions(self) -> list[ToolDefinition]:
        return list(self._tools.values())

    async def call(self, name: str, arguments: Mapping[str, Any] | None = None) -> ToolResult:
        """Runs one tool. Calls run one at a time, in order. Every failure comes back as a result."""
        arguments = dict(arguments or {})
        async with self._turn:
            self._steps += 1
            step, redact = self._steps, self._session.redact
            target = await self._locate(arguments) if self._observer else None
            if self._observer:
                label = redact(label_for(name, arguments, target))
                self._observer.step_started(step, name, label, target.box if target else None)
            started = time.perf_counter()
            text, failure = await self._run(name, arguments)
            tabs = await self._tabs()
            result = ToolResult(redact(text + self._state_block(tabs)), failure is not None)
            ms = (time.perf_counter() - started) * 1000
            self._log.write(name, arguments, result, ms)
            if self._observer:
                summary = redact(summary_for(name, arguments, target, failure))
                self._observer.step_finished(step, failure is None, ms, len(result.text), summary, tabs)
        return result

    async def _run(self, name: str, arguments: dict[str, Any]) -> tuple[str, str | None]:
        """The result text and, when the call failed, why in a few words for the person watching."""
        tool = self._tools.get(name)
        if tool is None:
            return f"Unknown tool '{name}'. Available: {', '.join(sorted(self._tools))}.", "unknown tool"
        try:
            args = tool.args.model_validate(arguments)
        except ValidationError as exc:
            problem = describe_problem(exc)
            return f"{name}: {problem}", problem
        try:
            return await tool.handler(self._session, args), None
        except PolicyBlocked as exc:
            if self._observer:
                self._observer.navigation_blocked(exc.url, exc.reason)
            return str(exc), exc.reason
        except BapError as exc:
            return str(exc), exc.reason
        except Exception as exc:
            # The last line of defence: an agent's call must never take the service down.
            logger.exception("%s failed unexpectedly", name)
            return (
                f"{name} failed unexpectedly ({type(exc).__name__}). Try again, or take a new snapshot.",
                "something went wrong",
            )

    async def _locate(self, arguments: Mapping[str, Any]) -> Located | None:
        """The element a call names, for the sentence and the outline a person sees."""
        driver, ref = self._session.started_driver, arguments.get("ref")
        if driver is None or not isinstance(ref, str):
            return None
        try:
            return await driver.locate(ref)
        except BapError:
            return None

    async def _tabs(self) -> list[TabInfo]:
        driver = self._session.started_driver
        if driver is None:
            return []
        try:
            return await driver.tabs()
        except BapError:
            return []

    @staticmethod
    def _state_block(tabs: Sequence[TabInfo]) -> str:
        if not tabs:
            return ""
        return "\n[tabs] " + " | ".join(f"{tab.id}{'*' if tab.active else ''} {tab.url}" for tab in tabs)
