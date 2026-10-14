"""Take over of a Linux desktop elsewhere (spec 22.6.2): a person's hand on the engine's page reaches
that desktop's X screen through the helper there, as the commands of xdotool."""

from bap_browser.driver.x11_hand import X11Hand
from bap_browser.service.machine_helper import RemoteHand


class Screen:
    """In the X screen's place: 1280 by 800, and the lines it is sent."""

    def __init__(self) -> None:
        self.sent: list[str] = []

    def size(self) -> tuple[float, float]:
        return 1280.0, 800.0

    def send(self, line: str) -> None:
        self.sent.append(line)


def a_hand(screen: Screen) -> RemoteHand:
    return RemoteHand(screen, X11Hand(screen), key_chars=32)


def test_where_a_person_points_and_presses_is_that_place_on_the_x_screen() -> None:
    screen = Screen()
    hand = a_hand(screen)
    hand.given({"kind": "pointer", "action": "move", "x": 0.5, "y": 0.25, "button": "left"})
    hand.given({"kind": "pointer", "action": "down", "x": 0.5, "y": 0.25, "button": "left"})
    hand.given({"kind": "pointer", "action": "up", "x": 0.5, "y": 0.25, "button": "right"})

    assert screen.sent == [
        "mousemove 640 200",
        "mousemove 640 200 mousedown 1",
        "mousemove 640 200 mouseup 3",
    ]


def test_keys_and_the_wheel_are_the_x_screens_own() -> None:
    screen = Screen()
    hand = a_hand(screen)
    hand.given({"kind": "key", "action": "down", "key": "Enter"})
    hand.given({"kind": "key", "action": "up", "key": "a"})
    hand.given({"kind": "key", "action": "down", "key": "no such key at all"})
    hand.given({"kind": "wheel", "x": 0.5, "y": 0.5, "dx": 0, "dy": 40})

    assert screen.sent == ["keydown Return", "keyup a", "mousemove 640 400", "click 5"]


def test_nothing_that_is_no_hand_reaches_the_screen() -> None:
    screen = Screen()
    hand = a_hand(screen)
    for odd in (
        {"kind": "pointer", "action": "down", "x": "a", "y": 1, "button": "left"},
        {"kind": "exec", "line": "rm -rf /"},
        "text",
        None,
    ):
        hand.given(odd)

    assert screen.sent == []
