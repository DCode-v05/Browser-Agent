"""The browsers of a window that has several, as the HTTP surface asks about them (spec 9.17): each
is a system with settings of its own, a log, the record of its tasks, and a person's hand on
whether it runs. Whoever runs the browsers answers; the service only asks."""

from __future__ import annotations

from typing import Any, Literal, Protocol

Rating = Literal["good", "bad"]


class Systems(Protocol):
    def described(self) -> list[dict[str, Any]]:
        """Each system: where it stands, whether it is turned on, its model, and where its log is."""
        ...

    async def settings_changed(self, system: str) -> None:
        """A person changed a system's settings: one turned off is ended, one turned on is started."""
        ...

    async def manage(self, system: str, action: str) -> str | None:
        """`start`, `stop` or `restart`. None when it was done; otherwise why not, as a sentence."""
        ...

    def log(self, system: str) -> dict[str, Any]:
        """The newest lines of a system's log, and where the file is."""
        ...

    def evals(self, system: str) -> dict[str, Any]:
        """What a system's tasks took and cost, how they ended, and its checklist as last run."""
        ...

    def overall(self) -> dict[str, Any]:
        """What the tasks of every system took, as one: the admin's view of the whole."""
        ...

    def trace(self, system: str, task: str) -> dict[str, Any] | None:
        """One task with every reply of the model and every step, in order. None for no such task."""
        ...

    def rate(self, system: str, task: str, rating: Rating | None) -> bool:
        """Keeps a person's word on one answer. False for no such task."""
        ...

    async def check(self, system: str) -> dict[str, Any] | str:
        """Runs the checklist. The result; or, as a sentence, why it could not run now."""
        ...

    def suite(self, system: str) -> dict[str, Any]:
        """The task sets of a system: what each is, how its newest run went, and the run under way."""
        ...

    def suite_overall(self) -> dict[str, Any]:
        """The newest run of each task set on each system, side by side."""
        ...

    def start_suite(self, system: str, name: str, trials: int, mode: Any) -> str | None:
        """Begins a run of a task set. None when it began; otherwise why not, as a sentence."""
        ...

    async def stop_suite(self, system: str) -> bool:
        """Ends the run under way after the task it is on. False when there is none."""
        ...
