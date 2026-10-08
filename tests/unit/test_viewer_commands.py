"""What a viewer sends is done in the order it was sent, and no more of it is kept waiting than the
configured number (spec 4.8)."""

import asyncio
import json
from collections import deque
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from fakes import FakeDriver

from bap_browser.config import Config
from bap_browser.service.session import ServiceSession
from bap_browser.service.viewer_socket import serve_viewer


class Viewer:
    """Stands in for a viewer's connection: it hands over what the viewer sent, then stays open
    until the viewer leaves."""

    def __init__(self, commands: list[dict[str, Any]]) -> None:
        self._commands = deque(commands)
        self.all_read = asyncio.Event()
        self.leave = asyncio.Event()

    async def receive(self) -> dict[str, Any]:
        if self._commands:
            return {"type": "websocket.receive", "text": json.dumps(self._commands.popleft())}
        self.all_read.set()
        await self.leave.wait()
        return {"type": "websocket.disconnect", "code": 1000}

    async def send_text(self, text: str) -> None:
        pass

    async def send_bytes(self, data: bytes) -> None:
        pass


async def served(session: ServiceSession, commands: list[dict[str, Any]], backlog: int) -> None:
    """Serves one viewer that sends these commands all at once and leaves when they have been done."""
    viewer = Viewer(commands)
    _, subscriber = session.hub.subscribe()
    serving = asyncio.create_task(serve_viewer(cast(Any, viewer), session, subscriber, backlog))
    await viewer.all_read.wait()
    for _ in range(8):
        await asyncio.sleep(0)
    viewer.leave.set()
    await serving
    session.hub.unsubscribe(subscriber)


def press(x: int) -> dict[str, Any]:
    return {"type": "pointer", "action": "down", "x": x, "y": 1, "button": 0}


async def test_commands_are_done_in_the_order_they_were_sent(
    make_config: Callable[..., Config], tmp_path: Path
) -> None:
    driver = FakeDriver()
    session = ServiceSession(make_config(tmp_path), driver)
    await session.start()
    await served(session, [{"type": "take_over"}, press(1), press(2), {"type": "hand_back"}, press(3)], 16)
    assert [call[1][1] for call in driver.calls if call[0] == "pointer" and call[1][0] == "down"] == [1, 2]
    assert session.control == "agent"
    await session.close()


async def test_no_more_commands_are_kept_waiting_than_the_limit(
    make_config: Callable[..., Config], tmp_path: Path
) -> None:
    driver = FakeDriver()
    session = ServiceSession(make_config(tmp_path), driver)
    await session.start()
    await session.handle({"type": "take_over"})
    await served(session, [press(x) for x in range(1, 11)], 4)
    assert [call[1][1] for call in driver.calls if call[0] == "pointer"] == [1, 2, 3, 4]
    await session.close()


async def test_stop_is_done_even_when_the_limit_is_reached(
    make_config: Callable[..., Config], tmp_path: Path
) -> None:
    session = ServiceSession(make_config(tmp_path), FakeDriver())
    await session.start()
    await session.handle({"type": "take_over"})
    await served(session, [*(press(x) for x in range(1, 11)), {"type": "stop"}], 4)
    assert session.control == "ended"
