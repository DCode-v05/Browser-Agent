"""Stop ends a session for good and at once, whatever else is going on (spec 4.5)."""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path
from typing import Any

import pytest
from fakes import FakeDriver

from bap_browser.config import Config
from bap_browser.service.session import ServiceSession

Started = Callable[..., Awaitable[tuple[ServiceSession, FakeDriver]]]


@pytest.fixture
async def started(make_config: Callable[..., Config], tmp_path: Path) -> AsyncIterator[Started]:
    sessions: list[ServiceSession] = []

    async def start(**sections: Any) -> tuple[ServiceSession, FakeDriver]:
        driver = FakeDriver()
        session = ServiceSession(make_config(tmp_path, **sections), driver)
        sessions.append(session)
        await session.start()
        return session, driver

    yield start
    for session in sessions:
        await session.close()


async def settle() -> None:
    for _ in range(8):
        await asyncio.sleep(0)


async def test_a_call_in_progress_cannot_start_the_browser_again_after_stop(started: Started) -> None:
    session, driver = await started()
    release = asyncio.Event()
    resolve = session.browser.policy._resolve

    async def slow_lookup(host: str) -> list[str]:
        await release.wait()
        return await resolve(host)

    # The call is held where a navigation looks its name up, before it asks for the browser.
    session.browser.policy._resolve = slow_lookup
    call = asyncio.create_task(session.toolkit.call("browser_navigate", {"url": "https://example.com/"}))
    await settle()
    await session.handle({"type": "stop"})
    release.set()
    result = await asyncio.wait_for(call, 2)
    assert driver.started == 1, "the browser was started again after the session was stopped"
    assert result.is_error and result.text == "The session has ended."
    assert not [call for call in driver.calls if call[0] == "navigate"]


async def test_stop_does_not_wait_behind_a_pause_that_waits_for_an_action(started: Started) -> None:
    session, driver = await started()
    driver.hold = asyncio.Event()
    click = asyncio.create_task(session.toolkit.call("browser_click", {"ref": "e1"}))
    await settle()
    pause = asyncio.create_task(session.handle({"type": "pause"}))
    await settle()
    assert not pause.done()
    await asyncio.wait_for(session.handle({"type": "stop"}), 1)
    assert session.control == "ended"
    driver.hold.set()
    await asyncio.wait_for(asyncio.gather(click, pause), 2)
    assert session.control == "ended"


async def test_nothing_brings_a_stopped_session_back(started: Started) -> None:
    session, driver = await started()
    await session.handle({"type": "take_over"})
    original = driver.tabs
    reading = asyncio.Event()
    go_on = asyncio.Event()

    async def slow_tabs() -> Any:
        reading.set()
        await go_on.wait()
        return await original()

    driver.tabs = slow_tabs  # type: ignore[method-assign]
    hand_back = asyncio.create_task(session.handle({"type": "hand_back"}))
    await asyncio.wait_for(reading.wait(), 1)
    driver.tabs = original  # type: ignore[method-assign]
    await session.handle({"type": "stop"})
    go_on.set()
    await asyncio.wait_for(hand_back, 2)
    assert session.control == "ended"
    for command in ("resume", "hand_back", "pause", "take_over"):
        await session.handle({"type": command})
        assert session.control == "ended"
    result = await session.toolkit.call("browser_snapshot", {})
    assert result.text == "The session was ended by a person."
    assert driver.started == 1


async def test_keys_and_buttons_a_person_still_holds_are_let_go_when_they_hand_back(started: Started) -> None:
    session, driver = await started()
    await session.handle({"type": "take_over"})
    await session.handle({"type": "key", "action": "down", "key": "Control"})
    await session.handle({"type": "key", "action": "down", "key": "Shift"})
    await session.handle({"type": "key", "action": "down", "key": "a"})
    await session.handle({"type": "key", "action": "up", "key": "a"})
    await session.handle({"type": "pointer", "action": "down", "x": 30, "y": 40, "button": 0})
    driver.calls.clear()
    await session.handle({"type": "hand_back"})
    assert sorted(driver.calls) == [
        ("key", ("up", "Control")),
        ("key", ("up", "Shift")),
        ("pointer", ("up", 30, 40, "left")),
    ]
    # A key that comes up after the hand-back is the person's own business; it does not reach the page.
    await session.handle({"type": "key", "action": "up", "key": "Control"})
    assert len(driver.calls) == 3


async def test_the_pointer_can_move_without_a_button(started: Started) -> None:
    session, driver = await started()
    await session.handle({"type": "take_over"})
    # A browser reports -1 for the button of a move.
    await session.handle({"type": "pointer", "action": "move", "x": 12, "y": 34, "button": -1})
    await session.handle({"type": "pointer", "action": "move", "x": 13, "y": 35})
    assert driver.calls == [("pointer", ("move", 12, 34, "left")), ("pointer", ("move", 13, 35, "left"))]


@pytest.mark.parametrize("button", [[0], {"a": 1}, "0", None, 0.5, 9])
async def test_a_button_that_is_no_button_is_passed_over_without_breaking_the_connection(
    started: Started, button: Any
) -> None:
    session, driver = await started()
    await session.handle({"type": "take_over"})
    await session.handle({"type": "pointer", "action": "down", "x": 1, "y": 1, "button": button})
    assert driver.calls == []
