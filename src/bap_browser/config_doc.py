"""The configuration reference, generated from config.py so that it cannot drift."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel
from pydantic.fields import FieldInfo

from bap_browser.config import Config, Section


def reference_markdown() -> str:
    lines: list[str] = []
    _section(Config, "", lines)
    return "\n".join(lines).rstrip() + "\n"


def _section(model: type[BaseModel], prefix: str, lines: list[str]) -> None:
    fields = model.model_fields
    values = {name: field for name, field in fields.items() if _nested(field) is None}
    if values:
        lines.append(f"**`{prefix[:-1]}`**" if prefix else "**Top level**")
        lines += ["", "| Key | Default | Meaning |", "|---|---|---|"]
        for name, field in values.items():
            lines.append(f"| `{name}` | {_default(field.default)} | {field.description or ''} |")
        lines.append("")
    for name, field in fields.items():
        nested = _nested(field)
        if nested is not None:
            _section(nested, f"{prefix}{name}.", lines)


def _nested(field: FieldInfo) -> type[Section] | None:
    """The section a field opens, or None when the field is a value (even one shaped like an object)."""
    kind = field.annotation
    if (
        isinstance(kind, type)
        and issubclass(kind, Section)
        and all(not inner.is_required() for inner in kind.model_fields.values())
    ):
        return kind
    return None


def _default(value: Any) -> str:
    if value is None:
        return "none"
    if isinstance(value, BaseModel):
        value = value.model_dump()
    return f"`{json.dumps(value)}`"
