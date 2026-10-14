"""The container image and its configuration (spec 17.2). The image is not built here: these keep the
files that make it in step with the rest."""

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from bap_browser.config import load_config

ROOT = Path(__file__).parents[2]
DOCKERFILE = (ROOT / "deploy" / "Dockerfile").read_text(encoding="utf-8")


def test_the_image_has_the_browser_of_the_version_the_lock_file_names() -> None:
    lock = (ROOT / "uv.lock").read_text(encoding="utf-8")
    locked = re.search(r'name = "playwright"\nversion = "([^"]+)"', lock)
    assert locked, "the lock file names no playwright version"
    assert f"FROM mcr.microsoft.com/playwright/python:v{locked.group(1)}-noble" in DOCKERFILE


def test_the_configuration_in_the_image_is_valid_and_made_for_a_machine_others_reach() -> None:
    config = load_config(str(ROOT / "deploy" / "config.vm.json"))
    assert config.server.host == "0.0.0.0"
    assert config.browser.headless is True
    # A container has no user namespaces for the browser's own sandbox, and little shared memory.
    assert config.browser.chromium_sandbox is False
    assert "--disable-dev-shm-usage" in config.browser.args
    assert config.safety.block_private_networks is True
    # What the service writes goes to the one folder its user owns.
    assert config.server.state_file.startswith("/data/")
    assert str(config.logging.event_log).startswith("/data/")


def test_the_image_runs_as_an_unprivileged_user_and_carries_no_secret() -> None:
    lines = [line.strip() for line in DOCKERFILE.splitlines()]
    lines = [line for line in lines if line and not line.startswith("#")]
    assert lines.index("USER pwuser") < next(i for i, line in enumerate(lines) if line.startswith("CMD "))
    assert not [line for line in lines if re.match(r"(ENV|ARG)\b.*(TOKEN|API_KEY|PASSWORD)\s*=", line)]
    ignored = (ROOT / ".dockerignore").read_text(encoding="utf-8").split()
    assert ".env" in ignored and "config.json" in ignored
    assert lines[-1] == 'CMD ["uv", "run", "--project", "/app", "--no-sync", "bap-browser", "serve"]'


START = (ROOT / "deploy" / "vm-start.sh").read_text(encoding="utf-8")


def test_the_vm_joins_a_tailnet_only_when_it_is_given_a_key_and_then_forgets_the_key() -> None:
    """Spec 21.12: the key comes from the environment, never the image, and the service never has it."""
    lines = [
        line.strip() for line in DOCKERFILE.splitlines() if line.strip() and not line.strip().startswith("#")
    ]
    assert 'ENTRYPOINT ["/usr/local/bin/vm-start"]' in lines
    assert lines.index('ENTRYPOINT ["/usr/local/bin/vm-start"]') < len(lines) - 1, (
        "the service stays the command"
    )
    assert 'if [ -n "${TS_AUTHKEY:-}" ]' in START
    assert "unset TS_AUTHKEY" in START and START.index("unset TS_AUTHKEY") < START.index('exec "$@"')
    # The key's value is never written out: not echoed, not logged.
    assert not [line for line in START.splitlines() if "echo" in line and "$TS_AUTHKEY" in line]
    assert "--state=mem:" in START, "the VM's node is ephemeral: it leaves the tailnet when the VM ends"
    # With its state in memory a node has no folder for the HTTPS certificate `tailscale serve`
    # fetches: without one, every HTTPS call to the viewer fails with "no TailscaleVarRoot".
    assert '--statedir="$certs"' in START and "certs=$(mktemp -d)" in START


def test_the_image_with_a_desktop_installs_the_pinned_driver_and_names_no_version_of_it() -> None:
    """Spec 22.2.3: the micro VM's image reads the one lock file, through the engine's own installer."""
    assert "bap-browser computer install" in DOCKERFILE
    assert DOCKERFILE.index("USER pwuser") < DOCKERFILE.index("bap-browser computer install"), (
        "the driver is installed for the user the service runs as"
    )
    assert "at-spi2-core" in DOCKERFILE, "the driver reads a Linux app's elements through AT-SPI"
    assert not re.search(r"cua-driver-rs-v?\d|CUA_DRIVER_VERSION", DOCKERFILE)


def test_the_vm_gives_its_desktop_a_session_bus_when_it_has_one_to_give() -> None:
    """The driver finds a Linux app's elements on the session's bus. Without a desktop there is none."""
    assert "dbus-run-session" in START
    assert START.rstrip().splitlines()[-1].startswith("exec ")


@pytest.mark.skipif(
    sys.platform == "win32", reason="the script is for a Linux box, and the stand-in docker is a script"
)
def test_the_box_desktop_keeps_what_it_wrote_when_its_container_is_made_again(tmp_path: Path) -> None:
    """`deploy/box-desktop.sh` removes the old container and starts a new one. The desktop's task
    records, its settings and sign-ins stay in a volume that outlives both."""
    home, bin_dir = tmp_path / "home", tmp_path / "bin"
    (home / ".bap-box").mkdir(parents=True)
    (home / ".bap-box" / "docker-env").write_text("", encoding="utf-8")
    bin_dir.mkdir()
    asked = tmp_path / "docker-asked.txt"
    docker = bin_dir / "docker"
    docker.write_text(f'#!/bin/sh\nprintf "%s\\n" "$*" >> {asked}\n', encoding="utf-8")
    docker.chmod(0o755)
    env = {
        **os.environ,
        "HOME": str(home),
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "TS_AUTHKEY": "stand-in",
        "ANTHROPIC_API_KEY": "stand-in",
    }

    for _ in range(2):
        subprocess.run(
            ["bash", str(ROOT / "deploy" / "box-desktop.sh"), "you@example.com"],
            env=env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=True,
        )

    runs = [line for line in asked.read_text(encoding="utf-8").splitlines() if line.startswith("run ")]
    assert len(runs) == 2
    assert all("-v bap-desk-data:/data " in run for run in runs), runs
