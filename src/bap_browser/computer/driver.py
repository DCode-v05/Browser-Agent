"""The driver of computer use, `cua-driver`: one pinned version, fetched by its checksum (spec 22.2.3).

`driver.lock.json`, beside this file, is the only place a version of the driver is written. The
installer, the desktop's image and the micro VM's all read it.
"""

from __future__ import annotations

import hashlib
import io
import json
import platform
import shutil
import sys
import tarfile
import urllib.error
import urllib.request
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

LOCK = Path(__file__).with_name("driver.lock.json")
# How each kind of processor is named by the systems that report it.
PROCESSORS = {"arm64": "arm64", "aarch64": "arm64", "x86_64": "x64", "amd64": "x64"}
# Where the driver's program is in what is unpacked. On macOS it is inside the signed app, and is
# started from there: the permissions a person gives belong to that app.
BINARY = {
    "darwin": "CuaDriver.app/Contents/MacOS/cua-driver",
    "win32": "cua-driver.exe",
    "linux": "cua-driver",
}
# The makers' kit for other programs. Not used here, and not kept.
NOT_KEPT = "sdk"


class DriverError(Exception):
    """The driver could not be installed. The message is for the person who ran the command."""


@dataclass(frozen=True)
class Build:
    url: str
    sha256: str


@dataclass(frozen=True)
class Pin:
    version: str
    builds: dict[str, Build]


def pinned() -> Pin:
    """The version this engine installs and starts, with its build for each system."""
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    return Pin(lock["version"], {name: Build(**build) for name, build in lock["builds"].items()})


def target(system: str | None = None, machine: str | None = None) -> str:
    """The name of this system's build, such as `darwin-arm64`."""
    system = system or sys.platform
    kind = next((name for name in BINARY if system.startswith(name)), None)
    processor = PROCESSORS.get((machine or platform.machine()).lower())
    if kind is None or processor is None:
        raise DriverError(
            f"The driver of computer use has no build for {system} on {machine or platform.machine()}. "
            "It is built for macOS, Windows and Linux, on x86_64 and arm64."
        )
    return f"{kind}-{processor}"


def binary_in(target_name: str) -> str:
    """Where the driver's program is, inside what is unpacked for a system."""
    return BINARY[target_name.split("-")[0]]


def folder(home: Path, pin: Pin) -> Path:
    return home / "driver" / pin.version


def installed(home: Path, pin: Pin | None = None, target_name: str | None = None) -> Path | None:
    """The pinned driver's program, when it is installed in `home`. An older version is not it."""
    pin, target_name = pin or pinned(), target_name or target()
    binary = folder(home, pin) / binary_in(target_name)
    return binary if binary.is_file() else None


def download(url: str, timeout_s: float) -> bytes:
    try:
        with urllib.request.urlopen(url, timeout=timeout_s) as answer:
            return answer.read()
    except (urllib.error.URLError, TimeoutError) as wrong:
        raise DriverError(f"The driver could not be downloaded from {url}: {wrong}") from wrong


def unpack(data: bytes, into: Path) -> None:
    """Unpacks a release into a folder, and refuses one that names a file outside it."""
    into.mkdir(parents=True)
    if zipfile.is_zipfile(io.BytesIO(data)):
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            for name in archive.namelist():
                if PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts:
                    raise DriverError(f"The driver's archive names a file outside its folder: {name}")
            archive.extractall(into)
        return
    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:*") as archive:
            archive.extractall(into, filter="data")
    except (tarfile.TarError, OSError) as wrong:
        raise DriverError(f"The driver's archive could not be unpacked: {wrong}") from wrong


def install(
    home: Path,
    pin: Pin | None = None,
    target_name: str | None = None,
    fetch: Callable[[str], bytes] | None = None,
    timeout_s: float = 0.0,
) -> Path:
    """Installs the pinned driver for a system into `home` and returns its program. What was
    downloaded is unpacked only when it has the checksum the pin records."""
    pin, target_name = pin or pinned(), target_name or target()
    build = pin.builds.get(target_name)
    if build is None:
        raise DriverError(f"The pinned driver, {pin.version}, has no build for {target_name}.")
    data = fetch(build.url) if fetch is not None else download(build.url, timeout_s)
    found = hashlib.sha256(data).hexdigest()
    if found != build.sha256:
        raise DriverError(
            f"The driver that was downloaded does not have the pinned checksum: {found} and not "
            f"{build.sha256}. Nothing was installed."
        )
    final = folder(home, pin)
    partial = final.with_name(final.name + ".partial")
    shutil.rmtree(partial, ignore_errors=True)
    try:
        unpack(data, partial)
        # A release is one folder. What is in it becomes the version's folder.
        inside = [entry for entry in partial.iterdir()]
        root = inside[0] if len(inside) == 1 and inside[0].is_dir() else partial
        shutil.rmtree(root / NOT_KEPT, ignore_errors=True)
        binary = root / binary_in(target_name)
        if not binary.is_file():
            raise DriverError(f"The driver's archive does not hold {binary_in(target_name)}.")
        binary.chmod(binary.stat().st_mode | 0o111)
        shutil.rmtree(final, ignore_errors=True)
        root.rename(final)
    finally:
        shutil.rmtree(partial, ignore_errors=True)
    return final / binary_in(target_name)
