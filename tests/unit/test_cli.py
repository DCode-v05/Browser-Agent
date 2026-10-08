import json
import os
from pathlib import Path

import pytest

from bap_browser.cli import main


@pytest.fixture(autouse=True)
def no_settings_from_the_test_run(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    for name in [name for name in os.environ if name.startswith("BAP_BROWSER")]:
        monkeypatch.delenv(name)
    # The command reads a .env file in the folder it is run from. The developer's own must not be read.
    monkeypatch.chdir(tmp_path)


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


def test_settings_in_a_dot_env_file_beside_the_command_are_used(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / ".env").write_text("BAP_BROWSER__BROWSER__HEADLESS=false\n", encoding="utf-8")
    file = write(tmp_path / "config.json", {})
    assert main(["config", "show", "--config", str(file), "--sources"]) == 0
    assert capsys.readouterr().out.strip() == "browser.headless = false  (environment)"


def test_the_agent_command_can_show_its_browser(make_config, tmp_path: Path) -> None:
    from bap_browser.cli import build_parser, with_visible_browser

    assert build_parser().parse_args(["agent", "--show-browser", "--chat"]).show_browser is True
    assert build_parser().parse_args(["agent", "Read the page"]).show_browser is False
    config = make_config(tmp_path, browser={"channel": "chrome"})
    assert config.browser.headless is True and config.browser.viewport is not None
    shown = with_visible_browser(config)
    # A window a person watches: it is on screen, and the page is as large as the window.
    assert shown.browser.headless is False and shown.browser.viewport is None
    assert shown.browser.channel == "chrome", "nothing else about the browser changes"
    assert config.browser.headless is True, "the configuration it was made from is left as it was"


def test_the_extension_goes_with_the_chat(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    from bap_browser.cli import build_parser

    assert build_parser().parse_args(["agent", "--chat", "--extension"]).extension is True
    assert build_parser().parse_args(["agent", "--chat"]).extension is False
    os.chdir(tmp_path)
    assert main(["agent", "--extension", "Read the page"]) == 2
    assert "Use --extension together with --chat" in capsys.readouterr().err


def test_serve_is_a_command_with_the_browser_shown_or_not() -> None:
    from bap_browser.cli import build_parser

    args = build_parser().parse_args(["serve", "--show-browser", "--open"])
    assert (args.command, args.show_browser, args.open) == ("serve", True, True)
    assert build_parser().parse_args(["serve"]).show_browser is False
