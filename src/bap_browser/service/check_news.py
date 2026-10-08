"""What the check on each step reports, told to the people watching (spec 18.10): what was
decided, the task and its sites, how Auto Mode stands, a flagged page, a limit that was reached.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from bap_browser.config import Config
from bap_browser.driver.session import BrowserSession, Question
from bap_browser.policy.sites import origin_of
from bap_browser.safeguards.task import TaskSite
from bap_browser.service.events import EventHub
from bap_browser.tools.toolkit import Toolkit

# The commands of a viewer that are for the check (spec 18.10).
ASKED_OF_THE_CHECK = frozenset({"resume_auto", "allow_refused", "drop_site", "extend_limit"})


class CheckNews:
    """The part of a session that passes the check's news on to its viewers. It is told by the
    tool layer (`StepObserver`), and a session is one of these."""

    config: Config
    hub: EventHub
    browser: BrowserSession
    toolkit: Toolkit
    _clock: Callable[[], float]
    _auto_told: dict[str, Any] | None
    _unanswered: int

    def asked_of_the_check(self, kind: str, command: Mapping[str, Any]) -> None:
        """What a person asks of the check in the viewer: Auto Mode on again, a refused step
        allowed once, a site taken out of the task, more steps."""
        check = self.toolkit.check
        if kind == "resume_auto" and check.resume():
            self._tell_auto()
        elif kind == "allow_refused" and isinstance(command.get("id"), str):
            if check.allow_once(command["id"]) is not None:
                self.hub.publish({"type": "refused_allowed", "id": command["id"], "ts": self._clock()})
        elif kind == "drop_site" and isinstance(command.get("host"), str):
            if check.task.drop(command["host"]):
                self.sites_changed(check.task.sites())
        elif kind == "extend_limit" and self.toolkit.allow_more():
            self._limit_lifted()

    def _count_unanswered(self, ran_out: bool) -> None:
        """Keeps count of the questions nobody answered in a row, and says so when further ones
        will not be waited for (spec 18.8)."""
        self._unanswered = self._unanswered + 1 if ran_out else 0
        if ran_out and self._unanswered == self.config.limits.unanswered_in_a_row:
            self.hub.publish({"type": "questions_unanswered", "count": self._unanswered, "ts": self._clock()})

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

    def page_flagged(self, tab: str, site: str, rule: str, count: int) -> None:
        self.hub.publish(
            {
                "type": "page_flagged",
                "tab": tab,
                "site": site,
                "rule": rule,
                "count": count,
                "ts": self._clock(),
            }
        )

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


def _shown(sites: Sequence[TaskSite]) -> list[dict[str, str]]:
    return [{"host": site.host, "grade": site.grade} for site in sites]
