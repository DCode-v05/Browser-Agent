"""One session as the service runs it: what viewers are told, and who is driving (spec 4.5, 4.8)."""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path
from typing import Any

import pytest
from fakes import FakeDriver

from bap_browser.config import Config
from bap_browser.service.session import ServiceSession

NOW = 1_759_480_000.0
PUBLIC = "https://93.184.216.34"
# What a session says of itself when it starts: what it is, how it asks, and its tabs.
STARTED = 3


Started = Callable[..., Awaitable[tuple[ServiceSession, FakeDriver]]]


@pytest.fixture
async def started() -> AsyncIterator[Started]:
    """Starts a session on a fake browser, and closes every one it started when the test is over."""
    sessions: list[ServiceSession] = []

    async def start(
        make_config: Callable[..., Config], folder: Path, **sections: Any
    ) -> tuple[ServiceSession, FakeDriver]:
        driver = FakeDriver()
        session = ServiceSession(
            make_config(folder, **sections), driver, agent="Test agent", clock=lambda: NOW
        )
        sessions.append(session)
        await session.start()
        return session, driver

    yield start
    for session in sessions:
        await session.close()


def sent(session: ServiceSession) -> list[dict[str, Any]]:
    """Every event so far, as a viewer that connects now would be sent them."""
    return [item for item in session.hub.subscribe()[0] if isinstance(item, dict)]


def kinds(session: ServiceSession) -> list[str]:
    return [
        f"control:{event['state']}" if event["type"] == "control_changed" else event["type"]
        for event in sent(session)
    ]


async def settle() -> None:
    """Lets every task that can run, run."""
    for _ in range(5):
        await asyncio.sleep(0)


async def test_a_session_starts_its_browser_and_says_what_it_is(
    make_config, tmp_path: Path, started: Started
) -> None:
    session, driver = await started(make_config, tmp_path)
    assert driver.started == 1
    assert sent(session) == [
        {
            "type": "session_started",
            "session": "default",
            "agent": "Test agent",
            "backend": "remote_headless",
            "browser": "Fake 1.0",
            "viewport": {"width": 1280, "height": 800},
            "ts": NOW,
        },
        # How the session asks before it acts (spec 18.10).
        {"type": "auto_changed", "mode": "risky", "state": "off", "ts": NOW},
        {
            "type": "tab_changed",
            "tabs": [{"id": "t1", "title": "Fake", "url": "about:blank", "active": True}],
        },
    ]
    assert session.control == "agent"


async def test_each_call_reaches_viewers_as_a_step_and_a_changed_tab(
    make_config, tmp_path: Path, started: Started
) -> None:
    session, _ = await started(make_config, tmp_path)
    opened = await session.toolkit.call("browser_navigate", {"url": f"{PUBLIC}/"})
    await session.toolkit.call("browser_click", {"ref": "e1"})
    events = sent(session)[STARTED:]
    assert events[0] == {
        "type": "step_started",
        "step": 1,
        "tool": "browser_navigate",
        "label": "Opening 93.184.216.34",
        "ts": NOW,
    }
    assert events[1] == {
        "type": "step_finished",
        "step": 1,
        "ok": True,
        "ms": events[1]["ms"],
        "chars": len(opened.text),
        "summary": "Opened 93.184.216.34",
        "url": f"{PUBLIC}/",
    }
    assert isinstance(events[1]["ms"], int) and events[1]["ms"] >= 0
    assert events[2] == {
        "type": "tab_changed",
        "tabs": [{"id": "t1", "title": "Fake", "url": f"{PUBLIC}/", "active": True}],
    }
    assert events[3]["label"] == 'Clicking "Go"'
    assert events[3]["target"] == {"x": 10, "y": 20, "w": 80, "h": 24}
    assert events[4]["summary"] == 'Clicked "Go" (button)'
    # The tabs did not change, so they are not sent again.
    assert [event["type"] for event in events] == [
        "step_started",
        "step_finished",
        "tab_changed",
        "step_started",
        "step_finished",
    ]


async def test_a_blocked_address_is_shown_as_blocked(make_config, tmp_path: Path, started: Started) -> None:
    session, _ = await started(make_config, tmp_path, safety={"block_private_networks": True})
    await session.toolkit.call("browser_navigate", {"url": "http://10.0.0.5/admin"})
    assert sent(session)[STARTED + 1] == {
        "type": "navigation_blocked",
        "url": "http://10.0.0.5/admin",
        "reason": "private address",
        "ts": NOW,
    }
    assert kinds(session)[STARTED:] == ["step_started", "navigation_blocked", "step_finished"]


async def test_what_viewers_are_told_is_redacted(make_config, tmp_path: Path, started: Started) -> None:
    session, driver = await started(make_config, tmp_path, safety={"redact_patterns": ["tok-[a-z]+"]})
    driver.title = "Order tok-abc"
    await session.toolkit.call("browser_navigate", {"url": f"{PUBLIC}/?key=tok-abc"})
    assert "tok-abc" not in repr(sent(session))
    assert sent(session)[-1]["tabs"][0] == {
        "id": "t1",
        "title": "Order [REDACTED]",
        "url": f"{PUBLIC}/?key=[REDACTED]",
        "active": True,
    }


async def test_a_paused_session_holds_the_agents_call_until_it_is_resumed(
    make_config, tmp_path: Path, started: Started
) -> None:
    session, driver = await started(make_config, tmp_path)
    await session.handle({"type": "pause"})
    assert session.control == "paused"
    call = asyncio.create_task(session.toolkit.call("browser_snapshot", {}))
    await settle()
    assert not call.done()
    assert driver.calls == []
    await session.handle({"type": "resume"})
    result = await asyncio.wait_for(call, 1)
    assert not result.is_error and result.text.startswith("Page: Fake")
    assert kinds(session)[STARTED:] == ["control:paused", "control:agent", "step_started", "step_finished"]
    assert sent(session)[STARTED] == {"type": "control_changed", "state": "paused", "since": NOW}


async def test_a_held_call_gives_up_politely_and_nothing_was_done(
    make_config, tmp_path: Path, started: Started
) -> None:
    session, driver = await started(make_config, tmp_path, control={"hold_timeout_s": 0})
    await session.handle({"type": "pause"})
    paused = await session.toolkit.call("browser_click", {"ref": "e1"})
    assert not paused.is_error
    assert paused.text == "A person paused the session, so nothing was done. Call again to keep waiting."
    await session.handle({"type": "take_over"})
    driven = await session.toolkit.call("browser_snapshot", {})
    assert not driven.is_error
    assert driven.text == (
        "A person is in control of the browser, so nothing was done. Call again to keep waiting."
    )
    assert driver.calls == []
    assert "step_started" not in kinds(session)


async def test_taking_over_waits_for_the_action_in_progress(
    make_config, tmp_path: Path, started: Started
) -> None:
    session, driver = await started(make_config, tmp_path)
    driver.hold = asyncio.Event()
    click = asyncio.create_task(session.toolkit.call("browser_click", {"ref": "e1"}))
    await settle()
    take_over = asyncio.create_task(session.handle({"type": "take_over"}))
    await settle()
    assert session.control == "agent" and not take_over.done()
    driver.hold.set()
    await asyncio.wait_for(asyncio.gather(click, take_over), 1)
    assert session.control == "person"
    assert kinds(session)[STARTED:] == ["step_started", "step_finished", "control:person"]


async def test_after_a_hand_back_the_next_result_says_what_changed_once(
    make_config, tmp_path: Path, started: Started
) -> None:
    session, driver = await started(make_config, tmp_path)
    await session.toolkit.call("browser_navigate", {"url": f"{PUBLIC}/signup"})
    await session.handle({"type": "take_over"})
    waiting = asyncio.create_task(session.toolkit.call("browser_snapshot", {}))
    await settle()
    assert not waiting.done()
    driver.url = f"{PUBLIC}/verify"
    await session.handle({"type": "hand_back"})
    first = await asyncio.wait_for(waiting, 1)
    assert first.text.startswith(
        "[A person was in control of the browser and has handed it back. "
        f"The address was {PUBLIC}/signup and is now {PUBLIC}/verify. "
        "Refs from before may be out of date: take a new snapshot before you act.]\nPage: Fake"
    )
    second = await session.toolkit.call("browser_snapshot", {})
    assert second.text.startswith("Page: Fake")
    # Viewers saw the address change as soon as the person handed back.
    assert kinds(session)[-7:] == [
        "control:person",
        "tab_changed",
        "control:agent",
        "step_started",
        "step_finished",
        "step_started",
        "step_finished",
    ]


async def test_a_hand_back_with_nothing_changed_says_so(
    make_config, tmp_path: Path, started: Started
) -> None:
    session, _ = await started(make_config, tmp_path)
    await session.toolkit.call("browser_navigate", {"url": f"{PUBLIC}/signup"})
    await session.handle({"type": "take_over"})
    await session.handle({"type": "hand_back"})
    result = await session.toolkit.call("browser_snapshot", {})
    assert result.text.startswith(
        "[A person was in control of the browser and has handed it back. "
        f"The address is still {PUBLIC}/signup. "
        "Refs from before may be out of date: take a new snapshot before you act.]\n"
    )


async def test_resuming_after_a_pause_adds_no_note(make_config, tmp_path: Path, started: Started) -> None:
    session, _ = await started(make_config, tmp_path)
    await session.handle({"type": "pause"})
    await session.handle({"type": "resume"})
    assert (await session.toolkit.call("browser_snapshot", {})).text.startswith("Page: Fake")


async def test_stop_ends_the_session_at_once_and_every_later_call_is_told(
    make_config, tmp_path: Path, started: Started
) -> None:
    session, driver = await started(make_config, tmp_path)
    await session.handle({"type": "pause"})
    held = asyncio.create_task(session.toolkit.call("browser_snapshot", {}))
    await settle()
    await session.handle({"type": "stop"})
    assert session.control == "ended"
    assert ("close", None) in driver.calls
    for result in (
        await asyncio.wait_for(held, 1),
        await session.toolkit.call("browser_click", {"ref": "e1"}),
    ):
        assert not result.is_error
        assert result.text == "The session was ended by a person."
    assert sent(session)[-1] == {"type": "session_ended", "reason": "person", "ts": NOW}
    assert [call for call in driver.calls if call[0] != "close"] == []


async def test_a_session_the_agent_finished_says_so_and_closes_once(
    make_config, tmp_path: Path, started: Started
) -> None:
    session, driver = await started(make_config, tmp_path)
    await session.close("agent")
    await session.close("agent")
    assert kinds(session).count("session_ended") == 1
    assert sent(session)[-1] == {"type": "session_ended", "reason": "agent", "ts": NOW}
    assert driver.calls.count(("close", None)) == 1
    assert (await session.toolkit.call("browser_snapshot", {})).text == "The session has ended."


async def test_commands_that_do_not_apply_or_make_no_sense_change_nothing(
    make_config, tmp_path: Path, started: Started
) -> None:
    session, _ = await started(make_config, tmp_path)
    before = sent(session)
    for command in (
        {"type": "resume"},
        {"type": "hand_back"},
        {"type": "fly"},
        {"type": 7},
        {},
        {"type": ["pause"]},
        "pause",
        None,
    ):
        await session.handle(command)  # type: ignore[arg-type]
    assert session.control == "agent"
    assert sent(session) == before
    await session.handle({"type": "pause"})
    await session.handle({"type": "pause"})
    assert kinds(session)[STARTED:] == ["control:paused"]


async def test_a_person_can_take_over_from_a_pause_and_pause_is_not_a_way_out_of_it(
    make_config, tmp_path: Path, started: Started
) -> None:
    session, _ = await started(make_config, tmp_path)
    await session.handle({"type": "pause"})
    await session.handle({"type": "take_over"})
    assert session.control == "person"
    await session.handle({"type": "pause"})
    await session.handle({"type": "resume"})
    assert session.control == "person"
    await session.handle({"type": "hand_back"})
    assert session.control == "agent"


async def test_pictures_from_the_browser_reach_viewers_at_the_level_the_configuration_names(
    make_config, tmp_path: Path, started: Started
) -> None:
    session, driver = await started(make_config, tmp_path, viewer={"quality": "data_saver"})
    assert driver.level is not None and (driver.level.max_fps, driver.level.max_width) == (8, 800)
    _, viewer = session.hub.subscribe()
    driver.on_frame(b"picture-1")
    assert await asyncio.wait_for(viewer.next(), 1) == b"picture-1"
    assert session.hub.subscribe()[0][-1] == b"picture-1"


async def test_a_still_page_is_confirmed_as_current_and_a_moving_one_is_not(
    make_config, tmp_path: Path, started: Started
) -> None:
    session, driver = await started(make_config, tmp_path, viewer={"picture_heartbeat_s": 1})
    _, viewer = session.hub.subscribe()
    driver.on_frame(b"picture-1")
    assert await asyncio.wait_for(viewer.next(), 1) == b"picture-1"
    assert await asyncio.wait_for(viewer.next(), 3) == {"type": "picture_current", "ts": NOW}
    # It means nothing to a viewer that connects later, so it is not kept.
    assert "picture_current" not in kinds(session)


async def test_an_address_that_changes_between_steps_reaches_viewers(
    make_config, tmp_path: Path, started: Started
) -> None:
    session, driver = await started(make_config, tmp_path, viewer={"picture_heartbeat_s": 1})
    _, viewer = session.hub.subscribe()
    driver.url = f"{PUBLIC}/moved-by-the-page"
    event = await asyncio.wait_for(viewer.next(), 3)
    assert event == {
        "type": "tab_changed",
        "tabs": [{"id": "t1", "title": "Fake", "url": f"{PUBLIC}/moved-by-the-page", "active": True}],
    }


async def test_a_persons_mouse_and_keys_reach_the_page_only_while_they_drive(
    make_config, tmp_path: Path, started: Started
) -> None:
    session, driver = await started(make_config, tmp_path)
    click = {"type": "pointer", "action": "down", "x": 100, "y": 50.5, "button": 0}
    await session.handle(click)
    assert driver.calls == []
    await session.handle({"type": "take_over"})
    await session.handle(click)
    await session.handle({"type": "pointer", "action": "up", "x": 100, "y": 50.5, "button": 2})
    await session.handle({"type": "key", "action": "down", "key": "a", "code": "KeyA"})
    await session.handle({"type": "wheel", "x": 10, "y": 20, "dx": 0, "dy": 120})
    assert driver.calls == [
        ("pointer", ("down", 100, 50.5, "left")),
        ("pointer", ("up", 100, 50.5, "right")),
        ("key", ("down", "a")),
        ("wheel", (10, 20, 0, 120)),
    ]
    await session.handle({"type": "hand_back"})
    # What they still held down was let go for them. Nothing they do after that reaches the page.
    handed_back = list(driver.calls)
    await session.handle(click)
    assert driver.calls == handed_back


async def test_what_a_person_types_is_neither_logged_nor_told_to_viewers(
    make_config, tmp_path: Path, started: Started
) -> None:
    session, _ = await started(make_config, tmp_path)
    await session.handle({"type": "take_over"})
    for key in "hunter2":
        await session.handle({"type": "key", "action": "down", "key": key, "code": ""})
    assert "hunter2" not in repr(sent(session))
    assert not (tmp_path / "events.jsonl").exists()


@pytest.mark.parametrize(
    "command",
    [
        {"type": "pointer", "action": "down", "x": float("nan"), "y": 5, "button": 0},
        {"type": "pointer", "action": "down", "x": -1, "y": 5, "button": 0},
        {"type": "pointer", "action": "down", "x": 5, "y": 801, "button": 0},
        {"type": "pointer", "action": "down", "x": "5", "y": 5, "button": 0},
        {"type": "pointer", "action": "down", "x": True, "y": 5, "button": 0},
        {"type": "pointer", "action": "drag", "x": 5, "y": 5, "button": 0},
        {"type": "pointer", "action": "down", "x": 5, "y": 5, "button": 7},
        {"type": "pointer", "action": "down", "x": 5, "y": 5},
        {"type": "key", "action": "down", "key": ""},
        {"type": "key", "action": "down", "key": "x" * 200},
        {"type": "key", "action": "down", "key": 5},
        {"type": "key", "action": "hold", "key": "a"},
        {"type": "wheel", "x": 5, "y": 5, "dx": float("inf"), "dy": 0},
        {"type": "wheel", "x": 5, "y": 5, "dx": 0},
    ],
)
async def test_input_that_makes_no_sense_never_reaches_the_page(
    make_config, tmp_path: Path, started: Started, command: dict[str, Any]
) -> None:
    session, driver = await started(make_config, tmp_path)
    await session.handle({"type": "take_over"})
    await session.handle(command)
    assert driver.calls == []


async def test_a_wheel_turn_larger_than_the_page_is_cut_to_one_screen(
    make_config, tmp_path: Path, started: Started
) -> None:
    session, driver = await started(make_config, tmp_path)
    await session.handle({"type": "take_over"})
    await session.handle({"type": "wheel", "x": 5, "y": 5, "dx": -99999, "dy": 99999})
    assert driver.calls == [("wheel", (5, 5, -1280, 800))]


@pytest.mark.parametrize(("headless", "told"), [(True, None), (False, True)])
async def test_viewers_are_told_when_the_browser_is_a_window_on_the_persons_own_screen(
    make_config, tmp_path: Path, headless: bool, told: bool | None
) -> None:
    session = ServiceSession(make_config(tmp_path, browser={"headless": headless}), FakeDriver())
    await session.start()
    try:
        first = sent(session)[0]
        assert first["type"] == "session_started"
        assert first.get("on_screen") is told
    finally:
        await session.close()


@pytest.mark.parametrize(
    ("backend", "attached", "own"),
    [
        ("remote_headless", False, False),
        ("takeover_chrome", False, True),
        ("bundled_chromium", False, True),
        # Nobody said which backend it is: a browser that was attached to and not launched is the
        # desktop app's or a person's own Chrome, so a file that arrives there is asked about.
        (None, True, True),
        (None, False, False),
        ("remote_headless", True, False),
    ],
)
def test_a_session_knows_when_its_browser_is_on_the_persons_own_machine(
    make_config, tmp_path: Path, backend: str | None, attached: bool, own: bool
) -> None:
    browser = {"cdp_url": "http://127.0.0.1:9222"} if attached else {}
    session = ServiceSession(make_config(tmp_path, browser=browser), FakeDriver(), backend=backend)
    assert session.browser.own_machine is own
