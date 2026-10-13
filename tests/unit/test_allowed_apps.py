"""The agent held to the allowed apps on a real machine (spec 22.7): the list of apps in the settings
becomes the file the driver itself enforces, in the driver's own format."""

from __future__ import annotations

import json
from pathlib import Path

from bap_browser import computer
from bap_browser.computer import allowed
from bap_browser.config import Config


def a_machine(tmp_path: Path, **settings: object) -> Config:
    base = {"home": str(tmp_path), **settings.pop("base", {})}  # type: ignore[dict-item]
    return Config.model_validate({"computer": {"runs": "machine", **settings, "base": base}})


def found_in(folder: str):
    """Finds every program in one folder, as a system that has them all installed would."""
    return lambda name: f"{folder}/{name}"


def test_on_macos_each_allowed_app_is_named_by_its_bundle_and_the_terminal_is_left_out(
    tmp_path: Path,
) -> None:
    listed = allowed.manifest(a_machine(tmp_path).computer, "darwin", found_in("/usr/bin"))

    apps = listed["resources"]["apps"]
    assert [app["bundle_id"] for app in apps] == [
        "com.apple.TextEdit",
        "com.apple.finder",
        "com.apple.calculator",
    ]
    assert all(app["launch"] is True and "executable" not in app for app in apps)


def test_on_windows_and_linux_each_allowed_app_is_named_by_its_program_in_full(tmp_path: Path) -> None:
    settings = a_machine(tmp_path, apps={"terminal": True}).computer

    on_windows = allowed.manifest(settings, "win32", found_in("C:/Windows/System32"))
    on_linux = allowed.manifest(settings, "linux", found_in("/usr/bin"))

    assert "C:/Windows/System32/notepad.exe" in [app["executable"] for app in on_windows["resources"]["apps"]]
    assert [app["executable"] for app in on_linux["resources"]["apps"]] == [
        "/usr/bin/mousepad",
        "/usr/bin/pcmanfm",
        "/usr/bin/galculator",
        "/usr/bin/xterm",
    ]


def test_an_app_this_machine_does_not_have_is_left_out(tmp_path: Path) -> None:
    listed = allowed.manifest(a_machine(tmp_path).computer, "linux", lambda name: None)

    assert listed["resources"]["apps"] == []


def test_the_admin_can_allow_more_apps_by_bundle_or_by_program(tmp_path: Path) -> None:
    more = ["com.example.Notes", "/opt/tools/zenity"]
    settings = a_machine(tmp_path, base={"also_allowed": more}).computer

    apps = allowed.manifest(settings, "linux", found_in("/usr/bin"))["resources"]["apps"]

    assert {"bundle_id": "com.example.Notes", "launch": True} in apps
    assert {"executable": "/opt/tools/zenity", "launch": True} in apps


def test_the_file_is_in_the_form_the_driver_takes_in_its_bounded_mode(tmp_path: Path) -> None:
    listed = allowed.manifest(a_machine(tmp_path).computer, "darwin", found_in("/usr/bin"))

    # The driver refuses a file that names a mode, and one for bounded mode with no lifetimes.
    assert listed["version"] == 3 and "mode" not in listed
    assert listed["expires_after"] and listed["idle_timeout"]
    assert {"get_window_state", "click", "type_text", "launch_app"} <= set(listed["allow"]["tools"])
    # Nothing that updates the driver or changes its settings is among them.
    assert not {"check_for_update", "set_telemetry"} & set(listed["allow"]["tools"])


def test_on_a_machine_the_driver_is_started_held_to_the_file(tmp_path: Path) -> None:
    with computer.base(a_machine(tmp_path)):
        seen = computer.settings_seen()["computer_use"]
        written = json.loads(Path(seen["capability_manifest"]).read_text(encoding="utf-8"))

    assert seen["permission_mode"] == "bounded"
    assert written["version"] == 3


def test_where_the_person_allows_any_app_the_driver_is_not_held(tmp_path: Path) -> None:
    with computer.base(a_machine(tmp_path, mac_any_app=True)):
        seen = computer.settings_seen()["computer_use"]

    assert seen["permission_mode"] == "standard"
    assert seen["capability_manifest"] is None


def test_an_admin_who_sets_the_mode_to_standard_is_not_overruled(tmp_path: Path) -> None:
    with computer.base(a_machine(tmp_path, base={"permission_mode": "standard"})):
        seen = computer.settings_seen()["computer_use"]

    assert seen["permission_mode"] == "standard"
