"""What was saved in the window (spec 10.1, 10.2), and the configuration it makes.

    defaults  <  config.json  <  environment  <  the admin's configuration  <  a user's settings  <  per-session options

Two people save here (spec 4.11). The **admin** sets the system up: every setting is theirs to
choose, the looser choices too, except one the deployment locked in `config.json`. A **user**
sets a part of it for themselves: only the settings that are a user's, only where the admin lets
users change them, and only to a value at least as strict as the admin's. A value that no longer
holds (a choice no longer offered, a setting since locked, a value that would now loosen what
stands above it) is passed over, and what stands above it holds.

Where a service has several browsers, each a system of its own (spec 9.17), most settings are
set for each system by itself. A system's own value holds for it; where it has none, the value
set for every browser holds.

The admin also keeps a **policy**: which systems users may use, which settings users may change,
and what of the evaluations users may see.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from bap_browser import __version__
from bap_browser.config import Config, deep_merge, defaults
from bap_browser.errors import ConfigError
from bap_browser.private_file import write_json
from bap_browser.settings.catalogue import (
    BY_ID,
    CATALOGUE,
    ENABLED,
    FREE,
    GROUPS,
    SURFACES,
    Entry,
    Reason,
    Value,
)

Role = Literal["admin", "user"]
# Where a value comes from when nobody said: the configuration file or the environment.
UNKNOWN_SOURCE = "configuration"
# In the saved file: the systems' own values, the user's part, and the admin's policy.
SYSTEMS, USER, POLICY = "systems", "user", "policy"
# The user's preferred browser, kept with their settings. It is no setting of the catalogue: its
# choices are the systems the service has, which the catalogue does not know.
PREFERRED = "preferred_browser"
A_SYSTEMS_NAME = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")
# What of a system's evaluations a user may be shown, in the words of the admin's screen, and
# whether it is shown until the admin says otherwise.
SEES: Mapping[str, tuple[str, bool]] = {
    "evaluations": ("Evaluations of the browsers they use", True),
    "cost": ("What the tasks cost", True),
    "traces": ("The tasks and their traces", True),
    "checklist": ("Run the checklist", True),
    "log": ("The log of the agent's steps", False),
}
# What each of them is, for the admin who decides it.
SEEN: Mapping[str, str] = {
    "evaluations": (
        "On: a user has the Evaluations view under each browser they may use, with how its tasks went and "
        "how long they took. Off: a user has no Evaluations view."
    ),
    "cost": "On: a user also sees the tokens the tasks used and what they cost. Off: no cost is shown to them.",
    "traces": (
        "On: a user sees the list of recent tasks, opens the trace of each, and says Good or Bad on an "
        "answer. Off: they see only the totals."
    ),
    "checklist": (
        "On: a user sees the checklist and may run it: a few real steps on the demo site, to check the "
        "browser works. Off: they neither see nor run it."
    ),
    "log": "On: a user may read the newest lines of the log of the agent's steps. Off: the log is yours alone.",
}

Saved = dict[str, Value]


class Refused(Exception):
    """A change a person may not make. Nothing was changed."""

    def __init__(self, setting: str, reason: Reason) -> None:
        super().__init__(f"{setting}: {reason}")
        self.setting = setting
        self.reason: Reason = reason


@dataclass
class _Layer:
    """What one person saved: for every browser, and for each system by itself."""

    common: Saved = field(default_factory=Saved)
    own: dict[str, Saved] = field(default_factory=dict[str, Saved])

    def places(self, entry: Entry, system: str | None) -> list[Saved]:
        """Where a value for this setting is looked for: the system's own first."""
        places = [self.own.get(system, {})] if system and entry.per_system else []
        if not entry.only_per_system:
            places.append(self.common)
        return places

    def keep(self, checked: Mapping[str, Value], system: str | None) -> None:
        own = {name: value for name, value in checked.items() if system and BY_ID[name].per_system}
        self.common = {**self.common, **{n: v for n, v in checked.items() if n not in own}}
        if system and own:
            self.own = {**self.own, system: {**self.own.get(system, {}), **own}}

    def written(self) -> dict[str, Any]:
        kept: dict[str, Any] = dict(self.common)
        systems = {system: values for system, values in self.own.items() if values}
        if systems:
            kept[SYSTEMS] = systems
        return kept


class SettingsStore:
    def __init__(self, config: Config, sources: Mapping[str, str] | None = None) -> None:
        """`config` is the deployment's configuration. `sources` says, for each key that differs
        from its default, where the value came from; without it, the configuration says so itself."""
        self._config = config
        self._sources = dict(config.sources if sources is None else sources)
        self._path = Path(config.settings.file)
        self._admin, self._user, self._policy, self._preferred = _read(self._path)
        self.systems: tuple[str, ...] = ()
        """The browsers the service has, where it has several. Whoever runs them says so."""

    # The two layers.

    def _held(self, entry: Entry, config: Config, layer: _Layer, system: str | None) -> tuple[bool, Value]:
        """Whether a saved value holds for this setting in one layer, and the value that holds.
        `config` is what stands above the layer; `entry` says what may be chosen against it."""
        for saved in layer.places(entry, system):
            if entry.id in saved and entry.problem(saved[entry.id], config) is None:
                return True, entry.tidy(saved[entry.id])
        return False, entry.deployed(config)

    def _admins(self, entry: Entry, config: Config, system: str | None) -> tuple[bool, Value]:
        """The admin's value: any choice, unless the deployment locked the setting."""
        if entry.id in config.settings.locked:
            return False, entry.deployed(config)
        return self._held(FREE[entry.id], config, self._admin, system)

    def _users(self, entry: Entry, above: Config, system: str | None) -> tuple[bool, Value]:
        """A user's value. `above` is the configuration as the admin has it."""
        if self._locked_for_users(entry, above):
            return False, entry.deployed(above)
        return self._held(entry, above, self._user, system)

    def _locked_for_users(self, entry: Entry, above: Config) -> bool:
        return (
            not entry.user
            or entry.id in above.settings.locked
            or not self.user_may_change(entry.id)
            or entry.fixed_by_deployment(above)
        )

    def _laid(self, config: Config, backend: str, system: str | None, role: Role) -> Config:
        """A configuration with one layer laid over it."""
        patch: dict[str, Any] = {}
        for entry in CATALOGUE:
            if entry.backends is not None and backend not in entry.backends:
                continue
            read = self._admins if role == "admin" else self._users
            holds, value = read(entry, config, system)
            if holds:
                patch = deep_merge(patch, _nested(entry.patch(value, config, system)))
        if not patch:
            return config
        return Config.model_validate(deep_merge(config.model_dump(), patch))

    def apply_to(self, config: Config, backend: str | None = None, system: str | None = None) -> Config:
        """A session's configuration with what was saved laid over it: the admin's configuration,
        then the user's settings. `config` is what the deployment and the session's own options
        give; `backend` is where the session's browser is; `system` names the session's browser
        where the service has several."""
        backend = backend or config.backend.kind
        return self._laid(self._laid(config, backend, system, "admin"), backend, system, "user")

    def _above_users(self, system: str | None) -> Config:
        """The configuration as the admin has it, which a user's settings are held against."""
        return self._laid(self._config, self._config.backend.kind, system, "admin")

    # The settings screen.

    def answer(self, surface: str, system: str | None = None, role: Role = "admin") -> dict[str, Any]:
        """What the settings screen is drawn from: the groups and their settings on this surface.
        With `system`, the settings are those of that one browser of the window. A user is told
        only the settings that are a user's."""
        above = self._config if role == "admin" else self._above_users(system)
        groups: list[dict[str, Any]] = []
        for title in GROUPS:
            settings: list[dict[str, Any]] = []
            for entry in CATALOGUE:
                if entry.group != title or surface not in entry.surfaces:
                    continue
                if entry.only_per_system and system is None:
                    continue
                if role == "user" and not entry.user:
                    continue
                if role == "admin":
                    drawn, value = FREE[entry.id], self._admins(entry, above, system)[1]
                    locked = entry.id in above.settings.locked
                else:
                    drawn, value = entry, self._users(entry, above, system)[1]
                    locked = self._locked_for_users(entry, above)
                setting: dict[str, Any] = {
                    "id": entry.id,
                    "title": entry.title,
                    "description": entry.description,
                    "control": entry.control,
                    **drawn.described(above),
                    "value": drawn.shown(value, above),
                    "default": drawn.deployed(above),
                    "locked": locked,
                    "applies": entry.applies,
                }
                if system is not None:
                    # Whether a change is this browser's alone, or every browser's.
                    setting["scope"] = "system" if entry.per_system else "all"
                settings.append(setting)
            if settings:
                groups.append({"id": title.lower().replace(" ", "_"), "title": title, "settings": settings})
        answer: dict[str, Any] = {"surface": surface, "groups": groups, "role": role}
        if system is not None:
            answer["system"] = system
        return answer

    def change(
        self, surface: str, changes: Mapping[str, Any], system: str | None = None, role: Role = "admin"
    ) -> dict[str, Value]:
        """Saves a person's changes. Nothing is changed when any one of them is refused. Gives the
        settings that changed, with their new values, for the sessions to take up.

        With `system`, a setting that is each system's own is saved for that system alone. Every
        other setting is saved for every browser, whichever system's screen it was changed on."""
        if system is not None and not A_SYSTEMS_NAME.match(system):
            raise Refused(SYSTEMS, "not_on_this_surface")
        above = self._config if role == "admin" else self._above_users(system)
        checked: dict[str, Value] = {}
        for name, value in changes.items():
            entry = BY_ID.get(name)
            if entry is None or surface not in entry.surfaces or (entry.only_per_system and system is None):
                raise Refused(name, "not_on_this_surface")
            if role == "user" and not entry.user:
                raise Refused(name, "not_on_this_surface")
            if name in above.settings.locked or (role == "user" and not self.user_may_change(name)):
                raise Refused(name, "locked")
            judged = FREE[name] if role == "admin" else entry
            reason = judged.problem(value, above)
            if reason is not None:
                raise Refused(name, reason)
            if role == "user" and entry.fixed_by_deployment(above):
                raise Refused(name, "locked")
            checked[name] = entry.tidy(value)
        if not checked:
            return {}
        (self._admin if role == "admin" else self._user).keep(checked, system)
        self._save()
        return checked

    def enabled(self, system: str) -> bool:
        """Whether the admin has this browser of the window turned on (spec 9.17). It is, until
        they turn it off."""
        return self._admins(ENABLED, self._config, system)[1] is not False

    # The admin's policy for users (spec 4.11).

    def users_may_use(self, system: str) -> bool:
        """Whether a user may use this browser: it is turned on, and the admin lets users in."""
        return self.enabled(system) and self._policy[SYSTEMS].get(system, True) is not False

    def user_may_change(self, setting: str) -> bool:
        entry = BY_ID.get(setting)
        return entry is not None and entry.user and self._policy["may_change"].get(setting, True) is not False

    def user_sees(self, what: str) -> bool:
        return self._policy["sees"].get(what, SEES[what][1]) is not False if what in SEES else False

    def policy(self) -> dict[str, Any]:
        """The policy as the admin's screen draws it: each line with its words and whether it is allowed."""
        return {
            "systems": [
                {"id": system, "allowed": self._policy[SYSTEMS].get(system, True) is not False}
                for system in self.systems
            ],
            "may_change": [
                {
                    "id": entry.id,
                    "title": entry.title,
                    # What the setting is, so that the admin knows what they are letting users change.
                    "description": entry.description,
                    "allowed": self.user_may_change(entry.id),
                }
                for entry in CATALOGUE
                if entry.user
            ],
            "sees": [
                {"id": what, "title": title, "description": SEEN[what], "allowed": self.user_sees(what)}
                for what, (title, _) in SEES.items()
            ],
        }

    def change_policy(self, changes: Mapping[str, Any]) -> None:
        """Takes the admin's changes to the policy. Nothing is changed when any one is not one."""
        known = {
            SYSTEMS: set(self.systems),
            "may_change": {e.id for e in CATALOGUE if e.user},
            "sees": set(SEES),
        }
        taken: dict[str, dict[str, bool]] = {}
        for part, lines in changes.items():
            if part not in known or not isinstance(lines, Mapping):
                raise Refused(str(part), "not_a_choice")
            for line, allowed in lines.items():
                if line not in known[part] or not isinstance(allowed, bool):
                    raise Refused(f"{part}.{line}", "not_a_choice")
            taken[part] = {str(line): bool(allowed) for line, allowed in lines.items()}
        for part, lines in taken.items():
            self._policy[part] = {**self._policy[part], **lines}
        self._save()

    # The user's preferred browser.

    def allowed_systems(self, role: Role) -> list[str]:
        """The browsers a person may use: all of them for the admin, and for a user those that
        are turned on and that the admin lets users in."""
        return [system for system in self.systems if role == "admin" or self.users_may_use(system)]

    def preferred(self, role: Role = "user") -> str | None:
        """The browser a person's window opens on: the one they chose while they may still use it,
        else the first they may use. None where they may use none."""
        allowed = self.allowed_systems(role)
        if self._preferred in allowed:
            return self._preferred
        return allowed[0] if allowed else None

    def prefer(self, system: object, role: Role = "user") -> str:
        if not isinstance(system, str) or system not in self.allowed_systems(role):
            raise Refused(PREFERRED, "not_a_choice")
        self._preferred = system
        self._save()
        return system

    def about(self, browser: str) -> dict[str, Any]:
        """What "About this deployment" lists. The configuration holds no secret: those come from the
        environment and are named in it, never held."""
        ours, theirs = _leaves(self._config.model_dump()), _leaves(defaults().model_dump())
        changed = [
            {"key": key, "value": json.dumps(value), "source": self._sources.get(key, UNKNOWN_SOURCE)}
            for key, value in sorted(ours.items())
            if theirs.get(key) != value
        ]
        return {"version": __version__, "browser": browser, "changed": changed}

    def _save(self) -> None:
        kept = self._admin.written()
        user = self._user.written()
        if self._preferred:
            user[PREFERRED] = self._preferred
        if user:
            kept[USER] = user
        policy = {part: lines for part, lines in self._policy.items() if lines}
        if policy:
            kept[POLICY] = policy
        write_json(self._path, kept, indent=2, sort_keys=True)


def known_surface(surface: str | None) -> bool:
    return surface in SURFACES


def _nested(patch: Mapping[str, Any]) -> dict[str, Any]:
    """Keys written with dots, as the sections they name."""
    out: dict[str, Any] = {}
    for key, value in patch.items():
        *sections, last = key.split(".")
        node = out
        for section in sections:
            node = node.setdefault(section, {})
        node[last] = value
    return out


def _leaves(data: Mapping[str, Any], prefix: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(value, Mapping) and value:
            out |= _leaves(value, f"{prefix}{key}.")
        else:
            out[f"{prefix}{key}"] = value
    return out


def _known(data: Mapping[str, Any]) -> Saved:
    """The settings of this build among what a file holds. One this build does not know is passed
    over: the file may have been written by another build."""
    return {name: value for name, value in data.items() if name in BY_ID}


def _layer(data: Any) -> _Layer:
    if not isinstance(data, dict):
        return _Layer()
    systems = data.get(SYSTEMS)
    own = {
        str(system): _known(values)
        for system, values in (systems.items() if isinstance(systems, dict) else ())
        if isinstance(values, dict) and A_SYSTEMS_NAME.match(str(system))
    }
    return _Layer(_known(data), own)


def _read(path: Path) -> tuple[_Layer, _Layer, dict[str, dict[str, bool]], str | None]:
    """What was saved: the admin's configuration, the user's settings, the admin's policy, and
    the browser the user prefers."""
    policy: dict[str, dict[str, bool]] = {SYSTEMS: {}, "may_change": {}, "sees": {}}
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return _Layer(), _Layer(), policy, None
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        # Passing over it in silence would drop what a person chose, a blocked site among it.
        raise ConfigError(
            f"{path}: the saved settings are not valid JSON (line {exc.lineno}). Correct the file or remove it"
        ) from exc
    if not isinstance(data, dict):
        raise ConfigError(f"{path}: the saved settings must be an object. Correct the file or remove it")
    user = data.get(USER)
    preferred = user.get(PREFERRED) if isinstance(user, dict) else None
    kept = data.get(POLICY)
    for part in policy:
        lines = kept.get(part) if isinstance(kept, dict) else None
        if isinstance(lines, dict):
            policy[part] = {
                str(line): allowed for line, allowed in lines.items() if isinstance(allowed, bool)
            }
    return _layer(data), _layer(user), policy, preferred if isinstance(preferred, str) else None
