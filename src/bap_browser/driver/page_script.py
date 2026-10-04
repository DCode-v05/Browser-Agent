"""Calls the page script inside an isolated world of a page's main frame."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from playwright.async_api import CDPSession
from playwright.async_api import Error as PlaywrightError

from bap_browser.errors import BrowserError

SCRIPT = Path(__file__).with_name("snapshot_page.js").read_text(encoding="utf-8")
WORLD = "bap"
NOT_INSTALLED = "__bap_not_installed__"


class _DocumentGone(Exception):
    """The document was replaced while it was being used."""


class PageScript:
    def __init__(self, cdp: CDPSession, reply_ms: int) -> None:
        self._cdp = cdp
        self._reply_ms = reply_ms
        self._frame_id: str | None = None
        self._context_id: int | None = None

    async def call(self, operation: str, arguments: dict[str, Any], *, wait_ms: int = 0) -> Any:
        """Runs one operation. `wait_ms` is how long the operation itself may wait inside the page.

        A page can be too busy to answer, or be held up by a navigation that never finishes. The
        call then fails; it never waits for ever.
        """
        limit = (self._reply_ms + wait_ms) / 1000
        try:
            async with asyncio.timeout(limit):
                return await self._call_on_the_live_document(operation, arguments)
        except TimeoutError:
            raise BrowserError(
                f"The page did not answer within {limit:g} s. It may be busy or still loading. "
                "Try again, or open another page with browser_navigate.",
                reason="the page is not answering",
            ) from None

    async def _call_on_the_live_document(self, operation: str, arguments: dict[str, Any]) -> Any:
        """A document replaced part-way is tried once more on the new one."""
        try:
            return await self._call(operation, arguments)
        except _DocumentGone:
            self._context_id = None
        try:
            return await self._call(operation, arguments)
        except _DocumentGone as exc:
            self._context_id = None
            raise BrowserError(
                "The page changed while it was being read. Try again.", reason="the page changed"
            ) from exc

    async def frames_passed(self, count: int, frame_ms: int) -> bool:
        """Waits for `count` animation frames. False means the document went away: a navigation."""
        try:
            async with asyncio.timeout((self._reply_ms + count * frame_ms) / 1000):
                await self._call("frames", {"count": count, "frameMs": frame_ms})
        except _DocumentGone:
            self._context_id = None
            return False
        except TimeoutError:
            # A page too busy to draw a frame is still the same document.
            return True
        return True

    def forget_document(self) -> None:
        """The driver loaded another document: the next call makes its world in that one."""
        self._context_id = None

    async def _call(self, operation: str, arguments: dict[str, Any]) -> Any:
        context_id = await self._context()
        expression = (
            f"typeof __bap === 'function' ? __bap({json.dumps(operation)}, {json.dumps(arguments)})"
            f" : {json.dumps(NOT_INSTALLED)}"
        )
        value = await self._evaluate(expression, context_id)
        if value == NOT_INSTALLED:
            await self._evaluate(SCRIPT, context_id)
            value = await self._evaluate(expression, context_id)
        return value

    async def _context(self) -> int:
        if self._context_id is None:
            try:
                if self._frame_id is None:
                    tree = await self._cdp.send("Page.getFrameTree")
                    self._frame_id = tree["frameTree"]["frame"]["id"]
                world = await self._cdp.send(
                    "Page.createIsolatedWorld", {"frameId": self._frame_id, "worldName": WORLD}
                )
            except PlaywrightError as exc:
                raise _DocumentGone(str(exc)) from exc
            context_id: int = world["executionContextId"]
            self._context_id = context_id
            return context_id
        return self._context_id

    async def _evaluate(self, expression: str, context_id: int) -> Any:
        try:
            reply = await self._cdp.send(
                "Runtime.evaluate",
                {
                    "expression": expression,
                    "contextId": context_id,
                    "returnByValue": True,
                    "awaitPromise": True,
                },
            )
        except PlaywrightError as exc:
            raise _DocumentGone(str(exc)) from exc
        details = reply.get("exceptionDetails")
        if details:
            text = details.get("exception", {}).get("description") or details.get("text") or "script error"
            raise BrowserError(text.splitlines()[0], reason="the page could not be read")
        return reply["result"].get("value")
