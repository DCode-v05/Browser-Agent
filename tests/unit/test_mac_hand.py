"""A person's hand on a Mac's own screen, through the page's picture (spec 22.3.1): what the page
sends is turned into the events of a Mac's mouse and keyboard."""

import sys
import time
from pathlib import Path
from typing import Any

import pytest
from desktop_stand_in import Desk

from bap_browser.driver.hermes_driver import HermesDriver
from bap_browser.driver.mac_hand import MacHand, MacOS
from bap_browser.service.session import ServiceSession
from bap_browser.tools.computer_tools import computer_tools_for


class Kept:
    """In macOS's place: it keeps the events it is given."""

    def __init__(self, allowed: bool = True) -> None:
        self.events: list[tuple[Any, ...]] = []
        self.is_allowed = allowed

    def allowed(self) -> bool:
        return self.is_allowed

    def size(self) -> tuple[float, float]:
        return 1280.0, 800.0

    def mouse(self, kind: int, x: float, y: float, button: int, clicks: int) -> None:
        self.events.append(("mouse", kind, x, y, button, clicks))

    def key(self, code: int, down: bool, flags: int, text: str) -> None:
        self.events.append(("key", code, down, flags, text))

    def scroll(self, down: int, right: int) -> None:
        self.events.append(("scroll", down, right))


def a_hand(kept: Kept) -> MacHand:
    return MacHand(kept, again_within_s=0.5, again_within_points=4)


def test_a_press_and_a_release_are_the_mouses_own_and_a_second_press_at_once_is_a_double_press() -> None:
    kept = Kept()
    hand = a_hand(kept)
    for _ in range(2):
        hand.pointer("down", 100, 50, "left")
        hand.pointer("up", 100, 50, "left")
    hand.pointer("down", 400, 50, "right")

    assert kept.events == [
        ("mouse", 1, 100, 50, 0, 1),
        ("mouse", 2, 100, 50, 0, 1),
        ("mouse", 1, 100, 50, 0, 2),
        ("mouse", 2, 100, 50, 0, 2),
        # Somewhere else, with another button: a first press again.
        ("mouse", 3, 400, 50, 1, 1),
    ]


def test_a_move_with_a_button_held_drags() -> None:
    kept = Kept()
    hand = a_hand(kept)
    hand.pointer("move", 10, 10, "left")
    hand.pointer("down", 10, 10, "left")
    hand.pointer("move", 60, 10, "left")
    hand.pointer("up", 60, 10, "left")
    hand.pointer("move", 70, 10, "left")

    assert [event[1] for event in kept.events] == [5, 1, 6, 2, 5]


def test_a_character_is_given_as_itself_and_a_command_as_its_key() -> None:
    kept = Kept()
    hand = a_hand(kept)
    hand.key("down", "é")
    hand.key("down", "Enter")
    hand.key("down", "Meta")
    hand.key("down", "c")
    hand.key("up", "c")
    hand.key("up", "Meta")
    hand.key("down", "c")

    assert kept.events == [
        ("key", 0, True, 0, "é"),
        ("key", 36, True, 0, ""),
        ("key", 55, True, 0x100000, ""),
        # cmd+c: the key of C, with the command held, so that the app copies.
        ("key", 8, True, 0x100000, ""),
        ("key", 8, False, 0x100000, ""),
        ("key", 55, False, 0, ""),
        ("key", 0, True, 0, "c"),
    ]


def test_the_wheel_turns_the_way_the_page_was_turned() -> None:
    kept = Kept()
    hand = a_hand(kept)
    hand.wheel(0, 120)
    hand.wheel(0, 0)

    assert kept.events == [("scroll", -120, 0)]


async def a_session(make_config, tmp_path: Path, kept: Kept | None) -> ServiceSession:
    config = make_config(tmp_path, computer={"runs": "machine", "base": {"home": str(tmp_path / "home")}})
    driver = HermesDriver(config, backend=Desk, macos=(lambda: kept) if kept else None)
    session = ServiceSession(
        config, driver, name="computer", backend="contained_desktop", tools=computer_tools_for
    )
    await session.start()
    return session


async def test_on_a_mac_that_allows_it_a_press_on_the_picture_lands_at_that_place_on_the_screen(
    make_config, tmp_path: Path
) -> None:
    """The page works in the points of the Mac's screen, 1280 by 800 here, whatever size the
    picture is: a press in the middle of the picture is in the middle of the screen."""
    kept = Kept()
    session = await a_session(make_config, tmp_path, kept)
    try:
        driver = session.browser.started_driver
        assert isinstance(driver, HermesDriver) and driver.takes_a_hand()
        wide, high = await driver.viewport()
        assert (wide, high) == (1280, 800)
        await driver.pointer("down", wide / 2, high / 2, "left")
        await driver.pointer("up", wide / 2, high / 2, "left")
        await driver.key("down", "a")
        await driver.wheel(wide / 2, high / 2, 0, 30)
    finally:
        await session.close()

    assert kept.events == [
        ("mouse", 1, 640.0, 400.0, 0, 1),
        ("mouse", 2, 640.0, 400.0, 0, 1),
        ("key", 0, True, 0, "a"),
        ("mouse", 5, 640.0, 400.0, 0, 0),
        ("scroll", -30, 0),
    ]


async def test_a_mac_that_has_not_allowed_it_is_sent_nothing_and_says_so(make_config, tmp_path: Path) -> None:
    kept = Kept(allowed=False)
    session = await a_session(make_config, tmp_path, kept)
    try:
        driver = session.browser.started_driver
        assert isinstance(driver, HermesDriver) and not driver.takes_a_hand()
        await driver.pointer("down", 400, 300, "left")
    finally:
        await session.close()

    assert kept.events == []


@pytest.mark.skipif(
    sys.platform != "darwin" or not MacOS().allowed(),
    reason="a test about macos, where this program is allowed under Accessibility",
)
def test_macos_itself_moves_the_pointer_where_it_is_told() -> None:
    """The real system: macOS takes the event and the pointer is where it was told to be."""
    macos = MacOS()
    wide, high = macos.size()
    assert wide > 0 and high > 0
    before = macos.pointer_at()
    try:
        MacHand(macos, again_within_s=0.5, again_within_points=4).pointer("move", 200, 200, "left")
        # macOS takes an event in its own time.
        ends = time.monotonic() + 2
        while [round(value) for value in macos.pointer_at()] != [200, 200] and time.monotonic() < ends:
            time.sleep(0.02)
        assert [round(value) for value in macos.pointer_at()] == [200, 200]
    finally:
        macos.mouse(5, *before, 0, 0)
