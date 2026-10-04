"""The driver interface: the seam between the core and a backend.

Every operation takes and returns plain data, so the same call can be made inside one process or
sent as one message over the bridge channel.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

from bap_browser.config import QualityLevel

MouseButton = Literal["left", "right", "middle"]
PointerAction = Literal["move", "down", "up"]
KeyAction = Literal["down", "up"]


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

    async def viewport(self) -> tuple[int, int]:
        """The width and height of what the browser shows, in page pixels."""
        ...

    async def navigate(self, url: str) -> str: ...

    async def locate(self, ref: str) -> Located: ...

    async def snapshot(self, *, mode: str, ref: str | None, max_chars: int, include_bboxes: bool) -> str: ...

    async def click(
        self, ref: str, *, button: MouseButton, click_count: int, modifiers: Sequence[str]
    ) -> ActionOutcome: ...

    async def type_text(
        self, ref: str | None, text: str, *, clear: bool, submit: bool, slowly: bool
    ) -> ActionOutcome: ...

    async def start_frames(self, on_frame: Callable[[bytes], None], level: QualityLevel) -> None:
        """Sends a JPEG picture of the page to `on_frame` whenever the page changes, within the level's limits."""
        ...

    async def stop_frames(self) -> None: ...

    # What a person does with the mouse and the keyboard while they are in control.

    async def pointer(self, action: PointerAction, x: float, y: float, button: MouseButton) -> None: ...

    async def key(self, action: KeyAction, key: str) -> None: ...

    async def wheel(self, x: float, y: float, dx: float, dy: float) -> None: ...
