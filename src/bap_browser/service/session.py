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
from bap_browser.driver.base import Box, Driver, MouseButton, TabInfo
from bap_browser.driver.session import BrowserSession
from bap_browser.errors import BapError
from bap_browser.service.events import EventHub
from bap_browser.tools.gate import Admission
from bap_browser.tools.toolkit import Toolkit

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
    ) -> None:
        self.config = config
        self.name = name
        self.hub = EventHub(config.viewer.history_events)
        self.browser = BrowserSession(config, driver)
        self.browser.ask_person = self._ask_person
        self.toolkit = Toolkit(self.browser, observer=self, gate=self._admit)
        # The request for a person that is open now, and how it was answered.
        self._help: str | None = None
        self._help_outcome: HelpOutcome | None = None
        self._helps = 0
        self.control: ControlState = "agent"
        self._on_task = on_task
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
            "backend": self.config.backend.kind,
            "browser": driver.description(),
            "viewport": {"width": width, "height": height},
            "ts": self._clock(),
        }
        if self._on_task is not None:
            started["chat"] = True
        if not self.config.browser.headless:
            # The person watches the browser itself, so a viewer need not show its picture.
            started["on_screen"] = True
        self.hub.publish(started)
        self._publish_tabs(await self.toolkit.tabs())
        viewer = self.config.viewer
        await driver.start_frames(self._picture, getattr(viewer.quality_levels, viewer.quality))
        self._heartbeat = asyncio.create_task(self._keep_viewers_current())

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
        if kind == "pause":
            await self._take("paused", ("agent",))
        elif kind == "take_over":
            await self._take("person", ("agent", "paused", "person_requested"))
        elif kind in ("done", "could_not") and self._help is not None:
            await self._answer_help(kind)
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

    def working(self, on_a_task: bool) -> None:
        """Tells viewers whether the agent is on a task or waits for one."""
        self._on_a_task = on_a_task
        self._task_stopped = False
        self.hub.publish({"type": "task_changed", "working": on_a_task, "ts": self._clock()})

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
            for tab in tabs
        ]
        if shown != self._tabs:
            self._tabs = shown
            self.hub.publish({"type": "tab_changed", "tabs": shown})


def _number(value: Any, lowest: float, highest: float, *, cut_to: float | None = None) -> float | None:
    """A finite number within the limits, or None. With `cut_to`, a larger one is cut to that size instead."""
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        return None
    if cut_to is not None:
        return max(-cut_to, min(cut_to, value))
    return value if lowest <= value <= highest else None
