"""One browser with the policy and the redactor that apply to it."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from bap_browser.config import Config
from bap_browser.driver.base import Driver
from bap_browser.driver.playwright_driver import PlaywrightDriver
from bap_browser.policy.redaction import Redactor
from bap_browser.policy.url_policy import UrlPolicy


class BrowserSession:
    def __init__(self, config: Config, driver: Driver | None = None) -> None:
        self.config = config
        self.policy = UrlPolicy(config.safety)
        self.redact = Redactor(config.safety.redact_patterns)
        self._driver: Driver = driver if driver is not None else PlaywrightDriver(config)
        self._started = False

    @property
    def started_driver(self) -> Driver | None:
        return self._driver if self._started else None

    async def driver(self) -> Driver:
        """The driver, with its browser started on the first use."""
        if not self._started:
            await self._driver.start()
            self._started = True
        return self._driver

    async def close(self) -> None:
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
