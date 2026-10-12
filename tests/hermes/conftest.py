"""Hermes' own tests of the code taken from it (spec 22.10), run here against our seams.

The test files in this folder are Hermes', taken by `scripts/take_hermes.py` and never edited by
hand. This file is ours: it gives each test what Hermes' own fixtures gave it there, a home folder
of its own and no backend left over from the test before.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from bap_browser.computer.hermes.computer_use import tool
from bap_browser.computer.seams.state import Working, work_for


@pytest.fixture(autouse=True)
def a_home_of_its_own(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.delenv("BAP_BROWSER_CUA_DRIVER_CMD", raising=False)
    before = work_for(Working(home=tmp_path))
    yield
    tool.reset_backend_for_tests()
    work_for(before)


# Hermes' tests of what was not taken from it: its package manager, its own modules, its settings
# file. Each is named with the reason, and is left out of the run. A name that matches no test is an
# error, so the list cannot outlive the tests it names.
NOT_HERE = Path(__file__).with_name("not_here.json")


def leave_out(config: pytest.Config, items: list[pytest.Item]) -> None:
    ours = [item for item in items if Path(str(item.fspath)).parent == NOT_HERE.parent]
    if not ours:
        return
    not_here: dict[str, str] = json.loads(NOT_HERE.read_text(encoding="utf-8"))
    names = {item.nodeid.split("/")[-1]: item for item in ours}
    whole_files = {Path(str(item.fspath)).name for item in ours}
    stale = [name for name in not_here if name not in names and name.split("::")[0] in whole_files]
    if stale:
        raise pytest.UsageError(f"tests/hermes/not_here.json names tests that are not there: {stale}")
    left_out = [names[name] for name in not_here if name in names]
    config.hook.pytest_deselected(items=left_out)
    items[:] = [item for item in items if item not in left_out]


# Hermes marks a test with the systems it is about: `platforms("linux")`, `platforms("not macos")`.
SYSTEMS = {
    "linux": ("linux",),
    "macos": ("darwin",),
    "windows": ("win32",),
    "posix": ("linux", "darwin"),
    "any": ("linux", "darwin", "win32"),
}


def runs_here(wanted: tuple[str, ...], system: str) -> bool:
    """Whether a test marked for `wanted` runs on `system`: on any it names, and on none it rules out."""
    named = [spec for spec in wanted if not spec.startswith("not ")]
    ruled_out = [spec.removeprefix("not ").strip() for spec in wanted if spec.startswith("not ")]
    if any(system in SYSTEMS[spec] for spec in ruled_out):
        return False
    return not named or any(system in SYSTEMS[spec] for spec in named)


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "platforms(*systems): the systems a test of Hermes is about")
    config.addinivalue_line(
        "markers", "live_system_guard_bypass: a test of Hermes that starts a real program"
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    leave_out(config, items)
    system = "linux" if sys.platform.startswith("linux") else sys.platform
    for item in items:
        for mark in item.iter_markers("platforms"):
            wanted = tuple(str(spec).strip().lower() for spec in mark.args)
            item.add_marker(
                pytest.mark.skipif(not runs_here(wanted, system), reason=f"a test about {', '.join(wanted)}")
            )


@pytest.fixture
def grant_computer_use_approvals() -> Iterator[None]:
    """Hermes' fixture of this name: every question of the copied tool is answered with a yes."""
    tool.set_approval_callback(lambda command, description, **more: "once")
    yield
    tool.set_approval_callback(None)
