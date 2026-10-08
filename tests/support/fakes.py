"""Stand-ins shared by the tests. This folder is on the tests' import path (see pyproject.toml)."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
from typing import Any

from bap_browser.config import QualityLevel
from bap_browser.driver.base import (
    ActionOutcome,
    Box,
    Checked,
    ConsoleLine,
    Dragged,
    Found,
    Happened,
    Located,
    NetworkLine,
    PageDialog,
    Place,
    SavedFile,
    ScrollPosition,
    Selected,
    Shot,
    TabInfo,
)
from bap_browser.errors import BadInput, StaleRef
from bap_browser.results import Picture

PICTURE = Picture(b"not really a picture", "image/png")

SNAPSHOT = (
    'Page: Fake\nURL: https://example.com/\nScroll: 0px of 800px (viewport 800px)\n- button "Go" [ref=e1]'
)


class QuietObserver:
    """Takes every notice of the tool layer and does nothing with it. A test's own observer
    inherits from it, and listens to what the test is about."""

    def step_started(self, step: int, tool: str, label: str, target: Box | None) -> None: ...

    def step_finished(
        self, step: int, ok: bool, ms: float, chars: int, summary: str, tabs: Sequence[TabInfo]
    ) -> None: ...

    def navigation_blocked(self, url: str, reason: str) -> None: ...

    def limit_reached(self, kind: str, limit: float, on_a_task: bool) -> None: ...

    def task_declared(self, limit_lifted: bool) -> None: ...

    def check_decided(
        self,
        step: int,
        stage: str,
        outcome: str,
        findings: Sequence[str],
        reason: str,
        said: str = "",
        refused_id: str | None = None,
    ) -> None: ...

    def sites_changed(self, sites: Sequence[Any]) -> None: ...

    def page_flagged(self, tab: str, site: str, rule: str, count: int) -> None: ...

    def auto_changed(self) -> None: ...


class FakeDriver:
    def __init__(self) -> None:
        self.started = 0
        self.calls: list[tuple[str, Any]] = []
        self.url = "about:blank"
        self.running = 0
        self.most_at_once = 0
        self.fail_with: Exception | None = None
        self.next_address: str | None = None
        self.title = "Fake"
        self.on_frame: Callable[[bytes], None] = lambda frame: None
        """Call it to send a picture, as the browser would."""
        self.level: QualityLevel | None = None
        self.hold: asyncio.Event | None = None
        """When set, a click waits for it: an action in progress, for as long as a test needs."""
        self.alive = True
        """Where the next navigation ends up, when that is not where it was sent."""
        self.tell: Callable[[Happened], None] = lambda event: None
        """Call it to say what happened in the browser by itself, as the browser would."""
        self.open_tabs = ["t1"]
        self.active_tab = "t1"
        self.dialog: PageDialog | None = None
        self._dialog_open = asyncio.Event()
        self.pixel = 1.0
        """Page pixels per pixel of the last screenshot."""
        self.console_lines: list[ConsoleLine] = []
        self.requests: list[NetworkLine] = []
        self.saved: list[SavedFile] = []
        self.value: Any = None
        """What the next script gives."""
        self.elements: dict[str, Located] = {}
        """What a test puts on the page, by ref, besides the elements every fake page has."""
        self.at_point: Located | None = None
        """The control a press by its place lands on."""
        self.focused: Located | None = None
        """The element that has the focus."""
        self.said: list[str] = []
        self.hidden: list[str] = []
        """The text the last read left out because no person can see it."""
        """The page's headings and buttons."""
        self.mark: str | None = None
        """What the page says of itself after a step. The same twice means that nothing changed;
        None means that it cannot be told."""

    def listen(self, on_event: Callable[[Happened], None]) -> None:
        self.tell = on_event

    def guard(self, judge: Any) -> None:
        self.judge = judge

    def open_dialog(self, dialog: PageDialog) -> None:
        """A page opens a dialog, as it would in the middle of an action."""
        self.dialog = dialog
        self._dialog_open.set()

    def pending_dialog(self) -> PageDialog | None:
        return self.dialog

    async def dialog_opened(self) -> None:
        await self._dialog_open.wait()

    async def answer_dialog(self, accept: bool, text: str | None) -> PageDialog:
        if self.dialog is None:
            raise BadInput("No dialog is open.", reason="no dialog is open")
        answered, self.dialog = self.dialog, None
        self._dialog_open.clear()
        self.calls.append(("answer_dialog", {"accept": accept, "text": text}))
        if self.hold is not None:
            # The page goes on with what the dialog had interrupted.
            self.hold.set()
        return answered

    def page_point(self, x: float, y: float) -> tuple[float, float]:
        return x * self.pixel, y * self.pixel

    async def screenshot(self, *, full_page: bool, annotate: bool) -> Shot:
        self.calls.append(("screenshot", {"full_page": full_page, "annotate": annotate}))
        return Shot(PICTURE, 1280, 3000 if full_page else 800)

    async def zoom(self, region: tuple[float, float, float, float]) -> Shot:
        self.calls.append(("zoom", region))
        return Shot(PICTURE, round(region[2] - region[0]), round(region[3] - region[1]))

    async def drag(self, start: Place, end: Place) -> Dragged:
        self.calls.append(("drag", (start, end)))
        return Dragged('clickable "Card A"', 'clickable "Done column"')

    async def new_tab(self) -> str:
        tab = f"t{len(self.open_tabs) + 1}"
        self.open_tabs.append(tab)
        self.active_tab = tab
        self.calls.append(("new_tab", tab))
        return tab

    async def switch_tab(self, tab_id: str) -> None:
        if tab_id not in self.open_tabs:
            raise BadInput(f"There is no tab {tab_id}.", reason="there is no such tab")
        self.active_tab = tab_id
        self.calls.append(("switch_tab", tab_id))

    async def close_tab(self, tab_id: str | None) -> str:
        closed = tab_id or self.active_tab
        self.open_tabs.remove(closed)
        self.active_tab = self.open_tabs[-1] if self.open_tabs else ""
        self.calls.append(("close_tab", closed))
        return closed

    def console(self, *, clear: bool) -> list[ConsoleLine]:
        lines = list(self.console_lines)
        if clear:
            self.console_lines.clear()
        return lines

    def network(self, *, clear: bool) -> list[NetworkLine]:
        lines = list(self.requests)
        if clear:
            self.requests.clear()
        return lines

    async def evaluate(self, expression: str) -> Any:
        self.calls.append(("evaluate", expression))
        return self.value

    async def upload(self, ref: str, paths: Sequence[str]) -> ActionOutcome:
        self.calls.append(("upload", {"ref": ref, "paths": list(paths)}))
        return ActionOutcome('button "Attach files"')

    def guard_files(self, judge: Any) -> None:
        self.judge_file = judge

    async def settle_download(self, name: str, keep: bool, reason: str = "") -> None:
        self.calls.append(("settle_download", (name, keep, reason)))
        self.saved = [
            SavedFile(file.name, "saved" if keep else "failed", file.path, file.size, "" if keep else reason)
            if file.name == name and file.state == "held"
            else file
            for file in self.saved
        ]

    def downloads(self) -> list[SavedFile]:
        return list(self.saved)

    async def start(self) -> None:
        self.started += 1
        self.alive = True

    async def close(self) -> None:
        self.calls.append(("close", None))

    def is_alive(self) -> bool:
        return self.started > 0 and self.alive

    def description(self) -> str:
        return "Fake 1.0"

    async def tabs(self) -> list[TabInfo]:
        asking = self.dialog.tab if self.dialog else ""
        return [
            TabInfo(tab, self.url, self.title, tab == self.active_tab, tab == asking)
            for tab in self.open_tabs
        ]

    async def viewport(self) -> tuple[int, int]:
        return 1280, 800

    async def start_frames(self, on_frame: Callable[[bytes], None], level: QualityLevel) -> None:
        self.on_frame, self.level = on_frame, level

    async def stop_frames(self) -> None:
        self.level = None

    async def pointer(self, action: str, x: float, y: float, button: str) -> None:
        self.calls.append(("pointer", (action, x, y, button)))

    async def key(self, action: str, key: str) -> None:
        self.calls.append(("key", (action, key)))

    async def wheel(self, x: float, y: float, dx: float, dy: float) -> None:
        self.calls.append(("wheel", (x, y, dx, dy)))

    async def change_mark(self) -> str | None:
        return self.mark

    async def locate_point(self, x: float, y: float) -> Located | None:
        return self.at_point

    async def locate_focus(self) -> Located | None:
        return self.focused

    async def gist(self) -> list[str]:
        return self.said

    def where(self) -> tuple[str, str]:
        return self.active_tab, self.url

    def unseen(self) -> list[str]:
        return self.hidden

    async def locate(self, ref: str, *, press: bool = False) -> Located:
        if ref in self.elements:
            return self.elements[ref]
        if ref == "e9":
            raise StaleRef(ref)
        if ref == "e3":
            return Located("textbox", "Email", Box(10, 60, 200, 24), kind="text")
        if ref == "e5":
            return Located("checkbox", "Terms", Box(10, 90, 16, 16), kind="check")
        if ref == "e6":
            return Located("combobox", "Country", Box(10, 120, 200, 24), kind="select")
        if ref == "e7":
            return Located("button", "Pay now", Box(10, 150, 80, 24))
        if ref == "e8":
            return Located("textbox", "Password", Box(10, 180, 200, 24), secret=True, kind="text")
        return Located("button", "Go", Box(10, 20, 80, 24))

    async def navigate(self, url: str) -> str:
        self.calls.append(("navigate", url))
        self.url = self.next_address or url
        return self.url

    async def snapshot(self, *, mode: str, ref: str | None, max_chars: int, include_bboxes: bool) -> str:
        self.calls.append(
            ("snapshot", {"mode": mode, "ref": ref, "max_chars": max_chars, "bboxes": include_bboxes})
        )
        return SNAPSHOT

    async def click(
        self, ref: str, *, button: str, click_count: int, modifiers: Sequence[str]
    ) -> ActionOutcome:
        self.running += 1
        self.most_at_once = max(self.most_at_once, self.running)
        await asyncio.sleep(0)
        if self.hold is not None:
            await self.hold.wait()
        self.running -= 1
        if self.fail_with is not None:
            raise self.fail_with
        self.calls.append(
            ("click", {"ref": ref, "button": button, "count": click_count, "modifiers": list(modifiers)})
        )
        return ActionOutcome('button "Go"', "https://example.com/next" if ref == "e2" else None)

    async def type_text(
        self, ref: str | None, text: str, *, clear: bool, submit: bool, slowly: bool
    ) -> ActionOutcome:
        self.calls.append(
            ("type", {"ref": ref, "text": text, "clear": clear, "submit": submit, "slowly": slowly})
        )
        return ActionOutcome('textbox "Email"')

    async def back(self) -> str | None:
        self.calls.append(("back", None))
        return self.next_address

    async def forward(self) -> str | None:
        self.calls.append(("forward", None))
        return self.next_address

    async def reload(self) -> str:
        self.calls.append(("reload", None))
        return self.url

    async def text(self, ref: str | None, max_chars: int) -> tuple[str, int]:
        self.calls.append(("text", {"ref": ref, "max_chars": max_chars}))
        words = "Welcome to the fake page."
        return words[:max_chars], max(0, len(words) - max_chars)

    async def find(self, query: str, limit: int) -> Found:
        self.calls.append(("find", {"query": query, "limit": limit}))
        lines = ['- button "Go" [ref=e1]', '- link "Go home" [ref=e2]'] if "go" in query.lower() else []
        return Found(lines[:limit], len(lines))

    async def click_at(
        self, x: float, y: float, *, button: str, click_count: int, modifiers: Sequence[str]
    ) -> ActionOutcome:
        self.calls.append(("click_at", {"x": x, "y": y, "button": button, "count": click_count}))
        return ActionOutcome('button "Go"')

    async def hover(self, ref: str) -> ActionOutcome:
        self.calls.append(("hover", ref))
        return ActionOutcome('button "Go"')

    async def hover_at(self, x: float, y: float) -> ActionOutcome:
        self.calls.append(("hover_at", (x, y)))
        return ActionOutcome("")

    async def scroll(
        self, dx: float, dy: float, *, ref: str | None, at: tuple[float, float] | None
    ) -> ScrollPosition:
        self.calls.append(("scroll", {"dx": dx, "dy": dy, "ref": ref, "at": at}))
        return ScrollPosition(
            int(max(dx, 0)), int(max(dy, 0)), 1280, 3200, moved=dx > 0 or dy > 0, inside=ref is not None
        )

    async def scroll_to(self, ref: str) -> ActionOutcome:
        self.calls.append(("scroll_to", ref))
        return ActionOutcome('button "Go"')

    async def press_key(self, keys: str, *, repeat: int, ref: str | None) -> ActionOutcome:
        self.calls.append(("press_key", {"keys": keys, "repeat": repeat, "ref": ref}))
        return ActionOutcome('textbox "Email"' if ref else "")

    async def select_option(self, ref: str, values: Sequence[str]) -> Selected:
        self.calls.append(("select_option", {"ref": ref, "values": list(values)}))
        return Selected('combobox "Country"', [value.title() for value in values])

    async def set_checked(self, ref: str, checked: bool) -> Checked:
        if self.fail_with is not None:
            raise self.fail_with
        self.calls.append(("set_checked", {"ref": ref, "checked": checked}))
        return Checked('checkbox "Terms"', checked, changed=True)

    async def wait_for_text(self, text: str, *, gone: bool, timeout_s: float) -> bool:
        self.calls.append(("wait_for_text", {"text": text, "gone": gone, "timeout_s": timeout_s}))
        return text != "never"

    async def wait_for_load(self, state: str, timeout_s: float) -> bool:
        self.calls.append(("wait_for_load", {"state": state, "timeout_s": timeout_s}))
        return True
