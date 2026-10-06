"""The settings catalogue (spec 10.2): each setting a person can change, the configuration key it
changes, the surfaces it appears on, and how a person's value is limited by the deployment's.

The settings screen is drawn from this, so a setting is defined once. A build lists only the
settings whose feature it contains.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
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
GROUPS = ("Browser", "Approvals", "Sites", "Files", "Privacy", "Live view", "Appearance", "Advanced")
CLOUD = "remote_headless"
BACKEND_NAMES = {
    "remote_headless": ("Cloud browser", "Runs beside the agent. You watch a live picture of it."),
    "takeover_chrome": ("My Chrome", "A tab of your own Chrome, with your sign-ins."),
    "bundled_chromium": ("Built-in browser", "The app's own browser. It keeps its sign-ins."),
}
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

    def patch(self, value: Value, config: Config) -> Patch:
        """What the value changes in the configuration."""
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

    def patch(self, value: Value, config: Config) -> Patch:
        return {self.key: value}

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


@dataclass(frozen=True, kw_only=True)
class PreferredBrowser(Choice):
    """The browser a new session uses, among those the deployment offers."""

    def offered(self, config: Config) -> tuple[Option, ...]:
        return tuple(Option(kind, *BACKEND_NAMES[kind]) for kind in config.backend.offered)


@dataclass(frozen=True, kw_only=True)
class ApprovalWait(Choice):
    """How long an approval waits, among the waits the deployment offers. The value is in seconds."""

    def offered(self, config: Config) -> tuple[Option, ...]:
        waits = sorted({*config.control.approval_timeout_choices_s, config.control.approval_timeout_s})
        return tuple(Option(str(seconds), _wait_in_words(seconds)) for seconds in waits)

    def patch(self, value: Value, config: Config) -> Patch:
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

    def patch(self, value: Value, config: Config) -> Patch:
        return {self.key: bool(value)}

    def fixed_by_deployment(self, config: Config) -> bool:
        return self.tighten and not self.deployed(config)


@dataclass(frozen=True, kw_only=True)
class StaySignedIn(Switch):
    """Whether the cloud browser keeps its profile from one session to the next."""

    def deployed(self, config: Config) -> Value:
        return config.browser.user_data_dir is not None

    def patch(self, value: Value, config: Config) -> Patch:
        kept = config.browser.user_data_dir or config.browser.kept_profile_dir
        return {self.key: kept if value else None}


@dataclass(frozen=True, kw_only=True)
class ActivityLog(Switch):
    """Whether the event log is written."""

    def deployed(self, config: Config) -> Value:
        return config.logging.event_log is not None

    def patch(self, value: Value, config: Config) -> Patch:
        where = config.logging.event_log or str(Path(config.data_dir) / EVENT_LOG_NAME)
        return {self.key: where if value else None}


@dataclass(frozen=True, kw_only=True)
class SiteList(Entry):
    """A list of sites, one for each line. `example.com` covers the site and its subdomains."""

    key: str
    adds_to_deployment: bool
    """True: the person's sites are added to the deployment's, which stay (blocked sites). False: the
    person's sites take the place of the deployment's and may only narrow them (allowed sites)."""

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
        if deployment and not all(any(_inside(site, wide) for wide in deployment) for site in sites):
            return "would_loosen"
        return None

    def patch(self, value: Value, config: Config) -> Patch:
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

    def patch(self, value: Value, config: Config) -> Patch:
        return {}


CATALOGUE: tuple[Entry, ...] = (
    PreferredBrowser(
        id="preferred_browser",
        group="Browser",
        surfaces=NOT_ON_MOBILE,
        title="Preferred browser",
        description="The browser the agent uses for a new session.",
        key="backend.kind",
        options=(),
        applies="next_session",
    ),
    StaySignedIn(
        id="stay_signed_in",
        group="Browser",
        surfaces=EVERYWHERE,
        title="Stay signed in to sites",
        description="Keeps the cloud browser's cookies and site data between sessions.",
        key="browser.user_data_dir",
        applies="next_session",
        backends=(CLOUD,),
    ),
    Choice(
        id="ask_before",
        group="Approvals",
        surfaces=EVERYWHERE,
        title="Ask before",
        description="When the agent must wait for your approval.",
        key="safety.ask_before",
        tighten=True,
        options=(
            Option("risky", "Risky actions", "Uploads, page scripts and whatever your organisation lists"),
            Option("every_action", "Every action", "Each click, key press and page change"),
        ),
    ),
    ApprovalWait(
        id="approval_wait",
        group="Approvals",
        surfaces=EVERYWHERE,
        title="Wait for my answer",
        description="How long an approval waits. Then the action is denied.",
        key="control.approval_timeout_s",
        options=(),
        dropdown=True,
    ),
    Choice(
        id="remember_site_approval",
        group="Approvals",
        surfaces=EVERYWHERE,
        title='Remember "Allow on this site"',
        description="How long that answer lasts.",
        key="control.site_grant_lifetime",
        tighten=True,
        dropdown=True,
        options=(Option("session", "Until the session ends"), Option("none", "Never")),
    ),
    SiteList(
        id="blocked_sites",
        group="Sites",
        surfaces=EVERYWHERE,
        title="Blocked sites",
        description="Sites the agent must never open.",
        key="safety.blocked_domains",
        adds_to_deployment=True,
    ),
    SiteList(
        id="allowed_sites",
        group="Sites",
        surfaces=EVERYWHERE,
        title="Only allow these sites",
        description="When this list has entries, the agent may open only these.",
        key="safety.allowed_domains",
        adds_to_deployment=False,
    ),
    Switch(
        id="allow_downloads",
        group="Files",
        surfaces=EVERYWHERE,
        title="Let the agent download files",
        description="Files are saved where you can find them after the session.",
        key="browser.downloads.enabled",
        tighten=True,
    ),
    Switch(
        id="allow_uploads",
        group="Files",
        surfaces=EVERYWHERE,
        title="Let the agent upload files",
        description="Each upload still asks for your approval.",
        key="browser.uploads.enabled",
        tighten=True,
    ),
    ActivityLog(
        id="activity_log",
        group="Privacy",
        surfaces=EVERYWHERE,
        title="Keep a log of the agent's steps",
        description="What you type is never logged, only how many characters.",
        key="logging.event_log",
    ),
    Choice(
        id="picture_quality",
        group="Live view",
        surfaces=EVERYWHERE,
        title="Picture quality",
        description="How much data the live picture uses.",
        key="viewer.quality",
        options=(
            Option("standard", "Standard"),
            Option("data_saver", "Data saver", "For a slow or metered connection"),
            Option("high", "High", "For a fast connection"),
        ),
    ),
    Switch(
        id="show_agent_pointer",
        group="Live view",
        surfaces=EVERYWHERE,
        title="Show where the agent is acting",
        description="Outlines the element and shows the agent's pointer over the live picture.",
        key="viewer.show_agent_pointer",
    ),
    Choice(
        id="colour_mode",
        group="Appearance",
        surfaces=EVERYWHERE,
        title="Colour mode",
        description="Light, dark, or whatever your device uses.",
        key="viewer.theme",
        options=(Option("system", "Match system"), Option("light", "Light"), Option("dark", "Dark")),
    ),
    Switch(
        id="page_scripts",
        group="Advanced",
        surfaces=NOT_ON_MOBILE,
        title="Let the agent run scripts in pages",
        description="Offers the agent a tool that runs JavaScript in the page. Each use still asks.",
        key="browser.javascript.allow_evaluate",
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
