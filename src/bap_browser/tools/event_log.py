"""One line per tool call. Typed text and form values are replaced by their length."""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from bap_browser.config import Logging
from bap_browser.results import ToolResult

TYPED_ARGUMENTS = frozenset({"text"})


def masked(arguments: Mapping[str, Any], redact: Callable[[str], str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name, value in arguments.items():
        if name in TYPED_ARGUMENTS and isinstance(value, str):
            out[name] = f"<{len(value)} characters>"
        elif isinstance(value, str):
            out[name] = redact(value)
        else:
            out[name] = value
    return out


class EventLog:
    def __init__(self, settings: Logging, redact: Callable[[str], str]) -> None:
        self._settings = settings
        self._redact = redact
        self._path = Path(settings.event_log) if settings.event_log else None

    def write(self, tool: str, arguments: Mapping[str, Any], result: ToolResult, ms: float) -> None:
        if self._path is None:
            return
        line: dict[str, Any] = {"ts": round(time.time(), 3), "tool": tool}
        if self._settings.log_tool_args:
            line["args"] = masked(arguments, self._redact)
        line |= {
            "ok": not result.is_error,
            "ms": round(ms, 1),
            "chars": len(result.text),
            "result": result.text[: self._settings.max_result_chars],
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as log:
            log.write(json.dumps(line, ensure_ascii=False) + "\n")
