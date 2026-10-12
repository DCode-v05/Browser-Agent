"""Hermes can describe a screenshot with a second model, for a model that sees no pictures. Every
model this engine runs computer use with sees pictures, so a screenshot goes to it as it is."""

from __future__ import annotations

from typing import Any


def read_main_provider() -> str:
    return ""


def read_main_model() -> str:
    return ""


def native_tool_result_images(provider: str, model: str, settings: dict[str, Any]) -> bool:
    """Whether the model takes a picture in a tool's result. Here it always does."""
    return True


def run_async(coro: Any) -> Any:
    raise RuntimeError("This engine describes no screenshot with a second model.")


def vision_analyze_tool(*given: Any, **named: Any) -> Any:
    raise RuntimeError("This engine describes no screenshot with a second model.")
