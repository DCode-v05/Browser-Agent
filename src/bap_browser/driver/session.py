"""One browser with the policy and the redactor that apply to it."""

from __future__ import annotations

from collections import deque
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Literal

from bap_browser.config import Config
from bap_browser.driver.base import Driver, Happened, PageDialog
from bap_browser.driver.playwright_driver import PlaywrightDriver
from bap_browser.errors import BrowserError
from bap_browser.policy.address import without_credentials
from bap_browser.policy.redaction import Redactor
from bap_browser.policy.url_policy import UrlPolicy

SESSION_ENDED = "The session has ended."

AskPerson = Callable[[str, str, float], Awaitable[tuple[str, str]]]
"""Asks a person to do a step in the browser: the reason, the kind of step and the longest wait in
seconds go in; the outcome (`done`, `could_not`, `timed_out`) and what changed meanwhile come out."""


ApprovalOutcome = Literal["allowed", "allowed_site", "denied", "expired", "unwatched"]
AskApproval = Callable[[str, str, str, bool], Awaitable[ApprovalOutcome]]
"""Asks a person whether an action may be done: the tool, what it will do in a sentence, and the
site go in, and whether such an action is asked about every time; their answer comes out."""


AskSite = Callable[[str, str, str], Awaitable[str | None]]
"""Asks whether the agent may read or act on a site: `read` or `act`, the address, and what the call
does in a sentence. None when it may; otherwise what the agent is told."""


class BrowserSession:
    def __init__(self, config: Config, driver: Driver | None = None) -> None:
        self.config = config
        self.policy = UrlPolicy(config.safety)
        self.redact = Redactor(config.safety.redact_patterns)
        self._driver: Driver = driver if driver is not None else PlaywrightDriver(config)
        self._started = False
        self._lost = False
        self.ask_person: AskPerson | None = None
        """Set by whoever can reach a person. None when nobody is watching this session."""
        self.ask_site: AskSite | None = None
        """Set on a person's own browser, where the bridge on their machine decides which sites the
        agent may read and act on (spec 8.8). None on every other backend."""
        self.site_done: Callable[[], Awaitable[None]] | None = None
        """Told when a call the bridge was asked about has finished: what was allowed once is over."""
        self.ask_approval: AskApproval | None = None
        """Set by whoever can reach a person. None when there is nobody to ask."""
        self._closed = False
        self.on_event: Callable[[Happened], None] | None = None
        """Set by whoever shows the session to a person. It is told at once what happens in the browser
        by itself: a tab that opens, a dialog, a file that was saved."""
        # The same, kept for the agent until its next result.
        self._news: deque[Happened] = deque(maxlen=config.browser.capture.max_state_events)
        self._driver.listen(self._happened)

    def _happened(self, event: Happened) -> None:
        if event.text:
            self._news.append(event)
        if self.on_event is not None:
            self.on_event(event)

    def take_news(self) -> list[str]:
        """What happened in the browser by itself since this was last asked."""
        news = [event.text for event in self._news]
        self._news.clear()
        return news

    def pending_dialog(self) -> PageDialog | None:
        """The dialog a page has open and that waits for an answer."""
        return self._driver.pending_dialog() if self._started else None

    async def dialog_opened(self) -> None:
        """Returns when a page has a dialog open that waits for an answer."""
        await self._driver.dialog_opened()

    def shown_address(self, url: str) -> str:
        """An address as it may appear in a result, an event or the log: no name and password, and capped,
        because a page can make its own address as long as it likes."""
        url, limit = without_credentials(url), self.config.browser.snapshot.max_text_chars
        return url if len(url) <= limit else url[:limit] + "…"

    @property
    def started_driver(self) -> Driver | None:
        return self._driver if self._started else None

    async def driver(self, *, may_restart: bool = False) -> Driver:
        """The driver, with its browser started on the first use.

        A browser that has gone away (it crashed, or a person closed its window) is started again
        only by a call that opens a page. Any other call is told that the page it meant is gone.
        """
        if self._closed:
            raise BrowserError(SESSION_ENDED, reason="the session ended")
        if self._started and not self._driver.is_alive():
            await self._stop()
            self._lost = True
            # The agent is told that the browser closed. That its tabs closed with it is no news.
            kept = [event for event in self._news if event.kind != "tab_closed"]
            self._news.clear()
            self._news.extend(kept)
        if self._lost and not may_restart:
            raise BrowserError(
                "The browser closed. Open a page with browser_navigate to start it again.",
                reason="the browser closed",
            )
        if not self._started:
            await self._driver.start()
            self._started, self._lost = True, False
            if self._closed:
                # The session was ended while the browser was starting.
                await self._stop()
                raise BrowserError(SESSION_ENDED, reason="the session ended")
        return self._driver

    async def close(self) -> None:
        """Ends the session for good. No later call starts the browser again."""
        self._closed = True
        await self._stop()

    async def _stop(self) -> None:
        if self._started:
            self._started = False
            await self._driver.close()


@asynccontextmanager
async def open_session(config: Config, driver: Driver | None = None) -> AsyncIterator[BrowserSession]:
    session = BrowserSession(config, driver)
    try:
        yield session
    finally:
        await session.close()
