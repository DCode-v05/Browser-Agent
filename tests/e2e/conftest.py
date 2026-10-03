"""Browsers shared by the end-to-end tests. One launch per test module keeps the suite fast."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable

import pytest

from bap_browser.config import Config
from bap_browser.driver.playwright_driver import PlaywrightDriver


@pytest.fixture(scope="module")
async def driver(
    make_config: Callable[..., Config], tmp_path_factory: pytest.TempPathFactory
) -> AsyncIterator[PlaywrightDriver]:
    instance = PlaywrightDriver(make_config(tmp_path_factory.mktemp("data")))
    await instance.start()
    yield instance
    await instance.close()


@pytest.fixture(scope="module")
async def impatient_driver(
    make_config: Callable[..., Config], tmp_path_factory: pytest.TempPathFactory
) -> AsyncIterator[PlaywrightDriver]:
    """A driver that gives up on an element after 600 ms, for tests of elements that never become ready."""
    config = make_config(tmp_path_factory.mktemp("data"), browser={"timeouts": {"action_ms": 600}})
    instance = PlaywrightDriver(config)
    await instance.start()
    yield instance
    await instance.close()
