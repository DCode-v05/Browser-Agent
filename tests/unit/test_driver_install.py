"""The driver of computer use: one pinned version, installed by its checksum (spec 22.2.3)."""

from __future__ import annotations

import hashlib
import io
import json
import re
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

from bap_browser import computer
from bap_browser.cli import main
from bap_browser.computer import commands, driver
from bap_browser.computer.seams.driver_package import installed_package
from bap_browser.config import Config

REPOSITORY = Path(__file__).resolve().parents[2]
SYSTEMS = (("darwin", "arm64"), ("darwin", "x86_64"), ("linux", "x86_64"), ("linux", "aarch64"))
SYSTEMS += (("win32", "AMD64"), ("win32", "ARM64"))


def an_archive(target: str, files: dict[str, bytes]) -> bytes:
    """A release as the driver's makers pack it: one folder, a zip for Windows and a tarball elsewhere."""
    packed = io.BytesIO()
    if target.startswith("win32"):
        with zipfile.ZipFile(packed, "w") as archive:
            for name, data in files.items():
                archive.writestr(name, data)
    else:
        with tarfile.open(fileobj=packed, mode="w:gz") as archive:
            for name, data in files.items():
                entry = tarfile.TarInfo(name)
                entry.size, entry.mode = len(data), 0o755
                archive.addfile(entry, io.BytesIO(data))
    return packed.getvalue()


def a_pin(target: str, data: bytes, version: str = "9.9.9") -> driver.Pin:
    build = driver.Build(url=f"https://example.invalid/{target}", sha256=hashlib.sha256(data).hexdigest())
    return driver.Pin(version=version, builds={target: build})


def test_the_pin_is_one_version_with_a_checksummed_build_for_each_of_the_six_systems() -> None:
    pin = driver.pinned()

    assert re.fullmatch(r"\d+\.\d+\.\d+", pin.version)
    assert {driver.target(system, machine) for system, machine in SYSTEMS} == set(pin.builds)
    for build in pin.builds.values():
        assert build.url.startswith("https://github.com/trycua/cua/releases/download/")
        assert pin.version in build.url
        assert re.fullmatch(r"[0-9a-f]{64}", build.sha256)


@pytest.mark.parametrize(("system", "machine"), SYSTEMS)
def test_the_build_for_a_system_is_unpacked_and_then_found(system: str, machine: str, tmp_path: Path) -> None:
    target = driver.target(system, machine)
    inside = driver.binary_in(target)
    data = an_archive(
        target, {f"cua-driver-rs-9.9.9/{inside}": b"the driver", "cua-driver-rs-9.9.9/sdk/x": b"-"}
    )
    pin = a_pin(target, data)
    asked: list[str] = []

    assert driver.installed(tmp_path, pin, target) is None
    binary = driver.install(tmp_path, pin, target, fetch=lambda url: asked.append(url) or data)

    assert asked == [f"https://example.invalid/{target}"]
    assert binary.read_bytes() == b"the driver"
    assert binary == driver.installed(tmp_path, pin, target)
    assert binary.is_relative_to(tmp_path / "driver" / "9.9.9")
    assert not (tmp_path / "driver" / "9.9.9" / "sdk").exists()


def test_a_download_that_does_not_match_its_checksum_is_refused_and_nothing_is_left(tmp_path: Path) -> None:
    target = driver.target("linux", "x86_64")
    data = an_archive(target, {"cua-driver-rs-9.9.9/cua-driver": b"the driver"})
    pin = a_pin(target, data)

    with pytest.raises(driver.DriverError, match="checksum"):
        driver.install(tmp_path, pin, target, fetch=lambda url: data + b"changed on the way")

    assert driver.installed(tmp_path, pin, target) is None
    assert not list((tmp_path / "driver").glob("*")) if (tmp_path / "driver").exists() else True


def test_an_archive_that_writes_outside_its_folder_is_refused(tmp_path: Path) -> None:
    target = driver.target("linux", "x86_64")
    data = an_archive(target, {"cua-driver-rs-9.9.9/cua-driver": b"x", "../../outside": b"not here"})

    with pytest.raises(driver.DriverError):
        driver.install(tmp_path / "home", a_pin(target, data), target, fetch=lambda url: data)

    assert not (tmp_path / "outside").exists()
    assert driver.installed(tmp_path / "home", a_pin(target, data), target) is None


def test_a_system_the_driver_has_no_build_for_is_named() -> None:
    with pytest.raises(driver.DriverError, match="freebsd"):
        driver.target("freebsd14", "amd64")


def test_a_newer_pin_is_not_answered_by_an_older_install(tmp_path: Path) -> None:
    target = driver.target("linux", "x86_64")
    data = an_archive(target, {"cua-driver-rs-9.9.9/cua-driver": b"the driver"})
    driver.install(tmp_path, a_pin(target, data), target, fetch=lambda url: data)

    assert driver.installed(tmp_path, a_pin(target, data, version="10.0.0"), target) is None


def test_the_copied_code_finds_the_driver_that_was_installed(tmp_path: Path) -> None:
    target = driver.target()
    data = an_archive(target, {f"cua-driver-rs-x/{driver.binary_in(target)}": b"the driver"})
    pin = driver.Pin(driver.pinned().version, {target: a_pin(target, data).builds[target]})
    config = Config.model_validate({"computer": {"base": {"home": str(tmp_path)}}})

    with computer.base(config):
        assert installed_package("cua-driver") is None
        binary = driver.install(tmp_path, pin, fetch=lambda url: data)
        found = installed_package("cua-driver")

    assert found is not None and found.binary == binary


def test_no_driver_version_is_written_anywhere_but_the_lock() -> None:
    a_version = re.compile(r"cua-driver-rs-v?\d+\.\d+\.\d+|CUA_DRIVER_VERSION\s*=\s*\d")
    listed = subprocess.run(
        ["git", "ls-files", "src", "deploy", "scripts", ".github", "desktop", "viewer/src"],
        cwd=REPOSITORY,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    elsewhere = [
        name
        for name in listed
        if "computer/hermes/" not in name
        and not name.endswith(("driver.lock.json", ".png", ".ico", ".woff2"))
        and (REPOSITORY / name).is_file()
        and a_version.search((REPOSITORY / name).read_text(encoding="utf-8", errors="replace"))
    ]

    assert elsewhere == []


def a_config(tmp_path: Path) -> str:
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"computer": {"base": {"home": str(tmp_path / "home")}}}), encoding="utf-8")
    return str(path)


def test_the_doctor_says_how_to_install_a_driver_that_is_not_there(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ended = main(["computer", "doctor", "--config", a_config(tmp_path)])

    assert ended != 0
    assert "bap-browser computer install" in capsys.readouterr().out


def test_the_permissions_command_says_whether_the_driver_is_installed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ended = main(["computer", "permissions", "--config", a_config(tmp_path)])

    said = capsys.readouterr().out
    assert ended != 0
    assert "not installed" in said
    assert "bap-browser computer install" in said


GOOD = {
    "binary_version": "0.21.0",
    "mcp_invocation": {"args": ["mcp"]},
    "subcommands": [
        {"name": "mcp", "args": [{"name": "--socket"}, {"name": "--grant"}]},
        {
            "name": "serve",
            "args": [
                {"name": flag}
                for flag in (
                    "--socket",
                    "--permission-mode",
                    "--capability-manifest",
                    "--approve-capability-manifest",
                    "--embedded",
                )
            ],
        },
        {"name": "stop", "args": [{"name": "--socket"}]},
    ],
}
ON_A_SYSTEM_WITH_SCRIPTS = pytest.mark.skipif(
    sys.platform == "win32", reason="the stand-in driver is a script Windows does not start"
)


def a_driver_that_says(tmp_path: Path, manifest: dict[str, object]) -> Path:
    """A program that answers `manifest` as a driver does, and writes down what else it is asked."""
    binary = tmp_path / "cua-driver"
    asked = tmp_path / "asked.txt"
    binary.write_text(
        f"#!{sys.executable}\nimport json, sys\n"
        f"if sys.argv[1:] == ['manifest']:\n    print(json.dumps({manifest!r}))\n"
        f"else:\n    open({str(asked)!r}, 'a').write(' '.join(sys.argv[1:]) + '\\n')\n",
        encoding="utf-8",
    )
    binary.chmod(0o755)
    return binary


def a_home(tmp_path: Path, **base: object) -> Config:
    return Config.model_validate({"computer": {"base": {"home": str(tmp_path), **base}}})


@ON_A_SYSTEM_WITH_SCRIPTS
def test_a_driver_too_old_to_work_with_is_refused_with_the_reason(tmp_path: Path) -> None:
    old = a_driver_that_says(tmp_path, {"binary_version": "0.9.0", "mcp_invocation": {"args": ["mcp"]}})

    problem = commands.not_ready(a_home(tmp_path), old)

    assert problem is not None and "0.20.0 or newer" in problem


@ON_A_SYSTEM_WITH_SCRIPTS
def test_the_drivers_own_telemetry_is_switched_off_for_good_when_it_is_installed(tmp_path: Path) -> None:
    binary = a_driver_that_says(tmp_path, GOOD)

    commands.not_ready(a_home(tmp_path), binary)

    assert (tmp_path / "asked.txt").read_text(encoding="utf-8").splitlines() == ["telemetry disable"]


@ON_A_SYSTEM_WITH_SCRIPTS
def test_the_drivers_telemetry_is_left_alone_when_the_settings_allow_it(tmp_path: Path) -> None:
    binary = a_driver_that_says(tmp_path, GOOD)

    commands.not_ready(a_home(tmp_path, driver_telemetry=True), binary)

    assert not (tmp_path / "asked.txt").exists()
