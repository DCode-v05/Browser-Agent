"""The driver interface: the seam between the core and a backend.

Every operation takes and returns plain data, so the same call can be made inside one process or
sent as one message over the bridge channel.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

MouseButton = Literal["left", "right", "middle"]


@dataclass(frozen=True)
class TabInfo:
    id: str
    url: str
    title: str
    active: bool


@dataclass(frozen=True)
class Box:
    """A rectangle in page pixels, from the top left of what the browser shows."""

    x: float
    y: float
    w: float
    h: float


@dataclass(frozen=True)
class Located:
    role: str
    name: str
    box: Box | None
    """Where the element is. None when it is outside what the browser shows."""


@dataclass(frozen=True)
class ActionOutcome:
    target: str
    """The element acted on, as the snapshot names it: 'button "Create account"'."""
    navigated_to: str | None = None


class Driver(Protocol):
    async def start(self) -> None: ...

    async def close(self) -> None: ...

    def is_alive(self) -> bool: ...

    def description(self) -> str: ...

    async def tabs(self) -> list[TabInfo]: ...

    async def navigate(self, url: str) -> str: ...

    async def locate(self, ref: str) -> Located: ...

    async def snapshot(self, *, mode: str, ref: str | None, max_chars: int, include_bboxes: bool) -> str: ...

    async def click(
        self, ref: str, *, button: MouseButton, click_count: int, modifiers: Sequence[str]
    ) -> ActionOutcome: ...

    async def type_text(
        self, ref: str | None, text: str, *, clear: bool, submit: bool, slowly: bool
    ) -> ActionOutcome: ...
