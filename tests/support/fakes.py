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
    Found,
    Located,
    ScrollPosition,
    Selected,
    TabInfo,
)
from bap_browser.errors import StaleRef

SNAPSHOT = (
    'Page: Fake\nURL: https://example.com/\nScroll: 0px of 800px (viewport 800px)\n- button "Go" [ref=e1]'
)


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
        return [TabInfo("t1", self.url, self.title, True)]

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

    async def locate(self, ref: str) -> Located:
        if ref == "e9":
            raise StaleRef(ref)
        if ref == "e3":
            return Located("textbox", "Email", Box(10, 60, 200, 24), kind="text")
        if ref == "e5":
            return Located("checkbox", "Terms", Box(10, 90, 16, 16), kind="check")
        if ref == "e6":
            return Located("combobox", "Country", Box(10, 120, 200, 24), kind="select")
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
