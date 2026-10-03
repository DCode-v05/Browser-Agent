"""Tool definitions: a name, a description for the model, typed arguments and a handler."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError

from bap_browser.driver.session import BrowserSession

REF_PATTERN = r"^(f\d+)?e\d+$"
NULL = {"type": "null"}


class Args(BaseModel):
    """Arguments of one tool. Unknown arguments are rejected."""

    model_config = ConfigDict(extra="forbid")


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    args: type[Args]
    handler: Callable[[BrowserSession, Any], Awaitable[str]]

    @property
    def input_schema(self) -> dict[str, Any]:
        return _tidy(self.args.model_json_schema())


def _tidy(node: Any) -> Any:
    """Drops what costs tokens and tells a model nothing: titles, and 'or null' on optional arguments."""
    if isinstance(node, list):
        return [_tidy(item) for item in node]
    if not isinstance(node, dict):
        return node
    tidy = {key: _tidy(value) for key, value in node.items() if key != "title"}
    choices = tidy.get("anyOf")
    if isinstance(choices, list) and NULL in choices:
        others = [choice for choice in choices if choice != NULL]
        if len(others) == 1:
            tidy = {key: value for key, value in tidy.items() if key not in ("anyOf", "default")} | others[0]
    return tidy


def describe_problem(error: ValidationError) -> str:
    first = error.errors()[0]
    name = ".".join(str(part) for part in first["loc"])
    if first["type"] == "extra_forbidden":
        return f"unknown argument '{name}'"
    if first["type"] == "missing":
        return f"missing argument '{name}'"
    return f"bad value for '{name}': {first['msg']}"
