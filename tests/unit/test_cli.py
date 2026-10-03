import json
import os
from pathlib import Path

import pytest

from bap_browser.cli import main


@pytest.fixture(autouse=True)
def no_settings_from_the_test_run(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in [name for name in os.environ if name.startswith("BAP_BROWSER")]:
        monkeypatch.delenv(name)


def write(path: Path, data: object) -> Path:
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_show_prints_the_effective_configuration(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    file = write(tmp_path / "config.json", {"browser": {"headless": False}})
    assert main(["config", "show", "--config", str(file)]) == 0
    assert json.loads(capsys.readouterr().out)["browser"]["headless"] is False


def test_show_sources_lists_only_what_was_overridden(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    file = write(tmp_path / "config.json", {"browser": {"headless": False}})
    assert main(["config", "show", "--config", str(file), "--sources"]) == 0
    assert capsys.readouterr().out.strip() == "browser.headless = false  (config.json)"


def test_show_sources_with_nothing_overridden(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    file = write(tmp_path / "config.json", {})
    assert main(["config", "show", "--config", str(file), "--sources"]) == 0
    assert capsys.readouterr().out.strip() == "Every value is at its default."


def test_init_writes_a_starter_file_and_never_overwrites(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target = tmp_path / "my folder" / "config.json"
    target.parent.mkdir()
    assert main(["config", "init", str(target)]) == 0
    starter = json.loads(target.read_text(encoding="utf-8"))
    assert starter["browser"] == {"channel": "chromium", "headless": True}
    assert main(["config", "init", str(target)]) == 2
    assert "already exists" in capsys.readouterr().err
    assert json.loads(target.read_text(encoding="utf-8")) == starter


def test_init_full_lists_every_key(tmp_path: Path) -> None:
    target = tmp_path / "config.json"
    assert main(["config", "init", str(target), "--full"]) == 0
    full = json.loads(target.read_text(encoding="utf-8"))
    assert full["browser"]["timeouts"]["action_ms"] == 10000
    assert full["safety"]["block_cloud_metadata"] is True


def test_a_full_file_loads_back_unchanged(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    target = tmp_path / "config.json"
    main(["config", "init", str(target), "--full"])
    capsys.readouterr()
    assert main(["config", "show", "--config", str(target), "--sources"]) == 0
    assert "(config.json)" in capsys.readouterr().out


def test_doc_has_every_section_and_key(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["config", "doc"]) == 0
    out = capsys.readouterr().out
    assert "**Top level**" in out
    assert "**`browser.timeouts`**" in out
    assert "| `action_ms` | `10000` | One action, including waiting for the element |" in out
    assert "| `executable_path` | none | Required for `custom`; overrides any channel |" in out
    assert '| `standard` | `{"max_fps": 24, "jpeg_quality": 70, "max_width": 1280}` |' in out


def test_an_error_goes_to_the_error_stream_and_returns_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["config", "show", "--config", str(tmp_path / "missing.json")]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("error: config file not found")


def test_version_is_printed(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as stop:
        main(["--version"])
    assert stop.value.code == 0
    assert capsys.readouterr().out.strip() == "bap-browser 0.1.0"
