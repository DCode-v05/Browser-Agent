"""`bap-browser agent`: one command runs the reference loop with the service and the viewer around it (spec 16.5)."""

import json
import os
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from bap_browser.cli import main
from bap_browser.config import Config

ANSWER = 'The account was created. The page now shows "Welcome, Ada" with 3 open invoices.'


def run(folder: Path, *arguments: str, timeout: float = 120) -> subprocess.CompletedProcess[str]:
    """Runs the real command the way a person would, in its own process."""
    return subprocess.run(
        [sys.executable, "-m", "bap_browser", "agent", "--config", str(folder / "config.json"), *arguments],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=timeout,
        cwd=folder,
        env={name: value for name, value in os.environ.items() if name != "BAP_BROWSER_TOKEN"},
    )


def test_the_demonstration_runs_from_one_command_and_leaves_its_steps_in_the_log(
    make_config: Callable[..., Config], tmp_path: Path
) -> None:
    make_config(tmp_path)
    done = run(tmp_path, "--demo", "--exit-when-done", "--pace", "0")
    assert done.returncode == 0, done.stderr
    # The answer is the only thing on standard output; everything else is for the person at the terminal.
    assert done.stdout.strip() == ANSWER

    viewer = re.search(r"^Viewer: (http://127\.0\.0\.1:\d+/#token=(\S+))$", done.stderr, re.MULTILINE)
    assert viewer, done.stderr
    token = viewer.group(2)
    assert len(token) >= 32
    assert token not in done.stdout

    log = (tmp_path / "events.jsonl").read_text(encoding="utf-8")
    lines = [json.loads(line) for line in log.splitlines()]
    assert [line["tool"] for line in lines] == [
        "browser_navigate",
        "browser_type",
        "browser_type",
        "browser_type",
        "browser_click",
        "browser_click",
        "browser_snapshot",
        "browser_type",
        "browser_click",
        "browser_snapshot",
    ]
    assert all(line["ok"] for line in lines)
    assert token not in log
    # The address that lets a person in is kept for the local user only while the service runs.
    assert not (tmp_path / ".bap-browser" / "service.json").exists()


def test_without_a_model_it_says_how_to_run_the_demonstration(
    make_config: Callable[..., Config], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    make_config(tmp_path)
    assert main(["agent", "Book a table", "--config", str(tmp_path / "config.json")]) == 2
    assert capsys.readouterr().err.strip() == (
        "error: agent.provider is 'anthropic', and the hosted model is not part of this build yet. "
        "Run the demonstration instead: bap-browser agent --demo"
    )


def test_the_scripted_model_plays_only_the_demonstration(
    make_config: Callable[..., Config], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    make_config(tmp_path, agent={"provider": "scripted"})
    assert main(["agent", "Book a table", "--config", str(tmp_path / "config.json")]) == 2
    assert capsys.readouterr().err.strip() == (
        "error: the scripted model only plays the demonstration. Run: bap-browser agent --demo"
    )


def test_a_task_is_needed_unless_it_is_the_demonstration(
    make_config: Callable[..., Config], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    make_config(tmp_path)
    assert main(["agent", "--config", str(tmp_path / "config.json")]) == 2
    assert capsys.readouterr().err.strip() == (
        'error: say what the agent should do, for example: bap-browser agent "Find the opening hours", '
        "or run the demonstration: bap-browser agent --demo"
    )
