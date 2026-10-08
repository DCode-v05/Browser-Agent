"""Files that are for the person who runs the service alone to read: their settings, their
passwords' hashes, the records of their tasks. Each is made readable by its owner only, and one that
is written whole is never left half written."""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from typing import Any

OWNER_ONLY = stat.S_IRUSR | stat.S_IWUSR


def write_json(path: Path, data: Any, **how: Any) -> None:
    """Writes the whole file. `how` is passed to `json.dump`, such as `indent=2`."""
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + ".partial")
    handle = os.open(partial, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, OWNER_ONLY)
    with os.fdopen(handle, "w", encoding="utf-8") as file:
        json.dump(data, file, **how)
    os.replace(partial, path)


def add_line(path: Path, line: str) -> None:
    """Adds one line to the end of the file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, OWNER_ONLY)
    with os.fdopen(handle, "a", encoding="utf-8") as file:
        file.write(line + "\n")
