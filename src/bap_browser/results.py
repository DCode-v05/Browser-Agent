"""What a tool call returns."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Picture:
    """An image a call asked for: a screenshot, or a part of one."""

    data: bytes
    mime: str


@dataclass(frozen=True)
class ToolResult:
    text: str
    is_error: bool = False
    picture: Picture | None = None
    """Only the tools that take a picture return one. No other result holds an image."""
