"""The driver interface: the seam between the core and a backend.

Every operation takes and returns plain data, so the same call can be made inside one process or
sent as one message over the bridge channel.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from bap_browser.config import QualityLevel
from bap_browser.results import Picture

MouseButton = Literal["left", "right", "middle"]
PointerAction = Literal["move", "down", "up"]
KeyAction = Literal["down", "up"]
FieldKind = Literal["text", "check", "select", "other"]
LoadState = Literal["domcontentloaded", "load", "networkidle"]
DialogKind = Literal["alert", "confirm", "prompt", "beforeunload"]
LogLevel = Literal["debug", "info", "warning", "error"]
Place = str | tuple[float, float]
"""An element by its ref, or a point of the page in pixels from the top left of what the browser shows."""


# The role of a place an agent names by its position instead of by an element.
POINT = "point"


@dataclass(frozen=True)
class TabInfo:
    id: str
    url: str
    title: str
    active: bool
    attention: bool = False
    """A dialog is open in it and waits for an answer."""


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
    # What the check needs to know of it besides its name (spec 18.4, 18.6).
    document: str = ""
    """The address of the document it is in: the page's, or a frame's own."""
    input_type: str = ""
    autocomplete: str = ""
    attributes: tuple[str, ...] = ()
    """Its `name` and `id` attributes, where it has them."""
    dots: bool = False
    """What is typed into it is drawn as dots, as in a password field, whatever its type."""
    multiline: bool = False
    """A text area or an editable block."""
    search: bool = False
    sends_form: tuple[tuple[str, str, bool, bool], ...] = ()
    """When pressing it sends a form: that form's text fields, each as its role, its name, whether
    it takes several lines and whether it is a search box."""
    around: tuple[str, ...] = ()
    """The text near a control that is pressed: of its form, then of the block around it."""


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


@dataclass(frozen=True)
class Shot:
    """A picture of the page, and its size in its own pixels."""

    picture: Picture
    width: int
    height: int
    scaled: bool = False
    """True when the picture is smaller than the page it shows."""


@dataclass(frozen=True)
class Dragged:
    source: str
    target: str
    navigated_to: str | None = None


@dataclass(frozen=True)
class PageDialog:
    """A dialog a page opened (alert, confirm, prompt, or "leave this page?") that waits for an answer."""

    id: str
    kind: DialogKind
    text: str
    tab: str

    @property
    def a_kind(self) -> str:
        """What it is, as a sentence says it: a confirm dialog."""
        if self.kind == "beforeunload":
            return "a dialog that asks whether to leave the page"
        return f"{'an' if self.kind == 'alert' else 'a'} {self.kind} dialog"

    @property
    def quoted(self) -> str:
        """What it says, to follow what it is: ('Proceed?'). The dialog that asks whether to leave
        the page says nothing of its own."""
        return "" if self.kind == "beforeunload" else f" ('{self.text}')"

    @property
    def named(self) -> str:
        """As a sentence names it: a confirm dialog ('Proceed?')."""
        return self.a_kind + self.quoted


@dataclass(frozen=True)
class ConsoleLine:
    level: LogLevel
    text: str


@dataclass(frozen=True)
class NetworkLine:
    method: str
    status: int | None
    """None when the request failed before any answer came."""
    kind: str
    """What was asked for: document, script, image, fetch, …"""
    url: str
    failure: str = ""


@dataclass(frozen=True)
class SavedFile:
    """A file the browser downloaded, or is downloading."""

    name: str
    state: Literal["saved", "downloading", "failed"]
    path: str = ""
    size: int = 0
    reason: str = ""
    """Why it failed, in a few words."""


@dataclass(frozen=True)
class Happened:
    """Something that happened in the browser by itself: a tab opened or closed, a dialog opened or
    was answered, a file was saved."""

    kind: Literal[
        "tab_opened",
        "tab_closed",
        "tab_out_of_reach",
        "dialog_opened",
        "dialog_closed",
        "download",
        "blocked",
        "file_chooser",
        "notice",
    ]
    text: str
    """As the agent is told, in the state block of its next result."""
    detail: Mapping[str, Any] = field(default_factory=dict[str, Any])
    """What a person watching is shown. Empty when there is nothing to show them."""


Guard = Callable[[str], Awaitable[tuple[bool, str]]]
"""Judges an address: whether it may be loaded, and when not, why in a few words."""


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

    async def locate(self, ref: str, *, press: bool = False) -> Located:
        """What an element is. With `press`, also what pressing it would send and what stands near it."""
        ...

    async def locate_point(self, x: float, y: float) -> Located | None:
        """The control that a press at a point of the page lands on. None when nothing is there."""
        ...

    async def locate_focus(self) -> Located | None:
        """The element that has the focus, where typed keys go. None when nothing has it."""
        ...

    async def gist(self) -> list[str]:
        """What the page says it is about, in a few words: its headings and its buttons."""
        ...

    def unseen(self) -> list[str]:
        """The text the last read of the active tab left out because no person can see it (spec
        18.5). It is not given to the agent; the rules that look for planted text read it."""
        ...

    def where(self) -> tuple[str, str]:
        """The active tab and the address it shows, as known without asking the page. Empty when no tab is open."""
        ...

    async def change_mark(self) -> str | None:
        """A value that is the same as the last time only when the active tab shows the same
        document and nothing in it has changed since: its structure, what is typed or chosen,
        what is scrolled, where the keyboard put the focus (spec 18.8). None when it cannot be told."""
        ...

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

    def listen(self, on_event: Callable[[Happened], None]) -> None:
        """Names who is told what happens in the browser by itself."""
        ...

    def guard(self, judge: Guard) -> None:
        """Names who decides, at the network, whether the browser may load an address (spec 8.1).
        Every document the browser sets out to load is put to it first: where a link leads, where a
        redirect goes, what a frame holds, what a page opens in a new window."""
        ...

    # Pictures. None is taken unless a call asks for one.

    async def screenshot(self, *, full_page: bool, annotate: bool) -> Shot:
        """A picture of what the browser shows, or of the whole page. `annotate` draws each
        element's ref on it."""
        ...

    async def zoom(self, region: tuple[float, float, float, float]) -> Shot:
        """A region of the last screenshot, given in its pixels, at the page's full resolution."""
        ...

    def page_point(self, x: float, y: float) -> tuple[float, float]:
        """A point given in the pixels of the last screenshot of the visible area, as a point of the page."""
        ...

    async def drag(self, start: Place, end: Place) -> Dragged: ...

    # Tabs. A window a page opens becomes a tab.

    async def new_tab(self) -> str:
        """Opens an empty tab, makes it the active one and returns its id."""
        ...

    async def switch_tab(self, tab_id: str) -> None: ...

    async def close_tab(self, tab_id: str | None) -> str:
        """Closes a tab, the active one when none is named, and returns its id."""
        ...

    # Dialogs. While one is open its page answers nothing.

    def pending_dialog(self) -> PageDialog | None:
        """The dialog that has waited longest for an answer."""
        ...

    async def dialog_opened(self) -> None:
        """Returns when a dialog is open that waits for an answer: at once, if one is open now."""
        ...

    async def answer_dialog(self, accept: bool, text: str | None) -> PageDialog: ...

    # Diagnostics, of the active tab.

    def console(self, *, clear: bool) -> list[ConsoleLine]: ...

    def network(self, *, clear: bool) -> list[NetworkLine]: ...

    async def evaluate(self, expression: str) -> Any:
        """Runs a script in the page, among the page's own scripts, and returns its value."""
        ...

    # Files.

    async def upload(self, ref: str, paths: Sequence[str]) -> ActionOutcome:
        """Gives files to a file field, or to the file chooser that a button opens."""
        ...

    def downloads(self) -> list[SavedFile]: ...
