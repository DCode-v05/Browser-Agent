"""The service on a real port, inside the event loop that also runs the sessions."""

from __future__ import annotations

import asyncio
import os
import secrets
import socket
from collections.abc import Mapping

import uvicorn

from bap_browser.config import Config
from bap_browser.service.app import create_app
from bap_browser.service.session import ServiceSession

# A person's command is a few dozen bytes. Nothing larger is read from a viewer.
LARGEST_VIEWER_MESSAGE = 64 * 1024


class Service:
    def __init__(
        self,
        config: Config,
        sessions: Mapping[str, ServiceSession],
        *,
        token: str | None = None,
        port: int | None = None,
    ) -> None:
        """`port` 0 means any free port; None means the configured one."""
        self._config = config
        self.token = token or os.environ.get(config.server.token_env) or secrets.token_urlsafe(32)
        self._app = create_app(config, sessions, self.token)
        self._wanted_port = config.server.port if port is None else port
        self.port = 0
        self._server: uvicorn.Server | None = None
        self._serving: asyncio.Task[None] | None = None

    @property
    def address(self) -> str:
        return f"http://{self._config.server.host}:{self.port}"

    @property
    def viewer_address(self) -> str:
        """Where a person opens the viewer. The token is in the fragment, which no server is sent."""
        return f"{self.address}/#token={self.token}"

    async def start(self) -> None:
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind((self._config.server.host, self._wanted_port))
        self.port = listener.getsockname()[1]
        self._server = uvicorn.Server(
            uvicorn.Config(
                self._app,
                log_config=None,
                access_log=False,
                server_header=False,
                lifespan="off",
                ws_max_size=LARGEST_VIEWER_MESSAGE,
            )
        )
        self._serving = asyncio.create_task(self._server.serve(sockets=[listener]))
        while not self._server.started:
            if self._serving.done():
                await self._serving
            await asyncio.sleep(0)

    async def wait(self) -> None:
        """Returns when the service has stopped: it was told to, or the process was interrupted."""
        if self._serving is not None:
            await asyncio.shield(self._serving)

    async def stop(self) -> None:
        if self._server is None or self._serving is None:
            return
        self._server.should_exit = True
        await self._serving
        self._server = self._serving = None
