"""Holding the agent to the allowed apps on a real machine (spec 22.7, remaining piece 3): the
file `bounded` mode reads is written from the settings, one app named for the system it runs on."""

from __future__ import annotations

import json
from pathlib import Path

from bap_browser import computer
from bap_browser.computer.seams import manifest
from bap_browser.config import Config
from bap_browser.config_computer import AllowedApps, Base


def test_only_the_allowed_apps_are_named_for_each_system() -> None:
    apps = AllowedApps(text_editor=True, files=False, calculator=True, terminal=False)
    base = Base()

    darwin = manifest.build(apps, base, "darwin")
    windows = manifest.build(apps, base, "win32")
    linux = manifest.build(apps, base, "linux")

    assert [app["bundle_id"] for app in darwin["resources"]["apps"]] == [
        "com.apple.TextEdit",
        "com.apple.calculator",
    ]
    assert [app["executable"] for app in windows["resources"]["apps"]] == [
        r"C:\Windows\System32\notepad.exe",
        r"C:\Windows\System32\calc.exe",
    ]
    assert [app["executable"] for app in linux["resources"]["apps"]] == [
        "/usr/bin/mousepad",
        "/usr/bin/galculator",
    ]


def test_no_app_is_allowed_outside_its_own_entry() -> None:
    manifest_dict = manifest.build(AllowedApps(terminal=True), Base(), "win32")
    for app in manifest_dict["resources"]["apps"]:
        assert app["launch"] is True
        assert app["windows"] == "all"


def test_the_manifest_declares_the_version_and_the_tools_the_engine_calls() -> None:
    manifest_dict = manifest.build(AllowedApps(), Base(), "darwin")

    assert manifest_dict["version"] == 3
    assert manifest_dict["expires_after"] == Base().capability_expires_after
    assert manifest_dict["idle_timeout"] == Base().capability_idle_timeout
    assert "click" in manifest_dict["allow"]["tools"]
    assert "type_text" in manifest_dict["allow"]["tools"]


def test_full_screen_capture_stays_open_for_the_persons_own_live_view() -> None:
    manifest_dict = manifest.build(AllowedApps(), Base(), "linux")
    assert manifest_dict["resources"]["desktop"]["display"] is True


def test_the_file_is_written_under_the_given_home(tmp_path: Path) -> None:
    path = manifest.write(tmp_path, AllowedApps(terminal=True), Base(), "linux")

    assert path == tmp_path / "capability-manifest.json"
    assert json.loads(path.read_text(encoding="utf-8")) == manifest.build(
        AllowedApps(terminal=True), Base(), "linux"
    )


def test_a_bounded_session_writes_the_manifest_and_points_the_driver_at_it(tmp_path: Path) -> None:
    config = Config.model_validate(
        {"computer": {"apps": {"terminal": True}, "base": {"permission_mode": "bounded"}}}
    )
    with computer.base(config, home=tmp_path, backend=lambda: None):
        seen = computer.settings_seen()

    assert seen["computer_use"]["permission_mode"] == "bounded"
    written = Path(seen["computer_use"]["capability_manifest"])
    assert written == tmp_path / "capability-manifest.json"
    assert written.exists()


def test_a_standard_session_writes_no_manifest(tmp_path: Path) -> None:
    config = Config.model_validate({"computer": {"base": {"permission_mode": "standard"}}})
    with computer.base(config, home=tmp_path, backend=lambda: None):
        seen = computer.settings_seen()

    assert seen["computer_use"]["permission_mode"] == "standard"
    assert seen["computer_use"]["capability_manifest"] is None
    assert not (tmp_path / "capability-manifest.json").exists()


def test_nothing_is_written_outside_a_real_session() -> None:
    """The bare default state (no session begun) must stay `standard`, with no manifest: Hermes'
    own tests read the copied code's settings against it directly
    (`tests/hermes/test_computer_use_cua_0_10_permissions.py`)."""
    from bap_browser.computer.seams import settings as seams_settings

    seen = seams_settings.load_config()

    assert seen["computer_use"]["permission_mode"] == "standard"
    assert seen["computer_use"]["capability_manifest"] is None
