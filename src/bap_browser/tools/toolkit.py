"""Runs a tool call: validate, act, add the state block, redact, log, and tell whoever is watching."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import re
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any

from pydantic import ValidationError

from bap_browser import keys
from bap_browser.code import IN_A_SCRIPT, Ran, ScriptRunner
from bap_browser.config import Config
from bap_browser.driver.base import POINT, Box, Driver, Located, TabInfo
from bap_browser.driver.session import ApprovalOutcome, BrowserSession, Question
from bap_browser.errors import BadInput, BapError, PolicyBlocked
from bap_browser.policy.address import presentable_address, without_credentials
from bap_browser.results import Picture, ToolResult
from bap_browser.safeguards.check import NOT_APPROVED, OPENS_AN_ADDRESS, PRESS, Check, Step
from bap_browser.safeguards.limits import NOTHING_CHANGED, Limits, Reached, same_step
from bap_browser.tools.browser_tools import RUN_A_SCRIPT, TOOLS, RunArgs
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
        "browser_begin_task",
    }
)
DECLARES_A_TASK = "browser_begin_task"
# The tools whose keys go to the element that has the focus when they name no element.
GO_WHERE_THE_FOCUS_IS = frozenset({"browser_type", "browser_press_key"})
# The tools that touch no site: asking a person, waiting, and the list of saved files.
NEED_NO_SITE = frozenset({"browser_request_human", "browser_wait", "browser_downloads", DECLARES_A_TASK})
ANSWERS_A_DIALOG = "browser_handle_dialog"
# While a page has a dialog open it answers nothing. Only these tools need nothing from it (spec 5.7).
RUN_BESIDE_A_DIALOG = frozenset(
    {
        ANSWERS_A_DIALOG,
        "browser_tabs",
        "browser_console",
        "browser_network",
        "browser_downloads",
        DECLARES_A_TASK,
    }
)
# The tools that are no step on a page. They are not watched for going round in circles.
NO_STEP_ON_A_PAGE = NEED_NO_SITE | {"browser_tabs", ANSWERS_A_DIALOG, RUN_A_SCRIPT}
# What a hover brings up is often drawn by a style, which cannot be seen from here.
CHANGES_UNSEEN = frozenset({"browser_hover"})
# A script in the page is mostly a way to read it. Whether it repeats itself is told by what it gives.
TOLD_BY_ITS_RESULT = READS | {"browser_evaluate"}
# What an acting step is told when its answer was lost on the way (spec 18.8).
OUTCOME_UNKNOWN = (
    "The connection to the browser was lost while this step ran. Whether it was done is not known. "
    "Read the page before anything else, and do not repeat a step that pays, sends or deletes "
    "without looking."
)


def _typed(name: str, arguments: Mapping[str, Any]) -> str | None:
    """What a call puts into a page: the text it types, the answer to a prompt, a script."""
    if name == "browser_fill_form":
        fields = arguments.get("fields")
        values = [
            field["value"]
            for field in (fields if isinstance(fields, list) else [])
            if isinstance(field, Mapping) and isinstance(field.get("value"), str)
        ]
        return "\n".join(values) or None
    put = arguments.get(
        {
            "browser_type": "text",
            "browser_press_key": "keys",
            ANSWERS_A_DIALOG: "prompt_text",
            "browser_evaluate": "expression",
        }.get(name, "")
    )
    if not isinstance(put, str) or (name == "browser_press_key" and not keys.is_typed_text(put)):
        return None
    return put


def tools_for(config: Config) -> tuple[ToolDefinition, ...]:
    """The tools a deployment offers. Four of them exist only when their feature is turned on."""
    browser = config.browser
    absent = {
        "browser_evaluate": not browser.javascript.allow_evaluate,
        # With no folder to upload from, no upload could ever be allowed.
        "browser_upload_file": not (browser.uploads.enabled and browser.uploads.allowed_dirs),
        "browser_downloads": not browser.downloads.enabled,
        RUN_A_SCRIPT: not config.code.enabled,
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
        # None when the tools are those the configuration offers, which a person's settings can change.
        self._chosen = tools
        offered = tools_for(session.config) if tools is None else tools
        self._tools = {tool.name: tool for tool in offered}
        self._observer = observer
        self._gate = gate
        self._turn = asyncio.Lock()
        self._log = EventLog(session.config.logging)
        self._steps = 0
        # The tools that are not on offer in this session, whatever the configuration offers.
        self._left_out: set[str] = set()
        session.tool_names = tuple(self._tools)
        session.begin_task = self._begin_task
        self._task_declared = False
        self.check = Check(session, observer)
        self.limits = Limits(lambda: self._session.config.limits, session.spend)
        # The limit the person watching has been told of, so that they are told once.
        self._reached: Reached | None = None
        # What the page said of itself after the last step (spec 18.8).
        self._mark: str | None = None
        # The action that a dialog interrupted. It goes on when the dialog has been answered.
        self._held: asyncio.Future[Outcome] | None = None
        # The code tool's worker (spec 7). It starts with the first script, and ends with the session.
        self._scripts = ScriptRunner(lambda: self._session.config.code, self.call, self._in_a_script)
        session.at_close(self._scripts.close)

    def reconfigure(self) -> None:
        """Takes up a change in the session's configuration: the tools on offer, and the log."""
        if self._chosen is None:
            offered = tools_for(self._session.config)
            self._tools = {tool.name: tool for tool in offered if tool.name not in self._left_out}
            self._session.tool_names = tuple(self._tools)
        self._log = EventLog(self._session.config.logging)

    def definitions(self) -> list[ToolDefinition]:
        return list(self._tools.values())

    def leave_out(self, name: str) -> None:
        """Takes a tool off offer for this session."""
        self._left_out.add(name)
        self._tools.pop(name, None)
        self._session.tool_names = tuple(self._tools)

    async def _begin_task(self, task: str, sites: Sequence[str]) -> str:
        """`browser_begin_task` (spec 18.3). The first task of a session is taken as it is, and so
        is one stated before the agent was given the text of any page. After that a change of task
        needs a person's yes: an agent that a page talked round cannot rewrite its own task."""
        config = self._session.config
        most = config.safeguards.task
        if len(task) > most.max_chars:
            raise BadInput(
                f"The task is longer than {most.max_chars} characters. Say it in fewer words.",
                reason="the task is too long",
            )
        if len(sites) > most.max_sites:
            raise BadInput(
                f"A task takes at most {most.max_sites} sites. Name the ones it needs.",
                reason="too many sites",
            )
        book = self.check.task
        if self._task_declared and book.read_a_page:
            ask = self._session.ask_approval
            answer: ApprovalOutcome = "unwatched"
            if ask is not None:
                answer = await ask(
                    Question(
                        DECLARES_A_TASK,
                        f"The agent wants to change its task to: {self._session.redact(task)}",
                        "",
                        every_time=True,
                        must_be_seen=True,
                        why=("an agent may not change its own task without you",),
                    )
                )
            if answer not in ("allowed", "allowed_site"):
                text, reason = NOT_APPROVED[answer]
                raise BapError(text, reason=reason)
        taken: list[str] = []
        refused: list[str] = []
        for site in sites:
            judged = await self._session.policy.check(site if "://" in site else f"https://{site}")
            (taken if judged.allowed else refused).append(site)
        book.declared(task, taken)
        self._task_declared = True
        lifted = self.task_began()
        self.check.task_began()
        if self._observer:
            self._observer.task_declared(lifted)
        names = ", ".join(site.host for site in book.sites())
        said = f"Task set. Its sites: {names}." if names else "Task set. It names no site."
        if refused:
            said += f" Left out, because this deployment does not allow them: {', '.join(refused)}."
        return said

    def _in_a_script(self) -> dict[str, list[str]]:
        """The tools a script has as methods of `browser`, each with the names of its arguments in order."""
        return {
            name: list(tool.args.model_fields)
            for name in IN_A_SCRIPT
            if (tool := self._tools.get(f"browser_{name}")) is not None
        }

    async def _run_script(self, arguments: dict[str, Any]) -> ToolResult:
        """`browser_run` (spec 7). Each step of the script is a tool call of its own, so this call
        holds neither the turn nor the browser while the script runs: a person pauses, takes over
        or stops between two steps, as between any two calls."""
        redact = self._session.redact
        waiting_since = time.perf_counter()
        # The script itself is never kept: it can hold what it types.
        logged = names_only(arguments)
        async with self._gate() as admission:
            refused, note = admission.refused, admission.note
        if refused is not None:
            held = ToolResult(redact(refused))
            self._log.write(RUN_A_SCRIPT, logged, held, (time.perf_counter() - waiting_since) * 1000)
            return held
        self._steps += 1
        step = self._steps
        if self._observer:
            self._observer.step_started(step, RUN_A_SCRIPT, label_for(RUN_A_SCRIPT, arguments, None), None)
        started = time.perf_counter()
        checked = self._validated(RUN_A_SCRIPT, arguments)
        limited = (
            None if isinstance(checked, CannotRun) else await self._within_limits(RUN_A_SCRIPT, arguments)
        )
        if isinstance(checked, CannotRun):
            ran = Ran(checked.text, checked.reason)
        elif limited is not None:
            ran = Ran(limited.text, limited.failure)
        else:
            args = checked[1]
            assert isinstance(args, RunArgs)
            ran = await self._scripts.run(args.code, args.timeout_s)
        tabs = await self.tabs()
        text = note + ran.text + self._state_block(tabs, self._session.take_news())
        result = ToolResult(redact(text), ran.failure is not None)
        ms = (time.perf_counter() - started) * 1000
        self._log.write(RUN_A_SCRIPT, logged, result, ms)
        if self._observer:
            summary = summary_for(RUN_A_SCRIPT, arguments, None, ran.failure)
            if ran.failure is None:
                # Each step is a row of its own. This row says how many there were.
                summary += f": {ran.steps} step{'' if ran.steps == 1 else 's'}"
            self._observer.step_finished(step, ran.failure is None, ms, len(result.text), summary, tabs)
        return result

    async def call(self, name: str, arguments: Mapping[str, Any] | None = None) -> ToolResult:
        """Runs one tool. Calls run one at a time, in order. Every failure comes back as a result."""
        arguments = dict(arguments or {})
        if name == RUN_A_SCRIPT and name in self._tools:
            return await self._run_script(arguments)
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
            checked = self._validated(name, arguments)
            decided: Mapping[str, Any] | None = None
            done: Step | None = None
            if isinstance(checked, CannotRun):
                outcome, logged = Outcome(checked.text, checked.reason), names_only(arguments)
            else:
                outcome = self._blocked_by_a_dialog(name) or await self._within_limits(name, arguments)
                if outcome is None:
                    made = await self._step(step, name, arguments, target)
                    decision = await self.check.before(made)
                    decided = decision.record
                    if decision.run:
                        outcome = await self._noted(name, arguments, await self._run(name, *checked))
                        done = made
                    else:
                        outcome = Outcome(decision.text, decision.reason)
                if self._session.site_done is not None and name not in NEED_NO_SITE:
                    # What the person allowed once was for this call.
                    await self._session.site_done()
                logged = masked(arguments, redact)
            tabs = await self.tabs()
            text = admission.note + outcome.text + self._state_block(tabs, self._session.take_news())
            result = ToolResult(redact(text), outcome.failure is not None, outcome.picture)
            ms = (time.perf_counter() - started) * 1000
            self._log.write(name, logged, result, ms, decided)
            summary = redact(summary_for(name, arguments, target, outcome.failure))
            if done is not None and outcome.failure is None:
                self.check.ran(done, summary)
            if self._observer:
                self._observer.step_finished(
                    step, outcome.failure is None, ms, len(result.text), summary, tabs
                )
        return result

    async def _step(
        self, number: int, name: str, arguments: Mapping[str, Any], target: Located | None
    ) -> Step:
        """The call as the check sees it (spec 18.4): where it acts, the control it lands on and
        what it types. A press by its place is turned into the element at that place, and keys that
        name no element into the element that has the focus."""
        driver = self._session.started_driver
        tab, here = driver.where() if driver is not None else ("", "")
        opens: str | None = None
        if name in OPENS_AN_ADDRESS and isinstance(arguments.get("url"), str):
            opens = presentable_address(arguments["url"])
        control = target
        fields: list[Located] = []
        # A page with a dialog open answers nothing, so it is not asked.
        if driver is not None and self._session.pending_dialog() is None:
            with contextlib.suppress(BapError):
                if target is not None and target.role == POINT and target.box is not None:
                    control = await driver.locate_point(target.box.x, target.box.y)
                elif target is None and name in GO_WHERE_THE_FOCUS_IS and arguments.get("ref") is None:
                    control = await driver.locate_focus()
                asked = arguments.get("fields") if name == "browser_fill_form" else None
                for entry in asked if isinstance(asked, list) else []:
                    ref = entry.get("ref") if isinstance(entry, Mapping) else None
                    if isinstance(ref, str) and re.fullmatch(REF_PATTERN, ref):
                        fields.append(await driver.locate(ref))
        if name in GO_WHERE_THE_FOCUS_IS and control is not None:
            fields = [control]
        # An element in a frame is on the frame's own site, which may not be the page's.
        in_a_frame = control is not None and control.document.startswith(("http://", "https://"))
        address = (control.document if control and in_a_frame else here) if opens is None else opens
        return Step(
            number,
            name,
            arguments,
            acts=name not in READS,
            address="" if name in NEED_NO_SITE else without_credentials(address),
            opens=opens,
            tab=tab,
            control=control,
            fields=tuple(fields),
            typed=_typed(name, arguments),
            label=self._session.redact(label_for(name, arguments, target)),
            on_a_site=name not in NEED_NO_SITE,
        )

    def _validated(self, name: str, arguments: dict[str, Any]) -> tuple[ToolDefinition, Args] | CannotRun:
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

    async def _within_limits(self, name: str, arguments: Mapping[str, Any]) -> Outcome | None:
        """The limits of a task, and a step that goes round in circles (spec 18.8). None when the
        call may run. Each call that is let through is counted."""
        admitted = await self.limits.admit()
        if isinstance(admitted, Reached):
            if admitted != self._reached and self._observer:
                self._observer.limit_reached(admitted.kind, admitted.limit, self.limits.on_a_task)
            self._reached = admitted
            return Outcome(admitted.text, "a limit was reached")
        self._reached = None
        if admitted is not None:
            return Outcome(admitted, "too many calls at once")
        if name in TOLD_BY_ITS_RESULT or name in NO_STEP_ON_A_PAGE:
            return None
        again = self.limits.goes_in_circles(same_step(name, arguments))
        if again is None:
            if self._mark is None:
                # What the page is like before the first step, so that it can be said to have changed.
                await self._page_moved()
            return None
        if await self._page_moved():
            # The page changed by itself meanwhile: the step may do something now.
            self.limits.page_changed()
            return None
        return Outcome(again, "the same step again and again")

    def allow_more(self) -> bool:
        """A person allowed more steps and minutes. False when no limit had stopped anything."""
        told, self._reached = self._reached, None
        self.limits.extend()
        return told is not None

    def task_began(self) -> bool:
        """A task begins: its steps are counted from here. True when a limit had stopped the one before."""
        told, self._reached = self._reached, None
        self.limits.begin_task()
        return told is not None

    def task_ended(self) -> bool:
        told, self._reached = self._reached, None
        self.limits.end_task()
        return told is not None

    async def _page_moved(self) -> bool:
        """Whether the page has changed since this was last asked. True when it cannot be told."""
        driver = self._session.started_driver
        mark: str | None = None
        # A page with a dialog open answers nothing.
        if driver is not None and self._session.pending_dialog() is None:
            try:
                mark = await driver.change_mark()
            except BapError:
                mark = None
        moved = mark is None or mark != self._mark
        self._mark = mark
        return moved

    async def _noted(self, name: str, arguments: Mapping[str, Any], outcome: Outcome) -> Outcome:
        """What a result gains when the step changed nothing, or is the same once more (spec 18.8)."""
        if name in NO_STEP_ON_A_PAGE:
            return outcome
        step = same_step(name, arguments)
        if name in TOLD_BY_ITS_RESULT:
            note = self.limits.read(step, outcome.text)
        else:
            note = self.limits.acted(step, changed=await self._page_moved())
            if outcome.failure is not None or name in CHANGES_UNSEEN:
                # A step that failed has said so; and what a hover changes is not always seen.
                note = note.removeprefix(NOTHING_CHANGED)
        return replace(outcome, text=outcome.text + note) if note else outcome

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
            if name not in READS and self._lost_on_the_way(exc):
                # Reading again is safe. Acting again may do the thing twice.
                return Outcome(OUTCOME_UNKNOWN, "it is not known whether it was done")
            return Outcome(
                f"{name} failed unexpectedly ({type(exc).__name__}). Try again, or take a new snapshot.",
                "something went wrong",
            )
        if isinstance(returned, Shown):
            return Outcome(returned.text, None, returned.picture)
        return Outcome(returned)

    def _lost_on_the_way(self, error: Exception) -> bool:
        """Whether a failure means that the browser, the tab or the way to it went away under a step."""
        driver = self._session.started_driver
        return (
            isinstance(error, ConnectionError | EOFError | OSError)
            or type(error).__module__.startswith("playwright")
            or (driver is not None and not driver.is_alive())
        )

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
            return await driver.locate(ref, press=name in PRESS or name == "browser_press_key")
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
