"""The policy and the browser must read an address the same way (review finding C1)."""

import functools
import threading
from collections.abc import Callable, Iterator
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

from bap_browser.config import Config
from bap_browser.driver import open_session
from bap_browser.tools import Toolkit

SITE = Path(__file__).parents[1] / "site"


@pytest.fixture
def asked() -> Iterator[tuple[str, list[str]]]:
    """A local site that remembers every path it was asked for."""
    paths: list[str] = []

    class Recording(SimpleHTTPRequestHandler):
        def do_GET(self) -> None:
            paths.append(self.path)
            super().do_GET()

        def log_message(self, format: str, *args: Any) -> None:
            """The site writes nothing to the test output."""

    server = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Recording, directory=str(SITE)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"127.0.0.1:{server.server_port}", paths
    server.shutdown()
    server.server_close()
    thread.join()


TRICKS = [
    "http://{host}\\@example.com/../form.html",
    "http://%31%32%37.0.0.1:{port}/form.html",
    "http://2130706433:{port}/form.html",
    "http://0x7f.1:{port}/form.html",
    "http://１２７.0.0.1:{port}/form.html",
    "http://127。0。0。1:{port}/form.html",
    "http://[::ffff:127.0.0.1]:{port}/form.html",
]


@pytest.mark.parametrize("trick", TRICKS)
async def test_no_spelling_of_a_private_address_reaches_it_in_a_cloud_deployment(
    make_config: Callable[..., Config], tmp_path: Path, asked: tuple[str, list[str]], trick: str
) -> None:
    host, paths = asked
    config = make_config(tmp_path, safety={"block_private_networks": True, "blocked_domains": ["127.0.0.1"]})
    async with open_session(config) as session:
        result = await Toolkit(session).call(
            "browser_navigate", {"url": trick.format(host=host, port=host.split(":")[1])}
        )
        assert result.is_error and "blocked" in result.text, result.text
        assert session.started_driver is None
    assert paths == []


async def test_what_is_allowed_opens_exactly_what_was_judged(
    make_config: Callable[..., Config], tmp_path: Path, asked: tuple[str, list[str]]
) -> None:
    host, paths = asked
    async with open_session(make_config(tmp_path)) as session:
        result = await Toolkit(session).call(
            "browser_navigate", {"url": f"http://{host}\\@example.com/../form.html"}
        )
    # The browser was handed the address as the policy read it: this machine, not example.com.
    assert result.text.startswith(f"Navigated to http://{host}/form.html\nPage: Sign up\n"), result.text
    assert paths[0] == "/form.html"
