"""The dock: carries the driver's pipe through `docker exec` into the contained desktop's
container (spec 22.2). Piece 5 of "Computer use on Hermes: built and remaining"."""

from __future__ import annotations

from typing import Any

import pytest

from bap_browser.computer import dock


def test_it_runs_the_driver_inside_the_named_container(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(dock.CONTAINER, "the-desktop-7")
    asked: list[list[str]] = []

    class Ran:
        returncode = 0

    def run(argv: list[str], **kwargs: Any) -> Ran:
        asked.append(argv)
        return Ran()

    monkeypatch.setattr(dock.subprocess, "run", run)

    code = dock.main(["manifest"])

    assert code == 0
    assert asked == [["docker", "exec", "-i", "the-desktop-7", "cua-driver", "manifest"]]


def test_without_a_container_it_says_so_and_does_not_call_docker(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv(dock.CONTAINER, raising=False)
    called = False

    def run(*args: Any, **kwargs: Any) -> None:
        nonlocal called
        called = True

    monkeypatch.setattr(dock.subprocess, "run", run)

    code = dock.main(["mcp"])

    assert code == 2
    assert not called
    assert dock.CONTAINER in capsys.readouterr().err


def test_dockers_own_exit_code_is_passed_back(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(dock.CONTAINER, "the-desktop-7")

    class Ran:
        returncode = 17

    monkeypatch.setattr(dock.subprocess, "run", lambda *a, **k: Ran())

    assert dock.main(["mcp"]) == 17


def test_docker_not_being_installed_is_said_plainly(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv(dock.CONTAINER, "the-desktop-7")

    def run(*args: Any, **kwargs: Any) -> None:
        raise FileNotFoundError("no such file")

    monkeypatch.setattr(dock.subprocess, "run", run)

    code = dock.main(["mcp"])

    assert code == 2
    assert "docker" in capsys.readouterr().err
