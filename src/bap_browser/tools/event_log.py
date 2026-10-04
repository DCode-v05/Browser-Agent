"""One line per tool call: what was done, never what was typed or what the page holds."""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from bap_browser.config import Logging
from bap_browser.policy.address import without_credentials
from bap_browser.results import ToolResult

TYPED_ARGUMENTS = frozenset({"text"})


def masked(arguments: Mapping[str, Any], redact: Callable[[str], str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name, value in arguments.items():
        if name in TYPED_ARGUMENTS and isinstance(value, str):
            out[name] = f"<{len(value)} characters>"
        elif isinstance(value, str):
            out[name] = redact(without_credentials(value))
        else:
            out[name] = value
    return out


def names_only(arguments: Mapping[str, Any]) -> dict[str, str]:
    """For a call that could not run: its arguments were never checked, so none of their values is kept."""
    return {name: f"<{type(value).__name__}>" for name, value in arguments.items()}


class EventLog:
    def __init__(self, settings: Logging) -> None:
        self._settings = settings
        self._path = Path(settings.event_log) if settings.event_log else None

    def write(self, tool: str, arguments: Mapping[str, Any], result: ToolResult, ms: float) -> None:
        """`arguments` are written as given: the caller has already taken out what must not be kept."""
        if self._path is None:
            return
        line: dict[str, Any] = {"ts": round(time.time(), 3), "tool": tool}
        if self._settings.log_tool_args:
            line["args"] = arguments
        line |= {
            "ok": not result.is_error,
            "ms": round(ms, 1),
            "chars": len(result.text),
            # The first line says what was done. What follows is the page, which can hold anything.
            "result": result.text.split("\n", 1)[0][: self._settings.max_result_chars],
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as log:
            log.write(json.dumps(line, ensure_ascii=False) + "\n")
