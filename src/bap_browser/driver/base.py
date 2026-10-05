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
FieldKind = Literal["text", "check", "select", "other"]
LoadState = Literal["domcontentloaded", "load", "networkidle"]


# The role of a place an agent names by its position instead of by an element.
POINT = "point"


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
    secret: bool = False
    """A password field. Nothing about what it holds, not even its length, is told to anyone."""
    kind: FieldKind = "other"
    """How it is filled in a form: by typing, by ticking, or by choosing an option."""


@dataclass(frozen=True)
class ActionOutcome:
    target: str
    """The element acted on, as the snapshot names it: 'button "Create account"'."""
    navigated_to: str | None = None


@dataclass(frozen=True)
class ScrollPosition:
    """How far the page, or the box an element scrolls in, is scrolled, in page pixels."""

    x: int
    y: int
    width: int
    height: int
    moved: bool
    inside: bool = False
    """True when it is a box inside the page that scrolled, not the page."""


@dataclass(frozen=True)
class Found:
    lines: list[str]
    """Snapshot lines, best match first."""
    total: int


@dataclass(frozen=True)
class Checked:
    target: str
    checked: bool
    changed: bool


@dataclass(frozen=True)
class Selected:
    target: str
    labels: list[str]


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

    async def back(self) -> str | None:
        """The address now shown, or None when there is no earlier page."""
        ...

    async def forward(self) -> str | None: ...

    async def reload(self) -> str: ...

    async def text(self, ref: str | None, max_chars: int) -> tuple[str, int]:
        """The rendered text of the page or of one element, and how many characters were left out."""
        ...

    async def find(self, query: str, limit: int) -> Found: ...

    async def click_at(
        self, x: float, y: float, *, button: MouseButton, click_count: int, modifiers: Sequence[str]
    ) -> ActionOutcome: ...

    async def hover(self, ref: str) -> ActionOutcome: ...

    async def hover_at(self, x: float, y: float) -> ActionOutcome: ...

    async def scroll(
        self, dx: float, dy: float, *, ref: str | None, at: tuple[float, float] | None
    ) -> ScrollPosition: ...

    async def scroll_to(self, ref: str) -> ActionOutcome: ...

    async def press_key(self, keys: str, *, repeat: int, ref: str | None) -> ActionOutcome:
        """`keys` is in the form `bap_browser.keys.normalise` gives. The target is empty without a ref."""
        ...

    async def select_option(self, ref: str, values: Sequence[str]) -> Selected: ...

    async def set_checked(self, ref: str, checked: bool) -> Checked: ...

    async def wait_for_text(self, text: str, *, gone: bool, timeout_s: float) -> bool:
        """True when the page came to hold the text (or to hold it no longer) within the time."""
        ...

    async def wait_for_load(self, state: LoadState, timeout_s: float) -> bool: ...

    async def start_frames(self, on_frame: Callable[[bytes], None], level: QualityLevel) -> None:
        """Sends a JPEG picture of the page to `on_frame` whenever the page changes, within the level's limits."""
        ...

    async def stop_frames(self) -> None: ...

    # What a person does with the mouse and the keyboard while they are in control.

    async def pointer(self, action: PointerAction, x: float, y: float, button: MouseButton) -> None: ...

    async def key(self, action: KeyAction, key: str) -> None: ...

    async def wheel(self, x: float, y: float, dx: float, dy: float) -> None: ...
