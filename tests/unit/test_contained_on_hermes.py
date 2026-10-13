"""The contained desktop driven through Hermes' driver (spec 22.6, arrangement B): the driver runs
inside the desktop's container, and the engine reaches it through the dock."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from bap_browser import computer
from bap_browser.agent.loop import instructions_for
from bap_browser.computer.seams.driver_package import installed_package
from bap_browser.config import Config
from bap_browser.driver.hermes_driver import HermesDriver, desktop_driver_for
from bap_browser.tools.computer_tools import computer_tools_for


def a_config(tmp_path: Path, runs: str, **base: object) -> Config:
    return Config.model_validate({"computer": {"runs": runs, "base": {"home": str(tmp_path), **base}}})


@pytest.mark.parametrize("runs", ["container", "here", "mac", "machine", "remote"])
def test_every_desktop_is_driven_through_hermes_driver(runs: str, tmp_path: Path) -> None:
    config = a_config(tmp_path, runs)

    # The driver, the tools offered and what the model is told are the same wherever the desktop is.
    assert isinstance(desktop_driver_for(config), HermesDriver)
    assert "computer_use" in [tool.name for tool in computer_tools_for(config)]
    assert "computer_use" in instructions_for(config)


def test_for_the_contained_desktop_the_engine_starts_the_dock_in_the_drivers_place(tmp_path: Path) -> None:
    config = a_config(tmp_path, "container")

    with computer.base(config, container="bap-browser-desktop-x"):
        driver = installed_package("cua-driver")
        environment = computer.driver_environment()

    assert driver is not None and driver.binary.name.startswith("bap-browser-driver-dock")
    assert environment["BAP_BROWSER_DOCK_CONTAINER"] == "bap-browser-desktop-x"
    assert "BAP_BROWSER_DOCK_CONTAINER" not in os.environ


def test_the_contained_desktop_is_not_held_by_a_file_on_this_machine(tmp_path: Path) -> None:
    """In the container an app that is not allowed cannot run at all (spec 21.6). The driver there
    cannot read a file of this machine."""
    with computer.base(a_config(tmp_path, "container"), container="x"):
        seen = computer.settings_seen()["computer_use"]

    assert seen["permission_mode"] == "standard"


def test_nothing_of_this_machine_is_lacking_for_a_desktop_in_a_container(tmp_path: Path) -> None:
    assert computer.lacks(a_config(tmp_path / "empty", "container")) is None
