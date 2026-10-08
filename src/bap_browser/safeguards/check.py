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
from decimal import Decimal
from functools import partial
from typing import Any, Literal, Protocol
from urllib.parse import urlsplit

from bap_browser import keys
from bap_browser.driver.base import Located
from bap_browser.driver.session import ApprovalOutcome, BrowserSession, Question
from bap_browser.errors import BapError, ModelError
from bap_browser.policy.address import site_pattern
from bap_browser.policy.sites import registrable_name, site_of
from bap_browser.safeguards.actions import (
    NEVER_ON_A_MODELS_WORD,
    SENDING_KEYS,
    TYPED_INTO,
    ActionClass,
    class_of,
    is_message_box,
)
from bap_browser.safeguards.incoming import carries_hidden_characters, new_token
from bap_browser.safeguards.lookalikes import is_bare_public_ip, lookalike_of, mixed_script_of
from bap_browser.safeguards.model import ModelClient
from bap_browser.safeguards.outgoing import (
    Amount,
    CopyMemory,
    agrees,
    amounts,
    is_consent_address,
    is_long_address,
    largest,
    says_grant_access,
    sensitive_kind,
)
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
from bap_browser.safeguards.task import TaskBook, TaskSite

logger = logging.getLogger(__name__)

Stage = Literal["rule", "reviewer", "person"]
FindingOutcome = Literal["refuse", "person", "unsure"]
AutoState = Literal["off", "on", "paused", "waiting_for_task", "unavailable"]

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
# The tools that press a control, whose name can say what pressing it does.
PRESS = frozenset({"browser_click", "browser_set_checked", "browser_select_option"})
# The tools that put text into a field.
TYPE = frozenset({"browser_type", "browser_fill_form", "browser_press_key"})
# The keys that press the control that has the focus.
PRESSING_KEYS = frozenset({"Enter", "Space", " "})
OPENS_AN_ADDRESS = frozenset({"browser_navigate", "browser_tabs"})
# Addresses that are a page with no site of its own.
NO_SITE_OF_ITS_OWN = ("data:", "blob:")
# How many hosts are remembered as measured against the protected names. Past it the memory begins again.
MOST_HOSTS_MEASURED = 256

# The finding each class of step is, and what a person is told of it.
DOES: dict[ActionClass, tuple[str, str]] = {
    "pays": ("paying_step", "this step pays for or orders something"),
    "sends": ("sending_step", "this step sends something to other people"),
    "deletes": ("deleting_step", "this step deletes something"),
    "grants": ("granting_step", "this step gives access to something"),
    "commits": ("consequential_word", "this step makes something final"),
}
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
A_FIELD_FOR = {
    "password": "a password",
    "card": "a card number",
    "code": "a code",
    "identity": "an identity or account number",
}
A_SITE_FOR = {
    "money": "a money site",
    "identity": "an identity site",
    "health": "a health site",
    "government": "a government site",
    "more": "a sensitive site",
}


@dataclass(frozen=True)
class Finding:
    """What a fixed rule noticed about a step."""

    id: str
    outcome: FindingOutcome
    why: str
    """In the engine's own words, for the person and for the reviewer. Never text of a page."""
    held_high: bool = False
    """No model may let such a step run (the floor)."""
    sample: str = ""
    """For text that leaves: the text."""
    leaves: tuple[str, str] | None = None
    """For text that leaves: the site it was read on, and the site it goes to."""
    amount: str = ""
    site_wide: bool = False
    """It is about the site, not the step: an answer settles it for the site."""


@dataclass(frozen=True)
class Step:
    """One call of an agent, as the check sees it."""

    number: int
    tool: str
    arguments: Mapping[str, Any]
    acts: bool
    address: str
    """Where it acts: the address it asks for, or else where the browser is."""
    opens: str | None = None
    """The address it asks the browser to open."""
    tab: str = ""
    control: Located | None = None
    fields: tuple[Located, ...] = ()
    """The fields it types into."""
    typed: str | None = None
    label: str = ""
    """What it does, in a sentence for a person."""
    on_a_site: bool = True
    """False for a call that touches no site: asking a person, waiting, the list of saved files."""

    @property
    def site(self) -> str:
        return site_of(self.address)

    @property
    def host(self) -> str:
        try:
            return (urlsplit(self.address).hostname or "").lower()
        except ValueError:
            return ""


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


class Check:
    def __init__(
        self,
        session: BrowserSession,
        observer: CheckObserver | None = None,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._session = session
        self._observer = observer
        self._clock = clock
        self.task = TaskBook()
        self.memory = CopyMemory(lambda: self._session.config.safeguards.outgoing)
        # The tools a person allowed on a site for the rest of the session: "Allow on this site".
        self._grants: set[tuple[str, str]] = set()
        # The tabs whose page holds a planted instruction: the rule that found it, and the page.
        self.flagged: dict[str, tuple[str, str]] = {}
        # The sites a page of which was opened in this session.
        self._visited: set[str] = set()
        # What was settled about a site, for the task: the finding, the site, and the answer.
        self._settled: dict[tuple[str, str], bool] = {}
        # What a host looks like, measured against the protected names of the moment.
        self._measured: dict[tuple[str, tuple[str, ...]], tuple[str | None, bool]] = {}
        # The newest steps that ran: the tool, the site and the timeline sentence.
        self._ran: deque[tuple[str, str, str]] = deque(maxlen=64)
        # Auto Mode: the reviewer's refusals, the pause they lead to, and what a person allowed once.
        self._refused_in_a_row = 0
        self._refused_in_all = 0
        self._paused = ""
        self._refused: dict[str, tuple[str, str]] = {}
        self._allowed_once: dict[str, float] = {}
        self._reviewer: ModelClient | None = None
        self._reviewer_key = ""
        # What the paying steps a person approved add up to.
        self._paid = Decimal(0)

    # The mode.

    @property
    def mode(self) -> str:
        safety = self._session.config.safety
        if safety.ask_before == "auto" and not safety.auto_mode.offered:
            # A choice kept from a time when Auto was offered.
            return "risky"
        return safety.ask_before

    def auto_state(self) -> tuple[AutoState, str]:
        """How Auto Mode stands, and why when it is not simply on."""
        if self.mode != "auto":
            return "off", ""
        name = self._session.config.agent.api_key_env
        if not os.environ.get(name, "").strip():
            return "unavailable", f"{name} is not set, so there is no model to check the steps"
        if self._paused:
            return "paused", self._paused
        if not self.task.set:
            return "waiting_for_task", ""
        return "on", ""

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
        key, label = entry
        self._allowed_once[key] = self._clock() + self._session.config.safety.auto_mode.allow_once_s
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
            self._refused[refused_id] = (self._same_step(step), step.label)
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
                config.agent, config.safeguards.model, key, "reviewer", spend=self._session.spend
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
        return read_verdict(answer)

    # The findings.

    def _does(self, step: Step) -> ActionClass | None:
        """What the step does: the class of the control it presses, or sending a message."""
        control, config = step.control, self._session.config
        if control is None:
            return None
        actions = config.safeguards.actions
        a_field = control.role in TYPED_INTO or control.multiline or control.kind == "text"
        message_box = a_field and is_message_box(
            control.role, [control.name], actions, multiline=control.multiline, search=control.search
        )
        if step.tool == "browser_type":
            return "sends" if step.arguments.get("submit") is True and message_box else None
        if step.tool == "browser_press_key":
            pressed = _normal(step.arguments.get("keys"))
            if a_field:
                return "sends" if message_box and pressed in SENDING_KEYS else None
            if pressed not in PRESSING_KEYS:
                return None
        elif step.tool not in PRESS:
            return None
        named = control.name
        chosen = step.arguments.get("values")
        if step.tool == "browser_select_option" and isinstance(chosen, list):
            named = " ".join([named, *(value for value in chosen if isinstance(value, str))])
        does = class_of(named, actions, config.permissions.consequential_words, role=control.role)
        if does is None and any(
            is_message_box(role, [label], actions, multiline=multiline, search=search)
            for role, label, multiline, search in control.sends_form
        ):
            # The button of a form that holds a message sends it, whatever the button is called.
            return "sends"
        return does

    def _amount(self, step: Step) -> Amount | None:
        """The largest amount of money shown at a paying control: in its name, else in its form,
        else in the block around it."""
        control = step.control
        if control is None:
            return None
        currency = self._session.config.safeguards.money.currency
        for text in (control.name, *control.around):
            found = largest(amounts(text), currency)
            if found is not None:
                return found
        return None

    def _sensitive(self, located: Located) -> str | None:
        """The kind of sensitive field a field is, or None (spec 18.6)."""
        if located.secret or located.input_type == "password" or located.dots:
            return "password"
        completes = located.autocomplete
        if completes in ("current-password", "new-password"):
            return "password"
        if completes == "one-time-code":
            return "code"
        if completes.startswith("cc-"):
            return "card"
        return sensitive_kind(
            self._session.config.safeguards.outgoing.sensitive_words,
            texts=[located.name],
            attributes=list(located.attributes),
        )

    def _kind_of_site(self, host: str) -> str | None:
        """What kind of sensitive site a host is, or None (spec 18.7)."""
        lists = self._session.config.safeguards.sites.sensitive
        for kind in ("money", "identity", "health", "government", "more"):
            for entry in getattr(lists, kind):
                try:
                    listed = site_pattern(entry).removeprefix("*.")
                except ValueError:
                    continue
                if host == listed or host.endswith("." + listed):
                    return A_SITE_FOR[kind]
        return None

    async def _findings(self, step: Step) -> list[Finding]:
        """What the fixed rules notice about a step. On the core's own pages only what the step
        does is noticed: nothing there is a stranger's."""
        found: list[Finding] = []
        own = self.task.is_own(step.address)
        does = self._does(step)
        if does is not None:
            identity, why = DOES[does]
            amount = self._amount(step) if does == "pays" else None
            found.append(
                Finding(
                    identity,
                    "unsure",
                    why,
                    held_high=does in NEVER_ON_A_MODELS_WORD,
                    amount=amount.shown if amount else "",
                )
            )
            if does == "pays" and not own:
                found += self._money(step, amount)
        if own:
            return found
        found += self._what_goes_out(step)
        found += await self._grants_access(step)
        found += self._about_the_site(step)
        if step.acts and step.tab in self.flagged:
            found.append(
                Finding(
                    "step_on_flagged_page",
                    "unsure",
                    "this page held text that tried to give instructions to an AI agent",
                )
            )
        return found

    def _money(self, step: Step, amount: Amount | None) -> list[Finding]:
        """The caps on what a paying step may show (spec 18.6)."""
        money = self._session.config.safeguards.money
        cap, in_all = Decimal(str(money.max_amount)), Decimal(str(money.max_session_total))
        if not cap and not in_all:
            return []
        control = step.control
        if amount is None:
            shown_at_all = control is not None and any(
                amounts(text) for text in (control.name, *control.around)
            )
            if shown_at_all:
                return [
                    Finding(
                        "money_over_cap",
                        "refuse",
                        f"the page shows an amount that is not in {money.currency}, the currency of the "
                        "spending limit",
                    )
                ]
            return [Finding("money_unseen", "person", "a spending limit is set and the page shows no amount")]
        if cap and amount.value > cap:
            return [
                Finding(
                    "money_over_cap",
                    "refuse",
                    f"the page shows {amount.shown}, which is over the spending limit of {_plain(cap)} for one step",
                )
            ]
        if in_all and self._paid + amount.value > in_all:
            return [
                Finding(
                    "money_over_cap",
                    "refuse",
                    f"the page shows {amount.shown}, which would take this session over its spending "
                    f"limit of {_plain(in_all)}",
                )
            ]
        return []

    def _what_goes_out(self, step: Step) -> list[Finding]:
        """Passwords, text carried from one site to another, hidden characters, long addresses."""
        found: list[Finding] = []
        guards = self._session.config.safeguards
        outgoing = guards.outgoing
        if outgoing.sensitive_fields and step.tool in TYPE:
            typing_a_key = step.tool != "browser_press_key" or keys.is_typed_text(
                str(step.arguments.get("keys", ""))
            )
            kinds = [kind for located in step.fields if (kind := self._sensitive(located))]
            if kinds and typing_a_key:
                if step.address.startswith(NO_SITE_OF_ITS_OWN):
                    found.append(
                        Finding(
                            "data_address",
                            "refuse",
                            f"this page has no site of its own and asks for {A_FIELD_FOR[kinds[0]]}",
                        )
                    )
                else:
                    found.append(
                        Finding(
                            "sensitive_field",
                            "person",
                            f"this step types {A_FIELD_FOR[kinds[0]]} into a field",
                        )
                    )
        leaving = step.typed
        if step.opens is not None:
            parts = urlsplit(step.opens)
            leaving = " ".join(part for part in (parts.path, parts.query, parts.fragment) if part)
        if leaving:
            if carries_hidden_characters(leaving, guards.incoming.hidden_message_chars):
                found.append(
                    Finding(
                        "hidden_characters_out",
                        "unsure",
                        "what this step types or opens holds characters nobody can see",
                    )
                )
            if outgoing.cross_site_text and step.site:
                known = [self.task.text or "", *self.task.earlier]
                copy = self.memory.copied(leaving, step.site, known=known)
                if copy is not None:
                    found.append(
                        Finding(
                            "cross_site_text",
                            "unsure",
                            f"this step carries text that was read on {copy.site} to {step.site}",
                            held_high=True,
                            sample=copy.sample,
                            leaves=(copy.site, step.site),
                        )
                    )
        if step.opens is not None and is_long_address(step.opens, outgoing.long_address_chars):
            new_here = step.site not in self._visited and self.task.grade(step.site) is None
            if new_here and not self._is_settled("long_address", step.site):
                found.append(
                    Finding(
                        "long_address",
                        "unsure",
                        f"this step opens a very long address on {step.site}, a site that is new here",
                        site_wide=True,
                    )
                )
        return found

    async def _grants_access(self, step: Step) -> list[Finding]:
        """A press that agrees to give an app access to an account (spec 18.6)."""
        outgoing = self._session.config.safeguards.outgoing
        control = step.control
        if not outgoing.grant_access or control is None or step.tool not in PRESS or not agrees(control.name):
            return []
        on_a_consent_screen = is_consent_address(step.address, outgoing.consent_addresses)
        if not on_a_consent_screen:
            driver = self._session.started_driver
            try:
                on_a_consent_screen = driver is not None and says_grant_access(await driver.gist())
            except BapError:
                on_a_consent_screen = False
        if not on_a_consent_screen:
            return []
        return [Finding("grant_access", "person", "this step gives an app access to an account")]

    def _is_settled(self, finding: str, site: str) -> bool:
        return self._settled.get((finding, site)) is True

    def _about_the_site(self, step: Step) -> list[Finding]:
        """Bad and sensitive sites, and the sites of the task (spec 18.3, 18.7). The site is judged
        at every call: the one a navigation asks for, or else the one the browser is on."""
        found: list[Finding] = []
        config = self._session.config
        sites, site, host = config.safeguards.sites, step.site, step.host
        if step.opens is not None and step.opens.startswith(NO_SITE_OF_ITS_OWN):
            found.append(
                Finding("data_address", "person", "this step opens a page that has no site of its own")
            )
        if not host:
            return found
        like, mixed = self._alike(host, site)
        if like is not None and sites.lookalike and not self._is_settled("lookalike_site", site):
            found.append(
                Finding("lookalike_site", "person", f"{host} looks like {like} and is not it", site_wide=True)
            )
        if mixed and sites.mixed_script and not self._is_settled("mixed_script_site", site):
            found.append(
                Finding(
                    "mixed_script_site",
                    "person",
                    "the name of this site is written with look-alike letters",
                    site_wide=True,
                )
            )
        kind = self._kind_of_site(host)
        auto = self.auto_state()[0] == "on"
        if kind is not None:
            if not self._is_settled("sensitive_site", site):
                found.append(Finding("sensitive_site", "person", f"{host} is {kind}", site_wide=True))
            elif step.acts and not self._session.watched():
                found.append(
                    Finding("step_on_sensitive_site", "refuse", f"{host} is {kind} and nobody is watching")
                )
            elif step.acts and auto:
                found.append(Finding("step_on_sensitive_site", "unsure", f"this step acts on {host}, {kind}"))
        pressing_or_typing = step.tool in PRESS or step.tool in TYPE
        # A weak sign by itself: it is for the reviewer to weigh, not for a person to be asked about.
        if (
            auto
            and sites.ip_hosts
            and pressing_or_typing
            and is_bare_public_ip(host)
            and not self._is_settled("ip_host", site)
        ):
            found.append(Finding("ip_host", "unsure", f"{host} is a bare number, not a name", site_wide=True))
        if auto and self._session.ask_site is None:
            found += self._outside_the_task(step)
        return found

    def _alike(self, host: str, site: str) -> tuple[str | None, bool]:
        """The protected name a host looks like, and whether its name is written with look-alike
        letters. A host is measured once against the same names: it is met at every call."""
        config = self._session.config
        sites = config.safeguards.sites
        protected = (
            *(listed.host for listed in self.task.sites() if listed.grade == "named" and listed.host != site),
            *(registrable_name(entry.removeprefix("*.")) for entry in config.safety.allowed_domains),
            *sites.protected,
        )
        measured = self._measured.get((host, protected))
        if measured is None:
            if len(self._measured) >= MOST_HOSTS_MEASURED:
                self._measured.clear()
            measured = self._measured[(host, protected)] = (
                lookalike_of(host, protected, lure_words=sites.lure_words, common_words=sites.common_words),
                mixed_script_of(host, protected) is not None,
            )
        return measured

    def _outside_the_task(self, step: Step) -> list[Finding]:
        """Auto Mode, on the cloud browser and the built-in one: a site that is not the task's is
        not read and not acted on until that is settled (spec 18.3)."""
        site, grade = step.site, self.task.grade(step.site)
        if grade is None:
            if self._settled.get(("site_outside_task", site)) is False:
                return [
                    Finding(
                        "site_outside_task", "refuse", f"{site} is outside the task, and that was settled"
                    )
                ]
            return [Finding("site_outside_task", "unsure", f"{site} is not one of the sites of the task")]
        if grade == "added_read" and step.acts and step.tool not in OPENS_AN_ADDRESS:
            return [
                Finding(
                    "first_action_on_added_site",
                    "unsure",
                    f"this is the first step that acts on {site}, a site that was added for reading",
                )
            ]
        return []


def _plain(number: Decimal) -> str:
    """A number as a person writes it: 50, not 50.0 or 5E+1."""
    return format(number.normalize(), "f")


def _normal(pressed: Any) -> str:
    """Keys as the driver is given them, or as they came when they cannot be read."""
    if not isinstance(pressed, str):
        return ""
    try:
        return keys.normalise(pressed)
    except BapError:
        return pressed
