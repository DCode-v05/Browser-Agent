"""`bap-browser agent`: the reference loop on one task, with the service and the viewer around it (spec 16.5)."""

from __future__ import annotations

import asyncio
import sys
import webbrowser
from collections.abc import Awaitable, Callable

from bap_browser.agent.loop import Unfinished, run_agent
from bap_browser.agent.models import Model, ModelError
from bap_browser.config import Config
from bap_browser.service.server import Service
from bap_browser.service.session import ServiceSession

AGENT_NAME = "Reference agent"


class Interrupted(Exception):
    """The service was stopped (Ctrl+C) before the work was finished."""


def tell(text: str) -> None:
    """For the person at the terminal. Standard output carries the answer and nothing else."""
    print(text, file=sys.stderr, flush=True)


async def run_with_viewer(
    config: Config,
    task: str,
    model_for: Callable[[Service], Model],
    *,
    token: str | None = None,
    exit_when_done: bool,
    wait_for_viewer: bool,
    open_viewer: bool,
) -> None:
    """Runs the task while a person can watch, pause, take over and stop, and prints the answer.

    Raises ModelError when the model could not answer, Unfinished when the run stopped before an
    answer, and Interrupted when the service was stopped first.
    """
    session = ServiceSession(config, agent=AGENT_NAME)
    service = Service(config, {session.name: session}, token=token, port=0)
    await session.start()
    try:
        await service.start()
        tell(f"Viewer: {service.viewer_address}")
        if open_viewer:
            webbrowser.open(service.viewer_address)
        if open_viewer or wait_for_viewer:
            tell("Waiting for the viewer to connect.")
            await _unless_stopped(session.hub.wait_for_viewer(), service)
        try:
            answer = await _unless_stopped(
                run_agent(
                    task,
                    session.toolkit,
                    model_for(service),
                    config.agent,
                    on_text=tell,
                    ended=lambda: session.control == "ended",
                ),
                service,
            )
        except ModelError as failed:
            # A person watching sees why the session ended, not only the person at the terminal.
            await session.close("failed", str(failed))
            raise
        await session.close("agent")
        # The answer is the only thing on standard output, and it is there as soon as it is known.
        print(answer, flush=True)
        if not exit_when_done:
            tell("The session has ended. The viewer stays open until you press Ctrl+C.")
            await service.wait()
    except Unfinished:
        if not exit_when_done:
            tell("The session has ended. The viewer stays open until you press Ctrl+C.")
            await service.wait()
        raise
    finally:
        await session.close()
        await service.stop()


async def _unless_stopped[T](work: Awaitable[T], service: Service) -> T:
    """The result of the work, unless the service stops first."""
    working, stopped = asyncio.ensure_future(work), asyncio.ensure_future(service.wait())
    try:
        await asyncio.wait({working, stopped}, return_when=asyncio.FIRST_COMPLETED)
        if working.done():
            return working.result()
        raise Interrupted
    finally:
        for task in (working, stopped):
            task.cancel()
        await asyncio.gather(working, stopped, return_exceptions=True)
