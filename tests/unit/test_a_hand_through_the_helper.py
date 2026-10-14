"""Take over of a machine elsewhere (spec 22.6.2): a person on the engine's page uses that machine's
mouse and keyboard through the helper there, where its person switched that on."""

import socket
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
import uvicorn
from desktop_stand_in import Desk
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from bap_browser.computer.hermes.computer_use.backend import CaptureResult
from bap_browser.driver.hermes_driver import HermesDriver
from bap_browser.driver.mac_hand import MacHand
from bap_browser.service.machine_helper import Helper, RemoteHand, helper_app
from bap_browser.service.session import ServiceSession
from bap_browser.tools.computer_tools import computer_tools_for

CODE = "the-pairing-code"
FROM_THE_VM = "100.64.0.7"


class Kept:
    """In macOS's place: a screen of 1280 by 800 points, and the events it is given."""

    def __init__(self) -> None:
        self.events: list[tuple[Any, ...]] = []

    def allowed(self) -> bool:
        return True

    def size(self) -> tuple[float, float]:
        return 1280.0, 800.0

    def mouse(self, kind: int, x: float, y: float, button: int, clicks: int) -> None:
        self.events.append(("mouse", kind, x, y, button, clicks))

    def key(self, code: int, down: bool, flags: int, text: str) -> None:
        self.events.append(("key", code, down, flags, text))

    def scroll(self, down: int, right: int) -> None:
        self.events.append(("scroll", down, right))


class Pictured(Desk):
    """A machine elsewhere whose screen is pictured larger than the size the page was first told."""

    def capture(
        self, mode: str = "som", app: str | None = None, pid: int | None = None, window_id: int | None = None
    ) -> CaptureResult:
        if app == "screen":
            return CaptureResult(mode=mode, width=2560, height=1600, png_b64=A_PICTURE)
        return super().capture(mode, app, pid, window_id)


# The smallest picture there is, which is all a picture of the screen needs to be here.
A_PICTURE = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="


def a_helper(tmp_path: Path, said: list[str], kept: Kept | None) -> Helper:
    hand = (
        RemoteHand(kept, MacHand(kept, again_within_s=0.5, again_within_points=4), key_chars=32)
        if kept
        else None
    )
    return Helper(
        driver=["true"],
        code=CODE,
        allowed=("tag:bap-vm",),
        tailnet=True,
        who=lambda address: {"tag:bap-vm"} if address == FROM_THE_VM else set(),
        say=said.append,
        run_timeout_s=5,
        message_bytes=2**20,
        hand=hand,
    )


def asking(code: str = CODE) -> dict[str, str]:
    return {"authorization": f"Bearer {code}", "x-forwarded-for": FROM_THE_VM}


def test_a_person_on_the_engines_page_moves_and_presses_where_they_point(tmp_path: Path) -> None:
    """The engine sends where on the picture, as a share of it: the helper makes it a place on this
    machine's screen, whatever size the picture was."""
    kept, said = Kept(), []
    client = TestClient(helper_app(a_helper(tmp_path, said, kept)))
    with client.websocket_connect("/hand", headers=asking()) as hand:
        hand.send_json({"kind": "pointer", "action": "down", "x": 0.5, "y": 0.25, "button": "left"})
        hand.send_json({"kind": "pointer", "action": "up", "x": 0.5, "y": 0.25, "button": "left"})
        hand.send_json({"kind": "key", "action": "down", "key": "a"})
        hand.send_json({"kind": "wheel", "x": 0.5, "y": 0.25, "dx": 0, "dy": 40})
        hand.send_json({"kind": "nothing of this"})
        hand.send_text("not even json")
        hand.send_json({"kind": "key", "action": "up", "key": "a"})

    assert kept.events == [
        ("mouse", 1, 640.0, 200.0, 0, 1),
        ("mouse", 2, 640.0, 200.0, 0, 1),
        ("key", 0, True, 0, "a"),
        ("mouse", 5, 640.0, 200.0, 0, 0),
        ("scroll", -40, 0),
        ("key", 0, False, 0, "a"),
    ]
    # The person is told a hand is on their machine, and when it is gone. What was typed is not said.
    assert any("mouse and keyboard" in line for line in said)
    assert not any("'a'" in line or " a " in line for line in said)


def test_without_the_switch_on_that_machine_no_hand_is_let_in(tmp_path: Path) -> None:
    client = TestClient(helper_app(a_helper(tmp_path, [], None)))
    with pytest.raises(WebSocketDisconnect), client.websocket_connect("/hand", headers=asking()) as hand:
        hand.receive_text()


def test_a_hand_without_the_pairing_code_is_not_let_in(tmp_path: Path) -> None:
    kept = Kept()
    client = TestClient(helper_app(a_helper(tmp_path, [], kept)))
    with (
        pytest.raises(WebSocketDisconnect),
        client.websocket_connect("/hand", headers=asking("a guess")) as hand,
    ):
        hand.receive_text()
    assert kept.events == []


async def test_the_engine_lends_the_persons_hand_while_they_have_taken_over_and_takes_it_back(
    make_config, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The engine reaches the helper as over the tailnet. While a person on its page has taken
    over, what they do on the picture goes to the machine; after Hand back, nothing does."""
    kept, said = Kept(), []
    served = a_helper(tmp_path, said, kept)
    served.tailnet = False
    with a_helper_on_a_port(served) as address:
        monkeypatch.setenv("BAP_BROWSER_HELPER_TOKEN", CODE)
        config = make_config(
            tmp_path,
            computer={"runs": "remote", "helper_url": address, "base": {"home": str(tmp_path / "home")}},
        )
        driver = HermesDriver(config, backend=Pictured)
        session = ServiceSession(
            config, driver, name="computer", backend="contained_desktop", tools=computer_tools_for
        )
        await session.start()
        try:
            assert not driver.takes_a_hand()
            await driver.control_is("person")
            assert driver.takes_a_hand()
            wide, high = await driver.viewport()
            # The machine's screen is pictured afresh, larger than the size the page was told at the
            # start: the page still works in the size it was told.
            await driver.screenshot(full_page=False, annotate=False)
            await driver.pointer("down", wide / 2, high / 4, "left")
            await driver.key("down", "a")
            await driver.control_is("agent")
            assert not driver.takes_a_hand()
            await driver.pointer("up", wide / 2, high / 4, "left")
        finally:
            await session.close()
        ends = time.monotonic() + 5
        while len(kept.events) < 2 and time.monotonic() < ends:
            time.sleep(0.02)

    assert kept.events == [("mouse", 1, 640.0, 200.0, 0, 1), ("key", 0, True, 0, "a")]


@contextmanager
def a_helper_on_a_port(served: Helper) -> Iterator[str]:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    server = uvicorn.Server(
        uvicorn.Config(helper_app(served), host="127.0.0.1", port=port, log_level="error")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    ends = time.monotonic() + 10
    while not server.started and time.monotonic() < ends:
        time.sleep(0.02)
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=10)
