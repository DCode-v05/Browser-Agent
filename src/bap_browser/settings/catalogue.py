"""The settings catalogue (spec 10.2): each setting a person can change, the configuration key it
changes, the surfaces it appears on, and how a person's value is limited by the deployment's.

The settings screen is drawn from this, so a setting is defined once. A build lists only the
settings whose feature it contains.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, ClassVar, Literal

from bap_browser.config import Config
from bap_browser.policy.url_policy import site_pattern

Value = str | bool | list[str] | None
Reason = Literal["locked", "not_on_this_surface", "would_loosen", "not_a_choice", "bad_site"]
Patch = dict[str, Any]
"""Configuration keys, written with dots, and the values a setting gives them."""

SURFACES = ("web", "mobile", "desktop")
EVERYWHERE = SURFACES
NOT_ON_MOBILE = ("web", "desktop")
GROUPS = (
    "Browser",
    "Agent",
    "Approvals",
    "Safety",
    "Sites",
    "Files",
    "Limits",
    "Privacy",
    "Live view",
    "Appearance",
    "Advanced",
)
CLOUD = "remote_headless"
# The name of the event log, in the data folder, for a person who turns it on where the deployment has none.
EVENT_LOG_NAME = "events.jsonl"


def read(config: Config, key: str) -> Any:
    """The value of a configuration key written with dots."""
    node: Any = config
    for part in key.split("."):
        node = getattr(node, part)
    return node


@dataclass(frozen=True)
class Option:
    value: str
    label: str
    hint: str = ""


@dataclass(frozen=True, kw_only=True)
class Entry:
    """One setting. `config` is always the deployment's configuration for the session in question:
    what holds when the person has chosen nothing."""

    id: str
    group: str
    surfaces: tuple[str, ...]
    title: str
    description: str
    applies: Literal["now", "next_session"] = "now"
    backends: tuple[str, ...] | None = None
    """The backends whose sessions the setting changes. None means every one."""
    per_system: bool = False
    """Where a service has several browsers (spec 9.17), a person sets it for each one by itself."""
    only_per_system: bool = False
    """It is a setting of one browser among several, and of nothing else: it is not there for a
    service with one session."""
    user: bool = False
    """A user may set it for themselves (spec 4.11), inside what the admin set and where the admin
    lets users change it. Every other setting is the admin's alone."""

    CONTROL: ClassVar[str] = ""

    @property
    def control(self) -> str:
        """The kind of control the screen draws for it."""
        return self.CONTROL

    def deployed(self, config: Config) -> Value:
        """The setting's value as the deployment has it."""
        raise NotImplementedError

    def problem(self, value: Any, config: Config) -> Reason | None:
        """Why a person may not have this value. None when they may."""
        raise NotImplementedError

    def patch(self, value: Value, config: Config, system: str | None = None) -> Patch:
        """What the value changes in the configuration. `system` names the browser the
        configuration is for, where the service has several."""
        raise NotImplementedError

    def fixed_by_deployment(self, config: Config) -> bool:
        """The deployment's value is the only one a person may have, so there is nothing to choose."""
        return False

    def described(self, config: Config) -> dict[str, Any]:
        """What the screen needs besides the value: the control and what it offers."""
        return {}

    def tidy(self, value: Any) -> Value:
        """The value as it is kept, once it has been found to have no problem."""
        return value

    def shown(self, value: Value, config: Config) -> Value:
        """The value as the screen shows it."""
        return value

    def free(self) -> Entry:
        """The setting as the admin has it: with every choice open, the looser ones too. Only
        a user is held to what stands above them."""
        return self


@dataclass(frozen=True, kw_only=True)
class Choice(Entry):
    """One of a few named values of a configuration key."""

    key: str
    options: tuple[Option, ...]
    """With `tighten`, the loosest comes first and the strictest last."""
    tighten: bool = False
    """A person may choose a stricter value than the deployment's, never a looser one."""
    dropdown: bool = False

    @property
    def control(self) -> str:
        return "select" if self.dropdown else "choice"

    def offered(self, config: Config) -> tuple[Option, ...]:
        return self.options

    def deployed(self, config: Config) -> Value:
        return str(read(config, self.key))

    def _too_loose(self, value: str, config: Config) -> bool:
        if not self.tighten:
            return False
        order = [option.value for option in self.offered(config)]
        deployed = str(self.deployed(config))
        return deployed in order and order.index(value) < order.index(deployed)

    def problem(self, value: Any, config: Config) -> Reason | None:
        if not isinstance(value, str) or value not in [option.value for option in self.offered(config)]:
            return "not_a_choice"
        return "would_loosen" if self._too_loose(value, config) else None

    def patch(self, value: Value, config: Config, system: str | None = None) -> Patch:
        return {self.key: value}

    def free(self) -> Entry:
        return replace(self, tighten=False)

    def fixed_by_deployment(self, config: Config) -> bool:
        deployed = self.deployed(config)
        return self.tighten and all(
            option.value == deployed or self._too_loose(option.value, config)
            for option in self.offered(config)
        )

    def described(self, config: Config) -> dict[str, Any]:
        choices: list[dict[str, Any]] = []
        for option in self.offered(config):
            choice: dict[str, Any] = {"value": option.value, "label": option.label}
            if option.hint:
                choice["hint"] = option.hint
            if self._too_loose(option.value, config):
                # Shown, so that a person sees why it is not possible.
                choice["disabled"] = True
            choices.append(choice)
        return {"choices": choices}


# How much each way of asking asks: the least first.
ASKS = {"auto": 0, "risky": 1, "every_action": 2}


@dataclass(frozen=True, kw_only=True)
class AskBefore(Choice):
    """When the agent stops for a person. Auto asks least. It is the one value a user may choose
    although it is looser than the admin's (spec 18.4): only where the admin offers it, and not
    where the admin asks before every action."""

    def offered(self, config: Config) -> tuple[Option, ...]:
        auto = config.safety.auto_mode.offered and not (
            self.tighten and config.safety.ask_before == "every_action"
        )
        return tuple(option for option in self.options if option.value != "auto" or auto)

    def _too_loose(self, value: str, config: Config) -> bool:
        if not self.tighten or value == "auto":
            return False
        return ASKS[value] < ASKS[str(self.deployed(config))]


@dataclass(frozen=True, kw_only=True)
class StepLimit(Choice):
    """The most steps one task may take. A lower number is stricter. 0 means no limit, and is the
    loosest value there is (spec 18.11)."""

    def offered(self, config: Config) -> tuple[Option, ...]:
        deployed = config.limits.max_calls
        steps = sorted({*config.limits.max_calls_choices, *([deployed] if deployed else [])})
        unlimited = () if deployed else (Option("0", "No limit"),)
        return (*unlimited, *(Option(str(count), f"{count} steps") for count in steps))

    def _too_loose(self, value: str, config: Config) -> bool:
        deployed = config.limits.max_calls
        if not self.tighten or not deployed:
            return False
        return int(value) == 0 or int(value) > deployed

    def patch(self, value: Value, config: Config, system: str | None = None) -> Patch:
        return {self.key: int(str(value))}


@dataclass(frozen=True, kw_only=True)
class ApprovalWait(Choice):
    """How long an approval waits, among the waits the deployment offers. The value is in seconds."""

    def offered(self, config: Config) -> tuple[Option, ...]:
        waits = sorted({*config.control.approval_timeout_choices_s, config.control.approval_timeout_s})
        return tuple(Option(str(seconds), _wait_in_words(seconds)) for seconds in waits)

    def patch(self, value: Value, config: Config, system: str | None = None) -> Patch:
        return {self.key: int(str(value))}


def _wait_in_words(seconds: int) -> str:
    if seconds % 60:
        return f"{seconds} seconds"
    minutes = seconds // 60
    return "1 minute" if minutes == 1 else f"{minutes} minutes"


@dataclass(frozen=True, kw_only=True)
class Switch(Entry):
    """A configuration key that is on or off."""

    key: str
    tighten: bool = False
    """Off is the strict value. Where the deployment has it off, a person cannot turn it on."""

    CONTROL: ClassVar[str] = "switch"

    def deployed(self, config: Config) -> Value:
        return bool(read(config, self.key))

    def problem(self, value: Any, config: Config) -> Reason | None:
        if not isinstance(value, bool):
            return "not_a_choice"
        return "would_loosen" if value and self.fixed_by_deployment(config) else None

    def patch(self, value: Value, config: Config, system: str | None = None) -> Patch:
        return {self.key: bool(value)}

    def free(self) -> Entry:
        return replace(self, tighten=False)

    def fixed_by_deployment(self, config: Config) -> bool:
        return self.tighten and not self.deployed(config)


@dataclass(frozen=True, kw_only=True)
class Guard(Switch):
    """A safeguard that is on or off. Here on is the strict value: where the deployment has it on,
    a user cannot turn it off."""

    def problem(self, value: Any, config: Config) -> Reason | None:
        if not isinstance(value, bool):
            return "not_a_choice"
        return "would_loosen" if not value and self.fixed_by_deployment(config) else None

    def fixed_by_deployment(self, config: Config) -> bool:
        return self.tighten and bool(self.deployed(config))


@dataclass(frozen=True, kw_only=True)
class StaySignedIn(Switch):
    """Whether the cloud browser keeps its profile from one session to the next."""

    def deployed(self, config: Config) -> Value:
        return config.browser.user_data_dir is not None

    def patch(self, value: Value, config: Config, system: str | None = None) -> Patch:
        kept = config.browser.user_data_dir or config.browser.kept_profile_dir
        return {self.key: kept if value else None}


@dataclass(frozen=True, kw_only=True)
class ActivityLog(Switch):
    """Whether the event log is written."""

    def deployed(self, config: Config) -> Value:
        return config.logging.event_log is not None

    def patch(self, value: Value, config: Config, system: str | None = None) -> Patch:
        # A browser among several writes a log of its own (spec 9.17).
        fallback = Path(config.logging.systems_dir) / f"{system}.jsonl" if system else None
        where = config.logging.event_log or str(fallback or Path(config.data_dir) / EVENT_LOG_NAME)
        return {self.key: where if value else None}


@dataclass(frozen=True, kw_only=True)
class SiteList(Entry):
    """A list of sites, one for each line. `example.com` covers the site and its subdomains."""

    key: str
    adds_to_deployment: bool
    """True: the person's sites are added to the deployment's, which stay (blocked sites). False: the
    person's sites take the place of the deployment's and may only narrow them (allowed sites)."""
    must_narrow: bool = True
    """A list that takes the place of the one above it must lie inside it. Not so for the admin."""

    CONTROL: ClassVar[str] = "list"

    def _deployment(self, config: Config) -> list[str]:
        return list(read(config, self.key))

    def deployed(self, config: Config) -> Value:
        return [] if self.adds_to_deployment else self._deployment(config)

    def problem(self, value: Any, config: Config) -> Reason | None:
        if not isinstance(value, list) or not all(isinstance(site, str) for site in value):
            return "not_a_choice"
        sites = self.tidy(value)
        assert isinstance(sites, list)
        for site in sites:
            try:
                site_pattern(site)
            except ValueError:
                return "bad_site"
        if self.adds_to_deployment:
            return None
        deployment = self._deployment(config)
        # With a list of the deployment's, a person narrows it: each of their sites lies inside it.
        inside = all(any(_inside(site, wide) for wide in deployment) for site in sites)
        if self.must_narrow and deployment and not inside:
            return "would_loosen"
        return None

    def free(self) -> Entry:
        return replace(self, must_narrow=False)

    def patch(self, value: Value, config: Config, system: str | None = None) -> Patch:
        sites = value if isinstance(value, list) else []
        deployment = self._deployment(config)
        if self.adds_to_deployment:
            return {self.key: [*deployment, *(site for site in sites if site not in deployment)]}
        # A person with no list of their own narrows nothing: the deployment's list holds.
        return {self.key: list(sites) or deployment}

    def shown(self, value: Value, config: Config) -> Value:
        return value if self.adds_to_deployment else (value or self._deployment(config))

    def described(self, config: Config) -> dict[str, Any]:
        deployment = self._deployment(config)
        return {"fixed": deployment} if self.adds_to_deployment and deployment else {}

    def tidy(self, value: Any) -> Value:
        """One site for each entry, in lower case, each once, with no empty lines."""
        seen: list[str] = []
        for site in value:
            site = str(site).strip().lower()
            if site and site not in seen:
                seen.append(site)
        return seen


def _inside(site: str, wide: str) -> bool:
    """Whether every address of `site` is also one of `wide`."""
    site, wide = site.removeprefix("*."), wide.removeprefix("*.")
    return site == wide or site.endswith("." + wide)


@dataclass(frozen=True, kw_only=True)
class About(Entry):
    """Read-only: the version, the browser in use, and the configuration that differs from the defaults."""

    CONTROL: ClassVar[str] = "about"

    def deployed(self, config: Config) -> Value:
        return None

    def problem(self, value: Any, config: Config) -> Reason | None:
        return "not_a_choice"

    def patch(self, value: Value, config: Config, system: str | None = None) -> Patch:
        return {}


@dataclass(frozen=True, kw_only=True)
class Enabled(Entry):
    """Whether a browser of the window is in use at all (spec 9.17). It changes nothing in the
    configuration: whoever runs the browsers asks the store."""

    CONTROL: ClassVar[str] = "switch"

    def deployed(self, config: Config) -> Value:
        return True

    def problem(self, value: Any, config: Config) -> Reason | None:
        return None if isinstance(value, bool) else "not_a_choice"

    def patch(self, value: Value, config: Config, system: str | None = None) -> Patch:
        return {}


@dataclass(frozen=True, kw_only=True)
class AgentModel(Choice):
    """The model that plans the agent's steps, among those the deployment offers."""

    def offered(self, config: Config) -> tuple[Option, ...]:
        names = dict.fromkeys([config.agent.model, *config.agent.offered_models])
        return tuple(Option(name, name) for name in names)


@dataclass(frozen=True, kw_only=True)
class Action(About):
    """A button. It holds no value: what it does is a route of the service's own, and it asks first."""

    button: str
    question: str
    consequence: str

    CONTROL: ClassVar[str] = "action"

    def described(self, config: Config) -> dict[str, Any]:
        asks = {"question": self.question, "consequence": self.consequence, "button": self.button}
        return {"action": self.button, "confirm": asks}


ENABLED = Enabled(
    id="system_enabled",
    group="Browser",
    surfaces=EVERYWHERE,
    title="Use this browser",
    description="Turns this browser on or off in the window. Turning it off ends its session.",
    per_system=True,
    only_per_system=True,
)

CATALOGUE: tuple[Entry, ...] = (
    ENABLED,
    StaySignedIn(
        id="stay_signed_in",
        group="Browser",
        surfaces=EVERYWHERE,
        title="Stay signed in to sites",
        description="Keeps the cloud browser's cookies and site data from one session to the next, so sites stay signed in.",
        key="browser.user_data_dir",
        applies="next_session",
        backends=(CLOUD,),
    ),
    AgentModel(
        id="agent_model",
        group="Agent",
        surfaces=EVERYWHERE,
        title="Model",
        description="The model that plans the agent's steps. A change holds from the next task.",
        key="agent.model",
        options=(),
        dropdown=True,
        per_system=True,
    ),
    AskBefore(
        id="ask_before",
        user=True,
        per_system=True,
        group="Approvals",
        surfaces=EVERYWHERE,
        title="Ask before",
        description="When the agent must stop and wait for a person's approval before it acts.",
        key="safety.ask_before",
        tighten=True,
        options=(
            Option("risky", "Risky actions", "Uploads, page scripts and whatever the admin lists"),
            Option("every_action", "Every action", "Each click, key press and page change"),
            Option(
                "auto",
                "Auto",
                "A check looks at each step. Safe steps run, and you are asked only about the risky ones",
            ),
        ),
    ),
    Switch(
        id="offer_auto",
        per_system=True,
        group="Approvals",
        surfaces=EVERYWHERE,
        title="Offer Auto",
        description='Let people choose Auto for "Ask before". It asks less: a check decides each step, and it can be wrong.',
        key="safety.auto_mode.offered",
    ),
    ApprovalWait(
        id="approval_wait",
        user=True,
        per_system=True,
        group="Approvals",
        surfaces=EVERYWHERE,
        title="Wait for my answer",
        description="How long the agent waits for an answer to an approval. With no answer by then, the action is denied.",
        key="control.approval_timeout_s",
        options=(),
        dropdown=True,
    ),
    Choice(
        id="remember_site_approval",
        user=True,
        per_system=True,
        group="Approvals",
        surfaces=EVERYWHERE,
        title='Remember "Allow on this site"',
        description='After "Allow on this site", how long the agent may go on acting on that site without asking again.',
        key="control.site_grant_lifetime",
        tighten=True,
        dropdown=True,
        options=(Option("session", "Until the session ends"), Option("none", "Never")),
    ),
    Choice(
        id="scan_pages",
        user=True,
        per_system=True,
        group="Safety",
        surfaces=EVERYWHERE,
        title="Check pages for hidden instructions",
        description="A web page can hold text that tries to give the agent orders. What is found is kept from the agent, and you are told.",
        key="safeguards.incoming.scan",
        tighten=True,
        options=(
            Option("off", "Off", "Pages are not checked"),
            Option("local", "On this computer", "Fixed rules only. Nothing leaves this computer"),
            Option(
                "local_then_model",
                "On this computer, then a model",
                "What the rules find suspicious is sent to the model for a second opinion",
            ),
        ),
    ),
    Guard(
        id="cross_site_text",
        user=True,
        per_system=True,
        group="Safety",
        surfaces=EVERYWHERE,
        title="Copying between sites",
        description="Ask me before the agent types or sends, on one site, text that it read on another.",
        key="safeguards.outgoing.cross_site_text",
        tighten=True,
    ),
    SiteList(
        id="sensitive_sites",
        user=True,
        per_system=True,
        group="Safety",
        surfaces=EVERYWHERE,
        title="Sensitive sites",
        description="Sites the agent may enter only with your yes, such as your bank. They are added to the ones already listed.",
        key="safeguards.sites.sensitive.more",
        adds_to_deployment=True,
    ),
    StepLimit(
        id="task_limit",
        user=True,
        per_system=True,
        group="Limits",
        surfaces=EVERYWHERE,
        title="Steps in one task",
        description="The most steps the agent may take for one task before it stops and waits for you.",
        key="limits.max_calls",
        tighten=True,
        options=(),
        dropdown=True,
    ),
    SiteList(
        id="blocked_sites",
        user=True,
        per_system=True,
        group="Sites",
        surfaces=EVERYWHERE,
        title="Blocked sites",
        description="Sites the agent must never open.",
        key="safety.blocked_domains",
        adds_to_deployment=True,
    ),
    SiteList(
        id="allowed_sites",
        user=True,
        per_system=True,
        group="Sites",
        surfaces=EVERYWHERE,
        title="Only allow these sites",
        description="When this list has entries, the agent may open only these sites. Empty: any site that is not blocked.",
        key="safety.allowed_domains",
        adds_to_deployment=False,
    ),
    Switch(
        id="allow_downloads",
        per_system=True,
        group="Files",
        surfaces=EVERYWHERE,
        title="Let the agent download files",
        description="On: the agent may download files, saved where you can find them after the session. Off: it cannot.",
        key="browser.downloads.enabled",
        tighten=True,
    ),
    Switch(
        id="allow_uploads",
        per_system=True,
        group="Files",
        surfaces=EVERYWHERE,
        title="Let the agent upload files",
        description="On: the agent may upload a file to a site; each upload still asks for approval. Off: it cannot.",
        key="browser.uploads.enabled",
        tighten=True,
    ),
    ActivityLog(
        id="activity_log",
        per_system=True,
        group="Privacy",
        surfaces=EVERYWHERE,
        title="Keep a log of the agent's steps",
        description="Writes one line for each step the agent takes. What is typed is never logged, only its length.",
        key="logging.event_log",
    ),
    Action(
        id="clear_browsing_data",
        group="Privacy",
        surfaces=EVERYWHERE,
        title="Clear browsing data",
        description="Deletes cookies and site data in the cloud browser.",
        button="Clear data",
        question="Clear cookies and site data in the cloud browser?",
        consequence="You'll be signed out of sites there, and open sessions will end.",
    ),
    Choice(
        id="picture_quality",
        user=True,
        per_system=True,
        group="Live view",
        surfaces=EVERYWHERE,
        title="Picture quality",
        description="How sharp the live picture of the browser is. A sharper picture uses more data.",
        key="viewer.quality",
        options=(
            Option("standard", "Standard"),
            Option("data_saver", "Data saver", "For a slow or metered connection"),
            Option("high", "High", "For a fast connection"),
        ),
    ),
    Switch(
        id="show_agent_pointer",
        user=True,
        group="Live view",
        surfaces=EVERYWHERE,
        title="Show where the agent is acting",
        description="Outlines the element and shows the agent's pointer over the live picture.",
        key="viewer.show_agent_pointer",
    ),
    Choice(
        id="colour_mode",
        user=True,
        group="Appearance",
        surfaces=EVERYWHERE,
        title="Colour mode",
        description="The colours of this window: light, dark, or the same as your device.",
        key="viewer.theme",
        options=(Option("system", "Match system"), Option("light", "Light"), Option("dark", "Dark")),
    ),
    Switch(
        id="page_scripts",
        per_system=True,
        group="Advanced",
        surfaces=NOT_ON_MOBILE,
        title="Let the agent run scripts in pages",
        description="Offers the agent a tool that runs JavaScript in the page. Each use still asks.",
        key="browser.javascript.allow_evaluate",
        tighten=True,
    ),
    Switch(
        id="code_tool",
        per_system=True,
        group="Advanced",
        surfaces=NOT_ON_MOBILE,
        title="Let the agent run scripts of several steps",
        description="Offers the agent a tool that does several steps in one call. Each step is still checked.",
        key="code.enabled",
        tighten=True,
    ),
    About(
        id="about",
        group="Advanced",
        surfaces=NOT_ON_MOBILE,
        title="About this deployment",
        description="The version, the browser in use and the configuration that differs from the defaults.",
    ),
)

BY_ID: Mapping[str, Entry] = {entry.id: entry for entry in CATALOGUE}

# Each setting as the admin has it: every choice open (spec 4.11).
FREE: Mapping[str, Entry] = {entry.id: entry.free() for entry in CATALOGUE}
