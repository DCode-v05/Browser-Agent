"""The agent asks a person to do a step it must not do: a sign-in, a CAPTCHA, a code (spec 8.4)."""

import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import Any

from fakes import FakeDriver

from bap_browser.config import Config
from bap_browser.driver import BrowserSession
from bap_browser.results import ToolResult
from bap_browser.service.session import ServiceSession
from bap_browser.tools import Toolkit

NOW = 1_759_480_000.0
ASK = {"reason": "Solve the CAPTCHA on the sign-in page", "kind": "verification"}


async def started(
    make_config: Callable[..., Config], folder: Path, **sections: Any
) -> tuple[ServiceSession, FakeDriver]:
    driver = FakeDriver()
    session = ServiceSession(make_config(folder, **sections), driver, clock=lambda: NOW)
    await session.start()
    return session, driver


def events(session: ServiceSession, *kinds: str) -> list[dict[str, Any]]:
    sent = [item for item in session.hub.subscribe()[0] if isinstance(item, dict)]
    return [event for event in sent if event["type"] in kinds]


async def asking(session: ServiceSession, **arguments: Any) -> asyncio.Task[ToolResult]:
    """Starts the agent's call and returns once the request is in front of the person."""
    call = asyncio.create_task(session.toolkit.call("browser_request_human", {**ASK, **arguments}))
    for _ in range(50):
        if session.control == "person_requested":
            return call
        await asyncio.sleep(0)
    raise AssertionError(f"the request was never raised: {call}")


async def test_with_nobody_watching_the_agent_is_told_so(make_config, tmp_path: Path) -> None:
    tools = Toolkit(BrowserSession(make_config(tmp_path), FakeDriver()))
    result = await tools.call("browser_request_human", ASK)
    assert result.is_error and result.text.startswith("No person can be asked in this session")


async def test_the_person_takes_over_does_the_step_and_says_done(make_config, tmp_path: Path) -> None:
    session, driver = await started(make_config, tmp_path)
    try:
        call = await asking(session)
        assert events(session, "help_requested") == [
            {
                "type": "help_requested",
                "id": "h1",
                "reason": "Solve the CAPTCHA on the sign-in page",
                "kind": "verification",
                "expires_in_s": 900,
                "ts": NOW,
            }
        ]
        await session.handle({"type": "take_over"})
        assert session.control == "person"
        # The browser is the person's while they work: what they do reaches the page.
        await session.handle({"type": "pointer", "action": "down", "x": 40, "y": 30, "button": 0})
        assert ("pointer", ("down", 40, 30, "left")) in driver.calls
        driver.url = "https://example.com/account"
        await session.handle({"type": "done"})
        result = await asyncio.wait_for(call, 1)
        assert not result.is_error
        assert result.text == (
            "done: the person did the step.\n"
            "The address was about:blank and is now https://example.com/account. "
            "Refs from before may be out of date: take a new snapshot before you act.\n"
            "[tabs] t1* https://example.com/account"
        )
        assert session.control == "agent"
        assert events(session, "help_closed") == [{"type": "help_closed", "id": "h1", "outcome": "done"}]
        # The button the person still held was let go for them.
        assert ("pointer", ("up", 40, 30, "left")) in driver.calls
    finally:
        await session.close()


async def test_the_person_can_say_they_could_not(make_config, tmp_path: Path) -> None:
    session, _ = await started(make_config, tmp_path)
    try:
        call = await asking(session)
        await session.handle({"type": "could_not"})
        result = await asyncio.wait_for(call, 1)
        assert result.text.startswith("could_not: the person could not do the step.")
        assert "The address is still about:blank." in result.text
        assert session.control == "agent"
    finally:
        await session.close()


async def test_with_no_answer_in_time_the_agent_goes_on(make_config, tmp_path: Path) -> None:
    session, _ = await started(make_config, tmp_path, control={"handoff_timeout_s": 1})
    try:
        call = await asking(session, timeout_s=0.05)
        await session.handle({"type": "take_over"})
        result = await asyncio.wait_for(call, 2)
        assert result.text.startswith("timed_out: nobody answered in time.")
        assert session.control == "agent"
        assert events(session, "help_closed")[0]["outcome"] == "timed_out"
        # A late answer changes nothing.
        await session.handle({"type": "done"})
        assert session.control == "agent"
    finally:
        await session.close()


async def test_the_wait_is_never_longer_than_the_setting(make_config, tmp_path: Path) -> None:
    session, _ = await started(make_config, tmp_path, control={"handoff_timeout_s": 7})
    try:
        call = await asking(session, timeout_s=9999)
        assert events(session, "help_requested")[0]["expires_in_s"] == 7
        await session.handle({"type": "done"})
        await asyncio.wait_for(call, 1)
    finally:
        await session.close()


async def test_stopping_the_session_ends_the_wait(make_config, tmp_path: Path) -> None:
    session, _ = await started(make_config, tmp_path)
    call = await asking(session)
    await session.handle({"type": "stop"})
    result = await asyncio.wait_for(call, 1)
    assert result.is_error and result.text.startswith("The session was ended by a person.")


async def test_a_person_cannot_simply_hand_back_an_open_request(make_config, tmp_path: Path) -> None:
    session, _ = await started(make_config, tmp_path)
    try:
        call = await asking(session)
        await session.handle({"type": "take_over"})
        await session.handle({"type": "hand_back"})
        assert session.control == "person" and not call.done()
        await session.handle({"type": "done"})
        await asyncio.wait_for(call, 1)
    finally:
        await session.close()


async def test_the_request_is_a_step_a_person_can_read_and_a_chat_message(
    make_config, tmp_path: Path
) -> None:
    driver = FakeDriver()
    session = ServiceSession(make_config(tmp_path), driver, clock=lambda: NOW, on_task=lambda task: None)
    await session.start()
    try:
        call = await asking(session)
        await session.handle({"type": "done"})
        await asyncio.wait_for(call, 1)
        steps = events(session, "step_started", "step_finished")
        assert steps[0]["label"] == 'Asking for help: "Solve the CAPTCHA on the sign-in page"'
        assert steps[1]["summary"] == 'Asked for help: "Solve the CAPTCHA on the sign-in page"'
        assert (
            events(session, "message")[0]["text"] == "I need your help: Solve the CAPTCHA on the sign-in page"
        )
    finally:
        await session.close()
