"""The limits of a task, and steps that go round in circles (spec 18.8)."""

from typing import Any

import pytest

from bap_browser.config import Limits as LimitSettings
from bap_browser.safeguards.limits import NOTHING_CHANGED, TOO_MANY_CALLS, Limits, Reached, same_step
from bap_browser.safeguards.model import Spend


class Waits:
    """Stands in for the clock: a wait is written down and takes no time."""

    def __init__(self) -> None:
        self.taken: list[float] = []
        self.now = 5000.0

    async def sleep(self, seconds: float) -> None:
        self.taken.append(seconds)
        self.now += seconds

    def clock(self) -> float:
        return self.now


def limits(waits: Waits | None = None, spend: Spend | None = None, **settings: Any) -> Limits:
    waits = waits or Waits()
    chosen = LimitSettings(**settings)
    return Limits(lambda: chosen, spend, clock=waits.clock, sleep=waits.sleep)


async def test_a_session_with_no_task_stops_at_its_limit_of_steps() -> None:
    counted = limits(max_calls=3)
    assert [await counted.admit() for _ in range(3)] == [None, None, None]
    refused = await counted.admit()
    assert refused == Reached(
        "calls",
        3,
        "This session has reached its limit of 3 steps. Stop, and tell the person what is done and what is left.",
    )
    assert await counted.admit() == refused


async def test_the_count_begins_again_with_each_task() -> None:
    counted = limits(max_calls=2)
    for _ in range(2):
        counted.begin_task()
        assert [await counted.admit() for _ in range(2)] == [None, None]
        refused = await counted.admit()
        assert isinstance(refused, Reached) and refused.text.startswith(
            "This task has reached its limit of 2 steps."
        )


async def test_allow_more_adds_steps_and_minutes() -> None:
    waits = Waits()
    counted = limits(waits, max_calls=1, extend_calls=2, max_task_minutes=10, extend_minutes=5)
    counted.begin_task()
    assert await counted.admit() is None
    assert isinstance(await counted.admit(), Reached)
    counted.extend()
    assert [await counted.admit() for _ in range(2)] == [None, None]
    assert isinstance(await counted.admit(), Reached)
    counted.extend()
    waits.now += 14 * 60
    assert await counted.admit() is None
    waits.now += 6 * 60
    late = await counted.admit()
    assert isinstance(late, Reached) and (late.kind, late.limit) == ("minutes", 20)
    assert late.text.startswith("This task has reached its limit of 20 minutes.")


async def test_the_minutes_are_a_tasks_and_a_session_with_no_task_has_none() -> None:
    waits = Waits()
    counted = limits(waits, max_task_minutes=1)
    waits.now += 3600
    assert await counted.admit() is None
    counted.begin_task()
    waits.now += 61
    refused = await counted.admit()
    assert isinstance(refused, Reached) and refused.kind == "minutes"
    counted.end_task()
    assert await counted.admit() is None


async def test_zero_means_no_limit() -> None:
    waits = Waits()
    free = limits(waits, max_calls=0, max_task_minutes=0, max_calls_per_minute=0)
    free.begin_task()
    waits.now += 10**6
    assert {await free.admit() for _ in range(1000)} == {None}
    assert waits.taken == []


async def test_what_the_engines_own_model_calls_cost_has_a_limit() -> None:
    spend = Spend()
    counted = limits(spend=spend, max_model_spend_usd=0.5)
    assert await counted.admit() is None
    spend.add(1_000_000, 0, 0.5, 0)
    refused = await counted.admit()
    assert isinstance(refused, Reached) and (refused.kind, refused.limit) == ("spend", 0.5)
    assert refused.text.startswith("This session has reached its limit of $0.50 for the model calls")
    counted.extend()
    assert isinstance(await counted.admit(), Reached), "more steps do not buy more money"


async def test_a_call_too_many_in_one_minute_waits_for_the_minute() -> None:
    waits = Waits()
    paced = limits(waits, max_calls_per_minute=2, rate_wait_s=10)
    assert await paced.admit() is None
    waits.now += 55
    assert await paced.admit() is None
    # The first call leaves the minute in five seconds: that is waited for.
    assert await paced.admit() is None
    assert waits.taken == [pytest.approx(5)]


async def test_a_call_that_would_wait_too_long_is_refused_and_not_counted() -> None:
    waits = Waits()
    paced = limits(waits, max_calls_per_minute=2, rate_wait_s=10, max_calls=3)
    assert [await paced.admit() for _ in range(2)] == [None, None]
    assert await paced.admit() == TOO_MANY_CALLS
    assert waits.taken == []
    waits.now += 60
    assert await paced.admit() is None, "the refused call used up none of the task's steps"


def test_the_same_step_is_told_by_its_tool_and_its_arguments_whatever_their_order() -> None:
    assert same_step("browser_click", {"ref": "e1", "button": "left"}) == same_step(
        "browser_click", {"button": "left", "ref": "e1"}
    )
    assert same_step("browser_click", {"ref": "e1"}) != same_step("browser_click", {"ref": "e2"})
    assert same_step("browser_click", {"ref": "e1"}) != same_step("browser_hover", {"ref": "e1"})


def test_the_third_identical_step_that_changes_nothing_is_told_and_the_sixth_is_not_run() -> None:
    watched = limits()
    click = same_step("browser_click", {"ref": "e1"})
    notes = []
    for _ in range(5):
        assert not watched.goes_in_circles(click)
        notes.append(watched.acted(click, changed=False))
    assert notes == [
        NOTHING_CHANGED,
        NOTHING_CHANGED,
        NOTHING_CHANGED
        + "\n[notice] This is the 3rd identical step and the page has not changed. Something else is needed.",
        NOTHING_CHANGED,
        NOTHING_CHANGED,
    ]
    assert watched.goes_in_circles(click)


def test_reading_in_between_does_not_begin_the_count_again() -> None:
    watched = limits()
    click = same_step("browser_click", {"ref": "e1"})
    for _ in range(5):
        watched.acted(click, changed=False)
        watched.read(same_step("browser_snapshot", {}), "Page: Same")
    assert watched.goes_in_circles(click)


def test_a_change_of_the_page_or_another_step_begins_the_count_again() -> None:
    click, other = same_step("browser_click", {"ref": "e1"}), same_step("browser_click", {"ref": "e2"})
    watched = limits()
    for _ in range(5):
        watched.acted(click, changed=False)
    assert watched.acted(click, changed=True) == ""
    assert not watched.goes_in_circles(click)
    for _ in range(5):
        watched.acted(click, changed=False)
    watched.acted(other, changed=False)
    assert not watched.goes_in_circles(click)


def test_a_page_that_changed_by_itself_lets_the_step_run_again() -> None:
    watched = limits()
    click = same_step("browser_click", {"ref": "e1"})
    for _ in range(5):
        watched.acted(click, changed=False)
    assert watched.goes_in_circles(click)
    watched.page_changed()
    assert not watched.goes_in_circles(click)


def test_the_same_reading_with_the_same_result_is_told_and_never_refused() -> None:
    watched = limits()
    read = same_step("browser_snapshot", {})
    notes = [watched.read(read, "Page: Same") for _ in range(4)]
    assert notes == [
        "",
        "",
        "\n[notice] This is the 3rd identical call with the same result. Something else is needed.",
        "",
    ]
    assert watched.read(read, "Page: Other") == ""
    assert [watched.read(read, "Page: Other") for _ in range(2)][-1].startswith("\n[notice] This is the 3rd")


def test_a_new_task_forgets_the_steps_of_the_last() -> None:
    watched = limits()
    click = same_step("browser_click", {"ref": "e1"})
    for _ in range(5):
        watched.acted(click, changed=False)
    watched.begin_task()
    assert not watched.goes_in_circles(click)
