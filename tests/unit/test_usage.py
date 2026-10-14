"""What the model's use came to, for each of the four systems and in all (spec 12.6): tasks, model
calls, tokens and cost, kept in one file the backend writes as each task ends."""

import json
from pathlib import Path

from bap_browser.config import Agent, Evals
from bap_browser.evals.record import Recorder, TaskRecord
from bap_browser.evals.usage import usage_of

CLAUDE = Agent(
    provider="anthropic", model="claude-opus-5-5", input_price_per_million=4.0, output_price_per_million=20.0
)


def a_task(
    system: str, tokens_in: int, tokens_out: int, cost: float | None, model: str = "claude-opus-5-5"
) -> TaskRecord:
    return TaskRecord(
        id=f"{system}-{tokens_in}",
        system=system,
        backend="b",
        task="t",
        started=1.0,
        model=model,
        outcome="answered",
        answer="a",
        model_calls=3,
        input_tokens=tokens_in,
        output_tokens=tokens_out,
        tokens_known=True,
        cost_usd=cost,
    )


def test_each_system_and_all_of_them_add_up(tmp_path: Path) -> None:
    for system, records in {
        "cloud": [a_task("cloud", 100_000, 2_000, 0.44)],
        "chrome": [a_task("chrome", 50_000, 1_000, None)],
        "builtin": [],
        "computer": [
            a_task("computer", 200_000, 5_000, 0.9),
            a_task("computer", 10_000, 500, None, model="gpt-5.6-luna"),
        ],
    }.items():
        recorder = Recorder(Evals(dir=str(tmp_path)), system, "b")
        for record in records:
            recorder.keep(record)

    used = usage_of(tmp_path, CLAUDE)

    assert used["systems"]["cloud"] == {
        "name": "Remote use (Cloud browser)",
        "tasks": 1,
        "model_calls": 3,
        "input_tokens": 100_000,
        "output_tokens": 2_000,
        "cost_usd": 0.44,
        "tokens_unknown": 0,
        "cost_unknown": 0,
        "by_model": {
            "claude-opus-5-5": {"tasks": 1, "input_tokens": 100_000, "output_tokens": 2_000, "cost_usd": 0.44}
        },
    }
    # A task kept before the prices were set is costed at today's price for its model.
    assert used["systems"]["chrome"]["cost_usd"] == 0.22
    assert used["systems"]["builtin"]["tasks"] == 0
    # A model with no price here is counted in tokens, and said to be uncosted.
    assert used["systems"]["computer"]["cost_unknown"] == 1
    assert used["total"]["tasks"] == 4
    assert used["total"]["input_tokens"] == 360_000
    assert used["total"]["cost_usd"] == 1.56


def test_the_backend_keeps_the_file_up_to_date_as_each_task_ends(tmp_path: Path) -> None:
    recorder = Recorder(Evals(dir=str(tmp_path)), "computer", "contained_desktop")
    recorder.keep(a_task("computer", 1_000, 100, 0.006))
    recorder.keep(a_task("computer", 2_000, 200, 0.012))

    kept = json.loads((tmp_path / "usage.json").read_text(encoding="utf-8"))
    assert kept["systems"]["computer"]["tasks"] == 2
    assert kept["systems"]["computer"]["output_tokens"] == 300
    assert kept["total"]["cost_usd"] == 0.018
