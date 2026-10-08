"""The check (spec 18.4): whether one step of an agent may run.

Every call goes through the same stages, and the first that settles it wins: hard stops, the
person's own browser, what is always a person's to decide, every action, what the rules are
unsure of, and then the step runs. Fixed rules say what they notice about a step as findings.
In Auto Mode a model rates the steps the rules are unsure of; a table in code turns its rating
into run, ask or refuse.
"""

from __future__ import annotations

import logging
import os
import time
from collections import deque
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from functools import partial
from typing import Any, Literal, Protocol

from bap_browser.driver.session import ApprovalOutcome, BrowserSession, Question
from bap_browser.errors import BapError, ModelError
from bap_browser.safeguards.findings import (
    Finding,
    Findings,
    Step,
)
from bap_browser.safeguards.incoming import new_token
from bap_browser.safeguards.model import ModelClient, Spend
from bap_browser.safeguards.reviewer import (
    INSTRUCTIONS,
    VERDICT_SCHEMA,
    WITHHELD,
    Shown,
    Verdict,
    question,
    read_verdict,
    risk_held,
    ruling,
    why_refused,
)
from bap_browser.safeguards.scan import flagged_by
from bap_browser.safeguards.task import TaskSite

logger = logging.getLogger(__name__)

Stage = Literal["rule", "reviewer", "person"]

NO_OTHER_WAY = " Do not try another way: ask the person, or choose a different approach."
NOT_DONE = (
    "Not done: {why}. Do not reach the same end another way. Go on with a step that is safe, or say "
    "what you need from the person."
)
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
COULD_NOT_RUN = "the check could not run"
# The reviewer's category for what a fixed rule found, for when the model names none.
CATEGORY_OF = {
    "paying_step": "pays",
    "sending_step": "sends",
    "deleting_step": "deletes",
    "granting_step": "grants_access",
    "cross_site_text": "shares_data",
    "site_outside_task": "leaves_task",
    "step_on_flagged_page": "follows_page",
}


@dataclass(frozen=True)
class Decision:
    run: bool
    text: str = ""
    """What the agent is told when the step does not run."""
    reason: str = ""
    """The same in a few words, for the person watching."""
    record: Mapping[str, Any] = field(default_factory=dict[str, Any])
    """What the event log keeps of the decision. Never page text, typed text or a model's sentence."""


class CheckObserver(Protocol):
    """Who is told what the check decides. The session service listens, for the person watching."""

    def check_decided(
        self,
        step: int,
        stage: str,
        outcome: str,
        findings: Sequence[str],
        reason: str,
        said: str = "",
        refused_id: str | None = None,
    ) -> None: ...

    def sites_changed(self, sites: Sequence[TaskSite]) -> None: ...

    def auto_changed(self) -> None: ...


class Check(Findings):
    def __init__(
        self,
        session: BrowserSession,
        observer: CheckObserver | None = None,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__(session, clock=clock)
        self._observer = observer
        self.spend = Spend()
        """What the engine's own model calls have cost in this session (spec 18.8)."""
        # The tools a person allowed on a site for the rest of the session: "Allow on this site".
        self._grants: set[tuple[str, str]] = set()
        # The newest steps that ran: the tool, the site and the timeline sentence.
        self._ran: deque[tuple[str, str, str]] = deque(maxlen=64)
        # Auto Mode: the reviewer's refusals, and what a person allowed once.
        self._refused_in_a_row = 0
        self._refused_in_all = 0
        # The steps the reviewer refused: what makes each the same step, its label and its site.
        self._refused: dict[str, tuple[str, str, str]] = {}
        self._allowed_once: dict[str, float] = {}
        self._reviewer: ModelClient | None = None
        self._reviewer_key = ""

    def resume(self) -> bool:
        """A person pressed "Resume Auto". False when it was not paused."""
        if not self._paused:
            return False
        self._paused, self._refused_in_a_row, self._refused_in_all = "", 0, 0
        return True

    def allow_once(self, refused_id: str) -> str | None:
        """A person allowed a step the check had refused. What the step was, or None when the id
        names none."""
        entry = self._refused.pop(refused_id, None)
        if entry is None:
            return None
        key, label, site = entry
        self._allowed_once[key] = self._clock() + self._session.config.safety.auto_mode.allow_once_s
        if self._settled.get(("site_outside_task", site)) is False:
            # The refusal had settled the site as outside the task. The person's word is above it.
            del self._settled[("site_outside_task", site)]
        self._session.note(
            f"the person allowed a step that was refused: {label}. Do it again if it is still needed"
        )
        return label

    def flag(self, tab: str, address: str, rule: str) -> None:
        """A page holds text that tries to give an agent instructions (spec 18.5)."""
        self.flagged[tab] = (rule, address.partition("#")[0])

    def unflag(self, tab: str) -> None:
        self.flagged.pop(tab, None)

    def now_at(self, tab: str, address: str) -> None:
        """Where a tab is now. A flag was for the page that held the text, not for the tab."""
        held = self.flagged.get(tab)
        if held is not None and held[1] != address.partition("#")[0]:
            self.unflag(tab)

    def task_began(self) -> None:
        """Another task: what was settled for the last one is asked again."""
        self._settled.clear()

    def ran(self, step: Step, summary: str) -> None:
        """A step has run: the reviewer is shown the newest of them."""
        self._ran.append((step.tool, step.site, summary))
        if step.site:
            self._visited.add(step.site)
            if not self.task.is_own(step.address):
                # From here on the agent may have read what a stranger wrote.
                self.task.read_a_page = True

    # The stages.

    async def before(self, step: Step) -> Decision:
        began = self._clock()
        config = self._session.config
        policy = config.safety.action_policies.get(step.tool, config.safety.default_action_policy)
        if policy == "deny":
            return self._decided(
                step,
                began,
                "rule",
                False,
                (),
                f"{step.tool} is not allowed on this deployment.{NO_OTHER_WAY}",
                "it is not allowed here",
            )
        findings = await self._findings(step)
        refusing = [finding for finding in findings if finding.outcome == "refuse"]
        if refusing:
            return self._refuse(step, began, "rule", refusing, refusing[0].why)
        not_allowed = await self._own_browser(step)
        if not_allowed is not None:
            return self._decided(
                step, began, "person", False, (), not_allowed + NO_OTHER_WAY, "the person has not allowed it"
            )
        asking = [finding for finding in findings if finding.outcome == "person"]
        unsure = [finding for finding in findings if finding.outcome == "unsure"]
        confirm = policy == "confirm" or (self.mode == "every_action" and step.acts)
        if unsure and not asking and not confirm and self._allowed_now(step):
            # Their yes to this very step settles what a yes to a question about it settles.
            self._agreed(step, unsure)
            return self._decided(step, began, "person", True, unsure)
        if asking or (unsure and (confirm or self.auto_state()[0] != "on")):
            return await self._ask(step, began, asking + unsure)
        if unsure:
            return await self._review(step, began, unsure)
        if confirm:
            return await self._confirm(step, began)
        return self._decided(step, began, "rule", True, ())

    async def _own_browser(self, step: Step) -> str | None:
        """On a person's own browser, whether they let the agent read or act on this site (spec
        8.8). The bridge on their machine decides, and asks them when they have not chosen yet."""
        ask = self._session.ask_site
        if ask is None or not step.on_a_site:
            return None
        if step.opens is not None and not (await self._session.policy.check(step.opens)).allowed:
            # The core's own policy refuses it: the person is not asked about what cannot be done.
            return None
        return await ask("act" if step.acts else "read", step.address, step.label)

    async def _confirm(self, step: Step, began: float) -> Decision:
        """A tool that the deployment wants confirmed, or any acting step with "ask before every
        action". A person can allow it for the site; with nobody watching the deployment decides."""
        config = self._session.config
        if (step.tool, step.host) in self._grants:
            return self._decided(step, began, "rule", True, ())
        ask = self._session.ask_approval
        if ask is None:
            answer: ApprovalOutcome = (
                "allowed" if config.control.approval_without_viewer == "allow" else "unwatched"
            )
        else:
            try:
                answer = await ask(Question(step.tool, self._summary(step), step.host))
            except BapError as exc:
                return self._decided(step, began, "person", False, (), str(exc), exc.reason)
        if answer == "allowed_site" and config.control.site_grant_lifetime == "session":
            self._grants.add((step.tool, step.host))
        return self._answered(step, began, answer, ())

    async def _ask(
        self,
        step: Step,
        began: float,
        findings: Sequence[Finding],
        *,
        said: str = "",
        record: Mapping[str, Any] | None = None,
    ) -> Decision:
        """A question that a finding raised. It is asked every time, it cannot be allowed for a
        whole site, and with nobody watching it is refused whatever the deployment says of other
        questions: a person must have seen it."""
        ask = self._session.ask_approval
        answer: ApprovalOutcome = "unwatched"
        if ask is not None:
            leaving = next((finding for finding in findings if finding.leaves is not None), None)
            shown = self._session.config.safeguards.outgoing.question_chars
            asked = Question(
                step.tool,
                self._summary(step),
                step.host,
                every_time=True,
                must_be_seen=True,
                why=tuple(dict.fromkeys(finding.why for finding in findings)),
                leaves=(
                    None
                    if leaving is None or leaving.leaves is None
                    else (self._session.redact(leaving.sample[:shown]), *leaving.leaves)
                ),
                amount=next((finding.amount for finding in findings if finding.amount), ""),
                said=said,
            )
            try:
                answer = await ask(asked)
            except BapError as exc:
                return self._decided(step, began, "person", False, findings, str(exc), exc.reason)
        if answer in ("allowed", "allowed_site"):
            self._agreed(step, findings)
        else:
            self._declined(step, findings)
        return self._answered(step, began, answer, findings, record)

    async def _review(self, step: Step, began: float, findings: Sequence[Finding]) -> Decision:
        """Auto Mode: a model rates the step, and the table in code says what happens."""
        flagged = step.tab in self.flagged
        try:
            verdict = await self._verdict(step, findings)
        except ModelError as failed:
            # The cause is for whoever runs the service. The person is asked instead.
            logger.warning("The check could not run: %s", failed)
            could_not = Finding("check_failed", "unsure", COULD_NOT_RUN)
            return await self._ask(step, began, [*findings, could_not])
        held = any(finding.held_high for finding in findings)
        what = ruling(verdict, held_high=held, page_flagged=flagged)
        record = {
            "risk": risk_held(verdict, held_high=held),
            "asked_for": verdict.asked_for,
            "category": verdict.category,
        }
        ids = [finding.id for finding in findings]
        if what == "refuse":
            by_the_rules = next(
                (CATEGORY_OF[finding.id] for finding in findings if finding.id in CATEGORY_OF), ""
            )
            why = why_refused(verdict, by_the_rules)
            return self._refuse(step, began, "reviewer", findings, why, verdict, record)
        self._refused_in_a_row = 0
        if self._observer is not None:
            self._observer.check_decided(step.number, "reviewer", what, ids, "", verdict.reason)
        if what == "ask":
            return await self._ask(step, began, findings, said=verdict.reason, record=record)
        self._agreed(step, findings, by_the_check=True)
        return self._decided(step, began, "reviewer", True, findings, record=record)

    # What a decision leads to.

    def _agreed(self, step: Step, findings: Sequence[Finding], *, by_the_check: bool = False) -> None:
        """A person said yes, or the reviewer let the step run: what that settles."""
        changed = False
        for finding in findings:
            if finding.site_wide:
                self._settled[(finding.id, step.site)] = True
            if finding.id == "site_outside_task":
                changed |= self.task.add(step.site, "added_read")
            elif finding.id == "first_action_on_added_site":
                changed |= self.task.add(step.site, "added_act")
            elif finding.id == "paying_step" and not by_the_check:
                paid = self._amount(step)
                if paid is not None:
                    self._paid += paid.value
        if changed and self._observer is not None:
            self._observer.sites_changed(self.task.sites())

    def _declined(self, step: Step, findings: Sequence[Finding]) -> None:
        for finding in findings:
            if finding.id == "site_outside_task":
                # One site is settled once for the task: it is not asked about at every call.
                self._settled[(finding.id, step.site)] = False

    def _refuse(
        self,
        step: Step,
        began: float,
        stage: Stage,
        findings: Sequence[Finding],
        why: str,
        verdict: Verdict | None = None,
        record: Mapping[str, Any] | None = None,
    ) -> Decision:
        refused_id: str | None = None
        if verdict is not None:
            # What the reviewer refused, a person may allow once. A hard stop has no such way round.
            refused_id = f"r{len(self._refused) + self._refused_in_all + 1}"
            self._refused[refused_id] = (self._same_step(step), step.label, step.site)
            self._count_a_refusal()
        self._declined(step, findings)
        if self._observer is not None:
            self._observer.check_decided(
                step.number,
                stage,
                "refuse",
                [finding.id for finding in findings],
                why,
                verdict.reason if verdict is not None else "",
                refused_id,
            )
        return self._decided(step, began, stage, False, findings, NOT_DONE.format(why=why), why, record)

    def _count_a_refusal(self) -> None:
        auto = self._session.config.safety.auto_mode
        self._refused_in_a_row += 1
        self._refused_in_all += 1
        if self._refused_in_a_row >= auto.refusals_in_a_row:
            self._paused = f"{self._refused_in_a_row} steps in a row were refused"
        elif self._refused_in_all >= auto.refusals_per_session:
            self._paused = f"{self._refused_in_all} steps were refused in this session"
        if self._paused and self._observer is not None:
            self._observer.auto_changed()

    def _answered(
        self,
        step: Step,
        began: float,
        answer: ApprovalOutcome,
        findings: Sequence[Finding],
        record: Mapping[str, Any] | None = None,
    ) -> Decision:
        if answer in ("allowed", "allowed_site"):
            return self._decided(step, began, "person", True, findings, record=record)
        text, reason = NOT_APPROVED[answer]
        return self._decided(step, began, "person", False, findings, text, reason, record)

    def _decided(
        self,
        step: Step,
        began: float,
        stage: Stage,
        run: bool,
        findings: Sequence[Finding],
        text: str = "",
        reason: str = "",
        record: Mapping[str, Any] | None = None,
    ) -> Decision:
        kept: dict[str, Any] = {
            "stage": stage,
            "outcome": "run" if run else "refuse",
            "findings": [finding.id for finding in findings],
            **(record or {}),
            "ms": round((self._clock() - began) * 1000, 1),
        }
        return Decision(run, text, reason or "", kept)

    def _summary(self, step: Step) -> str:
        return f"{step.label} on {step.host}" if step.host else step.label

    def _same_step(self, step: Step) -> str:
        """What makes a step the same step once more: its tool, its site, its control and what it types."""
        control = step.control
        return repr(
            (
                step.tool,
                step.site,
                control.role if control else "",
                control.name if control else "",
                step.typed,
            )
        )

    def _allowed_now(self, step: Step) -> bool:
        """Whether a person allowed this very step, a moment ago, after the check had refused it."""
        until = self._allowed_once.pop(self._same_step(step), None)
        return until is not None and self._clock() <= until

    # The reviewer.

    def _client(self) -> ModelClient:
        config = self._session.config
        key = os.environ.get(config.agent.api_key_env, "").strip()
        if not key:
            raise ModelError(f"{config.agent.api_key_env} is not set")
        if self._reviewer is None or key != self._reviewer_key:
            self._reviewer = ModelClient(
                config.agent, config.safeguards.model, key, "reviewer", spend=self.spend
            )
            self._reviewer_key = key
        return self._reviewer

    def _for_the_model(self, text: str, limit: int) -> tuple[str, bool]:
        """Text a page or the agent wrote, as a model may be given it: cut, and withheld when it
        trips a fixed rule. The second value says whether it was withheld."""
        cut = self._session.redact(text[:limit])
        tool_names = self._session.tool_names
        return (WITHHELD, True) if flagged_by(cut, tool_names) else (cut, False)

    async def _verdict(self, step: Step, findings: Sequence[Finding]) -> Verdict:
        config = self._session.config
        shown, auto = config.safeguards.reviewer, config.safety.auto_mode
        tripped = step.tab in self.flagged
        control = step.control
        name, withheld = self._for_the_model(control.name, shown.name_chars) if control else ("", False)
        tripped |= withheld
        typed: str | None = None
        if step.typed is not None:
            typed, withheld = self._for_the_model(step.typed, shown.typed_chars)
            tripped |= withheld
        address: str | None = None
        if step.opens is not None:
            address, withheld = self._for_the_model(step.opens, shown.address_chars)
            tripped |= withheld
        told: list[dict[str, str]] = []
        for finding in findings:
            entry = {"id": finding.id, "detail": finding.why}
            if finding.sample:
                entry["sample"], withheld = self._for_the_model(finding.sample, shown.sample_chars)
                tripped |= withheld
            told.append(entry)
        earlier: list[tuple[str, str, str]] = []
        for tool, site, summary in list(self._ran)[-auto.steps_shown :]:
            sentence, withheld = self._for_the_model(summary, len(summary))
            earlier.append((tool, site, sentence))
        sites = self.task.sites()
        given = partial(
            question,
            task=self.task.text or "",
            task_from=self.task.source or "person",
            earlier=self.task.earlier[-auto.earlier_tasks_shown :],
            named=[site.host for site in sites if site.grade == "named"],
            added=[site.host for site in sites if site.grade != "named"],
            own_browser=self._session.ask_site is not None,
            steps_so_far=earlier,
            step=Shown(
                step.tool,
                step.site,
                self._does(step),
                control.role if control else "",
                name,
                typed,
                address,
            ),
            findings=told,
            page_flagged=tripped,
        )
        # The marks are made with a token that occurs nowhere in what they are put around.
        token = new_token(given(token=""))
        answer = await self._client().ask(
            INSTRUCTIONS, given(token=token), name="verdict", schema=VERDICT_SCHEMA
        )
        return read_verdict(answer, self._session.config.safeguards.reviewer.reason_chars)
