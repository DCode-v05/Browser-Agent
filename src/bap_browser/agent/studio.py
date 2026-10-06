"""`bap-browser studio`: one window with the three browsers an agent can work in, each a page of it
(spec 9.16).

| Page | Where the browser is |
|---|---|
| Cloud browser | A headless browser of the service's own, with a fresh profile and a live picture |
| My Chrome | A tab of the person's own Chrome, reached through the extension (spec 4.9) |
| Built-in browser | A browser of the app's own that keeps its sign-ins, with a live picture |

Each page is a session of its own, with its own chat. A session a person stopped can be started
again from the page.
"""

from __future__ import annotations

import asyncio
import webbrowser
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from bap_browser import browser_extension
from bap_browser.agent.command import (
    AGENT_NAME,
    _do,  # pyright: ignore[reportPrivateUsage]
    _next_task,  # pyright: ignore[reportPrivateUsage]
    _paired,  # pyright: ignore[reportPrivateUsage]
    _unless_stopped,  # pyright: ignore[reportPrivateUsage]
    tell,
)
from bap_browser.agent.models import Message, Model
from bap_browser.config import Config
from bap_browser.desktop_app import DesktopApp
from bap_browser.driver.playwright_driver import PlaywrightDriver
from bap_browser.errors import BapError
from bap_browser.service.server import Service
from bap_browser.service.session import ServiceSession
from bap_browser.settings.store import SettingsStore

CLOUD, CHROME, BUILT_IN = "cloud", "chrome", "builtin"
# The folder, inside the data folder, where the built-in browser keeps its sign-ins.
BUILT_IN_PROFILE = "built-in-browser"
# Where the core of the desktop app says where it is, beside this service's own such file.
DESKTOP_STATE_FILE = "desktop-service.json"
# What a person needs the agent's attention for.
NEEDS_A_PERSON = ("person_requested", "waiting_approval")


@dataclass
class Room:
    """One page of the window: a browser, and the session that is on it now."""

    id: str
    backend: str
    session: ServiceSession | None = None
    phase: str = "starting"
    """While there is no session: `starting`, `waiting` for the person's Chrome, or `failed`."""
    note: str = ""
    """Why it failed, in words for the person."""
    restart: asyncio.Event = field(default_factory=asyncio.Event)

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


async def run_studio(
    config: Config, model_for: Callable[[Service], Model], *, open_viewer: bool, extension: Path
) -> None:
    """Serves the window and its three pages until the service is stopped (Ctrl+C), which raises
    Interrupted. `extension` is the folder the extension was put in, for the person's own Chrome."""
    config = browser_extension.may_show_viewer(config)
    sessions: dict[str, ServiceSession] = {}
    rooms = [
        Room(CLOUD, "remote_headless"),
        Room(CHROME, "takeover_chrome"),
        Room(BUILT_IN, "bundled_chromium"),
    ]
    desktop = _desktop_app(config)
    settings = SettingsStore(config)
    service = Service(
        config,
        sessions,
        port=0,
        bridge=True,
        rooms=lambda: [room.described(extension) for room in rooms],
        desktop=desktop,
        settings=settings,
    )
    await service.start()
    working: list[asyncio.Task[None]] = []
    try:
        cloud, chrome, built_in = rooms
        working = [
            asyncio.create_task(_own_browser(cloud, _cloud(config), service, sessions, model_for, settings)),
            asyncio.create_task(
                _persons_chrome(chrome, config, service, sessions, model_for, extension, settings)
            ),
            asyncio.create_task(
                _own_browser(built_in, _built_in(config), service, sessions, model_for, settings)
            ),
        ]
        tell(f"Viewer: {service.viewer_address}")
        tell(f"Demo site: {service.address}/demo-site/start.html")
        tell(
            'For the page "My Chrome", load the extension into your Chrome, once: open chrome://extensions, '
            f"switch on Developer mode, press Load unpacked and choose {extension}"
        )
        tell("Press Ctrl+C to end.")
        if open_viewer:
            webbrowser.open(service.viewer_address)
        await _unless_stopped(asyncio.gather(*working), service)
    finally:
        for task in working:
            task.cancel()
        await asyncio.gather(*working, return_exceptions=True)
        browser_extension.forget(extension)
        await asyncio.to_thread(desktop.close)
        for room in rooms:
            if room.session is not None:
                await room.session.close()
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


def _take_place(room: Room, sessions: dict[str, ServiceSession], session: ServiceSession) -> None:
    """Puts a session on the page. Whoever was watching the one before it connects again, and
    finds this one."""
    before = sessions.get(room.id)
    sessions[room.id] = room.session = session
    if before is not None:
        before.hub.start_over()


async def _own_browser(
    room: Room,
    config: Config,
    service: Service,
    sessions: dict[str, ServiceSession],
    model_for: Callable[[Service], Model],
    settings: SettingsStore,
) -> None:
    """A page whose browser this process starts itself. Each time a person asks for a new session,
    a new browser is started for it."""
    while True:
        room.phase, room.note = "starting", ""
        tasks: asyncio.Queue[str] = asyncio.Queue()
        session = ServiceSession(
            config,
            agent=AGENT_NAME,
            name=room.id,
            on_task=tasks.put_nowait,
            backend=room.backend,
            on_restart=room.restart.set,
            settings=settings,
        )
        try:
            await session.start()
        except BapError as failed:
            await session.close()
            room.session, room.phase, room.note = None, "failed", str(failed)
            return
        _take_place(room, sessions, session)
        await session.toolkit.call("browser_navigate", {"url": f"{service.address}/demo-site/start.html"})
        await _talk(tasks, session, model_for(service), config)
        await _asked_again(room)


async def _persons_chrome(
    room: Room,
    config: Config,
    service: Service,
    sessions: dict[str, ServiceSession],
    model_for: Callable[[Service], Model],
    extension: Path,
    settings: SettingsStore,
) -> None:
    """The page for the person's own Chrome. Its session begins when the extension has dialled in."""
    bridge = service.bridge
    assert bridge is not None
    while True:
        if room.session is None:
            room.phase = "waiting"
        await _paired(bridge, extension, service, config.bridge.pairing_ttl_s)
        # The driver attaches to the tab through this process's own end of the bridge.
        browser = config.browser.model_copy(update={"cdp_url": service.bridge_cdp_address})
        attached = config.model_copy(update={"browser": browser})
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
            settings=settings,
        )
        # Which sites the agent may read and act on is decided on the person's machine.
        session.browser.ask_site = bridge.permit
        session.browser.site_done = bridge.permit_done
        try:
            await session.start()
        except BapError as failed:
            await session.close()
            room.note = str(failed)
            await asyncio.sleep(config.bridge.heartbeat_s)
            continue
        room.note = ""
        _take_place(room, sessions, session)
        # The side panel in that Chrome shows this page's chat.
        panel = f"{service.address}/?session={room.id}#token={service.token}"
        browser_extension.announce(extension, panel, bridge=service.bridge_address)
        await session.toolkit.call("browser_navigate", {"url": f"{service.address}/demo-site/start.html"})
        await _talk(tasks, session, model_for(service), attached)
        await _asked_again(room)


async def _talk(tasks: asyncio.Queue[str], session: ServiceSession, model: Model, config: Config) -> None:
    """Does the tasks a person sends, one at a time, until the session ends."""
    history: list[Message] = []
    while True:
        task = await _next_task(tasks, session)
        if task is None:
            return
        await _do(task, session, model, config, history)


async def _asked_again(room: Room) -> None:
    """Waits until a person asks for a new session on the page."""
    room.restart.clear()
    await room.restart.wait()
    room.restart.clear()
