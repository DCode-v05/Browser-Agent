"""The HTTP surface (spec 4.7): the viewer's files, the API, and one WebSocket per viewer (spec 4.8).

How it is protected (spec 4.10): every request's Host must be this service's; the API and the
WebSocket need the token; a WebSocket's Origin must be the viewer's own or a listed one.
"""

from __future__ import annotations

import asyncio
import hmac
import json
import time
from collections.abc import Callable, Mapping
from importlib.resources import files
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from starlette.applications import Starlette
from starlette.datastructures import Headers
from starlette.middleware import Middleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route, WebSocketRoute
from starlette.staticfiles import StaticFiles
from starlette.types import ASGIApp, Message, Receive, Scope, Send
from starlette.websockets import WebSocket, WebSocketDisconnect

from bap_browser import browser_extension
from bap_browser.config import Config
from bap_browser.errors import ConfigError
from bap_browser.service.bridge import Bridge
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
LOCAL_CLIENTS = ("127.0.0.1", "::1")
# A person's command is a few dozen bytes. Nothing larger is taken from a viewer.
LARGEST_VIEWER_MESSAGE = 64 * 1024
# A request that is refused is read no further than this before it is answered.
LARGEST_REFUSED_REQUEST = 64 * 1024


def create_app(
    config: Config,
    sessions: Mapping[str, ServiceSession],
    token: str,
    mcp: ASGIApp | None = None,
    bridge: Bridge | None = None,
) -> Starlette:
    """`mcp` is what answers MCP over HTTP, and `bridge` is where the extension in a person's own
    Chrome dials in. Without them the service has no such endpoints."""
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
            await _serve_viewer(socket, session, subscriber, config.server.command_backlog)
        except WebSocketDisconnect:
            pass
        finally:
            session.hub.unsubscribe(subscriber)

    async def extension_socket(socket: WebSocket) -> None:
        """The extension dials in (spec 4.9). Only this product's extension may, and only with the token."""
        assert bridge is not None
        if socket.headers.get("origin") != browser_extension.ORIGIN:
            await socket.close(NOT_THE_VIEWERS_ORIGIN)
            return
        await socket.accept()
        try:
            async with asyncio.timeout(config.server.auth_wait_s):
                first = _command(await socket.receive())
        except (TimeoutError, WebSocketDisconnect):
            first = None
        # A pairing token lets it in once; the key it is given then lets it come back after a cut.
        admitted = bridge.admit(first) if first and first.get("type") == "auth" else None
        if admitted is None or first is None:
            await socket.close(REFUSED)
            return
        await socket.send_text(json.dumps(admitted))
        await bridge.serve_extension(socket, attached=first.get("attached") is True)

    async def driver_socket(socket: WebSocket) -> None:
        """The driver's end of the bridge. It is this process's own driver: it comes from this
        machine, with the token."""
        assert bridge is not None
        scheme, _, given = socket.headers.get("authorization", "").partition(" ")
        local = socket.client is not None and socket.client.host in LOCAL_CLIENTS
        if not local or scheme.lower() != "bearer" or not signed_in(given):
            await socket.close(REFUSED)
            return
        await socket.accept()
        await bridge.serve_driver(socket)

    bridged = (
        [WebSocketRoute("/bridge", extension_socket), WebSocketRoute("/bridge/cdp", driver_socket)]
        if bridge is not None
        else []
    )
    return Starlette(
        routes=[
            Route("/healthz", healthz),
            Route("/api/sessions", list_sessions),
            *([Route(config.mcp.http_path, _McpEndpoint(mcp, signed_in))] if mcp is not None else []),
            WebSocketRoute("/api/sessions/{name}/ws", viewer_socket),
            *bridged,
            Mount("/demo-site", StaticFiles(directory=package / "demo_site", html=True)),
            Mount("/", StaticFiles(directory=viewer, html=True)),
        ],
        middleware=[
            Middleware(TrustedHostMiddleware, allowed_hosts=hosts, www_redirect=False),
            Middleware(_ResponseHeaders, embed_origins=config.viewer.embed_origins),
        ],
    )


async def _serve_viewer(
    socket: WebSocket, session: ServiceSession, subscriber: Subscriber, backlog: int
) -> None:
    """Sends the viewer what happens, and does what the person asks, until either side stops."""
    waiting: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    async def tell() -> None:
        while True:
            await _send(socket, await subscriber.next())

    async def listen() -> None:
        while True:
            command = _command(await socket.receive())
            if command is None:
                continue
            if command.get("type") == "stop":
                # Stop never waits its turn: a pause or a take-over ahead of it may be waiting for an
                # action that does not end.
                await session.handle(command)
            elif waiting.qsize() < backlog:
                waiting.put_nowait(command)
            # Past the limit a command is dropped: the page is not keeping up with what is sent.

    async def act() -> None:
        # One at a time and in order: what a person types must reach the page as it was typed.
        while True:
            await session.handle(await waiting.get())

    tasks = [asyncio.create_task(work()) for work in (tell, listen, act)]
    try:
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
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
    if not isinstance(text, str) or len(text) > LARGEST_VIEWER_MESSAGE:
        return None
    try:
        command = json.loads(text)
    except ValueError:
        return None
    return command if isinstance(command, dict) else None


class _McpEndpoint:
    """The tools over MCP, for an agent in another process. It is let in by the service's token,
    sent as a bearer token, like the API."""

    def __init__(self, handle: ASGIApp, signed_in: Callable[[Any], bool]) -> None:
        self._handle = handle
        self._signed_in = signed_in

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        scheme, _, given = Headers(scope=scope).get("authorization", "").partition(" ")
        if scheme.lower() != "bearer" or not self._signed_in(given):
            # What was sent is read first. An answer that closes the connection over a request still
            # unread reaches the sender as a broken connection, not as a refusal.
            read = 0
            while read < LARGEST_REFUSED_REQUEST:
                message = await receive()
                read += len(message.get("body", b""))
                if message["type"] != "http.request" or not message.get("more_body"):
                    break
            refusal = Response(status_code=401, headers={"WWW-Authenticate": "Bearer"})
            await refusal(scope, receive, send)
            return
        await self._handle(scope, receive, send)


class _ResponseHeaders:
    """Headers on every response: who may show the viewer inside their page, nothing guessed or leaked,
    and no connection left open afterwards.

    A browser that is closed cuts the idle connections it still holds, and on Windows Python's asyncio
    can then fail to let go of such a connection. The agent's own browser loads the demo site from
    this service and is closed at the end of every session, so each answer ends its connection.
    """

    def __init__(self, app: ASGIApp, embed_origins: list[str]) -> None:
        self._app = app
        ancestors = " ".join(["'self'", *embed_origins])
        self._headers = [
            (b"content-security-policy", f"frame-ancestors {ancestors}".encode()),
            (b"x-content-type-options", b"nosniff"),
            (b"referrer-policy", b"no-referrer"),
            (b"connection", b"close"),
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
