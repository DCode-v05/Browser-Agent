"""What a tool call returns."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ToolResult:
    text: str
    is_error: bool = False
