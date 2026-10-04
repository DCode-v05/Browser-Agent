"""What a session tells its viewers: events, and pictures of the browser (spec 4.8)."""

from __future__ import annotations

import asyncio
from collections import deque
from typing import Any

Event = dict[str, Any]
Item = Event | bytes
"""An event, or one picture as JPEG bytes."""


class FellBehind(Exception):
    """The viewer stopped reading. It has to connect again and be sent everything from the start."""


class Subscriber:
    """One viewer's queue. Events keep their order; a picture not sent yet is replaced by a newer one."""

    def __init__(self, limit: int | None) -> None:
        self._items: deque[Item] = deque()
        self._limit = limit
        self._fell_behind = False
        self._wake = asyncio.Event()

    def push(self, item: Item) -> None:
        if self._fell_behind:
            return
        if isinstance(item, bytes) and self._items and isinstance(self._items[-1], bytes):
            self._items[-1] = item
        elif self._limit is not None and len(self._items) >= self._limit:
            self._fell_behind = True
            self._items.clear()
        else:
            self._items.append(item)
        self._wake.set()

    async def next(self) -> Item:
        while True:
            if self._fell_behind:
                raise FellBehind
            if self._items:
                return self._items.popleft()
            self._wake.clear()
            await self._wake.wait()


class EventHub:
    def __init__(self, history: int) -> None:
        self._history: deque[Event] = deque(maxlen=history)
        self._overflowed = False
        self._started: Event | None = None
        self._control: Event | None = None
        self._tabs: Event | None = None
        self._frame: bytes | None = None
        self._subscribers: list[Subscriber] = []
        self._viewer_arrived = asyncio.Event()

    @property
    def viewers(self) -> int:
        return len(self._subscribers)

    def publish(self, event: Event, *, keep: bool = True) -> None:
        """Sends an event to every viewer. `keep=False` is for what means nothing to a later viewer."""
        kind = event.get("type")
        if kind == "session_started":
            self._started, self._control, self._tabs = event, None, None
            self._history.clear()
            self._overflowed = False
        elif keep:
            if kind == "control_changed":
                self._control = event
            elif kind == "tab_changed":
                self._tabs = event
            if len(self._history) == self._history.maxlen:
                self._overflowed = True
            self._history.append(event)
        self._send(event)

    def publish_frame(self, frame: bytes) -> None:
        self._frame = frame
        self._send(frame)

    def subscribe(self) -> tuple[list[Item], Subscriber]:
        """What already happened, and the queue of what follows."""
        subscriber = Subscriber(self._history.maxlen or None)
        self._subscribers.append(subscriber)
        self._viewer_arrived.set()
        return self._replay(), subscriber

    async def wait_for_viewer(self) -> None:
        """Returns once a viewer has connected, so that a person misses nothing of what follows."""
        await self._viewer_arrived.wait()

    def unsubscribe(self, subscriber: Subscriber) -> None:
        if subscriber in self._subscribers:
            self._subscribers.remove(subscriber)

    def _replay(self) -> list[Item]:
        replay: list[Item] = []
        if self._started is not None:
            replay.append(self._started)
        if self._overflowed:
            # The events that said who is driving and which page is open may have been dropped.
            # They go first, so that anything newer in the history still has the last word.
            replay += [
                event
                for event in (self._control, self._tabs)
                if event is not None and event not in self._history
            ]
        replay += self._history
        if self._frame is not None:
            replay.append(self._frame)
        return replay

    def _send(self, item: Item) -> None:
        for subscriber in self._subscribers:
            subscriber.push(item)
