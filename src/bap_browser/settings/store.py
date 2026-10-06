"""What a person saved in the settings screen (spec 10.1, 10.2), and the configuration it makes.

    defaults  <  config.json  <  environment  <  a person's settings  <  per-session options

A person's value holds only while the deployment allows it: a locked setting, a choice that is no
longer offered and a value that would loosen what the deployment requires are passed over, and the
deployment's own value holds.

Where a service has several browsers, each a system of its own (spec 9.17), a person sets most
things for each system by itself. A system's own value holds for it; where it has none, the value
a person set for every browser holds; and where there is none of those, the deployment's.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from bap_browser import __version__
from bap_browser.config import Config, deep_merge, defaults
from bap_browser.errors import ConfigError
from bap_browser.settings.catalogue import (
    BY_ID,
    CATALOGUE,
    ENABLED,
    GROUPS,
    SURFACES,
    Entry,
    Reason,
    Value,
)

# Where a value comes from when nobody said: the configuration file or the environment.
UNKNOWN_SOURCE = "configuration"
# In the saved file, the systems' own values are under this name, beside the values for every browser.
SYSTEMS = "systems"
A_SYSTEMS_NAME = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")

Saved = dict[str, Value]


class Refused(Exception):
    """A change a person may not make. Nothing was changed."""

    def __init__(self, setting: str, reason: Reason) -> None:
        super().__init__(f"{setting}: {reason}")
        self.setting = setting
        self.reason: Reason = reason


class SettingsStore:
    def __init__(self, config: Config, sources: Mapping[str, str] | None = None) -> None:
        """`config` is the deployment's configuration. `sources` says, for each key that differs
        from its default, where the value came from; without it, the configuration says so itself."""
        self._config = config
        self._sources = dict(config.sources if sources is None else sources)
        self._path = Path(config.settings.file)
        # What a person set for every browser, and what they set for one system alone.
        self._saved, self._own = _read(self._path)

    def _locked(self, entry: Entry, config: Config) -> bool:
        return entry.id in config.settings.locked or entry.fixed_by_deployment(config)

    def _held(self, entry: Entry, config: Config, system: str | None = None) -> tuple[bool, Value]:
        """Whether a person's own value holds for this setting, and the value that holds. A
        system's own value comes before the one for every browser."""
        if not self._locked(entry, config):
            places = [self._own.get(system, {})] if system and entry.per_system else []
            if not entry.only_per_system:
                places.append(self._saved)
            for saved in places:
                if entry.id in saved and entry.problem(saved[entry.id], config) is None:
                    return True, entry.tidy(saved[entry.id])
        return False, entry.deployed(config)

    def answer(self, surface: str, system: str | None = None) -> dict[str, Any]:
        """What the settings screen is drawn from: the groups and their settings on this surface.
        With `system`, the settings are those of that one browser of the window."""
        config = self._config
        groups: list[dict[str, Any]] = []
        for title in GROUPS:
            settings: list[dict[str, Any]] = []
            for entry in CATALOGUE:
                if entry.group != title or surface not in entry.surfaces:
                    continue
                if entry.only_per_system and system is None:
                    continue
                setting: dict[str, Any] = {
                    "id": entry.id,
                    "title": entry.title,
                    "description": entry.description,
                    "control": entry.control,
                    **entry.described(config),
                    "value": entry.shown(self._held(entry, config, system)[1], config),
                    "default": entry.deployed(config),
                    "locked": self._locked(entry, config),
                    "applies": entry.applies,
                }
                if system is not None:
                    # Whether a change is this browser's alone, or every browser's.
                    setting["scope"] = "system" if entry.per_system else "all"
                settings.append(setting)
            if settings:
                groups.append({"id": title.lower().replace(" ", "_"), "title": title, "settings": settings})
        answer: dict[str, Any] = {"surface": surface, "groups": groups}
        if system is not None:
            answer["system"] = system
        return answer

    def change(self, surface: str, changes: Mapping[str, Any], system: str | None = None) -> dict[str, Value]:
        """Saves a person's changes. Nothing is changed when any one of them is refused. Gives the
        settings that changed, with their new values, for the sessions to take up.

        With `system`, a setting that is each system's own is saved for that system alone. Every
        other setting is saved for every browser, whichever system's screen it was changed on."""
        config = self._config
        if system is not None and not A_SYSTEMS_NAME.match(system):
            raise Refused(SYSTEMS, "not_on_this_surface")
        checked: dict[str, Value] = {}
        for name, value in changes.items():
            entry = BY_ID.get(name)
            if entry is None or surface not in entry.surfaces or (entry.only_per_system and system is None):
                raise Refused(name, "not_on_this_surface")
            if name in config.settings.locked:
                raise Refused(name, "locked")
            reason = entry.problem(value, config)
            if reason is not None:
                raise Refused(name, reason)
            if entry.fixed_by_deployment(config):
                raise Refused(name, "locked")
            checked[name] = entry.tidy(value)
        if not checked:
            return {}
        own = {name: value for name, value in checked.items() if system and BY_ID[name].per_system}
        self._saved = {**self._saved, **{name: value for name, value in checked.items() if name not in own}}
        if system and own:
            self._own = {**self._own, system: {**self._own.get(system, {}), **own}}
        _write(self._path, self._saved, self._own)
        return checked

    def apply_to(self, config: Config, backend: str | None = None, system: str | None = None) -> Config:
        """A session's configuration with the person's settings laid over it. `config` is what the
        deployment and the session's own options give; `backend` is where the session's browser is;
        `system` names the session's browser where the service has several."""
        backend = backend or config.backend.kind
        patch: dict[str, Any] = {}
        for entry in CATALOGUE:
            if entry.backends is not None and backend not in entry.backends:
                continue
            holds, value = self._held(entry, config, system)
            if holds:
                patch = deep_merge(patch, _nested(entry.patch(value, config, system)))
        if not patch:
            return config
        return Config.model_validate(deep_merge(config.model_dump(), patch))

    def enabled(self, system: str) -> bool:
        """Whether a person has this browser of the window turned on (spec 9.17). It is, until they
        turn it off."""
        return self._held(ENABLED, self._config, system)[1] is not False

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


def _read(path: Path) -> tuple[Saved, dict[str, Saved]]:
    """A person's saved settings: those for every browser, and each system's own."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}, {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        # Passing over it in silence would drop what a person chose, a blocked site among it.
        raise ConfigError(
            f"{path}: the saved settings are not valid JSON (line {exc.lineno}). Correct the file or remove it"
        ) from exc
    if not isinstance(data, dict):
        raise ConfigError(f"{path}: the saved settings must be an object. Correct the file or remove it")
    systems = data.get(SYSTEMS)
    own = {
        str(system): _known(values)
        for system, values in (systems.items() if isinstance(systems, dict) else ())
        if isinstance(values, dict) and A_SYSTEMS_NAME.match(str(system))
    }
    return _known(data), own


def _write(path: Path, saved: Mapping[str, Value], own: Mapping[str, Saved]) -> None:
    """The file is the person's alone to read, and is never left half written."""
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + ".partial")
    handle = os.open(partial, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    kept: dict[str, Any] = dict(saved)
    if own:
        kept[SYSTEMS] = {system: values for system, values in own.items() if values}
    with os.fdopen(handle, "w", encoding="utf-8") as file:
        json.dump(kept, file, indent=2, sort_keys=True)
    os.replace(partial, path)
