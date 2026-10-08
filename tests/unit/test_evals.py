"""The record of what a browser's tasks took (spec 12.6): time and where it went, steps, tokens and
their cost, how each task ended, the trace of each, and what they add up to."""

import asyncio
import json
import stat
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest

from bap_browser.agent.models import Message, ModelError, Reply, ToolCall, Usage
from bap_browser.agent.timed import TimedModel, TimedTools
from bap_browser.config import Config
from bap_browser.evals import Recorder, summarise, trace_of
from bap_browser.evals.record import cost_of
from bap_browser.evals.summary import percentile
from bap_browser.results import ToolResult
from bap_browser.tools import ToolDefinition

MakeConfig = Callable[..., Config]
# A reply of a model that goes on to call a tool, and says what it used.
A_REPLY = Reply("", (ToolCall("c", "x", {}),), Usage(1000, 50))
PRICED = {"model": "model-a", "input_price_per_million": 2.0, "output_price_per_million": 10.0}


class Tools:
    """Stands in for a toolkit: each call takes a moment, and `browser_click` fails."""

    def __init__(self, waits: Callable[[float], None] = lambda seconds: None) -> None:
        self.called: list[str] = []
        self._waits = waits

    def definitions(self) -> list[ToolDefinition]:
        return []

    async def call(self, name: str, arguments: Mapping[str, Any] | None = None) -> ToolResult:
        self.called.append(name)
        await asyncio.sleep(0.02)
        if name == "browser_upload_file":
            # A person took a while to allow it.
            self._waits(0.015)
        return ToolResult(f"did {name}", is_error=name == "browser_click")


class Says:
    """Stands in for a model: it answers with what it was built with, and says its tokens."""

    def __init__(self, reply: Reply | None) -> None:
        self._reply = reply

    async def complete(
        self, system: str, messages: Sequence[Message], tools: Sequence[ToolDefinition]
    ) -> Reply:
        await asyncio.sleep(0.01)
        if self._reply is None:
            raise ModelError("The model could not answer: it is out of reach")
        return self._reply


def recorder_in(make_config: MakeConfig, tmp_path: Path, **sections: Any) -> tuple[Config, Recorder]:
    config = make_config(tmp_path, **sections)
    return config, Recorder(config.evals, "cloud", "remote_headless")


async def a_task(
    recorder: Recorder,
    config: Config,
    *,
    task: str = "Find the cheapest fare to Lisbon",
    steps: Sequence[str] = ("browser_navigate", "browser_click"),
    reply: Reply | None = A_REPLY,
    outcome: str = "answered",
    keep_words: bool = True,
) -> dict[str, Any]:
    waited = [0.0]
    trace = recorder.begin(
        task,
        config.agent,
        keep_words=keep_words,
        waited_s=lambda: waited[0],
        redact=lambda text: text.replace("Lisbon", "[hidden]"),
    )
    tools = TimedTools(Tools(lambda seconds: waited.__setitem__(0, waited[0] + seconds)), trace)
    model = TimedModel(Says(reply), trace)
    try:
        for step in steps:
            await model.complete("", [], [])
            await tools.call(step, {})
    except ModelError:
        pass
    record = trace.finish(outcome, "The cheapest fare to Lisbon is 61 euros.")  # type: ignore[arg-type]
    return json.loads(json.dumps(record.__dict__, default=lambda span: span.__dict__))


async def test_a_task_is_kept_with_its_time_its_steps_its_tokens_and_its_trace(
    make_config: MakeConfig, tmp_path: Path
) -> None:
    config, recorder = recorder_in(make_config, tmp_path, agent=PRICED)
    done = await a_task(recorder, config)
    assert (done["system"], done["backend"], done["model"], done["outcome"]) == (
        "cloud",
        "remote_headless",
        "model-a",
        "answered",
    )
    assert (done["steps"], done["steps_failed"], done["model_calls"]) == (2, 1, 2)
    assert done["tokens_known"] is True and (done["input_tokens"], done["output_tokens"]) == (2000, 100)
    # 2,000 tokens in at 2 dollars a million, 100 out at 10.
    assert done["cost_usd"] == pytest.approx(0.005)
    # Each time is kept to a tenth of a millisecond, so the parts may add up a hair over the whole.
    assert done["duration_ms"] + 1 >= done["model_ms"] + done["tool_ms"] > 0
    # The trace: every reply of the model and every step, in the order they happened.
    assert [(span["kind"], span["name"], span["ok"]) for span in done["spans"]] == [
        ("model", "model-a", True),
        ("tool", "browser_navigate", True),
        ("model", "model-a", True),
        ("tool", "browser_click", False),
    ]
    assert [span["at_ms"] for span in done["spans"]] == sorted(span["at_ms"] for span in done["spans"])
    assert done["spans"][0]["input_tokens"] == 1000

    kept = recorder.tasks()
    assert [record["id"] for record in kept] == [done["id"]]
    file = recorder.folder / "tasks.jsonl"
    assert file == tmp_path / "evals" / "cloud" / "tasks.jsonl"
    assert stat.S_IMODE(file.stat().st_mode) == 0o600, "the record is the person's alone to read"


async def test_what_a_person_typed_never_reaches_the_record(make_config: MakeConfig, tmp_path: Path) -> None:
    config, recorder = recorder_in(
        make_config, tmp_path, evals={"max_task_chars": 20, "dir": str(tmp_path / "e")}
    )
    done = await a_task(recorder, config)
    # The task's own words are kept cut short, and with what the deployment hides taken out.
    assert done["task"] == "Find the cheapest fa" and done["answer"] == "The cheapest fare to"
    assert "Lisbon" not in (recorder.folder / "tasks.jsonl").read_text(encoding="utf-8")
    # Where the log is turned off for a browser, the words are not kept at all: only the numbers.
    silent = await a_task(recorder, config, keep_words=False)
    assert (silent["task"], silent["answer"]) == ("", "") and silent["steps"] == 2
    # A step is kept by its tool's name, its time and whether it worked. Never by what it was given.
    assert set(done["spans"][1]) == {
        "kind",
        "name",
        "at_ms",
        "ms",
        "ok",
        "waited_ms",
        "input_tokens",
        "output_tokens",
    }


async def test_a_wait_for_a_person_is_not_the_browsers_time(make_config: MakeConfig, tmp_path: Path) -> None:
    config, recorder = recorder_in(make_config, tmp_path)
    done = await a_task(recorder, config, steps=("browser_upload_file",))
    step = done["spans"][1]
    assert step["waited_ms"] == pytest.approx(15, abs=1)
    assert done["waited_ms"] == step["waited_ms"]
    assert done["tool_ms"] == pytest.approx(step["ms"] - step["waited_ms"], abs=0.2)


async def test_a_model_that_does_not_say_its_tokens_has_no_cost(
    make_config: MakeConfig, tmp_path: Path
) -> None:
    config, recorder = recorder_in(make_config, tmp_path, agent=PRICED)
    scripted = await a_task(recorder, config, reply=Reply("done"))
    assert scripted["tokens_known"] is False and scripted["cost_usd"] is None
    failed = await a_task(recorder, config, reply=None, outcome="failed")
    assert failed["outcome"] == "failed" and failed["spans"] == [
        {**failed["spans"][0], "kind": "model", "ok": False}
    ]
    # With no price given, tokens are counted and no cost is made up.
    unpriced, plain = recorder_in(make_config, tmp_path, agent={"model": "model-a"})
    assert (await a_task(plain, unpriced))["cost_usd"] is None
    assert cost_of(1_000_000, 0, config.agent) == 2.0 and cost_of(5, 5, unpriced.agent) is None


async def test_nothing_is_kept_where_a_deployment_turns_the_records_off(
    make_config: MakeConfig, tmp_path: Path
) -> None:
    config, recorder = recorder_in(
        make_config, tmp_path, evals={"enabled": False, "dir": str(tmp_path / "e")}
    )
    await a_task(recorder, config)
    assert recorder.tasks() == [] and not recorder.folder.exists()


def test_percentiles_are_by_nearest_rank() -> None:
    assert percentile([], 0.5) is None
    assert percentile([7.0], 0.95) == 7.0
    assert percentile([1, 2, 3, 4], 0.5) == 2 and percentile([4, 1, 3, 2], 0.95) == 4
    assert percentile(list(range(1, 101)), 0.95) == 95


async def test_the_records_add_up_to_latency_time_cost_and_how_tasks_ended(
    make_config: MakeConfig, tmp_path: Path
) -> None:
    config, recorder = recorder_in(make_config, tmp_path, agent=PRICED)
    empty = summarise(recorder, config.evals, "model-a")
    assert empty["tasks"]["count"] == 0 and empty["tasks"]["success_rate"] is None
    assert empty["latency"]["tool"] == {"count": 0, "p50_ms": None, "p95_ms": None, "max_ms": None}
    assert empty["cost"]["usd"] is None and empty["recent"] == [] and empty["checklist"] is None

    first = await a_task(recorder, config)
    await a_task(recorder, config, steps=("browser_navigate",), outcome="stopped")
    await a_task(recorder, config, reply=None, outcome="failed")
    last = await a_task(
        recorder, config, steps=("browser_upload_file", "browser_snapshot", "browser_navigate")
    )
    told = summarise(recorder, config.evals, "model-a")

    tasks = told["tasks"]
    assert (tasks["count"], tasks["answered"], tasks["stopped"], tasks["failed"]) == (4, 2, 1, 1)
    assert tasks["success_rate"] == 0.5
    assert (tasks["steps"], tasks["steps_failed"], tasks["steps_per_task"]) == (6, 1, 1.5)
    assert (told["system"], told["model"], told["models_used"]) == ("cloud", "model-a", ["model-a"])

    latency = told["latency"]
    assert latency["tool"]["count"] == 6 and latency["model"]["count"] == 7
    # How fast the machine is does not matter here: only that the three are in their order.
    assert 15 <= latency["tool"]["p50_ms"] <= latency["tool"]["p95_ms"] <= latency["tool"]["max_ms"]
    # The tool most used comes first, each with how often it failed.
    assert [(row["tool"], row["count"], row["failed"]) for row in latency["by_tool"]] == [
        ("browser_navigate", 3, 0),
        ("browser_click", 1, 1),
        ("browser_upload_file", 1, 0),
        ("browser_snapshot", 1, 0),
    ]
    # What a step waited for a person is taken out of that step's time.
    upload = next(row for row in latency["by_tool"] if row["tool"] == "browser_upload_file")
    waited = next(span for span in last["spans"] if span["name"] == "browser_upload_file")
    assert waited["waited_ms"] == pytest.approx(15, abs=1)
    assert upload["p50_ms"] == pytest.approx(waited["ms"] - waited["waited_ms"], abs=0.2)

    time = told["time"]
    assert time["task"]["count"] == 4 and time["task"]["p95_ms"] >= time["task"]["p50_ms"] > 0
    assert time["model_share"] + time["tool_share"] + time["waiting_share"] == pytest.approx(1, abs=0.002)
    assert time["waiting_share"] > 0

    cost = told["cost"]
    assert (cost["tasks_counted"], cost["input_tokens"], cost["output_tokens"]) == (3, 6000, 300)
    assert cost["usd"] == pytest.approx(0.015) and cost["usd_per_task"] == pytest.approx(0.005)

    # The newest task first, each without its trace, which is asked for by itself.
    assert told["recent"][0]["id"] == last["id"] and "spans" not in told["recent"][0]
    assert [span["name"] for span in (trace_of(recorder, first["id"]) or {})["spans"]] == [
        "model-a",
        "browser_navigate",
        "model-a",
        "browser_click",
    ]
    assert trace_of(recorder, "no-such-task") is None


async def test_a_person_says_whether_an_answer_was_good(make_config: MakeConfig, tmp_path: Path) -> None:
    config, recorder = recorder_in(make_config, tmp_path)
    good, bad = await a_task(recorder, config), await a_task(recorder, config)
    assert recorder.rate(good["id"], "good") and recorder.rate(bad["id"], "bad")
    assert not recorder.rate("no-such-task", "good")
    told = summarise(recorder, config.evals, "model-a")
    assert (told["tasks"]["rated_good"], told["tasks"]["rated_bad"]) == (1, 1)
    assert {row["id"]: row["rating"] for row in told["recent"]} == {good["id"]: "good", bad["id"]: "bad"}
    assert (trace_of(recorder, bad["id"]) or {})["rating"] == "bad"
    # A person takes their word back.
    assert recorder.rate(bad["id"], None)
    assert summarise(recorder, config.evals, "model-a")["tasks"]["rated_bad"] == 0


async def test_only_the_newest_records_are_read_and_a_spoiled_line_is_passed_over(
    make_config: MakeConfig, tmp_path: Path
) -> None:
    config, recorder = recorder_in(
        make_config, tmp_path, evals={"max_tasks_read": 3, "recent_tasks": 2, "dir": str(tmp_path / "e")}
    )
    ids = [(await a_task(recorder, config, steps=()))["id"] for _ in range(4)]
    with (recorder.folder / "tasks.jsonl").open("a", encoding="utf-8") as file:
        file.write("{not json\n[]\n")
    told = summarise(recorder, config.evals, "model-a")
    assert told["tasks"]["count"] == 1, "of the newest three lines, one is a record"
    assert [row["id"] for row in told["recent"]] == [ids[-1]]


async def test_the_checklist_as_it_was_last_run_is_kept(make_config: MakeConfig, tmp_path: Path) -> None:
    config, recorder = recorder_in(make_config, tmp_path)
    assert recorder.checklist() is None
    recorder.keep_checklist({"passed": 9, "failed": 0, "checks": []})
    assert summarise(recorder, config.evals, "model-a")["checklist"] == {
        "passed": 9,
        "failed": 0,
        "checks": [],
    }
