"""One browser session as the service runs it: its tools, what its viewers are told, and who is driving."""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncGenerator, Callable, Mapping, Sequence
from contextlib import asynccontextmanager
from typing import Any, Literal

from bap_browser.config import Config
from bap_browser.driver.base import Box, Driver, TabInfo
from bap_browser.driver.session import BrowserSession
from bap_browser.service.events import EventHub
from bap_browser.tools.gate import Admission
from bap_browser.tools.toolkit import Toolkit

ControlState = Literal["agent", "paused", "person", "ended"]
EndReason = Literal["person", "agent", "timeout", "failed"]

# What an agent's call is told when it could not run (spec 4.5). None of these is an error.
HELD = {
    "paused": "A person paused the session, so nothing was done. Call again to keep waiting.",
    "person": "A person is in control of the browser, so nothing was done. Call again to keep waiting.",
}
ENDED_BY_A_PERSON = "The session was ended by a person."
ENDED = "The session has ended."


class ServiceSession:
    def __init__(
        self,
        config: Config,
        driver: Driver | None = None,
        *,
        name: str = "default",
        agent: str = "Agent",
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.config = config
        self.name = name
        self.hub = EventHub(config.viewer.history_events)
        self.browser = BrowserSession(config, driver)
        self.toolkit = Toolkit(self.browser, observer=self, gate=self._admit)
        self.control: ControlState = "agent"
        self._agent = agent
        self._clock = clock
        self._ended_by: EndReason | None = None
        # Held while an action runs, so that a person takes the browser only between actions.
        self._acting = asyncio.Lock()
        self._changed = asyncio.Condition()
        self._tabs: list[dict[str, Any]] | None = None
        self._address_at_takeover = ""
        self._note = ""

    async def start(self) -> None:
        """Starts the browser and tells viewers what this session is."""
        driver = await self.browser.driver()
        width, height = await driver.viewport()
        self.hub.publish(
            {
                "type": "session_started",
                "session": self.name,
                "agent": self._agent,
                "backend": self.config.backend.kind,
                "browser": driver.description(),
                "viewport": {"width": width, "height": height},
                "ts": self._clock(),
            }
        )
        self._publish_tabs(await self.toolkit.tabs())

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
        await self.browser.close()

    async def handle(self, command: Mapping[str, Any]) -> None:
        """Does what a person asked for in the viewer. A command that does not apply changes nothing."""
        kind = command.get("type") if isinstance(command, Mapping) else None
        if kind == "pause":
            await self._take("paused", ("agent",))
        elif kind == "take_over":
            await self._take("person", ("agent", "paused"))
        elif kind == "resume" and self.control == "paused":
            await self._set_control("agent")
        elif kind == "hand_back" and self.control == "person":
            await self._hand_back()
        elif kind == "stop":
            await self.close("person")

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
            if self.control != "agent":
                remaining = deadline - asyncio.get_running_loop().time()
                try:
                    async with asyncio.timeout(max(remaining, 0)), self._changed:
                        await self._changed.wait_for(lambda: self.control in ("agent", "ended"))
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
        tabs = await self.toolkit.tabs()
        self._publish_tabs(tabs)
        before, after = self._address_at_takeover, self._active_address(tabs)
        change = (
            f"The address is still {after}."
            if after == before
            else f"The address was {before} and is now {after}."
        )
        self._note = (
            f"[A person was in control of the browser and has handed it back. {change} "
            "Refs from before may be out of date: take a new snapshot before you act.]\n"
        )
        await self._set_control("agent")

    async def _set_control(self, state: ControlState) -> None:
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
