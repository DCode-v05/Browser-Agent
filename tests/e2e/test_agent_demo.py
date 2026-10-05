"""The demonstration: the reference loop signs up on the demo site in a real browser, with no model key."""

import functools
import json
import threading
from collections.abc import Callable, Iterator
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path
from typing import Any

import pytest

from bap_browser.agent.demo import TASK, demo_script
from bap_browser.agent.loop import run_agent
from bap_browser.agent.models import ref_of
from bap_browser.config import Config
from bap_browser.driver import open_session
from bap_browser.service.session import ServiceSession
from bap_browser.tools import Toolkit


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        """The demo site writes nothing to the test output."""


@pytest.fixture
def demo_site() -> Iterator[str]:
    folder = str(files("bap_browser") / "demo_site")
    server = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(QuietHandler, directory=folder))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()
    thread.join()


async def test_the_scripted_agent_signs_up_and_a_viewer_is_told_every_step(
    make_config: Callable[..., Config], tmp_path: Path, demo_site: str
) -> None:
    config = make_config(tmp_path, agent={"provider": "scripted"})
    session = ServiceSession(config, agent="Reference agent")
    await session.start()
    try:
        answer = await run_agent(
            TASK,
            session.toolkit,
            demo_script(demo_site),
            config.agent,
            ended=lambda: session.control == "ended",
        )
    finally:
        await session.close("agent")

    assert answer == 'The account was created. The page now shows "Welcome, Ada" with 3 open invoices.'
    events = [item for item in session.hub.subscribe()[0] if isinstance(item, dict)]
    assert events[0]["agent"] == "Reference agent" and events[0]["browser"].startswith("Chromium ")
    host = demo_site.removeprefix("http://")
    assert [event["summary"] for event in events if event["type"] == "step_finished"] == [
        f"Opened {host}/signup.html",
        'Typed 12 characters into "Full name"',
        'Typed 15 characters into "Email"',
        'Typed a password into "Password"',
        'Clicked "I accept the terms" (checkbox)',
        'Clicked "Create account" (button)',
        "Read the page",
        'Typed 6 characters into "Verification code"',
        'Clicked "Continue" (button)',
        "Read the page",
    ]
    assert all(event["ok"] for event in events if event["type"] == "step_finished")
    # Every click and every typing step tells the viewer where on the page it happened.
    targets = [event.get("target") for event in events if event["type"] == "step_started"]
    assert sum(target is not None for target in targets) == 7
    assert events[-1] == {"type": "session_ended", "reason": "agent", "ts": events[-1]["ts"]}

    told = json.dumps(events)
    log = (tmp_path / "events.jsonl").read_text(encoding="utf-8")
    for typed in ("Ada Lovelace", "ada@example.com", "correct horse battery", "424242"):
        assert typed not in told, f"{typed!r} was sent to viewers"
        assert typed not in log, f"{typed!r} was written to the log"


async def test_the_check_in_pages_can_be_done_with_the_tools(
    make_config: Callable[..., Config], tmp_path: Path, demo_site: str
) -> None:
    async with open_session(make_config(tmp_path)) as session:
        tools = Toolkit(session)

        async def call(tool: str, **arguments: Any) -> str:
            result = await tools.call(tool, arguments)
            assert not result.is_error, result.text
            return result.text

        page = await call("browser_navigate", url=f"{demo_site}/checkin.html")
        # A booking that does not exist is refused in words, and the page stays.
        await call("browser_type", ref=ref_of(page, 'textbox "Booking reference"'), text="XX0000")
        await call("browser_type", ref=ref_of(page, 'textbox "Last name"'), text="Nobody")
        await call("browser_click", ref=ref_of(page, 'button "Find booking"'))
        assert "We could not find that booking" in await call("browser_get_text")

        await call("browser_type", ref=ref_of(page, 'textbox "Booking reference"'), text="sk4821")
        await call("browser_type", ref=ref_of(page, 'textbox "Last name"'), text="Lovelace")
        found = await call("browser_click", ref=ref_of(page, 'button "Find booking"'))
        assert "checkin-seat.html" in found

        page = await call("browser_snapshot")
        assert 'radio "15A, window (taken)"' in page and "[disabled]" in page
        # Checking in without a seat says what is missing.
        await call("browser_click", ref=ref_of(page, 'button "Check in"'))
        assert "Choose a seat before you check in." in await call("browser_get_text")

        await call("browser_set_checked", ref=ref_of(page, 'radio "14A, window"'), checked=True)
        await call("browser_select_option", ref=ref_of(page, 'combobox "Meal"'), values=["Vegetarian"])
        await call(
            "browser_set_checked",
            ref=ref_of(page, 'checkbox "I am not carrying any dangerous goods"'),
            checked=True,
        )
        done = await call("browser_click", ref=ref_of(page, 'button "Check in"'))
        assert "checkin-pass.html" in done

        boarding_pass = await call("browser_get_text")
        for said in ("You are checked in", "14A", "08:55", "B7", "Vegetarian", "SK4821"):
            assert said in boarding_pass, said
