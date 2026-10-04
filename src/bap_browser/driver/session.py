"""One browser with the policy and the redactor that apply to it."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from bap_browser.config import Config
from bap_browser.driver.base import Driver
from bap_browser.driver.playwright_driver import PlaywrightDriver
from bap_browser.errors import BrowserError
from bap_browser.policy.address import without_credentials
from bap_browser.policy.redaction import Redactor
from bap_browser.policy.url_policy import UrlPolicy

SESSION_ENDED = "The session has ended."


class BrowserSession:
    def __init__(self, config: Config, driver: Driver | None = None) -> None:
        self.config = config
        self.policy = UrlPolicy(config.safety)
        self.redact = Redactor(config.safety.redact_patterns)
        self._driver: Driver = driver if driver is not None else PlaywrightDriver(config)
        self._started = False
        self._lost = False
        self._closed = False

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
