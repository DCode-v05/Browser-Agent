"""`bap-browser sets`: the task sets of a browser run with no window, as a nightly job runs them
(spec 12.7). Here by their reference solutions, in a real browser, with no model."""

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from bap_browser.agent.sets_command import run_sets, said_of
from bap_browser.cli import main
from bap_browser.config import Config
from bap_browser.errors import ConfigError


async def test_the_sets_named_are_run_and_their_reports_are_kept_where_the_window_reads_them(
    make_config: Callable[..., Config], tmp_path: Path
) -> None:
    config = make_config(tmp_path)

    reports = await run_sets(config, None, ["long", "attack"], trials=1, mode="reference")

    assert [(report["set"], report["mode"], report["totals"]["pass_rate"]) for report in reports] == [
        ("long", "reference", 1.0),
        ("attack", "reference", 1.0),
    ]
    kept = (
        (Path(config.evals.dir) / "cloud" / "suite" / "runs.jsonl").read_text(encoding="utf-8").splitlines()
    )
    assert [json.loads(line)["set"] for line in kept] == ["long", "attack"]
    assert (
        said_of(reports[1]) == "attack: 25 of 25 tries passed (100%). 0 of 25 planted instructions followed."
    )


async def test_a_set_that_does_not_exist_is_named_before_anything_is_started(
    make_config: Callable[..., Config], tmp_path: Path
) -> None:
    with pytest.raises(
        ConfigError, match=r"no task set named sideways\. The sets are: short, confirm, attack, long"
    ):
        await run_sets(make_config(tmp_path), None, ["sideways"], trials=1, mode="reference")


def test_the_command_says_how_each_set_went(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    config = tmp_path / "config.json"
    config.write_text(
        json.dumps(
            {
                "data_dir": str(tmp_path),
                "evals": {"dir": str(tmp_path / "evals")},
                "server": {"state_file": str(tmp_path / "service.json")},
            }
        ),
        encoding="utf-8",
    )

    assert main(["sets", "long", "--reference", "--config", str(config)]) == 0

    assert capsys.readouterr().out.strip() == "long: 4 of 4 tries passed (100%)."


def test_the_sets_leave_the_address_of_a_window_that_is_open_as_it_was(tmp_path: Path) -> None:
    """The sets show no viewer. A window started from the same folder keeps its address, for its
    person to open it again."""
    studio = tmp_path / "service.json"
    studio.write_text(json.dumps({"viewer": "http://127.0.0.1:8765/#token=the-window"}), encoding="utf-8")
    config = tmp_path / "config.json"
    config.write_text(
        json.dumps(
            {
                "data_dir": str(tmp_path),
                "evals": {"dir": str(tmp_path / "evals")},
                "server": {"state_file": str(studio)},
            }
        ),
        encoding="utf-8",
    )

    assert main(["sets", "long", "--reference", "--config", str(config)]) == 0

    assert json.loads(studio.read_text(encoding="utf-8")) == {
        "viewer": "http://127.0.0.1:8765/#token=the-window"
    }
