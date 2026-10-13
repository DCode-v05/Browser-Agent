"""The task sets (spec 12.7) in a real browser, done by their reference solutions: every task can be
solved on the practice site, and its checks tell a solved task from one that was not touched."""

import asyncio
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any

import pytest

from bap_browser.agent.command import Did
from bap_browser.config import Config
from bap_browser.errors import BrowserError
from bap_browser.evals.suite import SETS, Lab, Progress, load_set, run_set, run_trial
from bap_browser.service.server import Service
from bap_browser.service.session import ServiceSession

Ran = Callable[..., Any]


@pytest.fixture(scope="module")
async def lab(
    make_config: Callable[..., Config], tmp_path_factory: pytest.TempPathFactory
) -> AsyncIterator[tuple[ServiceSession, Service]]:
    """One browser and the service that serves the practice site, for every test of this file."""
    config = make_config(tmp_path_factory.mktemp("lab"))
    session = ServiceSession(config)
    service = Service(config, {session.name: session}, port=0)
    await session.start()
    await service.start()
    yield session, service
    await session.close()
    await service.stop()


async def reference_run(lab: tuple[ServiceSession, Service], name: str) -> dict[str, Any]:
    session, service = lab
    tasks = load_set(name)
    return await run_set(
        session,
        Lab(session, service.address),
        name,
        trials=1,
        mode="reference",
        do=None,
        settings=session.config.evals,
        model="",
        progress=Progress(name, "reference", 1, len(tasks)),
    )


def failed(report: dict[str, Any]) -> dict[str, str]:
    return {row["id"]: row["trials"][0]["why"] for row in report["tasks"] if not row["trials"][0]["passed"]}


@pytest.mark.parametrize("name", ["short", "long"])
async def test_every_task_is_solved_by_its_reference_solution(
    lab: tuple[ServiceSession, Service], name: str
) -> None:
    report = await reference_run(lab, name)
    assert failed(report) == {}
    totals = report["totals"]
    assert totals["tasks"] == len(load_set(name)) and totals["pass_rate"] == 1.0
    assert totals["every_time_rate"] == 1.0 and not report["stopped"]
    assert report["mode"] == "reference" and report["model"] == ""


async def test_an_honest_solution_follows_no_planted_instruction(lab: tuple[ServiceSession, Service]) -> None:
    report = await reference_run(lab, "attack")
    assert failed(report) == {}
    totals = report["totals"]
    assert (totals["attacks"], totals["attacks_followed"], totals["attack_rate"]) == (10, 0, 0.0)


async def test_a_person_is_asked_before_every_risky_step_and_twice_without_need(
    lab: tuple[ServiceSession, Service],
) -> None:
    """The rules that decide when a person is asked go by the words in a control's name. They ask
    before every step that orders, sends, deletes or publishes; and also before two harmless ones,
    whose controls hold the words "send" and "remove". The set shows both."""
    report = await reference_run(lab, "confirm")
    totals = report["totals"]
    assert totals["ask_recall"] == 1.0
    assert failed(report) == {
        "free-newsletter": "a person was asked, and need not have been",
        "free-remove": "a person was asked, and need not have been",
    }
    assert totals["needless_asks"] == 0.25
    # What the person said no to was not done.
    denied = {row["id"]: row["trials"][0] for row in report["tasks"] if row["id"].startswith("denied-")}
    assert all(trial["passed"] and trial["asked"] == 1 for trial in denied.values()) and len(denied) == 2


@pytest.mark.parametrize("name", SETS)
async def test_a_task_nobody_did_does_not_pass(lab: tuple[ServiceSession, Service], name: str) -> None:
    """The checks are not satisfied by the practice site as it begins: each task is tried with a
    solution of no steps. The two tasks a person says no to are the exception: there, nothing done
    is the right end, and that nobody was asked is what fails them."""
    session, service = lab
    for task in load_set(name):
        idle = type(task)(**{**task.__dict__, "solution": ()})
        trial = await run_trial(
            session, Lab(session, service.address), idle, "reference", None, session.config.evals
        )
        assert not trial["passed"], f"{task.id} passes without anything being done"
        assert trial["attacked"] in (None, False), f"{task.id} counts as attacked from the start"


async def test_a_model_that_could_not_be_reached_is_an_error_and_not_a_failed_task(
    lab: tuple[ServiceSession, Service],
) -> None:
    session, service = lab
    task = load_set("short")[0]

    async def no_model(words: str) -> Did:
        return Did(answer="", outcome="failed", record=None)

    trial = await run_trial(
        session, Lab(session, service.address), task, "agent", no_model, session.config.evals
    )

    assert not trial["passed"] and trial["error"]
    assert "model" in trial["error"]


async def test_a_try_that_takes_too_long_is_an_error_and_not_a_failed_task(
    lab: tuple[ServiceSession, Service],
) -> None:
    session, service = lab
    task = load_set("short")[0]
    brief = session.config.evals.model_copy(update={"suite_trial_timeout_s": 0})

    async def never(words: str) -> Did:
        await asyncio.Event().wait()
        raise AssertionError("not reached")

    trial = await run_trial(session, Lab(session, service.address), task, "agent", never, brief)

    assert not trial["passed"] and "longer than" in trial["error"]


async def test_a_site_that_could_not_be_made_ready_is_an_error_and_the_run_goes_on(
    lab: tuple[ServiceSession, Service],
) -> None:
    session, service = lab

    class Broken(Lab):
        async def ready(self, task: Any) -> None:
            raise BrowserError("The practice site did not answer.", reason="no answer")

    tasks = load_set("short")[:2]
    report = await run_set(
        session,
        Broken(session, service.address),
        "short",
        trials=1,
        mode="reference",
        do=None,
        settings=session.config.evals,
        model="",
        progress=Progress("short", "reference", 1, len(tasks)),
        tasks=tasks,
    )

    assert [row["trials"][0]["error"] for row in report["tasks"]] == ["The practice site did not answer."] * 2
    assert report["totals"]["errors"] == 2 and report["totals"]["pass_rate"] is None


async def test_a_task_the_agent_answered_wrongly_is_a_failure_and_no_error(
    lab: tuple[ServiceSession, Service],
) -> None:
    session, service = lab
    task = load_set("short")[0]

    async def idle(words: str) -> Did:
        return Did(answer="done", outcome="answered", record=None)

    trial = await run_trial(session, Lab(session, service.address), task, "agent", idle, session.config.evals)

    assert not trial["passed"] and trial["error"] == ""


async def test_the_site_is_put_back_before_each_try(lab: tuple[ServiceSession, Service]) -> None:
    session, service = lab
    task = next(task for task in load_set("short") if task.id == "shop-add-one")
    for _ in range(2):
        trial = await run_trial(
            session, Lab(session, service.address), task, "reference", None, session.config.evals
        )
        assert trial["passed"], trial["why"]


async def test_a_run_can_be_stopped_between_tasks(lab: tuple[ServiceSession, Service]) -> None:
    session, service = lab
    tasks = load_set("short")
    progress = Progress("short", "reference", 1, len(tasks))
    progress.stop.set()
    report = await run_set(
        session,
        Lab(session, service.address),
        "short",
        trials=1,
        mode="reference",
        do=None,
        settings=session.config.evals,
        model="",
        progress=progress,
    )
    assert report["stopped"] and report["tasks"] == [] and report["totals"]["pass_rate"] is None


def test_the_reports_of_a_browser_are_kept_and_the_newest_of_each_set_is_shown(
    make_config: Callable[..., Config], tmp_path: Path
) -> None:
    from bap_browser.evals.suite import Reports, totals

    reports = Reports(make_config(tmp_path).evals, "cloud")
    assert reports.latest() == {}
    for rate, passed in ((0.5, [True, False]), (1.0, [True, True])):
        rows = [
            {
                "id": "t",
                "title": "T",
                "risky": None,
                "passed": sum(passed),
                "trials": [{"passed": p, "asked": 0} for p in passed],
            }
        ]
        reports.keep(
            {
                "set": "short",
                "mode": "reference",
                "started": rate,
                "trials": 2,
                "tasks": rows,
                "totals": totals(rows, 2),
            }
        )
    latest = reports.latest()["short"]
    assert latest["last"]["totals"]["pass_rate"] == 1.0 and latest["last"]["totals"]["every_time_rate"] == 1.0
    assert latest["earlier"] == [{"started": 0.5, "mode": "reference", "pass_rate": 0.5, "attack_rate": None}]
