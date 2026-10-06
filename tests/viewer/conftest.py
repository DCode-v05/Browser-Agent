"""The built viewer in a real browser. Build it first: npm --prefix viewer run build"""

from __future__ import annotations

import functools
import threading
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest
from playwright.async_api import Browser, Page, async_playwright

ROOT = Path(__file__).parents[2]
DIST = ROOT / "src" / "bap_browser" / "viewer_dist"
AXE = ROOT / "viewer" / "node_modules" / "axe-core" / "axe.min.js"
SHOTS = ROOT / ".bap-browser" / "viewer-shots"

SIZES = {"desktop": (1360, 850), "phone": (400, 820)}


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        """The viewer's file server writes nothing to the test output."""

    def do_GET(self) -> None:
        """A page opened with no token asks who signs in. This host answers as a service that
        nobody signs in to does; everything else is a file of the viewer."""
        if self.path.split("?")[0] != "/api/auth":
            return super().do_GET()
        body = b'{"accounts": false}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture(scope="session")
def viewer_url() -> Iterator[str]:
    if not (DIST / "index.html").is_file():
        pytest.fail("The viewer is not built. Run: npm --prefix viewer run build")
    if not AXE.is_file():
        pytest.fail("The accessibility scanner is not installed. Run: npm --prefix viewer install")
    server = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(QuietHandler, directory=str(DIST)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}/"
    server.shutdown()
    server.server_close()
    thread.join()


@pytest.fixture(scope="session")
async def browser() -> AsyncIterator[Browser]:
    async with async_playwright() as playwright:
        instance = await playwright.chromium.launch()
        yield instance
        await instance.close()


class View:
    """One open viewer page, with what went wrong on it."""

    def __init__(self, page: Page) -> None:
        self.page = page
        self.errors: list[str] = []
        page.on(
            "console", lambda message: self.errors.append(message.text) if message.type == "error" else None
        )
        page.on("pageerror", lambda error: self.errors.append(str(error)))

    async def sideways_overflow(self) -> int:
        return await self.page.evaluate(
            "document.documentElement.scrollWidth - document.documentElement.clientWidth"
        )

    async def settled(self) -> None:
        """Waits until everything has finished arriving. An element still fading in is paler than it will be."""
        await self.page.evaluate(
            "Promise.all(document.getAnimations().filter((a) => a.effect.getComputedTiming().iterations !== Infinity)"
            ".map((a) => a.finished))"
        )

    async def accessibility_violations(self) -> list[str]:
        """What the axe scanner finds wrong, one line per rule and element."""
        await self.settled()
        await self.page.add_script_tag(path=str(AXE))
        results = await self.page.evaluate("axe.run(document, { resultTypes: ['violations'] })")
        return [
            f"{violation['id']} ({violation['impact']}): {node['target']} {node.get('failureSummary', '').splitlines()[-1].strip()}"
            for violation in results["violations"]
            for node in violation["nodes"]
        ]

    async def shot(self, name: str) -> None:
        SHOTS.mkdir(parents=True, exist_ok=True)
        await self.settled()
        await self.page.screenshot(path=str(SHOTS / f"{name}.png"))


OpenView = Callable[..., Awaitable[View]]


@pytest.fixture
def view_of() -> Callable[[Page], View]:
    """For a page a test opened by itself: what went wrong on it, and how it looks."""
    return View


@pytest.fixture
async def open_view(browser: Browser, viewer_url: str) -> AsyncIterator[OpenView]:
    pages: list[Page] = []

    async def open_(query: str, size: str = "desktop", *, reduced_motion: bool = False) -> View:
        width, height = SIZES[size]
        page = await browser.new_page(
            viewport={"width": width, "height": height},
            reduced_motion="reduce" if reduced_motion else "no-preference",
        )
        pages.append(page)
        view = View(page)
        await page.goto(f"{viewer_url}?{query}")
        await page.wait_for_selector(".app")
        return view

    yield open_
    for page in pages:
        await page.close()
