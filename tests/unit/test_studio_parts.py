"""The parts the window of three pages is made of (spec 9.16): a session that names its backend and
can be replaced, the notice for a page that needs a person, and what a task tells the model."""

import asyncio
from pathlib import Path
from typing import Any

import pytest
from fakes import FakeDriver

from bap_browser import browser_extension
from bap_browser.agent.command import _with_where_the_browser_is  # pyright: ignore[reportPrivateUsage]
from bap_browser.agent.studio import Room
from bap_browser.service.events import FellBehind
from bap_browser.service.session import ServiceSession
from bap_browser.tools.human_checks import HUMAN_CHECK_NOTICE, SIGN_IN_NOTICE, notice_for

NOW = 1_759_480_000.0


def events(session: ServiceSession) -> list[dict[str, Any]]:
    return [item for item in session.hub.subscribe()[0] if isinstance(item, dict)]


async def test_a_session_says_which_browser_it_is_on_and_whether_it_can_be_started_again(
    make_config, tmp_path: Path
) -> None:
    asked: list[str] = []
    session = ServiceSession(
        make_config(tmp_path),
        FakeDriver(),
        name="builtin",
        backend="bundled_chromium",
        on_restart=lambda: asked.append("again"),
        clock=lambda: NOW,
    )
    plain = ServiceSession(make_config(tmp_path), FakeDriver())
    await session.start()
    await plain.start()
    try:
        started = events(session)[0]
        assert (started["session"], started["backend"], started["restartable"]) == (
            "builtin",
            "bundled_chromium",
            True,
        )
        assert events(plain)[0]["backend"] == "remote_headless" and "restartable" not in events(plain)[0]
        # A session that is running is not replaced.
        await session.handle({"type": "new_session"})
        assert asked == []
        await session.handle({"type": "stop"})
        await session.handle({"type": "new_session"})
        assert asked == ["again"]
        # One that cannot be started again ignores the request.
        await plain.close()
        await plain.handle({"type": "new_session"})
    finally:
        await session.close()
        await plain.close()


async def test_a_viewer_of_a_session_that_was_replaced_is_sent_to_connect_again(
    make_config, tmp_path: Path
) -> None:
    session = ServiceSession(make_config(tmp_path), FakeDriver())
    await session.start()
    try:
        _, viewer = session.hub.subscribe()
        waiting = asyncio.create_task(viewer.next())
        await asyncio.sleep(0)
        session.hub.start_over()
        with pytest.raises(FellBehind):
            await asyncio.wait_for(waiting, 1)
    finally:
        await session.close()


def test_what_the_window_is_told_about_a_page(tmp_path: Path) -> None:
    waiting = Room("chrome", "takeover_chrome", phase="waiting")
    assert waiting.described(tmp_path) == {
        "id": "chrome",
        "backend": "takeover_chrome",
        "state": "waiting",
        "attention": False,
        "working": False,
        "extension": str(tmp_path),
    }
    failed = Room(
        "cloud", "remote_headless", phase="failed", note="The browser could not be started: no such file"
    )
    assert failed.described(tmp_path)["note"].startswith("The browser could not be started")
    assert "extension" not in failed.described(tmp_path)


async def test_a_page_whose_agent_waits_for_the_person_says_so(make_config, tmp_path: Path) -> None:
    session = ServiceSession(make_config(tmp_path), FakeDriver(), name="cloud")
    await session.start()
    room = Room("cloud", "remote_headless", session=session)
    try:
        assert (room.described(tmp_path)["state"], room.described(tmp_path)["attention"]) == ("agent", False)
        asking = asyncio.create_task(session.toolkit.call("browser_request_human", {"reason": "Sign in"}))
        for _ in range(50):
            if session.control == "person_requested":
                break
            await asyncio.sleep(0)
        assert room.described(tmp_path)["attention"] is True
        await session.handle({"type": "could_not"})
        await asyncio.wait_for(asking, 1)
        assert room.described(tmp_path)["attention"] is False
    finally:
        await session.close()


SIGN_IN_PAGE = """Page: Sign in to Northfield
URL: https://example.com/members
Scroll: 0px of 800px (viewport 800px)
- heading "Sign in to your account" [ref=e1] [level=1]
- textbox "Email" [ref=e2] type=email
- textbox "Password" [ref=e3] type=password
- checkbox "I am not a robot" [ref=e4] [unchecked]
- button "Sign in" [ref=e5]"""

SIGN_UP_PAGE = """Page: Sign up
URL: https://example.com/login-help
- heading "Create your account" [ref=e1] [level=1]
- textbox "Password" [ref=e3] type=password
- button "Create account" [ref=e5]
- link "Sign in" [ref=e6]"""

CAPTCHA_PAGE = """Page: One more step
- iframe "reCAPTCHA" [ref=e1]
  - checkbox "I'm not a robot" [ref=f1e2] [unchecked]
- button "Continue" [ref=e3]"""


@pytest.mark.parametrize(
    ("page", "notice"),
    [
        (SIGN_IN_PAGE, SIGN_IN_NOTICE),
        (CAPTCHA_PAGE, HUMAN_CHECK_NOTICE),
        ('Page: Shop\n- heading "Verify you are human" [ref=e1]', HUMAN_CHECK_NOTICE),
        # A password to choose is not a sign-in, and a link or an address that says "login" is not a page that asks for one.
        (SIGN_UP_PAGE, ""),
        ('Page: News\n- link "Log in" [ref=e1]\n- button "Search" [ref=e2]', ""),
        ('Page: Fake\n- button "Go" [ref=e1]', ""),
    ],
)
def test_a_page_that_needs_a_person_is_noticed(page: str, notice: str) -> None:
    assert notice_for(page) == notice


async def test_the_result_that_shows_such_a_page_says_what_to_do(make_config, tmp_path: Path) -> None:
    driver = FakeDriver()

    async def snapshot(**_: Any) -> str:
        return SIGN_IN_PAGE

    driver.snapshot = snapshot  # type: ignore[method-assign]
    session = ServiceSession(make_config(tmp_path), driver)
    await session.start()
    try:
        read = await session.toolkit.call("browser_snapshot", {})
        assert read.text.startswith(f"{SIGN_IN_PAGE}\n{SIGN_IN_NOTICE}\n[tabs] ")
        assert 'call browser_request_human with kind "login"' in read.text
    finally:
        await session.close()


async def test_a_task_tells_the_model_where_the_browser_is(make_config, tmp_path: Path) -> None:
    driver = FakeDriver()
    session = ServiceSession(make_config(tmp_path), driver)
    await session.start()
    try:
        # A browser that is nowhere yet adds nothing.
        assert await _with_where_the_browser_is("Find the price", session) == "Find the price"
        driver.url = "https://example.com/shop"
        assert await _with_where_the_browser_is("Find the price", session) == (
            "Find the price\n\n[The browser is on https://example.com/shop now. "
            "Read the page with browser_snapshot before you act.]"
        )
    finally:
        await session.close()


def test_the_side_panel_is_told_which_page_of_the_window_is_its_own(tmp_path: Path) -> None:
    import json

    browser_extension.announce(
        tmp_path, "http://127.0.0.1:8765/?session=chrome#token=abc", bridge="ws://x/bridge"
    )
    told = json.loads((tmp_path / browser_extension.SESSION_FILE).read_text(encoding="utf-8"))
    assert told == {
        "viewer": "http://127.0.0.1:8765/?session=chrome&embed=1#token=abc",
        "bridge": "ws://x/bridge",
    }
    browser_extension.announce(tmp_path, "http://127.0.0.1:8765/#token=abc")
    told = json.loads((tmp_path / browser_extension.SESSION_FILE).read_text(encoding="utf-8"))
    assert told == {"viewer": "http://127.0.0.1:8765/?embed=1#token=abc"}
