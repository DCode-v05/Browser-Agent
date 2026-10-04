"""The HTTP surface (spec 4.7): the viewer's files, the API, and one WebSocket per viewer (spec 4.8).

How it is protected (spec 4.10): every request's Host must be this service's; the API and the
WebSocket need the token; a WebSocket's Origin must be the viewer's own or a listed one.
"""

from __future__ import annotations

import asyncio
import hmac
import json
import time
from collections.abc import Mapping
from importlib.resources import files
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route, WebSocketRoute
from starlette.staticfiles import StaticFiles
from starlette.types import ASGIApp, Message, Receive, Scope, Send
from starlette.websockets import WebSocket, WebSocketDisconnect

from bap_browser.config import Config
from bap_browser.errors import ConfigError
from bap_browser.service.events import FellBehind, Subscriber
from bap_browser.service.session import ServiceSession

# The first byte of a binary message says what it carries.
PICTURE = b"\x01"
# Close codes the viewer acts on.
REFUSED = 4401
NO_SUCH_SESSION = 4404
START_OVER = 1013
NOT_THE_VIEWERS_ORIGIN = 1008
LOCAL_HOSTS = ("127.0.0.1", "localhost")


def create_app(config: Config, sessions: Mapping[str, ServiceSession], token: str) -> Starlette:
    package = Path(str(files("bap_browser")))
    viewer = package / "viewer_dist"
    if not (viewer / "index.html").is_file():
        raise ConfigError("The viewer is not built. Run: npm --prefix viewer run build")
    public = urlsplit(config.server.public_url or "")
    hosts = [*LOCAL_HOSTS, *(name for name in (config.server.host, public.hostname) if name)]
    origins = {*config.viewer.embed_origins}
    if public.hostname:
        origins.add(f"{public.scheme}://{public.netloc}")

    def signed_in(given: Any) -> bool:
        return isinstance(given, str) and hmac.compare_digest(given.encode(), token.encode())

    async def healthz(request: Request) -> Response:
        return Response()

    async def list_sessions(request: Request) -> Response:
        scheme, _, given = request.headers.get("authorization", "").partition(" ")
        if scheme.lower() != "bearer" or not signed_in(given):
            return Response(status_code=401, headers={"WWW-Authenticate": "Bearer"})
        return JSONResponse(
            {"sessions": [{"id": name, "state": session.control} for name, session in sessions.items()]}
        )

    async def viewer_socket(socket: WebSocket) -> None:
        origin = socket.headers.get("origin")
        # A browser always says which page opened the connection. Only the viewer's own page may.
        own = {f"http://{socket.headers.get('host', '')}", f"https://{socket.headers.get('host', '')}"}
        if origin is not None and origin not in own | origins:
            await socket.close(NOT_THE_VIEWERS_ORIGIN)
            return
        await socket.accept()
        try:
            async with asyncio.timeout(config.server.auth_wait_s):
                first = _command(await socket.receive())
        except (TimeoutError, WebSocketDisconnect):
            first = None
        if not first or first.get("type") != "auth" or not signed_in(first.get("token")):
            await socket.close(REFUSED)
            return
        session = sessions.get(socket.path_params["name"])
        if session is None:
            await socket.close(NO_SUCH_SESSION)
            return
        replay, subscriber = session.hub.subscribe()
        try:
            for item in replay:
                await _send(socket, item)
            await _send(socket, {"type": "caught_up", "ts": time.time()})
            await _serve_viewer(socket, session, subscriber)
        except WebSocketDisconnect:
            pass
        finally:
            session.hub.unsubscribe(subscriber)

    return Starlette(
        routes=[
            Route("/healthz", healthz),
            Route("/api/sessions", list_sessions),
            WebSocketRoute("/api/sessions/{name}/ws", viewer_socket),
            Mount("/demo-site", StaticFiles(directory=package / "demo_site", html=True)),
            Mount("/", StaticFiles(directory=viewer, html=True)),
        ],
        middleware=[
            Middleware(TrustedHostMiddleware, allowed_hosts=hosts, www_redirect=False),
            Middleware(_ResponseHeaders, embed_origins=config.viewer.embed_origins),
        ],
    )


async def _serve_viewer(socket: WebSocket, session: ServiceSession, subscriber: Subscriber) -> None:
    """Sends the viewer what happens, and does what the person asks, until either side stops."""

    async def tell() -> None:
        while True:
            await _send(socket, await subscriber.next())

    async def listen() -> None:
        while True:
            command = _command(await socket.receive())
            if command is not None:
                await session.handle(command)

    telling, listening = asyncio.create_task(tell()), asyncio.create_task(listen())
    try:
        done, _ = await asyncio.wait({telling, listening}, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for task in (telling, listening):
            task.cancel()
        await asyncio.gather(telling, listening, return_exceptions=True)
    failure = next((task.exception() for task in done if not task.cancelled() and task.exception()), None)
    if isinstance(failure, FellBehind):
        # The viewer stopped reading. It connects again and is sent everything from the start.
        await socket.close(START_OVER)
    elif failure is not None and not isinstance(failure, WebSocketDisconnect):
        raise failure


async def _send(socket: WebSocket, item: dict[str, Any] | bytes) -> None:
    if isinstance(item, bytes):
        await socket.send_bytes(PICTURE + item)
    else:
        await socket.send_text(json.dumps(item, ensure_ascii=False, separators=(",", ":")))


def _command(message: Message) -> dict[str, Any] | None:
    """A viewer's message as a command, or None for anything that is not one."""
    if message["type"] == "websocket.disconnect":
        raise WebSocketDisconnect(message.get("code", 1000))
    text = message.get("text")
    if not isinstance(text, str):
        return None
    try:
        command = json.loads(text)
    except ValueError:
        return None
    return command if isinstance(command, dict) else None


class _ResponseHeaders:
    """Headers on every response: who may show the viewer inside their page, and nothing guessed or leaked."""

    def __init__(self, app: ASGIApp, embed_origins: list[str]) -> None:
        self._app = app
        ancestors = " ".join(["'self'", *embed_origins])
        self._headers = [
            (b"content-security-policy", f"frame-ancestors {ancestors}".encode()),
            (b"x-content-type-options", b"nosniff"),
            (b"referrer-policy", b"no-referrer"),
        ]

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                message = {**message, "headers": [*message.get("headers", []), *self._headers]}
            await send(message)

        await self._app(scope, receive, send_with_headers)
