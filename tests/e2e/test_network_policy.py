"""The address policy at the network (spec 8.1): what the browser sets out to load by itself is judged
too. A redirect, a link, a frame, a script and a new window cannot lead where the agent may not go."""

import functools
import threading
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest
from fakes import FakeDriver

from bap_browser.agent.models import ref_of
from bap_browser.config import Config
from bap_browser.driver import open_session
from bap_browser.driver.base import Happened
from bap_browser.service.session import ServiceSession
from bap_browser.tools import Toolkit

PAGES = {
    "/links.html": """<!doctype html><title>Links</title><h1>Links</h1>
<a href="{refused}/secret.html">To the refused site</a>
<a href="/hop?to={refused}/secret.html">Through a redirect</a>
<a href="/hop?to=/plain.html">An allowed redirect</a>
<a href="{refused}/secret.html" target="_blank">In a new tab</a>
<button onclick="location.href='{refused}/secret.html'">By script</button>""",
    "/framed.html": """<!doctype html><title>Framed</title><h1>Framed</h1>
<iframe title="Refused" src="{refused}/secret.html"></iframe>
<iframe title="Fine" src="/plain.html"></iframe>""",
    "/pictures.html": """<!doctype html><title>Pictures</title><h1>Pictures</h1>
<img src="{refused}/pixel.png" alt="from the refused site">
<script src="{refused}/script.js"></script>""",
    "/plain.html": "<!doctype html><title>Plain</title><h1>Plain page</h1>",
    "/secret.html": "<!doctype html><title>Secret</title><h1>The secret page</h1>",
}


@dataclass
class TwoSites:
    """One server under two names. The agent may use it as 127.0.0.1 and may not as localhost."""

    port: int
    asked: list[tuple[str, str]] = field(default_factory=list[tuple[str, str]])
    """Every request as it arrived: the name the site was called by, and the path."""

    @property
    def allowed(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    @property
    def refused(self) -> str:
        return f"http://localhost:{self.port}"

    def asked_of_the_refused_site(self) -> list[str]:
        return [path for host, path in self.asked if host.startswith("localhost")]


@pytest.fixture
def sites() -> Iterator[TwoSites]:
    known = TwoSites(0)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            known.asked.append((self.headers.get("Host", ""), self.path))
            address = urlsplit(self.path)
            if address.path == "/hop":
                self.send_response(302)
                self.send_header("Location", parse_qs(address.query)["to"][0])
                self.end_headers()
                return
            page = PAGES.get(address.path)
            body = (page or "").format(refused=known.refused).encode()
            self.send_response(200 if page is not None else 404)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: Any) -> None:
            """The site writes nothing to the test output."""

    server = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Handler))
    known.port = server.server_port
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield known
    server.shutdown()
    server.server_close()
    thread.join()


def guarded(make_config: Callable[..., Config], folder: Path, **safety: Any) -> Config:
    return make_config(folder, safety={"blocked_domains": ["localhost"], **safety})


async def test_a_redirect_cannot_lead_where_the_agent_may_not_go(
    make_config: Callable[..., Config], tmp_path: Path, sites: TwoSites
) -> None:
    async with open_session(guarded(make_config, tmp_path)) as session:
        tools = Toolkit(session)
        hop = await tools.call(
            "browser_navigate", {"url": f"{sites.allowed}/hop?to={sites.refused}/secret.html"}
        )
        assert hop.is_error
        assert hop.text.startswith(
            f"navigation to {sites.refused}/secret.html blocked: blocked site (safety.blocked_domains)"
        ), hop.text
        assert "secret" not in (await tools.call("browser_snapshot", {})).text.lower().replace(
            "secret.html", ""
        )
        # The request was stopped before it was made.
        assert sites.asked_of_the_refused_site() == []

        fine = await tools.call("browser_navigate", {"url": f"{sites.allowed}/hop?to=/plain.html"})
        assert fine.text.startswith(f"Navigated to {sites.allowed}/plain.html\nPage: Plain\n"), fine.text


async def test_a_link_and_a_script_cannot_lead_there_either(
    make_config: Callable[..., Config], tmp_path: Path, sites: TwoSites
) -> None:
    async with open_session(guarded(make_config, tmp_path)) as session:
        tools = Toolkit(session)
        for element in ('link "To the refused site"', 'link "Through a redirect"', 'button "By script"'):
            page = await tools.call("browser_navigate", {"url": f"{sites.allowed}/links.html"})
            clicked = await tools.call("browser_click", {"ref": ref_of(page.text, element)})
            told = clicked.text + (await tools.call("browser_wait", {"seconds": 0.3})).text
            assert (
                f"[events] navigation to {sites.refused}/secret.html blocked: blocked site "
                "(safety.blocked_domains)"
            ) in told, (element, told)
            assert "The secret page" not in (await tools.call("browser_get_text", {})).text
        assert sites.asked_of_the_refused_site() == []


async def test_a_frame_from_a_refused_site_is_left_empty(
    make_config: Callable[..., Config], tmp_path: Path, sites: TwoSites
) -> None:
    async with open_session(guarded(make_config, tmp_path)) as session:
        tools = Toolkit(session)
        page = await tools.call("browser_navigate", {"url": f"{sites.allowed}/framed.html"})
        waited = await tools.call("browser_wait", {"load_state": "networkidle"})
        read = await tools.call("browser_snapshot", {})
        # Whichever result comes next after the frame was stopped carries the news.
        told = page.text + waited.text + read.text
        assert f"[events] navigation to {sites.refused}/secret.html in a frame blocked: blocked site" in told
        assert "The secret page" not in read.text
        # The frame that may be loaded is read as ever.
        assert '- iframe "Fine"' in read.text and "Plain page" in read.text
        assert sites.asked_of_the_refused_site() == []


async def test_a_new_tab_cannot_open_there(
    make_config: Callable[..., Config], tmp_path: Path, sites: TwoSites
) -> None:
    async with open_session(guarded(make_config, tmp_path)) as session:
        tools = Toolkit(session)
        page = await tools.call("browser_navigate", {"url": f"{sites.allowed}/links.html"})
        clicked = await tools.call("browser_click", {"ref": ref_of(page.text, 'link "In a new tab"')})
        told = clicked.text + (await tools.call("browser_wait", {"seconds": 0.5})).text
        # Stopped at the network, or closed as soon as it was seen: either way the agent is told why.
        assert "blocked site" in told and f"{sites.refused}/secret.html" in told, told
        tabs = (await tools.call("browser_tabs", {"action": "list"})).text
        assert "secret" not in tabs.lower().replace("secret.html", ""), tabs
        for tab in tabs.splitlines()[1:-1]:
            assert sites.refused not in tab or "about:blank" in tab or "chrome-error" in tab, tabs


async def test_pictures_and_scripts_are_checked_only_when_the_deployment_asks(
    make_config: Callable[..., Config], tmp_path: Path, sites: TwoSites
) -> None:
    async with open_session(guarded(make_config, tmp_path)) as session:
        tools = Toolkit(session)
        await tools.call("browser_navigate", {"url": f"{sites.allowed}/pictures.html"})
        await tools.call("browser_wait", {"load_state": "networkidle"})
    # By default only documents are held up: a page with many requests loads at its own speed.
    assert sorted(sites.asked_of_the_refused_site()) == ["/pixel.png", "/script.js"]

    sites.asked.clear()
    (tmp_path / "strict").mkdir()
    strict = guarded(make_config, tmp_path / "strict", enforce_on_subresources=True)
    async with open_session(strict) as session:
        tools = Toolkit(session)
        page = await tools.call("browser_navigate", {"url": f"{sites.allowed}/pictures.html"})
        await tools.call("browser_wait", {"load_state": "networkidle"})
        assert not page.is_error
        # A picture that was stopped is not news for the agent: only a page that was.
        assert "[events]" not in page.text
    assert sites.asked_of_the_refused_site() == []


async def test_the_cloud_metadata_address_is_out_of_reach_by_any_way(
    make_config: Callable[..., Config], tmp_path: Path, sites: TwoSites
) -> None:
    async with open_session(make_config(tmp_path)) as session:
        tools = Toolkit(session)
        hop = await tools.call(
            "browser_navigate", {"url": f"{sites.allowed}/hop?to=http://169.254.169.254/latest/meta-data/"}
        )
        assert hop.is_error and "blocked: cloud metadata address" in hop.text, hop.text


async def test_a_person_watching_is_told_what_was_blocked(make_config, tmp_path: Path) -> None:
    driver = FakeDriver()
    session = ServiceSession(make_config(tmp_path), driver, clock=lambda: 1_759_480_000.0)
    await session.start()
    try:
        driver.tell(
            Happened(
                "blocked",
                "navigation to http://10.0.0.5/ blocked: private address (safety.block_private_networks)",
                {"url": "http://10.0.0.5/", "reason": "private address"},
            )
        )
        events = [item for item in session.hub.subscribe()[0] if isinstance(item, dict)]
        assert {
            "type": "navigation_blocked",
            "url": "http://10.0.0.5/",
            "reason": "private address",
            "ts": 1_759_480_000.0,
        } in events
        # The agent hears it with its next result.
        read = await session.toolkit.call("browser_snapshot", {})
        assert read.text.endswith(
            "[events] navigation to http://10.0.0.5/ blocked: private address (safety.block_private_networks)"
        )
    finally:
        await session.close()
