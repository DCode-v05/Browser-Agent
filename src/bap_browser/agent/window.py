"""`bap-browser studio` started: the service, the window of pages and the desktop app, until the
service is stopped (spec 9.16)."""

from __future__ import annotations

import asyncio
import webbrowser
from collections.abc import Callable
from pathlib import Path

from bap_browser import browser_extension
from bap_browser.agent.command import tell
from bap_browser.agent.models import Model
from bap_browser.agent.studio import Studio
from bap_browser.config import Config
from bap_browser.desktop_app import DesktopApp
from bap_browser.service.accounts import Accounts
from bap_browser.service.server import Service
from bap_browser.settings.store import SettingsStore

# Where the core of the desktop app says where it is, beside this service's own such file.
DESKTOP_STATE_FILE = "desktop-service.json"


async def run_studio(
    config: Config, model_for: Callable[[Service], Model], *, open_viewer: bool, extension: Path
) -> None:
    """Serves the window and its three pages until the service is stopped (Ctrl+C), which raises
    Interrupted. `extension` is the folder the extension was put in, for the person's own Chrome."""
    config = browser_extension.may_show_viewer(config)
    desktop = desktop_app_of(config)
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


def desktop_app_of(config: Config) -> DesktopApp:
    """The desktop app, a program of its own. Its core says where it is in a file beside this
    service's own."""
    return DesktopApp(
        Path(config.server.desktop_dir).expanduser().resolve(),
        Path(config.server.state_file).resolve().with_name(DESKTOP_STATE_FILE),
        close_wait_s=config.server.desktop_close_wait_s,
    )
