"""The limits of a task, and steps that go round in circles (spec 18.8).

An agent that never stops is stopped here: by a count of steps, by the time a task takes, by the
calls in one minute and by what the engine's own model calls have cost. And an agent that repeats
one step on a page that does not change is told so, and then held back.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections import deque
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any, Literal

from bap_browser.config import Limits as LimitSettings
from bap_browser.safeguards.model import Spend

MINUTE_S = 60
STOP_AND_TELL = " Stop, and tell the person what is done and what is left."
TOO_MANY_CALLS = "Too many calls at once. Wait a moment before the next step."
NOTHING_CHANGED = "\nNothing on the page changed."
IN_CIRCLES = (
    "Not done: this is the {nth} identical step and the page has not changed. "
    "Read the page, and choose a different step."
)

LimitKind = Literal["calls", "minutes", "spend"]


@dataclass(frozen=True)
class Reached:
    """A limit that has been reached: no further call runs until a person allows more."""

    kind: LimitKind
    limit: float
    text: str
    """What the agent is told."""


def same_step(name: str, arguments: Mapping[str, Any]) -> str:
    """What makes two calls the same step: the tool and its arguments, in whatever order they came."""
    return f"{name} {json.dumps(arguments, sort_keys=True, default=str)}"


def ordinal(number: int) -> str:
    if 10 <= number % 100 <= 20:
        return f"{number}th"
    return f"{number}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(number % 10, 'th') }"


class Limits:
    def __init__(
        self,
        settings: Callable[[], LimitSettings],
        spend: Spend | None = None,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        """`settings` gives the limits as they are now: a person may lower them while a task runs."""
        self._settings = settings
        self._spend = spend
        self._clock = clock
        self._sleep = sleep
        self._calls = 0
        self._more_calls = 0
        self._more_minutes = 0
        self._task_since: float | None = None
        # When each call of the last minute was let in.
        self._lately: deque[float] = deque()
        # The acting step that was last repeated with nothing changed, and how often in a row.
        self._step: str | None = None
        self._times = 0
        # The reading call that last gave the same result, and how often in a row.
        self._reading: tuple[str, int] | None = None
        self._readings = 0

    @property
    def on_a_task(self) -> bool:
        return self._task_since is not None

    def begin_task(self) -> None:
        """A task begins: its steps and its minutes are counted from here."""
        self._calls = self._more_calls = self._more_minutes = 0
        self._task_since = self._clock()
        self._forget_steps()

    def end_task(self) -> None:
        self._calls = self._more_calls = self._more_minutes = 0
        self._task_since = None
        self._forget_steps()

    def extend(self) -> None:
        """A person pressed "Allow more"."""
        settings = self._settings()
        self._more_calls += settings.extend_calls
        self._more_minutes += settings.extend_minutes

    def reached(self) -> Reached | None:
        """The limit that stops the next call, if one does. 0 means that there is no such limit."""
        settings = self._settings()
        scope = "task" if self.on_a_task else "session"
        if settings.max_calls and self._calls >= settings.max_calls + self._more_calls:
            limit = settings.max_calls + self._more_calls
            return Reached(
                "calls", limit, f"This {scope} has reached its limit of {limit} steps.{STOP_AND_TELL}"
            )
        if settings.max_task_minutes and self._task_since is not None:
            limit = settings.max_task_minutes + self._more_minutes
            if self._clock() - self._task_since >= limit * MINUTE_S:
                return Reached(
                    "minutes", limit, f"This task has reached its limit of {limit} minutes.{STOP_AND_TELL}"
                )
        limit = settings.max_model_spend_usd
        if limit and self._spend is not None and self._spend.usd >= limit:
            return Reached(
                "spend",
                limit,
                f"This session has reached its limit of ${limit:.2f} for the model calls the browser "
                f"itself makes.{STOP_AND_TELL}",
            )
        return None

    async def admit(self) -> Reached | str | None:
        """Lets one call in, and counts it. Otherwise the limit that was reached, or what the agent
        is told when calls come too fast."""
        reached = self.reached()
        if reached is not None:
            return reached
        settings = self._settings()
        if settings.max_calls_per_minute:
            now = self._clock()
            while self._lately and now - self._lately[0] >= MINUTE_S:
                self._lately.popleft()
            if len(self._lately) >= settings.max_calls_per_minute:
                wait = self._lately[0] + MINUTE_S - now
                if wait > settings.rate_wait_s:
                    return TOO_MANY_CALLS
                await self._sleep(wait)
                self._lately.popleft()
            self._lately.append(self._clock())
        self._calls += 1
        return None

    # Steps that go round in circles.

    def goes_in_circles(self, step: str) -> str | None:
        """What the agent is told instead, when this acting step has been done so often with nothing
        changed that it is not run again. None when it may run."""
        refuse_at = self._settings().repeat_refuse
        if step == self._step and self._times >= refuse_at - 1:
            return IN_CIRCLES.format(nth=ordinal(refuse_at))
        return None

    def page_changed(self) -> None:
        """The page changed by itself since the last step: the same step may do something now."""
        self._step, self._times = None, 0

    def acted(self, step: str, *, changed: bool) -> str:
        """An acting step has run. What its result gains: that nothing changed, and, the third time
        in a row, that something else is needed."""
        self._reading, self._readings = None, 0
        if changed:
            self._step, self._times = None, 0
            return ""
        self._times = self._times + 1 if step == self._step else 1
        self._step = step
        if self._times != self._settings().repeat_notice:
            return NOTHING_CHANGED
        return (
            f"{NOTHING_CHANGED}\n[notice] This is the {ordinal(self._times)} identical step and the "
            "page has not changed. Something else is needed."
        )

    def read(self, call: str, result: str) -> str:
        """A reading call has run. What its result gains when it is the same call with the same
        result several times in a row. A reading call is never refused for that: waiting for a
        page is honest work."""
        reading = (call, hash(result))
        self._readings = self._readings + 1 if reading == self._reading else 1
        self._reading = reading
        if self._readings != self._settings().repeat_notice:
            return ""
        return (
            f"\n[notice] This is the {ordinal(self._readings)} identical call with the same result. "
            "Something else is needed."
        )

    def _forget_steps(self) -> None:
        self._step, self._times = None, 0
        self._reading, self._readings = None, 0
