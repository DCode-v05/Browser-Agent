"""`bap-browser agent`: the reference loop on one task, with the service and the viewer around it (spec 16.5)."""

from __future__ import annotations

import asyncio
import sys
import webbrowser
from collections.abc import Awaitable, Callable
from pathlib import Path

from bap_browser import browser_extension
from bap_browser.agent.loop import Unfinished, run_agent
from bap_browser.agent.models import Message, Model, ModelError, Said, ToolOutput
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
    exit_when_done: bool,
    wait_for_viewer: bool,
    open_viewer: bool,
) -> None:
    """Runs the task while a person can watch, pause, take over and stop, and prints the answer.

    Raises ModelError when the model could not answer, Unfinished when the run stopped before an
    answer, and Interrupted when the service was stopped first.
    """
    session = ServiceSession(config, agent=AGENT_NAME)
    service = Service(config, {session.name: session}, port=0)
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


NOT_RUN = "Not run: the task was stopped first."
SESSION_OVER = "The session has ended. The viewer stays open until you press Ctrl+C."


async def chat_with_viewer(
    config: Config,
    model_for: Callable[[Service], Model],
    *,
    first_task: str | None,
    open_viewer: bool,
    extension: Path | None = None,
) -> None:
    """Keeps one session open and does the tasks a person sends from the viewer's chat, one at a time.

    A task that fails is answered in the chat and the session goes on. It ends when a person stops
    it. Raises Interrupted when the service was stopped (Ctrl+C).
    """
    tasks: asyncio.Queue[str] = asyncio.Queue()
    session = ServiceSession(config, agent=AGENT_NAME, on_task=tasks.put_nowait)
    service = Service(config, {session.name: session}, port=0)
    await session.start()
    try:
        await service.start()
        tell(f"Viewer: {service.viewer_address}")
        if open_viewer:
            webbrowser.open(service.viewer_address)
        tell(f"Demo site: {service.address}/demo-site/checkin.html")
        if extension is not None:
            # The side panel finds the session through this file, and the browser opens on a page
            # that says how to open the panel.
            browser_extension.announce(extension, service.viewer_address)
            await session.toolkit.call("browser_navigate", {"url": f"{service.address}/demo-site/start.html"})
            tell("In the browser that opened, click the BAP icon in the toolbar (or press Ctrl+Shift+Y).")
        tell("Type a task in the viewer's chat. Press Ctrl+C to end.")
        if first_task:
            session.give_task(first_task)
        model = model_for(service)
        history: list[Message] = []
        while True:
            task = await _unless_stopped(_next_task(tasks, session), service)
            if task is None:
                break
            await _unless_stopped(_do(task, session, model, config, history), service)
        tell(SESSION_OVER)
        await service.wait()
    finally:
        if extension is not None:
            browser_extension.forget(extension)
        await session.close()
        await service.stop()


async def _next_task(tasks: asyncio.Queue[str], session: ServiceSession) -> str | None:
    """The next task a person sent, or None once the session has ended."""
    waiting = asyncio.ensure_future(tasks.get())
    ended = asyncio.ensure_future(session.wait_until_ended())
    try:
        await asyncio.wait({waiting, ended}, return_when=asyncio.FIRST_COMPLETED)
        return waiting.result() if waiting.done() and session.control != "ended" else None
    finally:
        for task in (waiting, ended):
            task.cancel()
        await asyncio.gather(waiting, ended, return_exceptions=True)


async def _do(
    task: str, session: ServiceSession, model: Model, config: Config, history: list[Message]
) -> None:
    """Runs one task and says how it went in the chat."""
    begun = len(history)
    session.working(True)
    try:
        answer = await run_agent(
            task,
            session.toolkit,
            model,
            config.agent,
            on_text=lambda text: session.said("agent", text),
            ended=lambda: session.control == "ended",
            history=history,
        )
        session.said("agent", answer)
    except (ModelError, Unfinished) as stopped:
        if session.control != "ended":
            session.said("agent", str(stopped), failed=True)
    finally:
        _tidy(history, begun)
        session.working(False)


def _tidy(history: list[Message], begun: int) -> None:
    """Makes the conversation fit to go on from. Every call the model made gets a result, and the
    pages a finished task read are dropped: the next task reads the page as it is then, and pays
    for none of the old ones."""
    answered = {message.call.id for message in history if isinstance(message, ToolOutput)}
    for message in list(history[begun:]):
        if isinstance(message, Said):
            history += [
                ToolOutput(call, NOT_RUN, True) for call in message.tool_calls if call.id not in answered
            ]
    for index in range(begun, len(history)):
        message = history[index]
        if isinstance(message, ToolOutput) and "\n" in message.text:
            history[index] = ToolOutput(message.call, message.text.split("\n", 1)[0], message.is_error)


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
