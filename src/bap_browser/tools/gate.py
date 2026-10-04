"""Who decides whether a call may run now. A session with a person watching does: they may be driving."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass


@dataclass(frozen=True)
class Admission:
    refused: str | None = None
    """When set, the call is not run and this is its whole result. It is not an error."""
    note: str = ""
    """Goes in front of the result: what the agent must know before it reads the rest."""


Gate = Callable[[], AbstractAsyncContextManager[Admission]]
"""Entered before a call runs and left when it has finished, so that a person never takes the
browser in the middle of an action."""


@asynccontextmanager
async def always_open() -> AsyncGenerator[Admission]:
    yield Admission()
