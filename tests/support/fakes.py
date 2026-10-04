"""Stand-ins shared by the tests. This folder is on the tests' import path (see pyproject.toml)."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Any

from bap_browser.driver.base import ActionOutcome, Box, Located, TabInfo
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
        return [TabInfo("t1", self.url, "Fake", True)]

    async def locate(self, ref: str) -> Located:
        if ref == "e9":
            raise StaleRef(ref)
        if ref == "e3":
            return Located("textbox", "Email", Box(10, 60, 200, 24))
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
