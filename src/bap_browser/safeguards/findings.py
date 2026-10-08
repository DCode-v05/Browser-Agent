"""What the fixed rules notice about one step of an agent (spec 18.4): its findings.

Each finding says what was noticed and what it asks for: a refusal, a person, or a closer look
because the rules are unsure. `check.py` says what is then done.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal
from urllib.parse import urlsplit

from bap_browser import keys
from bap_browser.address import site_pattern
from bap_browser.driver.base import Located
from bap_browser.driver.session import BrowserSession
from bap_browser.errors import BapError
from bap_browser.policy.sites import registrable_name, site_of
from bap_browser.safeguards.actions import (
    NEVER_ON_A_MODELS_WORD,
    SENDING_KEYS,
    TYPED_INTO,
    ActionClass,
    class_of,
    is_message_box,
)
from bap_browser.safeguards.incoming import carries_hidden_characters, without_invisible
from bap_browser.safeguards.lookalikes import is_bare_public_ip, lookalike_of, mixed_script_of
from bap_browser.safeguards.outgoing import (
    Amount,
    CopyMemory,
    agrees,
    amounts,
    is_consent_address,
    is_long_address,
    judged_file,
    largest,
    says_grant_access,
    sensitive_kind,
)
from bap_browser.safeguards.task import TaskBook

FindingOutcome = Literal["refuse", "person", "unsure"]
AutoState = Literal["off", "on", "paused", "waiting_for_task", "unavailable"]

# The tools that press a control, whose name can say what pressing it does.
PRESS = frozenset({"browser_click", "browser_set_checked", "browser_select_option"})
# The tools that put text into a field.
TYPE = frozenset({"browser_type", "browser_fill_form", "browser_press_key"})
# The keys that press the control that has the focus.
PRESSING_KEYS = frozenset({"Enter", "Space", " "})
OPENS_AN_ADDRESS = frozenset({"browser_navigate", "browser_tabs"})
# Addresses that are a page with no site of its own.
NO_SITE_OF_ITS_OWN = ("data:", "blob:")
# The finding each class of step is, and what a person is told of it.
DOES: dict[ActionClass, tuple[str, str]] = {
    "pays": ("paying_step", "this step pays for or orders something"),
    "sends": ("sending_step", "this step sends something to other people"),
    "deletes": ("deleting_step", "this step deletes something"),
    "grants": ("granting_step", "this step gives access to something"),
    "commits": ("consequential_word", "this step makes something final"),
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


class Findings:
    """What is known of the session that the rules need, and the rules themselves."""

    def __init__(self, session: BrowserSession, *, clock: Callable[[], float] = time.monotonic) -> None:
        self._session = session
        self._clock = clock
        self.task = TaskBook()
        self.memory = CopyMemory(lambda: self._session.config.safeguards.outgoing)
        # The tabs whose page holds a planted instruction: the rule that found it, and the page.
        self.flagged: dict[str, tuple[str, str]] = {}
        # The sites a page of which was opened in this session.
        self._visited: set[str] = set()
        # What was settled about a site, for the task: the finding, the site, and the answer.
        self._settled: dict[tuple[str, str], bool] = {}
        # What a host looks like, measured against the protected names of the moment.
        self._measured: dict[tuple[str, tuple[str, ...]], tuple[str | None, bool]] = {}
        # Why Auto Mode is paused, when it is.
        self._paused = ""
        # What the paying steps a person approved add up to.
        self._paid = Decimal(0)

    def judge_file(self, name: str, first_bytes: bytes) -> tuple[Literal["keep", "ask", "delete"], str]:
        """What is done with a file that arrived (spec 18.6): a file that can run programs is never
        kept, whatever its name says; an archive, or any file on the person's own machine, waits
        for their yes."""
        shown, _ = without_invisible(name)
        what = judged_file(
            shown,
            first_bytes,
            self._session.config.safeguards.downloads,
            own_machine=self._session.own_machine,
        )
        if what == "risky":
            return "delete", "this kind of file can run programs"
        return ("ask", "") if what == "ask" else ("keep", "")

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
                            # The person is shown what would leave as it would leave, not as it is compared.
                            sample=leaving,
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
        state = self.auto_state()[0]
        # Paused, the mode is still Auto: what it watches is still watched. Only who is asked
        # changes, from the reviewer to the person (spec 18.4).
        auto = state in ("on", "paused")
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
            state == "on"
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
            if len(self._measured) >= sites.measured_hosts:
                self._measured.clear()
            measured = self._measured[(host, protected)] = (
                lookalike_of(host, protected, sites),
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
