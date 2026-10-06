"""The service on a real port, inside the event loop that also runs the sessions."""

from __future__ import annotations

import asyncio
import json
import os
import secrets
import socket
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import uvicorn
from mcp.server import Server as McpServer
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

from bap_browser.config import Config
from bap_browser.desktop_app import DesktopApp
from bap_browser.service.accounts import Accounts
from bap_browser.service.app import LARGEST_VIEWER_MESSAGE, create_app
from bap_browser.service.bridge import Bridge
from bap_browser.service.session import ServiceSession
from bap_browser.service.systems import Systems
from bap_browser.settings.store import SettingsStore


class Service:
    def __init__(
        self,
        config: Config,
        sessions: Mapping[str, ServiceSession],
        *,
        token: str | None = None,
        port: int | None = None,
        mcp: McpServer[Any] | None = None,
        bridge: bool = False,
        rooms: Callable[[], list[dict[str, Any]]] | None = None,
        desktop: DesktopApp | None = None,
        settings: SettingsStore | None = None,
        systems: Systems | None = None,
        accounts: Accounts | None = None,
    ) -> None:
        """`port` 0 means any free port; None means the configured one. `mcp` is the tools as an MCP
        server: with it, the service also offers them over HTTP at `mcp.http_path`. `bridge` adds
        the place where the extension in a person's own Chrome dials in (spec 4.9). `desktop` is
        the desktop app, for the window to open (spec 9.16). `settings` holds what a person chose in
        the settings screen; with it, the service has the settings API (spec 10.2). `systems` is
        whoever runs the browsers of a window that has several (spec 9.17). `accounts` holds who
        may sign in as the admin or as a user (spec 4.11)."""
        self._config = config
        self.token = token or os.environ.get(config.server.token_env) or secrets.token_urlsafe(32)
        # Each request stands by itself: an agent keeps no connection that could be lost.
        self._mcp = StreamableHTTPSessionManager(mcp, stateless=True) if mcp is not None else None
        self._mcp_running: asyncio.Task[None] | None = None
        self._mcp_over = asyncio.Event()
        self.bridge = Bridge(config) if bridge else None
        self._app = create_app(
            config,
            sessions,
            self.token,
            self._mcp.handle_request if self._mcp is not None else None,
            self.bridge,
            rooms,
            desktop,
            settings,
            systems,
            accounts,
        )
        self._wanted_port = config.server.port if port is None else port
        self.shutdown_wait_s = config.server.shutdown_wait_s
        self.port = 0
        self._server: uvicorn.Server | None = None
        self._serving: asyncio.Task[None] | None = None

    @property
    def address(self) -> str:
        return f"http://{self._config.server.host}:{self.port}"

    @property
    def bridge_address(self) -> str:
        """Where the extension dials in. It is on this machine, like the service."""
        return f"ws://{self._config.server.host}:{self.port}/bridge"

    @property
    def bridge_cdp_address(self) -> str:
        """Where this process's own driver reaches the tab the extension is attached to."""
        return f"{self.bridge_address}/cdp"

    @property
    def public_address(self) -> str:
        """Where people and agents reach the service: the public address a deployment names, or else
        where the service listens."""
        return (self._config.server.public_url or self.address).rstrip("/")

    @property
    def mcp_address(self) -> str:
        """Where an agent reaches the tools over MCP. It sends the token as a bearer token."""
        return f"{self.public_address}{self._config.mcp.http_path}"

    @property
    def viewer_address(self) -> str:
        """Where a person opens the viewer. The token is in the fragment, which no server is sent."""
        return f"{self.public_address}/#token={self.token}"

    async def _run_mcp(self, ready: asyncio.Event) -> None:
        """Keeps the MCP endpoint's own tasks alive. It is entered and left in one task, as it must be."""
        assert self._mcp is not None
        async with self._mcp.run():
            ready.set()
            await self._mcp_over.wait()

    async def start(self) -> None:
        if self._mcp is not None:
            ready = asyncio.Event()
            self._mcp_running = asyncio.create_task(self._run_mcp(ready))
            waiting = asyncio.create_task(ready.wait())
            await asyncio.wait({self._mcp_running, waiting}, return_when=asyncio.FIRST_COMPLETED)
            waiting.cancel()
            if self._mcp_running.done():
                await self._mcp_running
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            listener.bind((self._config.server.host, self._wanted_port))
        except OSError:
            # The port is taken. Whoever asked may try another; the socket is not left open.
            listener.close()
            raise
        self.port = listener.getsockname()[1]
        if self.bridge is not None:
            self.bridge.own_address = self.address
        self._server = uvicorn.Server(
            uvicorn.Config(
                self._app,
                log_config=None,
                access_log=False,
                server_header=False,
                lifespan="off",
                # A page read through the bridge is far larger than anything a viewer sends. A
                # viewer's own messages are held to their limit where they are read.
                ws_max_size=(
                    self._config.bridge.max_message_mb * 1024 * 1024
                    if self.bridge is not None
                    else LARGEST_VIEWER_MESSAGE
                ),
                # Without a limit, stopping can wait for ever: on Windows asyncio never counts a
                # connection that the other side cut as closed.
                timeout_graceful_shutdown=self.shutdown_wait_s,
            )
        )
        self._serving = asyncio.create_task(self._server.serve(sockets=[listener]))
        while not self._server.started:
            if self._serving.done():
                await self._serving
            await asyncio.sleep(0)
        # Files are written off the event loop, which is busy with sessions.
        await asyncio.to_thread(self._write_state)

    async def wait(self) -> None:
        """Returns when the service has stopped: it was told to, or the process was interrupted."""
        if self._serving is not None:
            await asyncio.shield(self._serving)

    async def stop(self) -> None:
        if self._server is None or self._serving is None:
            return
        if self.bridge is not None:
            await self.bridge.close()
        self._server.should_exit = True
        await self._serving
        self._server = self._serving = None
        if self._mcp_running is not None:
            self._mcp_over.set()
            await self._mcp_running
            self._mcp_running = None
        await asyncio.to_thread(self._remove_state)

    def _remove_state(self) -> None:
        Path(self._config.server.state_file).unlink(missing_ok=True)

    def _write_state(self) -> None:
        """The viewer address, for the local user to open again. The file is theirs alone to read."""
        state = Path(self._config.server.state_file)
        state.parent.mkdir(parents=True, exist_ok=True)
        handle = os.open(state, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(handle, "w", encoding="utf-8") as file:
            json.dump({"viewer": self.viewer_address}, file)
