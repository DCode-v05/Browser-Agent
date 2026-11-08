"""One viewer's connection (spec 4.8): what happened in the session is told to it, and its
commands are taken from it, until either side closes.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from enum import IntEnum
from typing import Any

from starlette.types import Message
from starlette.websockets import WebSocket, WebSocketDisconnect

from bap_browser.service.events import FellBehind, Subscriber
from bap_browser.service.session import ServiceSession

PICTURE = b"\x01"
LARGEST_VIEWER_MESSAGE = 64 * 1024


class Close(IntEnum):
    """Why a WebSocket is closed, as its code says it."""

    REFUSED = 4401
    NO_SUCH_SESSION = 4404
    START_OVER = 1013
    NOT_THE_VIEWERS_ORIGIN = 1008


async def serve_viewer(
    socket: WebSocket,
    session: ServiceSession,
    subscriber: Subscriber,
    backlog: int,
    shown_out: asyncio.Future[int] | None = None,
    must_leave: Callable[[], int | None] = lambda: None,
) -> None:
    """Sends the viewer what happens, and does what the person asks, until either side stops, or
    until the person may no longer be here: `shown_out` is then given the code to close with."""
    waiting: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    door = shown_out if shown_out is not None else asyncio.get_running_loop().create_future()

    async def tell() -> None:
        while True:
            await send(socket, await subscriber.next())

    async def listen() -> None:
        while True:
            command = command_of(await socket.receive())
            if command is None:
                continue
            leave = must_leave()
            if leave is not None:
                if not door.done():
                    door.set_result(leave)
                return
            if command.get("type") == "seen":
                subscriber.in_front = command.get("visible") is not False
            elif command.get("type") == "stop":
                await session.handle(command)
            elif waiting.qsize() < backlog:
                waiting.put_nowait(command)

    async def act() -> None:
        while True:
            await session.handle(await waiting.get())

    tasks = [asyncio.create_task(work()) for work in (tell, listen, act)]
    try:
        await asyncio.wait([*tasks, door], return_when=asyncio.FIRST_COMPLETED)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    if door.done():
        await socket.close(door.result())
        return
    failure = next(
        (task.exception() for task in tasks if not task.cancelled() and task.exception()),
        None,
    )
    if isinstance(failure, FellBehind):
        await socket.close(Close.START_OVER)
    elif failure is not None and not isinstance(failure, WebSocketDisconnect):
        raise failure


async def send(socket: WebSocket, item: dict[str, Any] | bytes) -> None:
    if isinstance(item, bytes):
        await socket.send_bytes(PICTURE + item)
    else:
        await socket.send_text(json.dumps(item, ensure_ascii=False, separators=(",", ":")))


def command_of(message: Message) -> dict[str, Any] | None:
    """A viewer's message as a command, or None for anything that is not one."""
    if message["type"] == "websocket.disconnect":
        raise WebSocketDisconnect(message.get("code", 1000))
    text = message.get("text")
    if not isinstance(text, str) or len(text) > LARGEST_VIEWER_MESSAGE:
        return None
    try:
        command = json.loads(text)
    except ValueError:
        return None
    return command if isinstance(command, dict) else None
