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


@pytest.mark.parametrize("runs", ["container", "here", "machine", "remote"])
def test_every_desktop_is_driven_through_hermes_driver(runs: str, tmp_path: Path) -> None:
    config = a_config(tmp_path, runs)

    # The driver, the tools offered and what the model is told are the same wherever the desktop is.
    assert isinstance(desktop_driver_for(config), HermesDriver)
    assert "computer_use" in [tool.name for tool in computer_tools_for(config)]
    assert "computer_use" in instructions_for(config)


def test_a_mac_is_named_as_a_machine_or_as_one_elsewhere_and_by_no_word_of_its_own(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="'container', 'here', 'machine' or 'remote'"):
        a_config(tmp_path, "mac")


def test_on_its_own_desktop_the_model_is_told_how_to_reach_the_items_of_a_menu(tmp_path: Path) -> None:
    """A capture there names what is on the screen, and an item of a menu is on it once the menu is open."""
    told = instructions_for(a_config(tmp_path, "container"))

    assert "click the menu, then capture again" in told


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


@pytest.mark.parametrize(
    ("runs", "said"),
    [
        ("container", "Contained desktop, 1280 by 800"),
        ("here", "This machine's own screen"),
        ("machine", "This machine's own screen"),
        ("remote", "A machine elsewhere"),
    ],
)
def test_the_page_says_which_desktop_the_agent_works_on(runs: str, said: str, tmp_path: Path) -> None:
    assert desktop_driver_for(a_config(tmp_path, runs)).description() == said


@pytest.mark.parametrize("runs", ["container", "here"])
def test_a_desktop_of_its_own_is_said_to_run_linux_whatever_the_engine_runs(
    runs: str, tmp_path: Path
) -> None:
    """The contained desktop and the micro VM's own screen are Linux desktops: the page is told so,
    not the system of the machine the engine runs on."""
    driver = desktop_driver_for(a_config(tmp_path, runs))
    assert isinstance(driver, HermesDriver)
    assert driver.system_known == "linux"
