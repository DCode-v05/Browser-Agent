"""Who is told about each tool call. The session service listens, so that a person can watch."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from bap_browser.driver.base import Box, TabInfo


class StepObserver(Protocol):
    def step_started(self, step: int, tool: str, label: str, target: Box | None) -> None:
        """A call is about to run. `label` says what the agent is doing; `target` is where on the page."""
        ...

    def step_finished(
        self, step: int, ok: bool, ms: float, chars: int, summary: str, tabs: Sequence[TabInfo]
    ) -> None:
        """The call returned `chars` characters to the agent. `summary` says what happened."""
        ...

    def navigation_blocked(self, url: str, reason: str) -> None:
        """The policy refused an address."""
        ...

    def limit_reached(self, kind: str, limit: float, on_a_task: bool) -> None:
        """A limit of the task, or of the session while it has no task, stopped a call (spec 18.8)."""
        ...
