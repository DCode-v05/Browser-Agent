"""Runs a tool call: validate, act, add the state block, redact, log, and tell whoever is watching."""

from __future__ import annotations

import asyncio
import logging
import re
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any
from urllib.parse import urlsplit

from pydantic import ValidationError

from bap_browser.driver.base import POINT, Box, Located, TabInfo
from bap_browser.driver.session import BrowserSession
from bap_browser.errors import BapError, PolicyBlocked
from bap_browser.policy.address import presentable_address
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


# The tools whose x and y are where the pointer goes. For browser_scroll they are only where the wheel turns.
POINTED = frozenset({"browser_click", "browser_hover"})


def _point(arguments: Mapping[str, Any]) -> Located | None:
    """The place a call names by x and y, so that the pointer a person sees goes there."""
    x, y = arguments.get("x"), arguments.get("y")
    if (
        isinstance(x, bool)
        or isinstance(y, bool)
        or not isinstance(x, int | float)
        or not isinstance(y, int | float)
    ):
        return None
    return Located(POINT, "", Box(x, y, 0, 0))


# The tools that only read, or only wait. With "ask before every action" these are still not asked about.
READS = frozenset(
    {"browser_snapshot", "browser_get_text", "browser_find", "browser_wait", "browser_request_human"}
)
# The tools that act on one control, whose name can show that the action pays, sends or deletes.
ACTS_ON_A_CONTROL = frozenset(
    {"browser_click", "browser_press_key", "browser_set_checked", "browser_select_option"}
)
NO_OTHER_WAY = " Do not try another way: ask the person, or choose a different approach."
# What the agent is told when an action was not approved, and the same in a few words for the person.
NOT_APPROVED = {
    "denied": ("The person did not allow this action." + NO_OTHER_WAY, "the person did not allow it"),
    "expired": (
        "The person did not answer in time, so this action was not done." + NO_OTHER_WAY,
        "the person did not answer",
    ),
    "unwatched": (
        "This action needs a person's approval and no one is watching, so it was not done." + NO_OTHER_WAY,
        "no one was watching",
    ),
}


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
        # The tools a person allowed on a site for the rest of the session: "Allow on this site".
        self._grants: set[tuple[str, str]] = set()

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
            target = await self._locate(name, arguments)
            if self._observer:
                label = redact(label_for(name, arguments, target))
                self._observer.step_started(step, name, label, target.box if target else None)
            started = time.perf_counter()
            checked = self._check(name, arguments)
            if isinstance(checked, CannotRun):
                text, failure, logged = checked.text, checked.reason, names_only(arguments)
            else:
                refused = await self._permit(name, arguments, target)
                text, failure = refused or await self._run(name, *checked)
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

    async def _permit(
        self, name: str, arguments: Mapping[str, Any], target: Located | None
    ) -> tuple[str, str] | None:
        """Whether a call may run now (spec 8.2). None when it may. Otherwise what the agent is told,
        and why in a few words for the person watching."""
        config = self._session.config
        policy = config.safety.action_policies.get(name, config.safety.default_action_policy)
        if policy == "deny":
            return f"{name} is not allowed on this deployment.{NO_OTHER_WAY}", "it is not allowed here"
        if config.safety.ask_before == "every_action" and name not in READS:
            policy = "confirm"
        consequential = self._consequential(name, target)
        if policy != "confirm" and not consequential:
            return None
        site = await self._site(name, arguments)
        # An action that pays, sends or deletes is asked about every time, whatever was allowed before.
        if not consequential and (name, site) in self._grants:
            return None
        ask = self._session.ask_approval
        if ask is None:
            outcome = "allowed" if config.control.approval_without_viewer == "allow" else "unwatched"
        else:
            doing = label_for(name, arguments, target)
            try:
                summary = self._session.redact(f"{doing} on {site}" if site else doing)
                outcome = await ask(name, summary, site, consequential)
            except BapError as exc:
                return str(exc), exc.reason or "the session ended"
        if (
            outcome == "allowed_site"
            and not consequential
            and config.control.site_grant_lifetime == "session"
        ):
            self._grants.add((name, site))
        return None if outcome in ("allowed", "allowed_site") else NOT_APPROVED[outcome]

    def _consequential(self, name: str, target: Located | None) -> bool:
        """Whether the call does something a person must agree to each time (spec 8.6): it acts on
        a control whose name says that it pays, sends or deletes."""
        if target is None or name not in ACTS_ON_A_CONTROL:
            return False
        words = self._session.config.permissions.consequential_words
        return any(re.search(rf"\b{re.escape(word)}\b", target.name, re.IGNORECASE) for word in words)

    async def _site(self, name: str, arguments: Mapping[str, Any]) -> str:
        """The site a call acts on: where it goes, for a navigation; otherwise where the browser is."""
        address: str | None = None
        if name == "browser_navigate" and isinstance(arguments.get("url"), str):
            address = presentable_address(arguments["url"])
        if address is None:
            address = next((tab.url for tab in await self.tabs() if tab.active), "")
        return urlsplit(address).hostname or ""

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
        if driver is None or name not in self._tools:
            return None
        # The arguments are not checked yet. Only what is a ref, for a tool that exists, goes to the page.
        if not isinstance(ref, str) or not re.fullmatch(REF_PATTERN, ref):
            return _point(arguments) if ref is None and name in POINTED else None
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
