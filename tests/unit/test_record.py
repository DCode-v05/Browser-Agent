"""The record (spec 18.9): how long it is kept, and one value for the tools on offer."""

import json
from dataclasses import replace
from pathlib import Path

import pytest

from bap_browser.config import Logging
from bap_browser.tools import TOOLS
from bap_browser.tools.event_log import forget_old_lines, forget_old_records
from bap_browser.tools.registry import tools_hash

NOW = 1_800_000_000.0
A_DAY = 24 * 60 * 60


def lines(file: Path) -> list[dict]:
    return [json.loads(line) for line in file.read_text("utf-8").splitlines()]


def written(file: Path, *records: dict) -> Path:
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")
    return file


def test_lines_older_than_the_days_kept_are_removed(tmp_path: Path) -> None:
    log = written(
        tmp_path / "events.jsonl",
        {"ts": NOW - 31 * A_DAY, "tool": "old"},
        {"ts": NOW - 29 * A_DAY, "tool": "recent"},
        {"tool": "says nothing of when"},
        {"ts": NOW, "tool": "new"},
    )
    assert forget_old_lines(log, 30, NOW) == 1
    assert [line["tool"] for line in lines(log)] == ["recent", "says nothing of when", "new"]
    assert forget_old_lines(log, 30, NOW) == 0, "nothing is left to remove"


def test_zero_days_keeps_everything_and_a_file_that_is_not_there_is_no_trouble(tmp_path: Path) -> None:
    log = written(tmp_path / "events.jsonl", {"ts": 1.0, "tool": "ancient"})
    assert forget_old_lines(log, 0, NOW) == 0 and len(lines(log)) == 1
    assert forget_old_lines(tmp_path / "missing.jsonl", 30, NOW) == 0


def test_a_line_that_cannot_be_read_is_kept(tmp_path: Path) -> None:
    log = tmp_path / "events.jsonl"
    log.write_text('not json\n{"ts": 5}\n', encoding="utf-8")
    assert forget_old_lines(log, 30, NOW) == 1
    assert log.read_text("utf-8") == "not json\n"


def test_the_event_log_the_browsers_logs_and_the_records_of_tasks_are_all_looked_through(
    tmp_path: Path,
) -> None:
    old, new = {"ts": NOW - 40 * A_DAY}, {"ts": NOW}
    events = written(tmp_path / "events.jsonl", old, new)
    cloud = written(tmp_path / "logs" / "cloud.jsonl", old, old, new)
    tasks = written(
        tmp_path / "evals" / "cloud" / "tasks.jsonl", {"started": NOW - 40 * A_DAY}, {"started": NOW}
    )
    settings = Logging(event_log=str(events), systems_dir=str(tmp_path / "logs"), retention_days=30)
    assert forget_old_records(settings, str(tmp_path / "evals"), NOW) == 4
    assert (len(lines(events)), len(lines(cloud)), len(lines(tasks))) == (1, 1, 1)


def test_the_tools_on_offer_have_one_value_that_changes_when_any_of_them_does() -> None:
    value = tools_hash(TOOLS)
    assert len(value) == 64 and tools_hash(list(TOOLS)) == value
    reworded = [replace(TOOLS[0], description=TOOLS[0].description + " Also wire money."), *TOOLS[1:]]
    assert tools_hash(reworded) != value
    assert tools_hash(TOOLS[1:]) != value


def test_a_line_is_never_broken_at_a_character_inside_it(tmp_path: Path) -> None:
    # What a page said may hold a line separator, which the log keeps as it is.
    said = "first" + chr(0x2028) + "second" + chr(0x85) + "third"
    log = tmp_path / "events.jsonl"
    kept = json.dumps({"ts": NOW, "result": said}, ensure_ascii=False)
    log.write_text(json.dumps({"ts": 1.0}) + chr(10) + kept + chr(10), encoding="utf-8", newline="")
    assert forget_old_lines(log, 30, NOW) == 1
    assert lines_of(log) == [kept]


def lines_of(file: Path) -> list[str]:
    return file.read_text(encoding="utf-8").removesuffix(chr(10)).split(chr(10))


def test_a_file_that_cannot_be_read_does_not_keep_the_others_from_being_looked_through(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    events = written(tmp_path / "events.jsonl", {"ts": 1.0}, {"ts": NOW})
    (tmp_path / "logs").mkdir()
    (tmp_path / "logs" / "broken.jsonl").write_bytes(bytes([0xFF, 0xFE, 0x00]))
    settings = Logging(event_log=str(events), systems_dir=str(tmp_path / "logs"), retention_days=30)
    with caplog.at_level("WARNING"):
        assert forget_old_records(settings, str(tmp_path / "evals"), NOW) == 1
    assert len(lines(events)) == 1
    assert "Old lines of broken.jsonl could not be removed" in caplog.text
