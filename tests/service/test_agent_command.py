"""`bap-browser agent`: one command runs the reference loop with the service and the viewer around it (spec 16.5)."""

import json
import os
import re
import subprocess
import sys
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from model_stand_in import ModelStandIn, called, response, said

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
        env={
            name: value
            for name, value in os.environ.items()
            if name not in ("BAP_BROWSER_TOKEN", "OPENAI_API_KEY")
        },
    )


@pytest.fixture(autouse=True)
def nothing_from_the_developers_own_setup(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The command reads a .env file in the folder it is run from, and the key from the environment.
    A test must never pick up the developer's real key and call the real provider with it."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


@pytest.fixture
def provider() -> Iterator[Callable[..., ModelStandIn]]:
    started: list[ModelStandIn] = []

    def start(*replies: object) -> ModelStandIn:
        stand_in = ModelStandIn(*replies)  # type: ignore[arg-type]
        started.append(stand_in)
        return stand_in

    yield start
    for stand_in in started:
        stand_in.close()


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


def test_without_a_key_it_says_where_to_put_one(
    make_config: Callable[..., Config], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    make_config(tmp_path)
    assert main(["agent", "Book a table", "--config", str(tmp_path / "config.json")]) == 2
    assert capsys.readouterr().err.strip() == (
        "error: OPENAI_API_KEY is not set. Put a line OPENAI_API_KEY=... in a file named .env in this "
        "folder, or set it in the environment. To try without a model: bap-browser agent --demo"
    )


def test_the_key_comes_from_dot_env_and_the_model_does_the_task(
    make_config: Callable[..., Config], tmp_path: Path, provider
) -> None:
    key = "sk-test-from-the-dot-env-file"
    stand_in = provider(
        response(said("I will read the page."), called("call_1", "browser_snapshot", "{}")),
        response(said("The page is blank.")),
    )
    make_config(tmp_path, agent={"base_url": stand_in.base_url})
    (tmp_path / ".env").write_text(f"OPENAI_API_KEY={key}\n", encoding="utf-8")
    done = run(tmp_path, "What is on the page?", "--exit-when-done")
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == "The page is blank."
    assert "I will read the page." in done.stderr

    first, second = stand_in.requests
    assert first["authorization"] == f"Bearer {key}"
    assert first["body"]["model"] == "gpt-5.6-luna"
    assert first["body"]["input"] == [{"role": "user", "content": "What is on the page?"}]
    assert second["body"]["input"][-1]["type"] == "function_call_output"
    assert second["body"]["input"][-1]["output"].startswith("Page: ")
    # The key is in the request to the provider and nowhere else.
    log = (tmp_path / "events.jsonl").read_text(encoding="utf-8")
    assert key not in done.stdout and key not in done.stderr and key not in log


def test_a_key_the_provider_refuses_ends_the_run_with_the_reason(
    make_config: Callable[..., Config], tmp_path: Path, provider
) -> None:
    stand_in = provider((401, {"error": {"message": "Incorrect API key provided: sk-wrong***"}}))
    make_config(tmp_path, agent={"base_url": stand_in.base_url})
    (tmp_path / ".env").write_text("OPENAI_API_KEY=sk-wrong-key\n", encoding="utf-8")
    done = run(tmp_path, "What is on the page?", "--exit-when-done")
    assert done.returncode == 1
    assert done.stdout == ""
    assert done.stderr.strip().splitlines()[-1] == (
        "error: The model provider did not accept the key (HTTP 401). Check OPENAI_API_KEY in your .env file."
    )
    assert "sk-wrong" not in done.stderr


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
