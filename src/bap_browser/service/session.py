"""One browser session as the service runs it: its tools, what its viewers are told, and who is driving."""

from __future__ import annotations

import asyncio
import contextlib
import math
import time
from collections.abc import AsyncGenerator, Callable, Mapping, Sequence
from contextlib import asynccontextmanager
from typing import Any, Literal

from bap_browser.config import Config
from bap_browser.driver.base import Box, Driver, Happened, MouseButton, TabInfo
from bap_browser.driver.session import ApprovalOutcome, BrowserSession, Question
from bap_browser.errors import BapError
from bap_browser.policy.sites import origin_of
from bap_browser.safeguards.task import TaskSite
from bap_browser.service.events import EventHub
from bap_browser.settings.store import SettingsStore
from bap_browser.tools.gate import Admission
from bap_browser.tools.toolkit import DECLARES_A_TASK, Toolkit

ControlState = Literal["agent", "paused", "person_requested", "person", "ended"]
HelpOutcome = Literal["done", "could_not", "timed_out"]
EndReason = Literal["person", "agent", "timeout", "failed"]

# What an agent's call is told when it could not run (spec 4.5). None of these is an error.
HELD = {
    "paused": "A person paused the session, so nothing was done. Call again to keep waiting.",
    "person": "A person is in control of the browser, so nothing was done. Call again to keep waiting.",
}
ENDED_BY_A_PERSON = "The session was ended by a person."
TASK_STOPPED = "A person stopped the task, so nothing was done."
ENDED = "The session has ended."
# Which button a pointer command names, as browsers number them.
BUTTONS: dict[int, MouseButton] = {0: "left", 1: "middle", 2: "right"}
LONGEST_KEY_NAME = 32


class ServiceSession:
    def __init__(
        self,
        config: Config,
        driver: Driver | None = None,
        *,
        name: str = "default",
        agent: str = "Agent",
        clock: Callable[[], float] = time.time,
        on_task: Callable[[str], None] | None = None,
        pictures: bool = True,
        backend: str | None = None,
        on_restart: Callable[[], None] | None = None,
        settings: SettingsStore | None = None,
    ) -> None:
        """`backend` names where the browser is, when that is not what the configuration says: a
        person's own Chrome, or the browser built into the app (spec 4.3). `on_restart` is told when
        a person asks, after this session has ended, for a new one in its place. `settings` holds
        what a person chose in the settings screen: it is laid over `config` (spec 10.1)."""
        # What the deployment and this session's own options give, before a person's settings.
        self._given = config
        self._settings = settings
        if settings is not None:
            # A browser among several has settings of its own, under the session's name (spec 9.17).
            config = settings.apply_to(config, backend, name)
        self.config = config
        self.name = name
        self.hub = EventHub(config.viewer.history_events)
        self.browser = BrowserSession(config, driver)
        self.browser.ask_person = self._ask_person_timed
        self.browser.ask_approval = self._ask_approval_timed
        self.browser.watched = lambda: self.hub.viewers > 0
        # How long the agent's calls have waited for a person in all, in seconds (spec 12.6).
        self.waited_for_a_person_s = 0.0
        self.browser.on_event = self._happened
        # The approval that is open now, and how it was answered.
        self._approval: str | None = None
        self._approval_outcome: ApprovalOutcome | None = None
        self._approvals = 0
        # Questions that ran out unanswered in a row. Past a limit, further ones are not waited for.
        self._unanswered = 0
        self.toolkit = Toolkit(self.browser, observer=self, gate=self._admit)
        if on_task is not None:
            # In a chat the person's own messages are the task. An agent cannot put its own in their place.
            self.toolkit.leave_out(DECLARES_A_TASK)
        # How Auto Mode stands, as viewers were last told (spec 18.10).
        self._auto_told: dict[str, Any] | None = None
        # The request for a person that is open now, and how it was answered.
        self._help: str | None = None
        self._help_outcome: HelpOutcome | None = None
        self._helps = 0
        self.control: ControlState = "agent"
        self._backend = backend
        self._on_restart = on_restart
        self._on_task = on_task
        # Whether viewers are sent live pictures of the browser. Not when each one would cross a bridge.
        self._pictures = pictures
        """Given each task a person sends from the viewer's chat. None when the agent takes no tasks there."""
        self._messages = 0
        # Whether the agent is on a task from the chat, and whether a person has stopped that task.
        self._on_a_task = False
        self._task_stopped = False
        self._agent = agent
        self._clock = clock
        self._ended_by: EndReason | None = None
        # Held while an action runs, so that a person takes the browser only between actions.
        self._acting = asyncio.Lock()
        self._changed = asyncio.Condition()
        self._tabs: list[dict[str, Any]] | None = None
        self._address_at_takeover = ""
        self._note = ""
        self._size = (0, 0)
        self._last_picture = 0.0
        self._heartbeat: asyncio.Task[None] | None = None
        # What a person is holding down in the page, so that it can be let go for them.
        self._held_keys: list[str] = []
        self._held_buttons: dict[MouseButton, tuple[float, float]] = {}

    async def start(self) -> None:
        """Starts the browser and tells viewers what this session is."""
        driver = await self.browser.driver()
        self._size = width, height = await driver.viewport()
        started: dict[str, Any] = {
            "type": "session_started",
            "session": self.name,
            "agent": self._agent,
            "backend": self._backend or self.config.backend.kind,
            "browser": driver.description(),
            "viewport": {"width": width, "height": height},
            "ts": self._clock(),
        }
        if self._on_task is not None:
            started["chat"] = True
        if self._on_restart is not None:
            # A person can ask for a new session here once this one has ended.
            started["restartable"] = True
        if not self.config.browser.headless or self.config.browser.cdp_url:
            # The person watches the browser itself, so a viewer need not show its picture.
            started["on_screen"] = True
        self.hub.publish(started)
        self._tell_auto()
        self._publish_tabs(await self.toolkit.tabs())
        viewer = self.config.viewer
        if self._pictures:
            await driver.start_frames(self._picture, getattr(viewer.quality_levels, viewer.quality))
        self._heartbeat = asyncio.create_task(self._keep_viewers_current())

    @property
    def backend(self) -> str:
        """Where this session's browser is (spec 4.3)."""
        return self._backend or self.config.backend.kind

    async def settings_changed(self, changes: Mapping[str, Any]) -> None:
        """A person changed their settings (spec 10.2). What is decided call by call follows at the
        agent's next call; what the browser was started with waits for the next session."""
        if self._settings is None or self.control == "ended":
            return
        before = self.config
        self.config = config = self._settings.apply_to(self._given, self._backend, self.name)
        self.browser.reconfigure(config)
        self.toolkit.reconfigure()
        self.hub.publish({"type": "settings_changed", "changes": dict(changes)})
        self._tell_auto()
        driver = self.browser.started_driver
        if self._pictures and driver is not None and config.viewer.quality != before.viewer.quality:
            await driver.stop_frames()
            await driver.start_frames(
                self._picture, getattr(config.viewer.quality_levels, config.viewer.quality)
            )

    async def close(self, reason: EndReason = "agent", detail: str | None = None) -> None:
        """Ends the session at once: viewers are told, waiting calls are let go, the browser closes."""
        if self.control == "ended":
            return
        self._ended_by = reason
        event: dict[str, Any] = {"type": "session_ended", "reason": reason, "ts": self._clock()}
        if detail:
            event["detail"] = detail
        self.control = "ended"
        self.hub.publish(event)
        await self._announce()
        if self._heartbeat is not None and self._heartbeat is not asyncio.current_task():
            self._heartbeat.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._heartbeat
        await self.browser.close()

    async def handle(self, command: Mapping[str, Any]) -> None:
        """Does what a person asked for in the viewer. A command that does not apply changes nothing."""
        kind = command.get("type") if isinstance(command, Mapping) else None
        # A person is here: their questions are waited for again (spec 18.8).
        self._unanswered = 0
        if kind == "pause":
            await self._take("paused", ("agent",))
        elif kind == "take_over":
            await self._take("person", ("agent", "paused", "person_requested"))
        elif kind in ("done", "could_not") and self._help is not None:
            await self._answer_help(kind)
        elif kind in ("approve", "deny") and self._approval is not None:
            if command.get("id") == self._approval and self._approval_outcome is None:
                allowed: ApprovalOutcome = "allowed_site" if command.get("scope") == "site" else "allowed"
                self._approval_outcome = "denied" if kind == "deny" else allowed
                await self._announce()
        elif kind == "resume" and self.control == "paused":
            await self._set_control("agent")
        elif kind == "hand_back" and self.control == "person" and self._help is None:
            await self._hand_back()
        elif kind == "stop":
            await self.close("person")
        elif kind in ("pointer", "key", "wheel") and self.control == "person":
            await self._input(kind, command)
        elif kind == "task":
            self.give_task(command.get("text"))
        elif kind == "stop_task":
            await self._stop_task()
        elif kind == "end_task":
            await self._end_task()
        elif kind == "resume_auto" and self.toolkit.check.resume():
            self._tell_auto()
        elif kind == "allow_refused" and isinstance(command.get("id"), str):
            if self.toolkit.check.allow_once(command["id"]) is not None:
                self.hub.publish({"type": "refused_allowed", "id": command["id"], "ts": self._clock()})
        elif kind == "drop_site" and isinstance(command.get("host"), str):
            if self.toolkit.check.task.drop(command["host"]):
                self.sites_changed(self.toolkit.check.task.sites())
        elif kind == "extend_limit" and self.toolkit.allow_more():
            self._limit_lifted()
        elif kind == "new_session" and self.control == "ended" and self._on_restart is not None:
            self._on_restart()
        elif kind == "select_tab" and self.control == "person":
            await self._select_tab(command.get("id"))

    async def _select_tab(self, tab_id: Any) -> None:
        """A person who is driving looks at another tab."""
        driver = self.browser.started_driver
        if driver is None or not isinstance(tab_id, str):
            return
        with contextlib.suppress(BapError):
            await driver.switch_tab(tab_id)
        self._publish_tabs(await self.toolkit.tabs())

    def _happened(self, event: Happened) -> None:
        """What happened in the browser by itself, for whoever is watching: a native dialog is not in
        the live picture, and neither is a file that was saved."""
        if not event.detail:
            return
        redact = self.browser.redact
        if event.kind == "dialog_opened":
            shown = {**event.detail, "text": redact(str(event.detail["text"]))}
            self.hub.publish({"type": "dialog_opened", **shown, "ts": self._clock()})
        elif event.kind == "dialog_closed":
            self.hub.publish({"type": "dialog_closed", **event.detail})
        elif event.kind == "blocked":
            self.navigation_blocked(str(event.detail["url"]), str(event.detail["reason"]))
        elif event.kind == "download":
            saved = {"name": redact(str(event.detail["name"])), "size": event.detail["size"]}
            self.hub.publish({"type": "download_saved", **saved, "ts": self._clock()})

    # The chat: a person gives the agent its tasks, and reads its answers (spec 9.14).

    def give_task(self, text: Any) -> bool:
        """Hands a person's task to the agent. False when it cannot be taken."""
        if self._on_task is None or self.control == "ended" or not isinstance(text, str):
            return False
        task = text.strip()
        if not task or len(task) > self.config.agent.max_task_chars:
            return False
        self.said("person", task)
        self._on_task(task)
        return True

    def said(self, role: Literal["person", "agent"], text: str, *, failed: bool = False) -> None:
        """Adds a message to the chat every viewer sees."""
        self._messages += 1
        message: dict[str, Any] = {
            "type": "message",
            "id": self._messages,
            "role": role,
            "text": self.browser.redact(text),
            "ts": self._clock(),
        }
        if failed:
            message["failed"] = True
        self.hub.publish(message)

    @property
    def busy(self) -> bool:
        """Whether the agent is on a task from the chat."""
        return self._on_a_task

    def task_stopped(self) -> bool:
        """Whether a person has stopped the task the agent is on."""
        return self._task_stopped

    async def _stop_task(self) -> None:
        """Ends the task the agent is on, and nothing else: the session, the browser and who is
        driving stay as they are. A call that is waiting for a person is let go."""
        if not self._on_a_task:
            return
        self._task_stopped = True
        if self._help is not None:
            await self._answer_help("could_not")
        await self._announce()

    def working(self, on_a_task: bool, task: str | None = None) -> None:
        """Tells viewers whether the agent is on a task or waits for one. `task` is what the
        person asked for, when the agent begins it: the check judges each step against it (spec 18.3)."""
        self._on_a_task = on_a_task
        self._task_stopped = False
        self.hub.publish({"type": "task_changed", "working": on_a_task, "ts": self._clock()})
        book = self.toolkit.check.task
        if on_a_task and task is not None:
            driver = self.browser.started_driver
            book.person_said(task, driver.where()[1] if driver is not None else "")
            self._task_set()
        elif not on_a_task and book.set and book.source == "person":
            book.end()
            self.hub.publish({"type": "task_ended", "ts": self._clock()})
            self._tell_auto()
        # The steps of a task are counted from where it begins (spec 18.8).
        if self.toolkit.task_began() if on_a_task else self.toolkit.task_ended():
            self._limit_lifted()

    async def wait_until_ended(self) -> None:
        async with self._changed:
            await self._changed.wait_for(lambda: self.control == "ended")

    # A person's mouse and keyboard. None of it is logged, and none of it is told to viewers or the agent.

    async def _input(self, kind: str, command: Mapping[str, Any]) -> None:
        driver = self.browser.started_driver
        if driver is None:
            return
        width, height = self._size
        x, y = _number(command.get("x"), 0, width), _number(command.get("y"), 0, height)
        action, key = command.get("action"), command.get("key")
        try:
            if kind == "pointer" and x is not None and y is not None:
                given = command.get("button")
                button = BUTTONS.get(given) if type(given) is int else None
                if action == "move":
                    # A move names no button of its own.
                    await driver.pointer("move", x, y, button or "left")
                elif action in ("down", "up") and button is not None:
                    if action == "down":
                        self._held_buttons[button] = (x, y)
                    else:
                        self._held_buttons.pop(button, None)
                    await driver.pointer(action, x, y, button)
            elif kind == "key" and action in ("down", "up"):
                if isinstance(key, str) and 0 < len(key) <= LONGEST_KEY_NAME:
                    if action == "up":
                        self._held_keys = [held for held in self._held_keys if held != key]
                    elif key not in self._held_keys:
                        self._held_keys.append(key)
                    await driver.key(action, key)
            elif kind == "wheel" and x is not None and y is not None:
                # One turn of the wheel never moves the page by more than one screen.
                dx = _number(command.get("dx"), -math.inf, math.inf, cut_to=width)
                dy = _number(command.get("dy"), -math.inf, math.inf, cut_to=height)
                if dx is not None and dy is not None:
                    await driver.wheel(x, y, dx, dy)
        except BapError:
            # The page did not take it. A person sees that in the picture; there is nobody to tell.
            return

    async def _let_go(self) -> None:
        """Releases every key and button the person still holds. A key that comes up after the
        hand-back never reaches the page, and a Control left down would turn the agent's next click
        into something else."""
        driver = self.browser.started_driver
        keys, buttons = self._held_keys, self._held_buttons
        self._held_keys, self._held_buttons = [], {}
        if driver is None:
            return
        for key in reversed(keys):
            with contextlib.suppress(BapError):
                await driver.key("up", key)
        for button, (x, y) in buttons.items():
            with contextlib.suppress(BapError):
                await driver.pointer("up", x, y, button)

    def _picture(self, jpeg: bytes) -> None:
        self._last_picture = asyncio.get_running_loop().time()
        self.hub.publish_frame(jpeg)

    async def _keep_viewers_current(self) -> None:
        """A page that is still sends no pictures, and an address can change without a step. Viewers
        are told that the picture is still current, and which page is open, at a steady pace."""
        period = self.config.viewer.picture_heartbeat_s
        while self.control != "ended":
            await asyncio.sleep(period)
            if self.control == "ended":
                return
            self._publish_tabs(await self.toolkit.tabs())
            if asyncio.get_running_loop().time() - self._last_picture >= period:
                self.hub.publish({"type": "picture_current", "ts": self._clock()}, keep=False)

    # What the tool layer reports (StepObserver).

    def step_started(self, step: int, tool: str, label: str, target: Box | None) -> None:
        event: dict[str, Any] = {"type": "step_started", "step": step, "tool": tool, "label": label}
        if target is not None:
            event["target"] = {"x": target.x, "y": target.y, "w": target.w, "h": target.h}
        self.hub.publish({**event, "ts": self._clock()})

    def step_finished(
        self, step: int, ok: bool, ms: float, chars: int, summary: str, tabs: Sequence[TabInfo]
    ) -> None:
        url = next((tab.url for tab in tabs if tab.active), "")
        self.hub.publish(
            {
                "type": "step_finished",
                "step": step,
                "ok": ok,
                "ms": round(ms),
                "chars": chars,
                "summary": summary,
                "url": self.browser.redact(url),
            }
        )
        if tabs:
            self._publish_tabs(tabs)

    def navigation_blocked(self, url: str, reason: str) -> None:
        self.hub.publish(
            {
                "type": "navigation_blocked",
                "url": self.browser.redact(url),
                "reason": reason,
                "ts": self._clock(),
            }
        )

    def check_decided(
        self,
        step: int,
        stage: str,
        outcome: str,
        findings: Sequence[str],
        reason: str,
        said: str = "",
        refused_id: str | None = None,
    ) -> None:
        event: dict[str, Any] = {
            "type": "check_decided",
            "step": step,
            "stage": stage,
            "outcome": outcome,
            "findings": list(findings),
            "reason": reason,
        }
        if said:
            # A model wrote this sentence. It goes to the people watching, and to no log.
            event["said"] = self.browser.redact(said)
        if refused_id is not None:
            event["refused_id"] = refused_id
        self.hub.publish({**event, "ts": self._clock()})

    def sites_changed(self, sites: Sequence[TaskSite]) -> None:
        self.hub.publish({"type": "sites_changed", "sites": _shown(sites)})

    def auto_changed(self) -> None:
        self._tell_auto()

    def _tell_auto(self) -> None:
        """Tells viewers how the session asks, and how Auto Mode stands, when either has changed."""
        check = self.toolkit.check
        state, why = check.auto_state()
        told: dict[str, Any] = {"type": "auto_changed", "mode": check.mode, "state": state}
        if why:
            told["why"] = why
        if told != self._auto_told:
            self._auto_told = told
            self.hub.publish({**told, "ts": self._clock()})

    def _task_set(self) -> None:
        """A task is set: it is shown to the person at once, with its sites."""
        book = self.toolkit.check.task
        self.toolkit.check.task_began()
        self.hub.publish(
            {
                "type": "task_set",
                "task": self.browser.redact(book.text or ""),
                "from": book.source,
                "sites": _shown(book.sites()),
                "ts": self._clock(),
            }
        )
        self._tell_auto()

    def task_declared(self, limit_lifted: bool) -> None:
        if limit_lifted:
            self._limit_lifted()
        self._task_set()

    async def _end_task(self) -> None:
        """A person ended the task: the one from the chat, or the one an agent declared."""
        book = self.toolkit.check.task
        if book.source == "agent" and book.set:
            book.end()
            if self.toolkit.task_ended():
                self._limit_lifted()
            self.hub.publish({"type": "task_ended", "ts": self._clock()})
            self._tell_auto()
        await self._stop_task()

    def served_at(self, address: str) -> None:
        """Where the service that shows this session listens: pages from there are the core's own."""
        self.toolkit.check.task.own_origins.add(origin_of(address))

    def limit_reached(self, kind: str, limit: float, on_a_task: bool) -> None:
        limits = self.config.limits
        event: dict[str, Any] = {
            "type": "limit_reached",
            "kind": kind,
            "limit": limit,
            "scope": "task" if on_a_task else "session",
        }
        # What "Allow more" adds. More steps do not buy more money.
        more = {"calls": limits.extend_calls, "minutes": limits.extend_minutes}.get(kind)
        if more:
            event["more"] = more
        self.hub.publish({**event, "ts": self._clock()})

    def _limit_lifted(self) -> None:
        self.hub.publish({"type": "limit_lifted", "ts": self._clock()})

    # Who is driving (spec 4.5).

    @asynccontextmanager
    async def _admit(self) -> AsyncGenerator[Admission]:
        """Lets an agent's call through when the agent is driving, and holds it while a person is."""
        deadline = asyncio.get_running_loop().time() + self.config.control.hold_timeout_s
        while True:
            if self.control == "ended":
                yield Admission(refused=ENDED_BY_A_PERSON if self._ended_by == "person" else ENDED)
                return
            if self._task_stopped:
                yield Admission(refused=TASK_STOPPED)
                return
            if self.control != "agent":
                remaining = deadline - asyncio.get_running_loop().time()
                try:
                    async with asyncio.timeout(max(remaining, 0)), self._changed:
                        await self._changed.wait_for(
                            lambda: self.control in ("agent", "ended") or self._task_stopped
                        )
                except TimeoutError:
                    yield Admission(refused=HELD.get(self.control, ENDED))
                    return
                continue
            await self._acting.acquire()
            if self.control == "agent":
                break
            self._acting.release()
        try:
            note, self._note = self._note, ""
            yield Admission(note=note)
        finally:
            self._acting.release()

    async def _take(self, state: Literal["paused", "person"], when: tuple[ControlState, ...]) -> None:
        """Pause or take-over. It begins when the action in progress has finished."""
        if self.control not in when:
            return
        async with self._acting:
            if self.control not in when:
                return
            if state == "person":
                self._address_at_takeover = self._active_address(await self.toolkit.tabs())
            await self._set_control(state)

    async def _hand_back(self) -> None:
        await self._let_go()
        tabs = await self.toolkit.tabs()
        if self.control != "person":
            # The session was stopped, or another viewer handed it back, while the tabs were being read.
            return
        self._publish_tabs(tabs)
        self._note = (
            f"[A person was in control of the browser and has handed it back. {self._change(tabs)} "
            "Refs from before may be out of date: take a new snapshot before you act.]\n"
        )
        await self._set_control("agent")

    def _change(self, tabs: Sequence[TabInfo]) -> str:
        """What a person changed while they had the browser, as far as the agent is told: the address."""
        before, after = self._address_at_takeover, self._active_address(tabs)
        return (
            f"The address is still {after}."
            if after == before
            else f"The address was {before} and is now {after}."
        )

    # The agent asks a person to do a step (spec 8.4): a sign-in, a CAPTCHA, a code.

    async def _ask_person_timed(self, reason: str, kind: str, timeout_s: float) -> tuple[str, str]:
        since = time.monotonic()
        try:
            return await self._ask_person(reason, kind, timeout_s)
        finally:
            self.waited_for_a_person_s += time.monotonic() - since

    async def _ask_approval_timed(self, question: Question) -> ApprovalOutcome:
        since = time.monotonic()
        try:
            return await self._ask_approval(question)
        finally:
            self.waited_for_a_person_s += time.monotonic() - since

    async def _ask_person(self, reason: str, kind: str, timeout_s: float) -> tuple[str, str]:
        """Runs inside the agent's call. The call holds the browser; it is let go while the person
        works, so that they can take over, and taken again before the call goes on."""
        self._helps += 1
        self._help, self._help_outcome = f"h{self._helps}", None
        self._address_at_takeover = self._active_address(await self.toolkit.tabs())
        self.hub.publish(
            {
                "type": "help_requested",
                "id": self._help,
                "reason": self.browser.redact(reason),
                "kind": kind,
                "expires_in_s": round(timeout_s),
                "ts": self._clock(),
            }
        )
        if self._on_task is not None:
            self.said("agent", f"I need your help: {reason}")
        await self._set_control("person_requested")
        self._acting.release()
        try:
            with contextlib.suppress(TimeoutError):
                async with asyncio.timeout(timeout_s), self._changed:
                    await self._changed.wait_for(
                        lambda: self._help_outcome is not None or self.control == "ended"
                    )
        finally:
            await self._acting.acquire()
        outcome: HelpOutcome = self._help_outcome or "timed_out"
        self.hub.publish({"type": "help_closed", "id": self._help, "outcome": outcome})
        self._help = None
        if self.control == "ended":
            raise BapError(
                ENDED_BY_A_PERSON if self._ended_by == "person" else ENDED, reason="the session ended"
            )
        await self._let_go()
        tabs = await self.toolkit.tabs()
        self._publish_tabs(tabs)
        await self._set_control("agent")
        return outcome, (
            f"{self._change(tabs)} Refs from before may be out of date: take a new snapshot before you act."
        )

    # The agent's action needs a person's yes (spec 8.2).

    async def _ask_approval(self, question: Question) -> ApprovalOutcome:
        """Runs inside the agent's call, which keeps the browser while the person decides, so nothing
        else happens on the page meanwhile. No answer in time means no. A question marked
        `every_time` cannot be answered for the whole site, and one that `must_be_seen` is never
        answered for a person who is not there (spec 18.4)."""
        every_time = question.every_time
        self._approvals += 1
        self._approval, self._approval_outcome = f"a{self._approvals}", None
        control = self.config.control
        watched = self.hub.viewers > 0
        if not watched and control.approval_without_viewer == "allow" and not question.must_be_seen:
            self._approval = None
            return "allowed"
        if watched and self._unanswered >= self.config.limits.unanswered_in_a_row:
            # Nobody has answered for a while. The agent is not kept waiting for nobody again.
            self._approval = None
            return "expired"
        self.hub.publish(
            {
                "type": "approval_requested",
                "id": self._approval,
                "tool": question.tool,
                "summary": question.summary,
                "site": question.site,
                "expires_in_s": control.approval_timeout_s,
                **({"every_time": True} if every_time else {}),
                **self._reasons(question),
                "ts": self._clock(),
            }
        )
        outcome: ApprovalOutcome = "unwatched"
        if watched:
            with contextlib.suppress(TimeoutError):
                async with asyncio.timeout(control.approval_timeout_s), self._changed:
                    await self._changed.wait_for(
                        lambda: (
                            self._approval_outcome is not None
                            or self.control == "ended"
                            or self._task_stopped
                        )
                    )
            # A task or a session that was stopped has its open question answered with no.
            stopped = self.control == "ended" or self._task_stopped
            outcome = self._approval_outcome or ("denied" if stopped else "expired")
            if every_time and outcome == "allowed_site":
                outcome = "allowed"
            self._count_unanswered(outcome == "expired")
        self.hub.publish({"type": "approval_closed", "id": self._approval, "outcome": outcome})
        self._approval = None
        if self.control == "ended":
            raise BapError(
                ENDED_BY_A_PERSON if self._ended_by == "person" else ENDED, reason="the session ended"
            )
        return outcome

    def _reasons(self, question: Question) -> dict[str, Any]:
        """Why a person is asked, what would leave and what it costs (spec 18.10). The text that
        would leave is shown here and nowhere else: a person cannot decide without seeing it."""
        told: dict[str, Any] = {}
        if question.why:
            told["why"] = list(question.why)
        if question.leaves is not None:
            text, from_site, to_site = question.leaves
            told["leaves"] = {"text": self.browser.redact(text), "from_site": from_site, "to_site": to_site}
        if question.amount:
            told["amount"] = self.browser.redact(question.amount)
        if question.said:
            told["said"] = self.browser.redact(question.said)
        return told

    def _count_unanswered(self, ran_out: bool) -> None:
        """Keeps count of the questions nobody answered in a row, and says so when further ones
        will not be waited for (spec 18.8)."""
        self._unanswered = self._unanswered + 1 if ran_out else 0
        if ran_out and self._unanswered == self.config.limits.unanswered_in_a_row:
            self.hub.publish({"type": "questions_unanswered", "count": self._unanswered, "ts": self._clock()})

    async def _answer_help(self, outcome: HelpOutcome) -> None:
        if self._help_outcome is None:
            self._help_outcome = outcome
            await self._announce()

    async def _set_control(self, state: ControlState) -> None:
        if self.control == "ended":
            # Nothing brings an ended session back.
            return
        self.control = state
        self.hub.publish({"type": "control_changed", "state": state, "since": self._clock()})
        await self._announce()

    async def _announce(self) -> None:
        async with self._changed:
            self._changed.notify_all()

    @staticmethod
    def _active_address(tabs: Sequence[TabInfo]) -> str:
        return next((tab.url for tab in tabs if tab.active), "")

    def _publish_tabs(self, tabs: Sequence[TabInfo]) -> None:
        redact = self.browser.redact
        shown = [
            {"id": tab.id, "title": redact(tab.title), "url": redact(tab.url), "active": tab.active}
            # A tab with a dialog open wants a person's eye.
            | ({"attention": True} if tab.attention else {})
            for tab in tabs
        ]
        if shown != self._tabs:
            self._tabs = shown
            self.hub.publish({"type": "tab_changed", "tabs": shown})


def _shown(sites: Sequence[TaskSite]) -> list[dict[str, str]]:
    return [{"host": site.host, "grade": site.grade} for site in sites]


def _number(value: Any, lowest: float, highest: float, *, cut_to: float | None = None) -> float | None:
    """A finite number within the limits, or None. With `cut_to`, a larger one is cut to that size instead."""
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        return None
    if cut_to is not None:
        return max(-cut_to, min(cut_to, value))
    return value if lowest <= value <= highest else None
