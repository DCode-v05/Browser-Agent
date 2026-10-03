"""Runs a tool call: validate, act, add the state block, redact, log."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import ValidationError

from bap_browser.driver.session import BrowserSession
from bap_browser.errors import BapError
from bap_browser.results import ToolResult
from bap_browser.tools.browser_tools import TOOLS
from bap_browser.tools.event_log import EventLog
from bap_browser.tools.registry import ToolDefinition, describe_problem

logger = logging.getLogger(__name__)


class Toolkit:
    def __init__(self, session: BrowserSession, tools: Sequence[ToolDefinition] = TOOLS) -> None:
        self._session = session
        self._tools = {tool.name: tool for tool in tools}
        self._turn = asyncio.Lock()
        self._log = EventLog(session.config.logging, session.redact)

    def definitions(self) -> list[ToolDefinition]:
        return list(self._tools.values())

    async def call(self, name: str, arguments: Mapping[str, Any] | None = None) -> ToolResult:
        """Runs one tool. Calls run one at a time, in order. Every failure comes back as a result."""
        arguments = dict(arguments or {})
        async with self._turn:
            started = time.perf_counter()
            result = await self._run(name, arguments)
            self._log.write(name, arguments, result, (time.perf_counter() - started) * 1000)
        return result

    async def _run(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult(f"Unknown tool '{name}'. Available: {', '.join(sorted(self._tools))}.", True)
        try:
            args = tool.args.model_validate(arguments)
        except ValidationError as exc:
            return ToolResult(f"{name}: {describe_problem(exc)}", True)
        try:
            text, failed = await tool.handler(self._session, args), False
        except BapError as exc:
            text, failed = str(exc), True
        except Exception as exc:
            # The last line of defence: an agent's call must never take the service down.
            logger.exception("%s failed unexpectedly", name)
            text, failed = (
                f"{name} failed unexpectedly ({type(exc).__name__}). Try again, or take a new snapshot.",
                True,
            )
        return ToolResult(self._session.redact(text + await self._state_block()), failed)

    async def _state_block(self) -> str:
        driver = self._session.started_driver
        if driver is None:
            return ""
        try:
            tabs = await driver.tabs()
        except BapError:
            return ""
        return "\n[tabs] " + " | ".join(f"{tab.id}{'*' if tab.active else ''} {tab.url}" for tab in tabs)
