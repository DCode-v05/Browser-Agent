"""`bap-browser computer`: install the driver, see what is missing, give macOS its permissions
(spec 22.2.2). The same three commands on Windows, macOS and Linux."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from bap_browser import computer
from bap_browser.computer import driver
from bap_browser.computer.hermes.computer_use import cua_backend, cua_backend_daemon, cua_backend_driver
from bap_browser.computer.hermes.computer_use import doctor as their_doctor
from bap_browser.computer.hermes.computer_use import permissions as their_permissions
from bap_browser.config import Config

NOT_INSTALLED = "The driver of computer use is not installed. Run: bap-browser computer install"
# The program of macOS that takes note of where an app is.
REGISTER = (
    "/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"
)
ON_MACOS = (
    "macOS must allow the driver to see the screen and to use the mouse and keyboard. "
    "Run: bap-browser computer permissions grant"
)


def tell(config: Config, binary: Path, *words: str) -> None:
    """Tells the driver something it keeps in its own settings, once."""
    subprocess.run(
        [str(binary), *words],
        capture_output=True,
        env=cua_backend.sanitized_cua_driver_env(),
        timeout=config.computer.base.register_timeout_s,
        check=False,
    )


def not_ready(config: Config, binary: Path, system: str = sys.platform) -> str | None:
    """Why an installed driver cannot be used here, or None when it can. It is asked what it can
    do; on macOS its app must be the makers' own, and the system is told where it is, as Hermes'
    installer does: the driver starts itself through the system by its app's name."""
    with computer.base(config):
        contract = cua_backend_driver.cua_driver_runtime_contract_status(str(binary))
        if not contract["ready"]:
            return f"The driver cannot be used: {contract['reason']}."
        if not config.computer.base.driver_telemetry:
            # The setting in the driver's environment does not reach a daemon the system starts for
            # it, so the driver is told once, in its own settings.
            tell(config, binary, "telemetry", "disable")
        if system == "win32" and config.computer.base.autostart:
            # The driver registers its own logon task, so that it is there before anybody opens a
            # window: a machine driven from elsewhere.
            tell(config, binary, "autostart", "enable")
        if system != "darwin":
            return None
        app = cua_backend_daemon.resolve_cua_driver_app_path(str(binary))
        if app is None:
            return "On macOS the driver must be its signed app, CuaDriver.app, and this is not."
        try:
            cua_backend_daemon.validate_cua_driver_app_signature(app)
            told = subprocess.run(
                [REGISTER, "-f", app],
                capture_output=True,
                text=True,
                timeout=config.computer.base.register_timeout_s,
                check=False,
            )
        except (RuntimeError, OSError, subprocess.SubprocessError) as wrong:
            return f"The driver's app could not be made known to macOS: {wrong}"
        return (
            None
            if told.returncode == 0
            else f"macOS did not take note of the driver's app: {told.stderr.strip()}"
        )


def install(config: Config) -> int:
    """Installs the pinned driver for this system. Says so when it is already there."""
    home, pin = computer.home_of(config), driver.pinned()
    try:
        binary = driver.installed(home)
        if binary is not None:
            print(f"cua-driver {pin.version} is already installed: {binary}")
        else:
            print(f"Downloading cua-driver {pin.version} for {driver.target()} ...")
            binary = driver.install(home, timeout_s=config.computer.base.install_timeout_s)
            print(f"Installed cua-driver {pin.version}: {binary}")
    except driver.DriverError as wrong:
        print(str(wrong))
        return 1
    problem = not_ready(config, binary)
    if problem is not None:
        print(problem)
        return 1
    if sys.platform == "darwin":
        print(ON_MACOS)
    return 0


def doctor(config: Config, as_json: bool) -> int:
    """What the driver itself says is ready and what is not, check by check."""
    with computer.base(config):
        return their_doctor.run_doctor(json_output=as_json)


def permissions(config: Config, grant: bool) -> int:
    """Whether the driver is ready, and on macOS which of the two permissions it has. With `grant`,
    macOS is asked to show its question."""
    with computer.base(config):
        if grant:
            return their_permissions.request_permissions_grant()
        status = their_permissions.computer_use_status()
    if not status["installed"]:
        print(NOT_INSTALLED)
        return 1
    print(f"cua-driver: {status['version'] or 'installed'} ({status['platform']})")
    if status["can_grant"]:
        for field, name in (("accessibility", "Accessibility"), ("screen_recording", "Screen Recording")):
            print(f"  {name}: {'allowed' if status[field] else 'not allowed'}")
        if not status["ready"]:
            print("  To allow them: bap-browser computer permissions grant")
    else:
        print(f"  Nothing to allow on {status['platform']}. The driver is ready: {bool(status['ready'])}")
    for check in status["checks"]:
        if check["status"] != "ok":
            print(f"  {check['label']}: {check['message']}")
    if status["error"]:
        print(f"  {status['error']}")
    return 0 if status["ready"] else 1
