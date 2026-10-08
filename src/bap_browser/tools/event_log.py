"""One line per tool call: what was done, never what was typed or what the page holds."""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from bap_browser import keys
from bap_browser.config import Logging
from bap_browser.policy.address import presentable_address
from bap_browser.results import ToolResult

# What an agent wrote to go into a page: what it typed, the answer to a prompt, a script.
TYPED_ARGUMENTS = frozenset({"text", "prompt_text", "expression", "task"})
ADDRESS_ARGUMENTS = frozenset({"url"})
# A key press that types a character is typed text. A named key, such as Enter, is not.
KEYS_ARGUMENT = "keys"
# The fields of a form: what goes into each is typed text.
FIELDS_ARGUMENT = "fields"


def _is_typed(name: str, value: str) -> bool:
    return name in TYPED_ARGUMENTS or (name == KEYS_ARGUMENT and keys.is_typed_text(value))


def _field(field: Any) -> Any:
    if not isinstance(field, Mapping):
        return f"<{type(field).__name__}>"
    value = field.get("value")
    kept = (
        value if isinstance(value, bool) else f"<{len(value)} characters>" if isinstance(value, str) else None
    )
    return {"ref": field.get("ref"), "value": kept}


def masked(arguments: Mapping[str, Any], redact: Callable[[str], str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name, value in arguments.items():
        if isinstance(value, str) and _is_typed(name, value):
            out[name] = f"<{len(value)} characters>"
        elif name == FIELDS_ARGUMENT and isinstance(value, list):
            out[name] = [_field(field) for field in value]
        elif name in ADDRESS_ARGUMENTS and isinstance(value, str):
            out[name] = redact(presentable_address(value) or "<not a valid address>")
        elif isinstance(value, str):
            out[name] = redact(value)
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

    def write(
        self,
        tool: str,
        arguments: Mapping[str, Any],
        result: ToolResult,
        ms: float,
        check: Mapping[str, Any] | None = None,
    ) -> None:
        """`arguments` are written as given: the caller has already taken out what must not be kept.
        `check` is what the check decided about the call (spec 18.9): never page text, typed text
        or a model's own sentence."""
        if self._path is None:
            return
        line: dict[str, Any] = {"ts": round(time.time(), 3), "tool": tool}
        if self._settings.log_tool_args:
            line["args"] = arguments
        line |= {
            "ok": not result.is_error,
            "ms": round(ms, 1),
            "chars": len(result.text),
            **({"check": dict(check)} if check is not None else {}),
            # The first line says what was done. What follows is the page, which can hold anything.
            "result": result.text.split("\n", 1)[0][: self._settings.max_result_chars],
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as log:
            log.write(json.dumps(line, ensure_ascii=False) + "\n")
