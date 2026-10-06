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

from bap_browser.config import Config
from bap_browser.driver.base import POINT, Box, Driver, Located, TabInfo
from bap_browser.driver.session import BrowserSession
from bap_browser.errors import BapError, PolicyBlocked
from bap_browser.policy.address import presentable_address
from bap_browser.results import Picture, ToolResult
from bap_browser.tools.browser_tools import TOOLS
from bap_browser.tools.event_log import EventLog, masked, names_only
from bap_browser.tools.gate import Gate, always_open
from bap_browser.tools.observer import StepObserver
from bap_browser.tools.registry import REF_PATTERN, Args, Shown, ToolDefinition, describe_problem
from bap_browser.tools.sentences import label_for, summary_for

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CannotRun:
    """A call that names no tool, or whose arguments are wrong."""

    text: str
    reason: str
    """The same in a few words, for the person watching."""


@dataclass(frozen=True)
class Outcome:
    """What a call came to: the result text, why it failed (in a few words, for the person watching)
    when it did, and the picture it took when it took one."""

    text: str
    failure: str | None = None
    picture: Picture | None = None


# The tools whose x and y are where the pointer goes. For browser_scroll they are only where the wheel turns.
POINTED = frozenset({"browser_click", "browser_hover"})


def _point(arguments: Mapping[str, Any], driver: Driver) -> Located | None:
    """The place a call names by x and y, so that the pointer a person sees goes there."""
    x, y = arguments.get("x"), arguments.get("y")
    if (
        isinstance(x, bool)
        or isinstance(y, bool)
        or not isinstance(x, int | float)
        or not isinstance(y, int | float)
    ):
        return None
    return Located(POINT, "", Box(*driver.page_point(x, y), 0, 0))


def _sentence(words: str) -> str:
    """The words with a capital letter in front, to begin a sentence."""
    return words[:1].upper() + words[1:]


# The tools that only read, or only wait. With "ask before every action" these are still not asked about.
READS = frozenset(
    {
        "browser_snapshot",
        "browser_get_text",
        "browser_find",
        "browser_screenshot",
        "browser_zoom",
        "browser_console",
        "browser_network",
        "browser_downloads",
        "browser_wait",
        "browser_request_human",
    }
)
# The tools that act on one control, whose name can show that the action pays, sends or deletes.
ACTS_ON_A_CONTROL = frozenset(
    {"browser_click", "browser_press_key", "browser_set_checked", "browser_select_option"}
)
# The tools that touch no site: asking a person, waiting, and the list of saved files.
NEED_NO_SITE = frozenset({"browser_request_human", "browser_wait", "browser_downloads"})
ANSWERS_A_DIALOG = "browser_handle_dialog"
# While a page has a dialog open it answers nothing. Only these tools need nothing from it (spec 5.7).
RUN_BESIDE_A_DIALOG = frozenset(
    {ANSWERS_A_DIALOG, "browser_tabs", "browser_console", "browser_network", "browser_downloads"}
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


def tools_for(config: Config) -> tuple[ToolDefinition, ...]:
    """The tools a deployment offers. Three of them exist only when their feature is turned on."""
    browser = config.browser
    absent = {
        "browser_evaluate": not browser.javascript.allow_evaluate,
        # With no folder to upload from, no upload could ever be allowed.
        "browser_upload_file": not (browser.uploads.enabled and browser.uploads.allowed_dirs),
        "browser_downloads": not browser.downloads.enabled,
    }
    return tuple(tool for tool in TOOLS if not absent.get(tool.name, False))


class Toolkit:
    def __init__(
        self,
        session: BrowserSession,
        tools: Sequence[ToolDefinition] | None = None,
        observer: StepObserver | None = None,
        gate: Gate = always_open,
    ) -> None:
        self._session = session
        offered = tools_for(session.config) if tools is None else tools
        self._tools = {tool.name: tool for tool in offered}
        self._observer = observer
        self._gate = gate
        self._turn = asyncio.Lock()
        self._log = EventLog(session.config.logging)
        self._steps = 0
        # The tools a person allowed on a site for the rest of the session: "Allow on this site".
        self._grants: set[tuple[str, str]] = set()
        # The action that a dialog interrupted. It goes on when the dialog has been answered.
        self._held: asyncio.Future[Outcome] | None = None

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
                outcome, logged = Outcome(checked.text, checked.reason), names_only(arguments)
            else:
                outcome = (
                    self._blocked_by_a_dialog(name)
                    or await self._site_permission(name, arguments, target)
                    or await self._permit(name, arguments, target)
                )
                if outcome is None:
                    outcome = await self._run(name, *checked)
                if self._session.site_done is not None and name not in NEED_NO_SITE:
                    # What the person allowed once was for this call.
                    await self._session.site_done()
                logged = masked(arguments, redact)
            tabs = await self.tabs()
            text = admission.note + outcome.text + self._state_block(tabs, self._session.take_news())
            result = ToolResult(redact(text), outcome.failure is not None, outcome.picture)
            ms = (time.perf_counter() - started) * 1000
            self._log.write(name, logged, result, ms)
            if self._observer:
                summary = redact(summary_for(name, arguments, target, outcome.failure))
                self._observer.step_finished(
                    step, outcome.failure is None, ms, len(result.text), summary, tabs
                )
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

    def _blocked_by_a_dialog(self, name: str) -> Outcome | None:
        """While a page has a dialog open, a tool that needs the page is refused (spec 5.7)."""
        dialog = self._session.pending_dialog()
        if dialog is None or name in RUN_BESIDE_A_DIALOG:
            return None
        return Outcome(
            f"{_sentence(dialog.a_kind)} is open{dialog.quoted} and blocks the page. "
            f"Answer it first with {ANSWERS_A_DIALOG}.",
            "a dialog is open",
        )

    async def _site_permission(
        self, name: str, arguments: Mapping[str, Any], target: Located | None
    ) -> Outcome | None:
        """On a person's own browser, whether they let the agent read or act on this site (spec
        8.8). The bridge on their machine decides, and asks them when they have not chosen yet."""
        ask = self._session.ask_site
        if ask is None or name not in self._tools or name in NEED_NO_SITE:
            return None
        address: str | None = None
        if name == "browser_navigate" and isinstance(arguments.get("url"), str):
            judged = await self._session.policy.check(arguments["url"])
            if not judged.allowed:
                # The core's own policy refuses it: the person is not asked about what cannot be done.
                return None
            address = judged.url
        if address is None:
            address = next((tab.url for tab in await self.tabs() if tab.active), "")
        summary = self._session.redact(label_for(name, arguments, target))
        refused = await ask("read" if name in READS else "act", address, summary)
        if refused is None:
            return None
        return Outcome(refused + NO_OTHER_WAY, "the person has not allowed it")

    async def _permit(
        self, name: str, arguments: Mapping[str, Any], target: Located | None
    ) -> Outcome | None:
        """Whether a call may run now (spec 8.2). None when it may. Otherwise what the agent is told,
        and why in a few words for the person watching."""
        config = self._session.config
        policy = config.safety.action_policies.get(name, config.safety.default_action_policy)
        if policy == "deny":
            return Outcome(
                f"{name} is not allowed on this deployment.{NO_OTHER_WAY}", "it is not allowed here"
            )
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
                return Outcome(str(exc), exc.reason or "the session ended")
        if (
            outcome == "allowed_site"
            and not consequential
            and config.control.site_grant_lifetime == "session"
        ):
            self._grants.add((name, site))
        return None if outcome in ("allowed", "allowed_site") else Outcome(*NOT_APPROVED[outcome])

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

    async def _run(self, name: str, tool: ToolDefinition, args: Args) -> Outcome:
        """Runs a tool to its result. A dialog that opens meanwhile interrupts it: the call returns
        with the dialog, and what it began goes on once the dialog has been answered (spec 5.7)."""
        note = await self._what_was_held_finished()
        work = asyncio.ensure_future(self._outcome(name, tool, args))
        if self._session.pending_dialog() is not None:
            # A tool that runs beside an open dialog. It does not wait for one to open.
            outcome = await work
            if name == ANSWERS_A_DIALOG and outcome.failure is None:
                outcome = await self._resume(outcome)
        else:
            outcome = await self._unless_a_dialog_opens(work)
        return replace(outcome, text=note + outcome.text)

    async def _unless_a_dialog_opens(self, work: asyncio.Future[Outcome]) -> Outcome:
        opened = asyncio.ensure_future(self._session.dialog_opened())
        try:
            await asyncio.wait({work, opened}, return_when=asyncio.FIRST_COMPLETED)
        except asyncio.CancelledError:
            work.cancel()
            raise
        finally:
            opened.cancel()
        if work.done():
            return work.result()
        self._held = work
        dialog = self._session.pending_dialog()
        what = _sentence(dialog.named) if dialog else "A dialog"
        return Outcome(
            f"{what} opened, and the page waits for the answer. Answer it with {ANSWERS_A_DIALOG}: "
            "what this call began is then finished."
        )

    async def _resume(self, answered: Outcome) -> Outcome:
        """The dialog has been answered: the action it interrupted goes on, and its result follows."""
        held, self._held = self._held, None
        if held is None:
            return answered
        then = await self._unless_a_dialog_opens(held)
        return Outcome(f"{answered.text}\n{then.text}", then.failure, then.picture)

    async def _what_was_held_finished(self) -> str:
        """A dialog can go away without an answer: it is dismissed when its time runs out, or its tab
        closes. The action it had interrupted then finishes by itself, and the agent is told how."""
        if self._held is None or self._session.pending_dialog() is not None:
            return ""
        held, self._held = self._held, None
        done = await held
        return f"[The dialog went away unanswered, and the action it had interrupted finished: {done.text}]\n"

    async def _outcome(self, name: str, tool: ToolDefinition, args: Args) -> Outcome:
        """The result of a tool's handler. It never raises: every failure is a result."""
        try:
            returned = await tool.handler(self._session, args)
        except PolicyBlocked as exc:
            if self._observer:
                self._observer.navigation_blocked(exc.url, exc.reason)
            return Outcome(str(exc), exc.reason)
        except BapError as exc:
            return Outcome(str(exc), exc.reason)
        except Exception as exc:
            # The last line of defence: an agent's call must never take the service down.
            logger.exception("%s failed unexpectedly", name)
            return Outcome(
                f"{name} failed unexpectedly ({type(exc).__name__}). Try again, or take a new snapshot.",
                "something went wrong",
            )
        if isinstance(returned, Shown):
            return Outcome(returned.text, None, returned.picture)
        return Outcome(returned)

    async def _locate(self, name: str, arguments: Mapping[str, Any]) -> Located | None:
        """The element a call names, for the sentence and the outline a person sees."""
        driver = self._session.started_driver
        # A page with a dialog open answers nothing, so it is not asked.
        if driver is None or name not in self._tools or self._session.pending_dialog() is not None:
            return None
        # A drag is shown where it starts.
        ref = arguments.get("ref", arguments.get("from_ref"))
        # The arguments are not checked yet. Only what is a ref, for a tool that exists, goes to the page.
        if not isinstance(ref, str) or not re.fullmatch(REF_PATTERN, ref):
            return _point(arguments, driver) if ref is None and name in POINTED else None
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
    def _state_block(tabs: Sequence[TabInfo], news: Sequence[str]) -> str:
        """What ends every result: the open tabs, and what happened in the browser by itself since
        the last call."""
        block = ""
        if tabs:
            block += "\n[tabs] " + " | ".join(
                f"{tab.id}{'*' if tab.active else ''} {tab.url}" for tab in tabs
            )
        if news:
            block += "\n[events] " + "; ".join(news)
        return block
