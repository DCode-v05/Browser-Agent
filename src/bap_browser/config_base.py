"""What a section of the configuration is, and how one setting is written."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Section(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def setting(default: Any, meaning: str) -> Any:
    """A setting with its default and the sentence the generated reference shows for it."""
    return Field(default=default, description=meaning)
