"""Secrets come from the environment, or from a `.env` file beside where the command is run.

The file is never required and never committed. What the environment already holds wins.
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping, MutableMapping
from pathlib import Path

SETTING = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$")


def apply_env_file(file: Path, environ: MutableMapping[str, str] = os.environ) -> None:
    """Adds the file's settings to the environment, so that every part of the program reads them."""
    environ.update(environment(file, environ))


def environment(file: Path, given: Mapping[str, str]) -> dict[str, str]:
    """The environment with the file's settings added."""
    env = dict(given)
    if not file.is_file():
        return env
    # utf-8-sig also reads a file that a Windows editor saved with a byte-order mark.
    for line in file.read_text(encoding="utf-8-sig").splitlines():
        found = SETTING.match(line)
        if found and found.group(1) not in given:
            env[found.group(1)] = _value(found.group(2))
    return env


def _value(text: str) -> str:
    text = text.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        return text[1:-1]
    # Without quotes, a note after the value is not part of it.
    return text.split(" #", 1)[0].rstrip()
