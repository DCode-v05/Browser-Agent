"""`bap-browser doctor` (spec 5.2): what this machine has, said plainly."""

from pathlib import Path

import pytest

from bap_browser import doctor
from bap_browser.cli import main
from bap_browser.config import Config


def launcher(installed: dict[str, str], broken: dict[str, str] | None = None) -> doctor.Launch:
    async def launch(config: Config, channel: str) -> str:
        if broken and channel in broken:
            raise RuntimeError(broken[channel])
        if channel not in installed:
            raise RuntimeError(
                f"BrowserType.launch: Chromium distribution '{channel}' is not found at /opt/x"
            )
        return installed[channel]

    return launch


async def examined(
    tmp_path: Path, launch: doctor.Launch, env: dict[str, str] | None = None, **browser: object
):
    config = Config(data_dir=str(tmp_path / "data"), browser=browser)  # type: ignore[arg-type]
    return await doctor.examine(config, {}, env or {}, launch)


async def test_a_machine_with_everything(tmp_path: Path) -> None:
    found = await examined(
        tmp_path,
        launcher({"chromium": "Chromium 153.0", "chrome": "Chrome 154.0"}),
        {"OPENAI_API_KEY": "sk-x"},
    )
    lines = doctor.report(found).splitlines()
    assert lines[0] == "bap-browser doctor"
    assert "  ok  Browser in use (chromium): Chromium 153.0 launched and opened a page" in lines
    assert "  ok  Browser chrome: Chrome 154.0 launched and opened a page" in lines
    # A browser that is not on the machine is not a fault.
    assert "  --  Browser msedge: not installed" in lines
    assert "  ok  Model key OPENAI_API_KEY: set" in lines
    assert lines[-1] == "Everything bap-browser needs is in place."
    assert doctor.healthy(found)
    assert (tmp_path / "data").is_dir()


async def test_the_key_is_never_shown_and_is_not_needed_for_everything(tmp_path: Path) -> None:
    secret = "sk-proj-very-secret"
    with_key = doctor.report(
        await examined(tmp_path, launcher({"chromium": "Chromium 1"}), {"OPENAI_API_KEY": secret})
    )
    assert secret not in with_key
    without = await examined(tmp_path, launcher({"chromium": "Chromium 1"}))
    assert doctor.healthy(without), "a missing key stops one command, not bap-browser"
    assert "  --  Model key OPENAI_API_KEY: not set." in doctor.report(without)


async def test_the_browser_in_use_must_launch(tmp_path: Path) -> None:
    absent = await examined(tmp_path, launcher({}))
    assert not doctor.healthy(absent)
    report = doctor.report(absent)
    assert (
        "  NO  Browser in use (chromium): it is not installed. Run: uv run playwright install chromium"
    ) in report
    assert report.splitlines()[-1] == "1 thing to put right (marked NO)."

    edge = await examined(tmp_path, launcher({"chromium": "Chromium 1"}), channel="msedge")
    assert "  NO  Browser in use (msedge): it is not installed on this machine" in doctor.report(edge)
    assert "  ok  Browser chromium: Chromium 1 launched and opened a page" in doctor.report(edge)

    crashed = await examined(tmp_path, launcher({}, {"chromium": "Target closed\nstack"}))
    assert "  NO  Browser in use (chromium): it did not launch: Target closed" in doctor.report(crashed)


async def test_a_custom_browser_and_a_browser_that_is_already_running(tmp_path: Path) -> None:
    no_path = await examined(tmp_path, launcher({"chromium": "Chromium 1"}), channel="custom")
    assert "  NO  Browser in use (custom): browser.executable_path is not set" in doctor.report(no_path)

    attached = await examined(tmp_path, launcher({"chromium": "Chromium 1"}), cdp_url="http://127.0.0.1:9222")
    report = doctor.report(attached)
    assert "  ok  Browser in use: one that is already running (browser.cdp_url); not started here" in report
    assert doctor.healthy(attached)


def test_browsers_are_called_by_their_names() -> None:
    names = {
        channel: doctor._product(channel)
        for channel in ("chromium", "chrome", "chrome-beta", "msedge", "msedge-dev")
    }  # pyright: ignore[reportPrivateUsage]
    assert names == {
        "chromium": "Chromium",
        "chrome": "Chrome",
        "chrome-beta": "Chrome Beta",
        "msedge": "Edge",
        "msedge-dev": "Edge Dev",
    }


async def test_a_data_folder_that_cannot_be_written_to(tmp_path: Path) -> None:
    blocker = tmp_path / "data"
    blocker.write_text("a file where the folder should be", encoding="utf-8")
    found = await examined(tmp_path, launcher({"chromium": "Chromium 1"}))
    assert not doctor.healthy(found)
    assert "cannot be written to" in doctor.report(found)


def test_the_command_launches_the_real_browser_and_ends_with_its_verdict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert main(["doctor"]) == 0
    printed = capsys.readouterr().out
    assert "  ok  Browser in use (chromium): Chromium " in printed
    assert printed.rstrip().endswith("Everything bap-browser needs is in place.")
