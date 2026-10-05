"""The container image and its configuration (spec 17.2). The image is not built here: these keep the
files that make it in step with the rest."""

import re
from pathlib import Path

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
