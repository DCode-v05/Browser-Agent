"""What a person saved in the settings screen (spec 10.1, 10.2), and the configuration it makes.

    defaults  <  config.json  <  environment  <  a person's settings  <  per-session options

A person's value holds only while the deployment allows it: a locked setting, a choice that is no
longer offered and a value that would loosen what the deployment requires are passed over, and the
deployment's own value holds.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from bap_browser import __version__
from bap_browser.config import Config, deep_merge, defaults
from bap_browser.errors import ConfigError
from bap_browser.settings.catalogue import BY_ID, CATALOGUE, GROUPS, SURFACES, Entry, Reason, Value

# Where a value comes from when nobody said: the configuration file or the environment.
UNKNOWN_SOURCE = "configuration"


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
        self._saved = _read(self._path)

    def _locked(self, entry: Entry, config: Config) -> bool:
        return entry.id in config.settings.locked or entry.fixed_by_deployment(config)

    def _held(self, entry: Entry, config: Config) -> tuple[bool, Value]:
        """Whether a person's own value holds for this setting, and the value that holds."""
        if entry.id in self._saved and not self._locked(entry, config):
            saved = self._saved[entry.id]
            if entry.problem(saved, config) is None:
                return True, entry.tidy(saved)
        return False, entry.deployed(config)

    def answer(self, surface: str) -> dict[str, Any]:
        """What the settings screen is drawn from: the groups and their settings on this surface."""
        config = self._config
        groups: list[dict[str, Any]] = []
        for title in GROUPS:
            settings: list[dict[str, Any]] = []
            for entry in CATALOGUE:
                if entry.group != title or surface not in entry.surfaces:
                    continue
                settings.append(
                    {
                        "id": entry.id,
                        "title": entry.title,
                        "description": entry.description,
                        "control": entry.control,
                        **entry.described(config),
                        "value": entry.shown(self._held(entry, config)[1], config),
                        "default": entry.deployed(config),
                        "locked": self._locked(entry, config),
                        "applies": entry.applies,
                    }
                )
            if settings:
                groups.append({"id": title.lower().replace(" ", "_"), "title": title, "settings": settings})
        return {"surface": surface, "groups": groups}

    def change(self, surface: str, changes: Mapping[str, Any]) -> dict[str, Value]:
        """Saves a person's changes. Nothing is changed when any one of them is refused. Gives the
        settings that changed, with their new values, for the sessions to take up."""
        config = self._config
        checked: dict[str, Value] = {}
        for name, value in changes.items():
            entry = BY_ID.get(name)
            if entry is None or surface not in entry.surfaces:
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
        self._saved = {**self._saved, **checked}
        _write(self._path, self._saved)
        return checked

    def apply_to(self, config: Config, backend: str | None = None) -> Config:
        """A session's configuration with the person's settings laid over it. `config` is what the
        deployment and the session's own options give; `backend` is where the session's browser is."""
        backend = backend or config.backend.kind
        patch: dict[str, Any] = {}
        for entry in CATALOGUE:
            if entry.backends is not None and backend not in entry.backends:
                continue
            holds, value = self._held(entry, config)
            if holds:
                patch = deep_merge(patch, _nested(entry.patch(value, config)))
        if not patch:
            return config
        return Config.model_validate(deep_merge(config.model_dump(), patch))

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


def _read(path: Path) -> dict[str, Value]:
    """A person's saved settings. A setting this build does not know is passed over: the file may
    have been written by another build."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        # Passing over it in silence would drop what a person chose, a blocked site among it.
        raise ConfigError(
            f"{path}: the saved settings are not valid JSON (line {exc.lineno}). Correct the file or remove it"
        ) from exc
    if not isinstance(data, dict):
        raise ConfigError(f"{path}: the saved settings must be an object. Correct the file or remove it")
    return {name: value for name, value in data.items() if name in BY_ID}


def _write(path: Path, saved: Mapping[str, Value]) -> None:
    """The file is the person's alone to read, and is never left half written."""
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + ".partial")
    handle = os.open(partial, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(handle, "w", encoding="utf-8") as file:
        json.dump(saved, file, indent=2, sort_keys=True)
    os.replace(partial, path)
