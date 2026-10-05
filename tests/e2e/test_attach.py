"""The driver attaches to a browser that is already running, and leaves it running (spec 5.2)."""

import socket
from collections.abc import AsyncIterator, Callable
from pathlib import Path

import pytest
from playwright.async_api import Browser, async_playwright

from bap_browser.config import Config
from bap_browser.driver import open_session
from bap_browser.service.session import ServiceSession
from bap_browser.tools import Toolkit


def free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


@pytest.fixture
async def running() -> AsyncIterator[tuple[Browser, str]]:
    """A browser someone else started, and the address at which it can be attached to."""
    port = free_port()
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(args=[f"--remote-debugging-port={port}"])
        yield browser, f"http://127.0.0.1:{port}"
        await browser.close()


async def test_it_drives_a_page_of_the_running_browser_and_leaves_the_browser_running(
    running: tuple[Browser, str], make_config: Callable[..., Config], tmp_path: Path, site: str
) -> None:
    browser, address = running
    theirs = await (await browser.new_context()).new_page()
    await theirs.goto(f"{site}/form.html")
    async with open_session(make_config(tmp_path, browser={"cdp_url": address})) as session:
        tools = Toolkit(session)
        page = await tools.call("browser_snapshot", {})
        assert not page.is_error and "form.html" in page.text, "it reads the page that was already open"
        moved = await tools.call("browser_navigate", {"url": f"{site}/slow_handler.html"})
        assert not moved.is_error and 'button "Think"' in moved.text
        assert (await session.driver()).description().startswith("Chromium ")
    # The page the person had is where the agent left it, and their browser is still there.
    assert browser.is_connected()
    assert theirs.url.endswith("/slow_handler.html")


async def test_it_takes_the_page_whose_address_holds_the_mark(
    running: tuple[Browser, str], make_config: Callable[..., Config], tmp_path: Path, site: str
) -> None:
    browser, address = running
    context = await browser.new_context()
    other = await context.new_page()
    await other.goto(f"{site}/form.html")
    meant = await context.new_page()
    await meant.goto(f"{site}/slow_handler.html#for-the-agent")
    attach = {"cdp_url": address, "cdp_target": "#for-the-agent"}
    async with open_session(make_config(tmp_path, browser=attach)) as session:
        page = await Toolkit(session).call("browser_snapshot", {})
        assert 'button "Think"' in page.text

    missing = {"cdp_url": address, "cdp_target": "#nobody"}
    async with open_session(make_config(tmp_path, browser=missing)) as session:
        result = await Toolkit(session).call("browser_snapshot", {})
        assert result.is_error
        assert result.text.startswith(
            "The browser could not be started: no open page has #nobody in its address"
        )


async def test_a_browser_that_is_not_there_is_said_so(
    make_config: Callable[..., Config], tmp_path: Path
) -> None:
    config = make_config(tmp_path, browser={"cdp_url": f"http://127.0.0.1:{free_port()}"})
    async with open_session(config) as session:
        result = await Toolkit(session).call("browser_snapshot", {})
    assert result.is_error and result.text.startswith("The browser could not be started: ")


async def test_viewers_are_told_that_such_a_browser_is_on_the_persons_screen(
    running: tuple[Browser, str], make_config: Callable[..., Config], tmp_path: Path
) -> None:
    browser, address = running
    await (await browser.new_context()).new_page()
    session = ServiceSession(make_config(tmp_path, browser={"cdp_url": address}))
    await session.start()
    try:
        assert session.hub.subscribe()[0][0]["on_screen"] is True  # type: ignore[index]
    finally:
        await session.close()
    assert browser.is_connected()
