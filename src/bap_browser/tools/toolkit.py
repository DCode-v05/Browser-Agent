"""Runs a tool call: validate, act, add the state block, redact, log, and tell whoever is watching."""

from __future__ import annotations

import asyncio
import logging
import re
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any

from pydantic import ValidationError

from bap_browser.driver.base import Located, TabInfo
from bap_browser.driver.session import BrowserSession
from bap_browser.errors import BapError, PolicyBlocked
from bap_browser.results import ToolResult
from bap_browser.tools.browser_tools import TOOLS
from bap_browser.tools.event_log import EventLog, masked, names_only
from bap_browser.tools.gate import Gate, always_open
from bap_browser.tools.observer import StepObserver
from bap_browser.tools.registry import REF_PATTERN, Args, ToolDefinition, describe_problem
from bap_browser.tools.sentences import label_for, summary_for

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CannotRun:
    """A call that names no tool, or whose arguments are wrong."""

    text: str
    reason: str
    """The same in a few words, for the person watching."""


class Toolkit:
    def __init__(
        self,
        session: BrowserSession,
        tools: Sequence[ToolDefinition] = TOOLS,
        observer: StepObserver | None = None,
        gate: Gate = always_open,
    ) -> None:
        self._session = session
        self._tools = {tool.name: tool for tool in tools}
        self._observer = observer
        self._gate = gate
        self._turn = asyncio.Lock()
        self._log = EventLog(session.config.logging)
        self._steps = 0

    def definitions(self) -> list[ToolDefinition]:
        return list(self._tools.values())

    async def call(self, name: str, arguments: Mapping[str, Any] | None = None) -> ToolResult:
        """Runs one tool. Calls run one at a time, in order. Every failure comes back as a result."""
        arguments = dict(arguments or {})
        redact = self._session.redact
        waiting_since = time.perf_counter()
        async with self._turn, self._gate() as admission:
            if admission.refused is not None:
                held = ToolResult(redact(admission.refused))
                self._log.write(
                    name, names_only(arguments), held, (time.perf_counter() - waiting_since) * 1000
                )
                return held
            self._steps += 1
            step = self._steps
            target = await self._locate(name, arguments) if self._observer else None
            if self._observer:
                label = redact(label_for(name, arguments, target))
                self._observer.step_started(step, name, label, target.box if target else None)
            started = time.perf_counter()
            checked = self._check(name, arguments)
            if isinstance(checked, CannotRun):
                text, failure, logged = checked.text, checked.reason, names_only(arguments)
            else:
                text, failure = await self._run(name, *checked)
                logged = masked(arguments, redact)
            tabs = await self.tabs()
            result = ToolResult(redact(admission.note + text + self._state_block(tabs)), failure is not None)
            ms = (time.perf_counter() - started) * 1000
            self._log.write(name, logged, result, ms)
            if self._observer:
                summary = redact(summary_for(name, arguments, target, failure))
                self._observer.step_finished(step, failure is None, ms, len(result.text), summary, tabs)
        return result

    def _check(self, name: str, arguments: dict[str, Any]) -> tuple[ToolDefinition, Args] | CannotRun:
        """The tool and its checked arguments, or what is wrong with the call."""
        tool = self._tools.get(name)
        if tool is None:
            available = ", ".join(sorted(self._tools))
            return CannotRun(f"Unknown tool '{name}'. Available: {available}.", "unknown tool")
        try:
            return tool, tool.args.model_validate(arguments)
        except ValidationError as exc:
            problem = describe_problem(exc)
            return CannotRun(f"{name}: {problem}", problem)

    async def _run(self, name: str, tool: ToolDefinition, args: Args) -> tuple[str, str | None]:
        """The result text and, when the call failed, why in a few words for the person watching."""
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

    async def _locate(self, name: str, arguments: Mapping[str, Any]) -> Located | None:
        """The element a call names, for the sentence and the outline a person sees."""
        driver, ref = self._session.started_driver, arguments.get("ref")
        # The arguments are not checked yet. Only what is a ref, for a tool that exists, goes to the page.
        if (
            driver is None
            or name not in self._tools
            or not isinstance(ref, str)
            or not re.fullmatch(REF_PATTERN, ref)
        ):
            return None
        try:
            return await driver.locate(ref)
        except BapError:
            return None

    async def tabs(self) -> list[TabInfo]:
        """The open tabs, with their addresses as they may be shown. None before the browser has started."""
        driver = self._session.started_driver
        if driver is None:
            return []
        try:
            tabs = await driver.tabs()
        except BapError:
            return []
        return [replace(tab, url=self._session.shown_address(tab.url)) for tab in tabs]

    @staticmethod
    def _state_block(tabs: Sequence[TabInfo]) -> str:
        if not tabs:
            return ""
        return "\n[tabs] " + " | ".join(f"{tab.id}{'*' if tab.active else ''} {tab.url}" for tab in tabs)
