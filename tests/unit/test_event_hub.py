"""What viewers are sent, and what a viewer that connects late is sent first (spec 4.8)."""

import asyncio
from typing import Any

import pytest

from bap_browser.service.events import EventHub, FellBehind

STARTED = {"type": "session_started", "session": "default", "ts": 1.0}


def step(n: int) -> dict[str, Any]:
    return {
        "type": "step_started",
        "step": n,
        "tool": "browser_click",
        "label": f"Clicking {n}",
        "ts": float(n),
    }


def control(state: str) -> dict[str, Any]:
    return {"type": "control_changed", "state": state, "since": 5.0}


def tabs(url: str) -> dict[str, Any]:
    return {"type": "tab_changed", "tabs": [{"id": "t1", "title": "", "url": url, "active": True}]}


async def drain(subscriber: Any, count: int) -> list[Any]:
    return [await asyncio.wait_for(subscriber.next(), 1) for _ in range(count)]


async def test_a_viewer_receives_what_is_published_in_order() -> None:
    hub = EventHub(history=10)
    replay, viewer = hub.subscribe()
    assert replay == []
    hub.publish(STARTED)
    hub.publish(step(1))
    hub.publish(step(2))
    assert await drain(viewer, 3) == [STARTED, step(1), step(2)]


async def test_a_late_viewer_is_first_sent_what_already_happened() -> None:
    hub = EventHub(history=10)
    hub.publish(STARTED)
    hub.publish(step(1))
    hub.publish_frame(b"picture-1")
    hub.publish(step(2))
    replay, viewer = hub.subscribe()
    # The history carries no pictures; the newest one comes last, so a still page is visible at once.
    assert replay == [STARTED, step(1), step(2), b"picture-1"]
    hub.publish(step(3))
    assert await drain(viewer, 1) == [step(3)]


async def test_when_history_has_overflowed_the_session_and_its_current_state_are_still_sent() -> None:
    hub = EventHub(history=3)
    hub.publish(STARTED)
    hub.publish(control("paused"))
    hub.publish(tabs("https://example.com/a"))
    for n in range(1, 6):
        hub.publish(step(n))
    replay, _ = hub.subscribe()
    assert replay == [STARTED, control("paused"), tabs("https://example.com/a"), step(3), step(4), step(5)]


async def test_state_that_is_still_in_the_history_is_not_sent_twice() -> None:
    hub = EventHub(history=3)
    hub.publish(STARTED)
    for n in range(1, 4):
        hub.publish(step(n))
    hub.publish(control("paused"))
    replay, _ = hub.subscribe()
    assert replay == [STARTED, step(2), step(3), control("paused")]


async def test_an_event_that_is_not_kept_is_delivered_but_not_replayed() -> None:
    hub = EventHub(history=10)
    hub.publish(STARTED)
    _, viewer = hub.subscribe()
    hub.publish({"type": "picture_current", "ts": 2.0}, keep=False)
    assert await drain(viewer, 1) == [{"type": "picture_current", "ts": 2.0}]
    assert hub.subscribe()[0] == [STARTED]


async def test_a_new_session_starts_a_new_history() -> None:
    hub = EventHub(history=10)
    hub.publish(STARTED)
    hub.publish(step(1))
    again = {**STARTED, "session": "second"}
    hub.publish(again)
    assert hub.subscribe()[0] == [again]


async def test_a_picture_that_was_not_sent_yet_is_replaced_by_a_newer_one() -> None:
    hub = EventHub(history=10)
    _, viewer = hub.subscribe()
    hub.publish_frame(b"picture-1")
    hub.publish_frame(b"picture-2")
    hub.publish(step(1))
    hub.publish_frame(b"picture-3")
    hub.publish_frame(b"picture-4")
    # A picture never overtakes an event: a step keeps the picture that was on screen when it finished.
    assert await drain(viewer, 3) == [b"picture-2", step(1), b"picture-4"]


async def test_a_viewer_that_stopped_listening_is_told_to_start_over() -> None:
    hub = EventHub(history=3)
    _, viewer = hub.subscribe()
    for n in range(1, 6):
        hub.publish(step(n))
    with pytest.raises(FellBehind):
        await viewer.next()


async def test_viewers_are_counted_and_one_that_left_receives_nothing_more() -> None:
    hub = EventHub(history=10)
    _, first = hub.subscribe()
    _, second = hub.subscribe()
    assert hub.viewers == 2
    hub.unsubscribe(first)
    assert hub.viewers == 1
    hub.publish(step(1))
    assert await drain(second, 1) == [step(1)]
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(first.next(), 0.05)
