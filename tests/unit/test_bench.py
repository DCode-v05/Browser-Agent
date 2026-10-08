"""The bench (spec 11.2, 12.3): how a line is judged, and that no line is ever left out."""

import json
from pathlib import Path

import pytest

from bap_browser.bench import runner
from bap_browser.bench.runner import Line, Measured
from bap_browser.bench.scenarios import SCENARIOS
from bap_browser.config import Config
from bap_browser.errors import ConfigError
from bap_browser.tools import TOOLS

BUDGET = Path(__file__).parents[2] / "perf" / "budget.json"
LINE = Line("snapshot.small", "browser_snapshot", "Small form", target_ms=5, fail_ms=15)


def test_the_budget_file_holds_the_lines_of_the_spec() -> None:
    lines = runner.load_budget(BUDGET)
    ids = [line.id for line in lines]
    assert len(ids) == len(set(ids)) == 41
    # The code tool is of milestone 4. Its lines are with those of the next steps (spec 11.4).
    known = {tool.name for tool in TOOLS} - {"browser_run"}
    assert {line.tool for line in lines} <= known
    # Every tool of milestone 1 has at least one line.
    assert {line.tool for line in lines} == known
    assert all(0 < line.target_ms < line.fail_ms for line in lines)
    # A scenario times a line of the budget, and nothing else.
    assert set(SCENARIOS) <= set(ids)


def test_a_budget_file_that_cannot_be_read_stops_the_bench(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="could not be read"):
        runner.load_budget(tmp_path / "nothing.json")
    (tmp_path / "bad.json").write_text('{"lines": [{"id": "x"}]}', encoding="utf-8")
    with pytest.raises(ConfigError, match="could not be read"):
        runner.load_budget(tmp_path / "bad.json")


@pytest.mark.parametrize(
    ("samples", "state"),
    [
        ([4.0] * 30, "OK"),
        ([5.0] * 30, "OK"),
        # Within five in a hundred above the target still counts as OK.
        ([5.25] * 30, "OK"),
        ([5.3] * 30, "WARN"),
        ([15.0] * 30, "WARN"),
        ([15.1] * 30, "FAIL"),
        # The median is fine, but the slow runs are at twice the fail limit.
        ([4.0] * 27 + [30.0] * 3, "FAIL"),
        ([4.0] * 29 + [30.0], "OK"),
    ],
)
def test_a_line_is_judged_on_its_median_and_its_slowest_runs(samples: list[float], state: str) -> None:
    assert runner.judge(LINE, "chromium", samples).state == state


def test_the_report_has_a_row_for_every_line_and_a_count_of_each_state() -> None:
    measured = [
        runner.judge(LINE, "chromium", [2.0] * 30),
        Measured("drag.refs", "chromium", "NOT RUN", target_ms=120, fail_ms=240, note="no scenario yet"),
    ]
    lines = runner.report(measured).splitlines()
    assert lines[0].split(" | ")[0].strip() == "line"
    assert [part.strip() for part in lines[1].split("|")] == [
        "snapshot.small",
        "chromium",
        "2.0",
        "2.0",
        "5",
        "15",
        "OK",
    ]
    assert lines[2].endswith("NOT RUN (no scenario yet)")
    assert lines[-1] == "1 OK, 0 WARN, 0 FAIL, 1 NOT RUN, 0 ERROR"


def test_a_failure_counts_once_it_is_seen_in_two_runs_one_after_the_other(tmp_path: Path) -> None:
    slow = runner.judge(LINE, "chromium", [20.0] * 30)
    fine = runner.judge(LINE, "msedge", [2.0] * 30)
    assert slow.state == "FAIL"
    assert runner.failed_before(tmp_path) == set()
    assert runner.blocking([slow, fine], runner.failed_before(tmp_path)) == []

    first = runner.save([slow, fine], tmp_path, now=0)
    assert json.loads(first.read_text(encoding="utf-8"))["results"][0]["median_ms"] == 20.0
    before = runner.failed_before(tmp_path)
    assert before == {("snapshot.small", "chromium")}
    assert runner.blocking([slow, fine], before) == [slow]
    # The same line on another browser failed for the first time: it does not count yet.
    elsewhere = runner.judge(LINE, "msedge", [20.0] * 30)
    assert runner.blocking([elsewhere], before) == []


async def test_lines_are_timed_in_a_real_browser_and_none_is_left_out(make_config, tmp_path: Path) -> None:
    # The configuration is read as a command reads it: a machine that runs the tests may have to
    # start the browser in its own way.
    bench = {"runs": 3, "warmup": 1, "results_dir": str(tmp_path / "bench")}
    config: Config = make_config(tmp_path, bench=bench)
    lines = [
        line
        for line in runner.load_budget(BUDGET)
        if line.id in ("snapshot.small", "fill_form.per_field", "tabs.switch", "drag.refs")
    ]
    measured = await runner.run(config, lines, ["chromium"])
    by_line = {m.line: m for m in measured}
    assert set(by_line) == {"snapshot.small", "fill_form.per_field", "tabs.switch", "drag.refs"}
    for timed in ("snapshot.small", "fill_form.per_field", "tabs.switch"):
        assert by_line[timed].state in ("OK", "WARN", "FAIL"), by_line[timed]
        assert (by_line[timed].median_ms or 0) > 0
    # A line with no scenario yet is said to be not run. It is not passed over, and it does not pass.
    assert (by_line["drag.refs"].state, by_line["drag.refs"].note) == ("NOT RUN", "no scenario yet")

    only = await runner.run(config, runner.load_budget(BUDGET), ["chromium"], only=["console.read"])
    assert [m.line for m in only] == ["console.read"]
