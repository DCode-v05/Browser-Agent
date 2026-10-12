"""Reads the file that says what the driver may touch. This engine writes it as JSON, which the
driver reads as it reads YAML."""

from __future__ import annotations

import json
from typing import IO, Any


def safe_load(file: IO[str]) -> Any:
    return json.load(file)
