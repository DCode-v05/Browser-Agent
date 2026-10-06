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
from bap_browser.desktop_app import DesktopApp
from bap_browser.errors import BapError, ConfigError
from bap_browser.service.bridge import Bridge
from bap_browser.service.browsing_data import CLEAR, clear_browsing_data
from bap_browser.service.events import FellBehind, Subscriber
from bap_browser.service.session import ServiceSession
from bap_browser.service.systems import Systems
from bap_browser.settings.store import Refused, SettingsStore, known_surface

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
    rooms: Callable[[], list[dict[str, Any]]] | None = None,
    desktop: DesktopApp | None = None,
    settings: SettingsStore | None = None,
    systems: Systems | None = None,
) -> Starlette:
    """`mcp` is what answers MCP over HTTP, and `bridge` is where the extension in a person's own
    Chrome dials in. Without them the service has no such endpoints. `desktop` is the desktop app,
    for the window to open. `settings` holds what a person chose in the settings screen. `systems`
    is whoever runs the browsers of a window that has several (spec 9.17)."""
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

    def refused(request: Request) -> Response | None:
        scheme, _, given = request.headers.get("authorization", "").partition(" ")
        if scheme.lower() != "bearer" or not signed_in(given):
            return Response(status_code=401, headers={"WWW-Authenticate": "Bearer"})
        return None

    async def list_sessions(request: Request) -> Response:
        if (no := refused(request)) is not None:
            return no
        listed: dict[str, Any] = {
            "sessions": [{"id": name, "state": session.control} for name, session in sessions.items()]
        }
        if rooms is not None:
            # One window, several browsers: each is a page of it (spec 9.16).
            listed["rooms"] = rooms()
        if desktop is not None:
            # Whether the window has a desktop app to open (spec 9.16).
            listed["desktop"] = desktop.there
        if settings is not None:
            # The settings screen is this service's to draw (spec 10.2).
            listed["settings"] = True
        if systems is not None:
            # Its browsers are systems to set up, manage and evaluate (spec 9.17).
            listed["systems"] = True
        return JSONResponse(listed)

    async def open_desktop(request: Request) -> Response:
        if (no := refused(request)) is not None:
            return no
        if desktop is None:
            return Response(status_code=404)
        try:
            opened = await asyncio.to_thread(desktop.start)
        except BapError as failed:
            return JSONResponse({"error": str(failed)}, status_code=409)
        return JSONResponse({"state": "opened" if opened else "open"})

    def a_system_or_none(system: Any) -> bool:
        """Whether a request names no system, or one of the browsers this service has."""
        if system is None:
            return True
        return isinstance(system, str) and rooms is not None and any(room["id"] == system for room in rooms())

    async def read_settings(request: Request) -> Response:
        """The settings screen is drawn from this answer (spec 10.2)."""
        if (no := refused(request)) is not None:
            return no
        surface = request.query_params.get("surface", "web")
        system = request.query_params.get("system")
        if settings is None:
            return Response(status_code=404)
        if not known_surface(surface) or not a_system_or_none(system):
            return Response(status_code=400)
        return JSONResponse(settings.answer(surface, system))

    async def change_settings(request: Request) -> Response:
        if (no := refused(request)) is not None:
            return no
        if settings is None:
            return Response(status_code=404)
        asked = await _json_object(request)
        surface = asked.get("surface") if asked is not None else None
        changes = asked.get("changes") if asked is not None else None
        system = asked.get("system") if asked is not None else None
        if not isinstance(surface, str) or not known_surface(surface) or not isinstance(changes, dict):
            return Response(status_code=400)
        if not a_system_or_none(system):
            return Response(status_code=400)
        try:
            changed = settings.change(surface, changes, system)
        except Refused as no_change:
            # Nothing was changed: one refused change refuses them all.
            return JSONResponse({"setting": no_change.setting, "reason": no_change.reason}, status_code=409)
        if changed:
            for session in list(sessions.values()):
                await session.settings_changed(changed)
            if systems is not None and system is not None:
                # A browser that was turned on or off is started or ended.
                await systems.settings_changed(system)
        return JSONResponse(settings.answer(surface, system))

    def a_system(request: Request) -> str | Response:
        """The system a request names, or the answer for a request that names none there is."""
        if (no := refused(request)) is not None:
            return no
        system = request.path_params.get("system")
        if systems is None or not any(told["id"] == system for told in systems.described()):
            return Response(status_code=404)
        return str(system)

    async def list_systems(request: Request) -> Response:
        """The browsers of the window as systems to set up and manage (spec 9.17)."""
        if (no := refused(request)) is not None:
            return no
        if systems is None:
            return Response(status_code=404)
        return JSONResponse({"systems": systems.described()})

    async def manage_system(request: Request) -> Response:
        system = a_system(request)
        if isinstance(system, Response):
            return system
        assert systems is not None
        why_not = await systems.manage(system, request.path_params["action"])
        if why_not is not None:
            return JSONResponse({"error": why_not}, status_code=409)
        return JSONResponse({"systems": systems.described()})

    async def system_log(request: Request) -> Response:
        system = a_system(request)
        if isinstance(system, Response):
            return system
        assert systems is not None
        return JSONResponse(await asyncio.to_thread(systems.log, system))

    async def system_evals(request: Request) -> Response:
        system = a_system(request)
        if isinstance(system, Response):
            return system
        assert systems is not None
        return JSONResponse(await asyncio.to_thread(systems.evals, system))

    async def system_trace(request: Request) -> Response:
        system = a_system(request)
        if isinstance(system, Response):
            return system
        assert systems is not None
        trace = await asyncio.to_thread(systems.trace, system, request.path_params["task"])
        return Response(status_code=404) if trace is None else JSONResponse(trace)

    async def rate_task(request: Request) -> Response:
        system = a_system(request)
        if isinstance(system, Response):
            return system
        assert systems is not None
        asked = await _json_object(request)
        rating = asked.get("rating") if asked is not None else "?"
        if rating not in ("good", "bad", None):
            return Response(status_code=400)
        known = await asyncio.to_thread(systems.rate, system, request.path_params["task"], rating)
        return JSONResponse({"rating": rating}) if known else Response(status_code=404)

    async def check_system(request: Request) -> Response:
        """Runs the checklist of one browser: real steps on the demo site (spec 12.6)."""
        system = a_system(request)
        if isinstance(system, Response):
            return system
        assert systems is not None
        result = await systems.check(system)
        if isinstance(result, str):
            return JSONResponse({"error": result}, status_code=409)
        return JSONResponse(result)

    async def clear_data(request: Request) -> Response:
        """Clear browsing data: the one setting that is an action (spec 10.2)."""
        if (no := refused(request)) is not None:
            return no
        if settings is None:
            return Response(status_code=404)
        if CLEAR in config.settings.locked:
            return JSONResponse({"setting": CLEAR, "reason": "locked"}, status_code=409)
        return JSONResponse(await clear_browsing_data(config, sessions, settings))

    async def read_config(request: Request) -> Response:
        """What "About this deployment" lists."""
        if (no := refused(request)) is not None:
            return no
        if settings is None:
            return Response(status_code=404)
        drivers = (session.browser.started_driver for session in sessions.values())
        browser = next((driver.description() for driver in drivers if driver is not None), "")
        return JSONResponse(settings.about(browser))

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
            Route("/api/desktop", open_desktop, methods=["POST"]),
            Route("/api/settings", read_settings, methods=["GET"]),
            Route("/api/settings", change_settings, methods=["PATCH"]),
            Route("/api/config", read_config, methods=["GET"]),
            Route("/api/browsing-data/clear", clear_data, methods=["POST"]),
            Route("/api/systems", list_systems, methods=["GET"]),
            Route("/api/systems/{system}/log", system_log, methods=["GET"]),
            Route("/api/systems/{system}/evals", system_evals, methods=["GET"]),
            Route("/api/systems/{system}/evals/{task}", system_trace, methods=["GET"]),
            Route("/api/systems/{system}/evals/{task}/rating", rate_task, methods=["POST"]),
            Route("/api/systems/{system}/checks", check_system, methods=["POST"]),
            Route("/api/systems/{system}/{action}", manage_system, methods=["POST"]),
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


async def _json_object(request: Request) -> dict[str, Any] | None:
    """What a request carries, when that is a JSON object no larger than a person's command."""
    body = b""
    async for part in request.stream():
        body += part
        if len(body) > LARGEST_VIEWER_MESSAGE:
            return None
    try:
        data = json.loads(body)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


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
