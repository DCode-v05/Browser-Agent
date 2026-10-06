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
from bap_browser.driver.playwright_driver import PlaywrightDriver
from bap_browser.evals.record import Outcome, Recorder
from bap_browser.service.bridge import Bridge
from bap_browser.service.server import Service
from bap_browser.service.session import ServiceSession
from bap_browser.settings.store import SettingsStore

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
    settings = SettingsStore(config)
    session = ServiceSession(config, agent=AGENT_NAME, settings=settings)
    service = Service(config, {session.name: session}, port=0, settings=settings)
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
    settings = SettingsStore(config)
    session = ServiceSession(config, agent=AGENT_NAME, on_task=tasks.put_nowait, settings=settings)
    service = Service(config, {session.name: session}, port=0, settings=settings)
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
        await _converse(tasks, session, service, model_for(service), config, first_task)
    finally:
        if extension is not None:
            browser_extension.forget(extension)
        await session.close()
        await service.stop()


async def _converse(
    tasks: asyncio.Queue[str],
    session: ServiceSession,
    service: Service,
    model: Model,
    config: Config,
    first_task: str | None,
) -> None:
    """Does the tasks a person sends, one at a time, until the session ends; then keeps the viewer
    open until the service is stopped."""
    if first_task:
        session.give_task(first_task)
    history: list[Message] = []
    while True:
        task = await _unless_stopped(_next_task(tasks, session), service)
        if task is None:
            break
        await _unless_stopped(_do(task, session, model, config, history), service)
    tell(SESSION_OVER)
    await service.wait()


async def chat_in_own_chrome(
    config: Config, model_for: Callable[[Service], Model], *, first_task: str | None, extension: Path
) -> None:
    """The chat, with the agent driving a tab of the person's own Chrome through the extension
    (spec 4.9). The extension dials in to this process; nothing here reaches into the browser.

    `extension` is the folder the extension was put in, which the person loads into their Chrome.
    Raises Interrupted when the service was stopped (Ctrl+C).
    """
    # The side panel shows the chat, which is this service's viewer inside the extension's page.
    config = browser_extension.may_show_viewer(config)
    tasks: asyncio.Queue[str] = asyncio.Queue()
    sessions: dict[str, ServiceSession] = {}
    settings = SettingsStore(config)
    service = Service(config, sessions, port=0, bridge=True, settings=settings)
    session: ServiceSession | None = None
    await service.start()
    try:
        assert service.bridge is not None
        bridge = service.bridge
        tell(
            "Load the extension into your Chrome, once: open chrome://extensions, switch on Developer "
            f"mode, press Load unpacked and choose {extension}"
        )
        tell("Then open its side panel with the BAP icon in the toolbar.")
        await _unless_stopped(_paired(bridge, extension, service, config.bridge.pairing_ttl_s), service)
        tell("The extension has connected. Opening the agent's tab.")
        # The driver attaches to the tab through this process's own end of the bridge.
        browser = config.browser.model_copy(update={"cdp_url": service.bridge_cdp_address})
        attached = config.model_copy(update={"browser": browser})
        driver = PlaywrightDriver(attached, cdp_headers={"Authorization": f"Bearer {service.token}"})
        # The person looks at their own browser: no picture of it is sent across the bridge.
        session = ServiceSession(
            attached,
            driver,
            agent=AGENT_NAME,
            on_task=tasks.put_nowait,
            pictures=False,
            settings=settings,
        )
        # Which sites the agent may read and act on is decided on the person's machine.
        session.browser.ask_site = bridge.permit
        session.browser.site_done = bridge.permit_done
        await _unless_stopped(session.start(), service)
        sessions[session.name] = session
        browser_extension.announce(extension, service.viewer_address, bridge=service.bridge_address)
        await session.toolkit.call("browser_navigate", {"url": f"{service.address}/demo-site/start.html"})
        tell("Type a task in the side panel's chat. Press Ctrl+C to end.")
        await _converse(tasks, session, service, model_for(service), attached, first_task)
    finally:
        browser_extension.forget(extension)
        if session is not None:
            await session.close()
        await service.stop()


async def _paired(bridge: Bridge, extension: Path, service: Service, ttl_s: float) -> None:
    """Waits for the extension to dial in. A pairing token is good for a short time only, so the
    extension is handed a new one before the last has run out."""
    waiting = asyncio.ensure_future(bridge.wait_connected())
    try:
        while not waiting.done():
            browser_extension.announce(extension, bridge=service.bridge_address, token=bridge.pairing_token())
            await asyncio.wait({waiting}, timeout=ttl_s / 2)
    finally:
        waiting.cancel()


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
    task: str,
    session: ServiceSession,
    model: Model,
    config: Config,
    history: list[Message],
    recorder: Recorder | None = None,
) -> None:
    """Runs one task and says how it went in the chat. With `recorder`, what the task took is
    kept: its time, its steps, its tokens and how it ended (spec 12.6)."""
    begun = len(history)
    session.working(True)
    # A person may have chosen another model for this browser since the last task (spec 10.2).
    use = getattr(model, "use", None)
    if callable(use):
        use(config.agent)
    trace = (
        recorder.begin(
            task,
            config.agent,
            # Where a person turned the log off, the task's own words are not kept either.
            keep_words=session.config.logging.event_log is not None,
            waited_s=lambda: session.waited_for_a_person_s,
            redact=session.browser.redact,
        )
        if recorder is not None
        else None
    )
    outcome: Outcome = "ended"
    answer = ""
    try:
        answer = await run_agent(
            await _with_where_the_browser_is(task, session),
            session.toolkit if trace is None else trace.tools(session.toolkit),
            model if trace is None else trace.model(model),
            config.agent,
            on_text=lambda text: session.said("agent", text),
            ended=lambda: session.control == "ended",
            stopped=session.task_stopped,
            history=history,
        )
        session.said("agent", answer)
        outcome = "answered"
    except (ModelError, Unfinished) as stopped:
        if isinstance(stopped, ModelError):
            outcome = "failed"
        elif session.task_stopped():
            outcome = "stopped"
        elif session.control != "ended":
            outcome = "step_limit"
        if session.control != "ended":
            # A task a person stopped has not failed.
            session.said("agent", str(stopped), failed=not session.task_stopped())
    finally:
        if trace is not None:
            trace.finish(outcome, answer)
        _tidy(history, begun)
        session.working(False)


NOWHERE = ("", "about:blank")


async def _with_where_the_browser_is(task: str, session: ServiceSession) -> str:
    """The task as the model is given it: with the page the browser is on now. A person who types a
    task looks at that page and means it; the model has not seen it yet."""
    here = next((tab for tab in await session.toolkit.tabs() if tab.active), None)
    if here is None or here.url in NOWHERE:
        return task
    return (
        f"{task}\n\n[The browser is on {here.url} now. Read the page with browser_snapshot before you act.]"
    )


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
