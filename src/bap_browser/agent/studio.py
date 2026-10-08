"""`bap-browser studio`: one window with the three browsers an agent can work in, each a page of it
(spec 9.16), and each a system of its own to set up, to manage and to evaluate (spec 9.17).

| Page | Where the browser is |
|---|---|
| Cloud browser | A headless browser of the service's own, with a fresh profile and a live picture |
| My Chrome | A tab of the person's own Chrome, reached through the extension (spec 4.9) |
| Built-in browser | A browser of the app's own that keeps its sign-ins, with a live picture |

Each page is a session of its own, with its own chat, its own settings, its own log and its own
record of what its tasks took. A session a person stopped can be started again from the page.
"""

from __future__ import annotations

import asyncio
import json
import logging
import webbrowser
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from bap_browser import browser_extension
from bap_browser.agent.command import (
    AGENT_NAME,
    do_task,
    next_task,
    paired,
    tell,
    unless_stopped,
)
from bap_browser.agent.models import Message, Model
from bap_browser.config import Config
from bap_browser.desktop_app import DesktopApp
from bap_browser.driver.playwright_driver import PlaywrightDriver
from bap_browser.errors import BapError
from bap_browser.evals import Rating, Recorder, overall, summarise, trace_of
from bap_browser.evals.checks import run_checklist
from bap_browser.evals.suite import SETS, Mode, Progress, Reports, run_set, suite_recorder
from bap_browser.evals.suite import described as set_described
from bap_browser.service.accounts import Accounts
from bap_browser.service.server import Service
from bap_browser.service.session import ServiceSession
from bap_browser.settings.store import SettingsStore

logger = logging.getLogger(__name__)

CLOUD, CHROME, BUILT_IN = "cloud", "chrome", "builtin"
# The folder, inside the data folder, where the built-in browser keeps its sign-ins.
BUILT_IN_PROFILE = "built-in-browser"
# Where the core of the desktop app says where it is, beside this service's own such file.
DESKTOP_STATE_FILE = "desktop-service.json"
# What a person needs the agent's attention for.
NEEDS_A_PERSON = ("person_requested", "waiting_approval")
# What the page of the person's own Chrome says when that Chrome has no window to work in.
NO_WINDOW = "Your Chrome has no window open. Open a window in Chrome: the agent works in a tab of it."


def said_of(failed: BaseException) -> str:
    """Why a browser could not be started, in words a person can act on."""
    words = str(failed)
    # Chrome says this when it runs with no window open. It is the person's to open one.
    return NO_WINDOW if "No current window" in words else words


# What a person may do with a browser of the window, besides setting it up.
ACTIONS = ("start", "stop", "restart")
# What the summary of an ended session says, in place of "You stopped it."
STOPPED = "You stopped this browser from the Systems page."
TURNED_OFF = "This browser was turned off."
RESTARTED = "It was ended to start a new session."


@dataclass
class Room:
    """One page of the window: a browser, and the session that is on it now."""

    id: str
    backend: str
    session: ServiceSession | None = None
    phase: str = "starting"
    """While there is no session: `starting`, `waiting` for the person's Chrome, `failed`, or
    `off` when a person has turned the browser off."""
    note: str = ""
    """Why it failed, in words for the person."""
    restart: asyncio.Event = field(default_factory=asyncio.Event)
    """Set when a new session is wanted on the page, or when whether it is wanted has changed."""
    turn: asyncio.Lock = field(default_factory=asyncio.Lock)
    """Held by whoever has the agent of this page working: a person's task, or a run of a task set.
    The other waits its turn."""

    def described(self, extension: Path) -> dict[str, Any]:
        """What the window is told about this page, to draw its tab and what is behind it."""
        session = self.session
        state = session.control if session is not None else self.phase
        told: dict[str, Any] = {
            "id": self.id,
            "backend": self.backend,
            "state": state,
            "attention": state in NEEDS_A_PERSON,
            "working": session is not None and session.busy and state == "agent",
        }
        if self.note:
            told["note"] = self.note
        if self.id == CHROME:
            # Where the extension is, for the person to load it into their Chrome.
            told["extension"] = str(extension)
        return told


class Studio:
    """The three browsers of the window as systems (spec 9.17): each with settings of its own, a
    log of its own, the record of what its tasks took, and a person's hand on whether it runs."""

    def __init__(
        self,
        config: Config,
        settings: SettingsStore,
        model_for: Callable[[Service], Model],
        extension: Path,
    ) -> None:
        self._config = config
        self._settings = settings
        self._model_for = model_for
        self._extension = extension
        self.sessions: dict[str, ServiceSession] = {}
        self.rooms = [
            Room(CLOUD, "remote_headless"),
            Room(CHROME, "takeover_chrome"),
            Room(BUILT_IN, "bundled_chromium"),
        ]
        self._recorders = {room.id: Recorder(config.evals, room.id, room.backend) for room in self.rooms}
        # The settings know which browsers there are: a user's preferred one is among them.
        settings.systems = tuple(room.id for room in self.rooms)
        # A checklist runs on one browser at a time, and not on one that is being checked already.
        self._checking: set[str] = set()
        # The task sets (spec 12.7): each browser's reports, and the run that is under way on it.
        self._reports = {room.id: Reports(config.evals, room.id) for room in self.rooms}
        self._runs: dict[str, Progress] = {}
        self._running: set[asyncio.Task[None]] = set()
        self.service: Service | None = None

    # What the window asks (the HTTP surface).

    def pages(self) -> list[dict[str, Any]]:
        """The pages of the window, for its tabs (spec 9.16)."""
        return [room.described(self._extension) for room in self.rooms]

    def described(self) -> list[dict[str, Any]]:
        """The systems, for the page that sets them up and manages them (spec 9.17)."""
        told: list[dict[str, Any]] = []
        for room in self.rooms:
            config = self._configured(room)
            log = config.logging.event_log
            told.append(
                {
                    **room.described(self._extension),
                    "enabled": self._settings.enabled(room.id),
                    "model": config.agent.model,
                    # Where this browser's log is written. None when a person turned it off.
                    "log": str(Path(log).resolve()) if log else None,
                    "records": str(self._recorders[room.id].folder.resolve()),
                }
            )
        return told

    def _room(self, system: str) -> Room | None:
        return next((room for room in self.rooms if room.id == system), None)

    def _configured(self, room: Room) -> Config:
        """The configuration this browser has now: its session's, or what a new session would get."""
        if room.session is not None and room.session.control != "ended":
            return room.session.config
        return self._settings.apply_to(self._given(room), room.backend, room.id)

    async def settings_changed(self, system: str) -> None:
        """A person changed this browser's settings. One that was turned off is ended, and one
        that was turned on is started."""
        room = self._room(system)
        if room is None:
            return
        wanted = self._settings.enabled(system)
        if not wanted:
            await self._end(room, TURNED_OFF)
        if wanted == (room.phase == "off"):
            # Whether it is wanted has changed: its loop looks again.
            room.restart.set()

    async def manage(self, system: str, action: str) -> str | None:
        """Starts, stops or starts again a browser of the window. None when it was done; otherwise
        why not, in words for the person."""
        room = self._room(system)
        if room is None or action not in ACTIONS:
            return "There is no such browser, or nothing of that name to do with it."
        if not self._settings.enabled(system):
            return "This browser is turned off. Turn it on first."
        running = room.session is not None and room.session.control != "ended"
        if action == "stop":
            if not running:
                return "This browser has no session to stop."
            await self._end(room, STOPPED)
            return None
        if action == "start" and running:
            return "This browser is running already."
        await self._end(room, RESTARTED)
        room.restart.set()
        return None

    async def _end(self, room: Room, why: str) -> None:
        if room.session is not None and room.session.control != "ended":
            await room.session.close("person", why)

    def log(self, system: str) -> dict[str, Any]:
        """The newest lines of a browser's log, as they are in its file."""
        room = self._room(system)
        assert room is not None
        named = self._configured(room).logging.event_log
        if not named:
            return {"path": None, "lines": [], "size": 0}
        path = Path(named)
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            return {"path": str(path.resolve()), "lines": [], "size": 0}
        lines: list[Any] = []
        for line in text.splitlines()[-self._config.logging.shown_lines :]:
            try:
                lines.append(json.loads(line))
            except ValueError:
                continue
        return {"path": str(path.resolve()), "lines": lines, "size": len(text.encode())}

    def evals(self, system: str) -> dict[str, Any]:
        room = self._room(system)
        assert room is not None
        told = summarise(self._recorders[system], self._config.evals, self._configured(room).agent.model)
        return {**told, "backend": room.backend, "checking": system in self._checking}

    def overall(self) -> dict[str, Any]:
        return overall(self._recorders.values(), self._config.evals)

    def trace(self, system: str, task: str) -> dict[str, Any] | None:
        return trace_of(self._recorders[system], task)

    def rate(self, system: str, task: str, rating: Rating | None) -> bool:
        return self._recorders[system].rate(task, rating)

    async def check(self, system: str) -> dict[str, Any] | str:
        """Runs the checklist on a browser. The result; or, as a sentence, why it could not run."""
        room, service = self._room(system), self.service
        assert room is not None and service is not None
        session = room.session
        if session is None or session.control == "ended":
            return "This browser has no session. Start it first."
        if session.control != "agent":
            return "The agent is not driving this browser now. Hand it back, or resume it, first."
        if session.busy or system in self._checking or system in self._runs:
            return "This browser is busy. Run the checklist when its task is finished."
        self._checking.add(system)
        try:
            result = await run_checklist(session, service.address, self._config.evals)
        finally:
            self._checking.discard(system)
        self._recorders[system].keep_checklist(result)
        return result

    # The task sets (spec 12.7).

    def suite(self, system: str) -> dict[str, Any]:
        """The task sets of a browser: what each is, how its newest run went, and the run under way."""
        room = self._room(system)
        assert room is not None
        latest = self._reports[system].latest()
        running = self._runs.get(system)
        settings = self._config.evals
        return {
            "system": system,
            "model": self._configured(room).agent.model,
            "sets": [
                {**set_described(name), **latest.get(name, {"last": None, "earlier": []})} for name in SETS
            ],
            "running": running.told() if running is not None else None,
            "trials": settings.suite_trials,
            "max_trials": settings.suite_max_trials,
        }

    def suite_overall(self) -> dict[str, Any]:
        """The newest run of each set on each browser, side by side: the admin's view of the whole."""
        lines: list[dict[str, Any]] = []
        for room in self.rooms:
            latest = self._reports[room.id].latest()
            runs = {
                name: {
                    **told["last"]["totals"],
                    "mode": told["last"]["mode"],
                    "started": told["last"]["started"],
                    # How many times each task was tried, not how many tries there were in all.
                    "trials": told["last"]["trials"],
                    "stopped": told["last"]["stopped"],
                }
                for name, told in latest.items()
            }
            lines.append({"system": room.id, "runs": runs})
        return {"sets": [set_described(name) for name in SETS], "systems": lines}

    def start_suite(self, system: str, name: str, trials: int, mode: Mode) -> str | None:
        """Begins a run of a task set on a browser. None when it began; otherwise why not."""
        room, service = self._room(system), self.service
        assert room is not None and service is not None
        session = room.session
        if name not in SETS:
            return "There is no task set of that name."
        if not 1 <= trials <= self._config.evals.suite_max_trials:
            return f"A task is tried between 1 and {self._config.evals.suite_max_trials} times."
        if session is None or session.control == "ended":
            return "This browser has no session. Start it first."
        if session.control != "agent":
            return "The agent is not driving this browser now. Hand it back, or resume it, first."
        if session.busy or system in self._checking or system in self._runs:
            return "This browser is busy. Run the task set when its task is finished."
        progress = Progress(name, mode, trials, set_described(name)["tasks"])
        self._runs[system] = progress
        running = asyncio.create_task(self._run_suite(room, session, service, progress))
        self._running.add(running)
        running.add_done_callback(self._running.discard)
        return None

    async def stop_suite(self, system: str) -> bool:
        """Ends the run under way on a browser after the task it is on. False when there is none."""
        progress, room = self._runs.get(system), self._room(system)
        if progress is None or room is None:
            return False
        progress.stop.set()
        if room.session is not None:
            # The task it is on is stopped as a person stops one from the chat.
            await room.session.handle({"type": "stop_task"})
        return True

    async def _run_suite(
        self, room: Room, session: ServiceSession, service: Service, progress: Progress
    ) -> None:
        recorder = suite_recorder(self._config.evals, room.id, room.backend)
        by_the_agent = progress.mode == "agent"

        async def do(words: str) -> Any:
            # Whoever watches the page sees each task in the chat, as if a person had sent it.
            session.said("person", words)
            # Each task starts with nothing remembered of the one before it: a conversation of its
            # own, and a model client of its own, which keeps the turns of one conversation.
            return await do_task(words, session, self._model_for(service), session.config, [], recorder)

        try:
            async with room.turn:
                report = await run_set(
                    session,
                    service.address,
                    progress.set,
                    trials=progress.trials,
                    mode=progress.mode,
                    do=do if by_the_agent else None,
                    settings=self._config.evals,
                    model=session.config.agent.model,
                    progress=progress,
                )
            await asyncio.to_thread(self._reports[room.id].keep, report)
        except BapError as failed:
            logger.warning("the run of the task set %s on %s ended: %s", progress.set, room.id, failed)
        finally:
            self._runs.pop(room.id, None)

    # The browsers themselves.

    def _given(self, room: Room) -> Config:
        """What the deployment gives this browser, before a person's settings."""
        config = self._config
        if room.id == CLOUD:
            config = _cloud(config)
        elif room.id == BUILT_IN:
            config = _built_in(config)
        return _with_its_own_log(config, room.id)

    async def run(self, service: Service) -> None:
        """Runs the three browsers until the service stops."""
        self.service = service
        cloud, chrome, built_in = self.rooms
        working = [
            asyncio.create_task(self._own_browser(cloud)),
            asyncio.create_task(self._persons_chrome(chrome)),
            asyncio.create_task(self._own_browser(built_in)),
        ]
        try:
            await unless_stopped(asyncio.gather(*working), service)
        finally:
            for task in (*working, *self._running):
                task.cancel()
            await asyncio.gather(*working, *self._running, return_exceptions=True)
            for room in self.rooms:
                if room.session is not None:
                    await room.session.close()

    async def _wanted(self, room: Room) -> None:
        """Waits until a session is wanted on the page: a person turned the browser on, or asked
        for a new session."""
        while not self._settings.enabled(room.id):
            # Turned off: there is nothing on its page, and nobody is connected to it.
            gone = self.sessions.pop(room.id, None)
            room.session, room.phase, room.note = None, "off", ""
            if gone is not None:
                gone.hub.start_over()
            room.restart.clear()
            await room.restart.wait()
        if room.phase == "off":
            room.phase = "starting"

    async def _asked_again(self, room: Room) -> None:
        """Waits until a person asks for a new session on the page, or turns the browser off."""
        await room.restart.wait()
        room.restart.clear()

    def _take_place(self, room: Room, session: ServiceSession) -> None:
        """Puts a session on the page. Whoever was watching the one before it connects again, and
        finds this one."""
        before = self.sessions.get(room.id)
        self.sessions[room.id] = room.session = session
        if self.service is not None:
            session.served_at(self.service.address)
        if before is not None:
            before.hub.start_over()

    async def _talk(self, room: Room, tasks: asyncio.Queue[str], session: ServiceSession) -> None:
        """Does the tasks a person sends, one at a time, until the session ends. Each is recorded."""
        assert self.service is not None
        model = self._model_for(self.service)
        history: list[Message] = []
        while True:
            task = await next_task(tasks, session)
            if task is None:
                return
            async with room.turn:
                await do_task(task, session, model, session.config, history, self._recorders[room.id])

    async def _own_browser(self, room: Room) -> None:
        """A page whose browser this process starts itself. Each time a person asks for a new
        session, a new browser is started for it."""
        assert self.service is not None
        service = self.service
        while True:
            await self._wanted(room)
            room.phase, room.note = "starting", ""
            room.restart.clear()
            tasks: asyncio.Queue[str] = asyncio.Queue()
            session = ServiceSession(
                self._given(room),
                agent=AGENT_NAME,
                name=room.id,
                on_task=tasks.put_nowait,
                backend=room.backend,
                on_restart=room.restart.set,
                settings=self._settings,
            )
            try:
                await session.start()
            except BapError as failed:
                await session.close()
                room.session, room.phase, room.note = None, "failed", str(failed)
                # A person can try again from the Systems page.
                await self._asked_again(room)
                continue
            self._take_place(room, session)
            await session.toolkit.call("browser_navigate", {"url": f"{service.address}/demo-site/start.html"})
            await self._talk(room, tasks, session)
            await self._asked_again(room)

    async def _persons_chrome(self, room: Room) -> None:
        """The page for the person's own Chrome. Its session begins when the extension has dialled in."""
        assert self.service is not None
        service, config = self.service, self._config
        bridge = service.bridge
        assert bridge is not None
        while True:
            await self._wanted(room)
            if room.session is None or room.session.control == "ended":
                room.phase = "waiting"
            room.restart.clear()
            if not await self._paired_or_unwanted(room):
                continue
            # The driver attaches to the tab through this process's own end of the bridge.
            given = self._given(room)
            browser = given.browser.model_copy(update={"cdp_url": service.bridge_cdp_address})
            attached = given.model_copy(update={"browser": browser})
            driver = PlaywrightDriver(attached, cdp_headers={"Authorization": f"Bearer {service.token}"})
            tasks: asyncio.Queue[str] = asyncio.Queue()
            session = ServiceSession(
                attached,
                driver,
                agent=AGENT_NAME,
                name=room.id,
                on_task=tasks.put_nowait,
                # The person looks at their own browser: no picture of it is sent across the bridge.
                pictures=False,
                backend=room.backend,
                on_restart=room.restart.set,
                settings=self._settings,
            )
            # Which sites the agent may read and act on is decided on the person's machine.
            session.browser.ask_site = bridge.permit
            session.browser.site_done = bridge.permit_done
            try:
                await session.start()
            except BapError as failed:
                await session.close()
                room.note = said_of(failed)
                await asyncio.sleep(config.bridge.heartbeat_s)
                continue
            room.note = ""
            self._take_place(room, session)
            # The side panel in that Chrome shows this page's chat.
            panel = f"{service.address}/?session={room.id}#token={service.token}"
            browser_extension.announce(self._extension, panel, bridge=service.bridge_address)
            await session.toolkit.call("browser_navigate", {"url": f"{service.address}/demo-site/start.html"})
            await self._talk(room, tasks, session)
            await self._asked_again(room)

    async def _paired_or_unwanted(self, room: Room) -> bool:
        """Waits for the extension to dial in. False when the browser was turned off meanwhile."""
        assert self.service is not None and self.service.bridge is not None
        pairing = asyncio.ensure_future(
            paired(self.service.bridge, self._extension, self.service, self._config.bridge.pairing_ttl_s)
        )
        changed = asyncio.ensure_future(room.restart.wait())
        try:
            await asyncio.wait({pairing, changed}, return_when=asyncio.FIRST_COMPLETED)
            return pairing.done() and self._settings.enabled(room.id)
        finally:
            for waiting in (pairing, changed):
                waiting.cancel()
            await asyncio.gather(pairing, changed, return_exceptions=True)


async def run_studio(
    config: Config, model_for: Callable[[Service], Model], *, open_viewer: bool, extension: Path
) -> None:
    """Serves the window and its three pages until the service is stopped (Ctrl+C), which raises
    Interrupted. `extension` is the folder the extension was put in, for the person's own Chrome."""
    config = browser_extension.may_show_viewer(config)
    desktop = _desktop_app(config)
    settings = SettingsStore(config)
    accounts = Accounts(config.auth)
    studio = Studio(config, settings, model_for, extension)

    def serving(port: int | None) -> Service:
        return Service(
            config,
            studio.sessions,
            port=port,
            bridge=True,
            rooms=studio.pages,
            desktop=desktop,
            settings=settings,
            systems=studio,
            accounts=accounts,
        )

    # The configured port, so that the two sign-in pages keep their addresses from one start to
    # the next. Where it is taken, any free port.
    service = serving(None)
    try:
        await service.start()
    except OSError:
        service = serving(0)
        await service.start()
    try:
        tell(f"Viewer: {service.viewer_address}")
        tell(f"Sign in as a user: {service.address}/")
        tell(f"Sign in as the admin: {service.address}/admin")
        tell(f"Demo site: {service.address}/demo-site/start.html")
        tell(
            'For the page "My Chrome", load the extension into your Chrome, once: open chrome://extensions, '
            f"switch on Developer mode, press Load unpacked and choose {extension}"
        )
        tell("Press Ctrl+C to end.")
        if open_viewer:
            # The first time, the admin's page with this start's own link, which creates the
            # admin's password. After that, the page where people sign in.
            first_time = f"{service.address}/admin#token={service.token}"
            webbrowser.open(f"{service.address}/" if accounts.has("admin") else first_time)
        await studio.run(service)
    finally:
        browser_extension.forget(extension)
        await asyncio.to_thread(desktop.close)
        await service.stop()


def _desktop_app(config: Config) -> DesktopApp:
    """The desktop app, a program of its own. Its core says where it is in a file beside this
    service's own."""
    return DesktopApp(
        Path(config.server.desktop_dir).expanduser().resolve(),
        Path(config.server.state_file).resolve().with_name(DESKTOP_STATE_FILE),
        close_wait_s=config.server.desktop_close_wait_s,
    )


def _cloud(config: Config) -> Config:
    """A headless browser that starts with nothing: no profile is kept from one session to the next."""
    browser = config.browser.model_copy(update={"headless": True, "user_data_dir": None, "cdp_url": None})
    return config.model_copy(update={"browser": browser})


def _built_in(config: Config) -> Config:
    """The app's own browser: it keeps its sign-ins, apart from the person's own browser and from
    the cloud browser."""
    profile = Path(config.data_dir).expanduser() / BUILT_IN_PROFILE
    browser = config.browser.model_copy(
        update={"headless": True, "user_data_dir": str(profile), "cdp_url": None}
    )
    return config.model_copy(update={"browser": browser})


def _with_its_own_log(config: Config, system: str) -> Config:
    """Each browser of the window writes a log of its own (spec 9.17), where the deployment keeps a
    log at all."""
    if config.logging.event_log is None:
        return config
    own = Path(config.logging.systems_dir) / f"{system}.jsonl"
    return config.model_copy(update={"logging": config.logging.model_copy(update={"event_log": str(own)})})
