"""The HTTP surface (spec 4.7): the viewer's files, the API, and one WebSocket per viewer (spec 4.8).

How it is protected (spec 4.10): every request's Host must be this service's; the API and the
WebSocket need the token; a WebSocket's Origin must be the viewer's own or a listed one.
"""

from __future__ import annotations

import asyncio
import hmac
import json
import math
import time
from collections.abc import Callable, Mapping
from importlib.resources import files
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, Response
from starlette.routing import Mount, Route, WebSocketRoute
from starlette.staticfiles import StaticFiles
from starlette.types import ASGIApp
from starlette.websockets import WebSocket, WebSocketDisconnect

from bap_browser import browser_extension
from bap_browser.config import Config
from bap_browser.desktop_app import DesktopApp
from bap_browser.errors import BapError, ConfigError
from bap_browser.service.accounts import ROLES, Accounts, BadPassword, LockedOut, Role
from bap_browser.service.bridge import Bridge
from bap_browser.service.browsing_data import CLEAR, clear_browsing_data
from bap_browser.service.session import ServiceSession
from bap_browser.service.systems import Systems
from bap_browser.service.viewer_socket import LARGEST_VIEWER_MESSAGE, Close, command_of, send, serve_viewer
from bap_browser.service.wrapping import McpEndpoint, ResponseHeaders
from bap_browser.settings.store import SEES, Refused, SettingsStore, known_surface

LOCAL_HOSTS = ("127.0.0.1", "localhost")
LOCAL_CLIENTS = ("127.0.0.1", "::1")


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
    accounts: Accounts | None = None,
) -> Starlette:
    """`mcp` is what answers MCP over HTTP, and `bridge` is where the extension in a person's own
    Chrome dials in. Without them the service has no such endpoints. `desktop` is the desktop app,
    for the window to open. `settings` holds what a person chose in the settings screen. `systems`
    is whoever runs the browsers of a window that has several (spec 9.17). `accounts` holds who
    may sign in, as the admin or as a user (spec 4.11); without it, the service's own token is the
    one way in."""
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
        """Whether this is the service's own token: whoever started the service holds it."""
        return isinstance(given, str) and hmac.compare_digest(given.encode(), token.encode())

    def role_of(given: Any) -> Role | None:
        """Who a token speaks for (spec 4.11). The service's own token is the admin's: it is the
        person who started the service. Any other is a visit someone signed in for."""
        if signed_in(given):
            return "admin"
        return accounts.role_of(given) if accounts is not None else None

    def bearer(request: Request) -> str | None:
        scheme, _, given = request.headers.get("authorization", "").partition(" ")
        return given if scheme.lower() == "bearer" else None

    def allowed(request: Request, *roles: Role) -> Role | Response:
        """The role of whoever asks, when it is one of `roles`. Otherwise the refusal: 401 for
        nobody, 403 for someone who may not."""
        role = role_of(bearer(request))
        if role is None:
            return Response(status_code=401, headers={"WWW-Authenticate": "Bearer"})
        return role if role in roles else Response(status_code=403)

    def may_use(role: Role, system: str) -> bool:
        """Whether a person may use a browser of the window: the admin any, a user those the admin lets users in."""
        return role == "admin" or settings is None or settings.users_may_use(system)

    def sees(role: Role, what: str) -> bool:
        return role == "admin" or (settings is not None and settings.user_sees(what))

    # The viewers connected now: the token each came with, the browser each is on, and the way to
    # end the connection. A person is let in when they connect; this is how they stop being let in.
    watching: dict[WebSocket, tuple[Any, str, asyncio.Future[int]]] = {}

    def must_leave(given: Any, name: str) -> int | None:
        """Why a viewer may no longer be on a browser, as the code its connection is closed with:
        the visit is over, or the admin now keeps this browser from users. None while it may stay."""
        role = role_of(given)
        if role is None:
            return Close.REFUSED
        return None if may_use(role, name) else Close.NO_SUCH_SESSION

    def show_out() -> None:
        """Ends the connection of every viewer that may no longer be where it is (spec 4.11)."""
        for given, name, door in list(watching.values()):
            code = must_leave(given, name)
            if code is not None and not door.done():
                door.set_result(code)

    async def healthz(request: Request) -> Response:
        return Response()

    async def admin_page(request: Request) -> Response:
        """The admin's sign-in page. It is the viewer's own page: the page reads where it was opened."""
        return FileResponse(viewer / "index.html")

    async def list_sessions(request: Request) -> Response:
        role = allowed(request, "admin", "user")
        if isinstance(role, Response):
            return role
        listed: dict[str, Any] = {
            "sessions": [
                {"id": name, "state": session.control}
                for name, session in sessions.items()
                if may_use(role, name)
            ]
        }
        if rooms is not None:
            # One window, several browsers: each is a page of it (spec 9.16). A user is shown
            # those the admin lets users use.
            listed["rooms"] = [room for room in rooms() if may_use(role, room["id"])]
        if desktop is not None and role == "admin":
            # Whether the window has a desktop app to open (spec 9.16).
            listed["desktop"] = desktop.there
        if settings is not None:
            # The settings screen is this service's to draw (spec 10.2).
            listed["settings"] = True
        if systems is not None:
            # Its browsers are systems to set up, manage and evaluate (spec 9.17).
            listed["systems"] = True
        if accounts is not None:
            # People sign in, as the admin or as a user (spec 4.11).
            listed["role"] = role
        return JSONResponse(listed)

    async def open_desktop(request: Request) -> Response:
        role = allowed(request, "admin")
        if isinstance(role, Response):
            return role
        if desktop is None:
            return Response(status_code=404)
        try:
            opened = await asyncio.to_thread(desktop.start)
        except BapError as failed:
            return JSONResponse({"error": str(failed)}, status_code=409)
        return JSONResponse({"state": "opened" if opened else "open"})

    # Signing in (spec 4.11).

    async def auth_state(request: Request) -> Response:
        """What a sign-in page needs before anyone has signed in: whether there is a password to
        sign in with, and who the page's own token speaks for, when it has one."""
        if accounts is None:
            # Nobody signs in to this service: its own token is the one way in. It says so rather
            # than refuse the question, so that the page that asked shows no error for it.
            return JSONResponse({"accounts": False})
        given = bearer(request)
        return JSONResponse(
            {
                "accounts": True,
                "admin_set": accounts.has("admin"),
                "user_set": accounts.has("user"),
                "role": role_of(given),
                # The link the service printed when it started: it creates the admin's password.
                "operator": signed_in(given),
            }
        )

    async def sign_in(request: Request) -> Response:
        if accounts is None:
            return Response(status_code=404)
        asked = await _json_object(request)
        role = asked.get("role") if asked is not None else None
        if role not in ROLES or asked is None:
            return Response(status_code=400)
        if not accounts.has(role):
            return JSONResponse({"error": "not_set"}, status_code=409)
        try:
            # The hash is made slow on purpose: it is not made on the loop that runs the sessions.
            visit = await asyncio.to_thread(accounts.sign_in, role, asked.get("password"))
        except LockedOut as locked:
            return JSONResponse({"error": "locked", "wait_s": math.ceil(locked.wait_s)}, status_code=429)
        if visit is None:
            return JSONResponse({"error": "wrong"}, status_code=401)
        return JSONResponse({"token": visit, "role": role})

    async def set_password(request: Request) -> Response:
        """Sets a password: the admin's own, or the one users sign in with. For the admin alone,
        which the first time is whoever holds the link the service printed."""
        role = allowed(request, "admin")
        if isinstance(role, Response):
            return role
        if accounts is None:
            return Response(status_code=404)
        asked = await _json_object(request)
        whose = asked.get("role") if asked is not None else None
        if whose not in ROLES or asked is None:
            return Response(status_code=400)
        try:
            # The admin who changes their own password stays signed in.
            await asyncio.to_thread(accounts.set_password, whose, asked.get("password"), bearer(request))
        except BadPassword as bad:
            return JSONResponse({"error": str(bad)}, status_code=400)
        # Everyone who signed in with the old one signs in again: their open pages are closed too.
        show_out()
        return JSONResponse({"admin_set": accounts.has("admin"), "user_set": accounts.has("user")})

    async def sign_out(request: Request) -> Response:
        if accounts is None:
            return Response(status_code=404)
        accounts.sign_out(bearer(request))
        show_out()
        return JSONResponse({})

    def me_for(role: Role) -> dict[str, Any]:
        assert settings is not None
        return {
            "role": role,
            # The browsers this person may use, and the one their window opens on.
            "systems": settings.allowed_systems(role),
            "preferred": settings.preferred(role),
            "sees": {what: sees(role, what) for what in SEES},
        }

    async def read_me(request: Request) -> Response:
        role = allowed(request, "admin", "user")
        if isinstance(role, Response):
            return role
        if settings is None:
            return Response(status_code=404)
        return JSONResponse(me_for(role))

    async def change_me(request: Request) -> Response:
        """A person's preferred browser: the one their window opens on (spec 4.11)."""
        role = allowed(request, "admin", "user")
        if isinstance(role, Response):
            return role
        if settings is None:
            return Response(status_code=404)
        asked = await _json_object(request)
        if asked is None or "preferred" not in asked:
            return Response(status_code=400)
        try:
            settings.prefer(asked["preferred"], role)
        except Refused as no_change:
            return JSONResponse({"setting": no_change.setting, "reason": no_change.reason}, status_code=409)
        return JSONResponse(me_for(role))

    async def read_policy(request: Request) -> Response:
        role = allowed(request, "admin")
        if isinstance(role, Response):
            return role
        if settings is None:
            return Response(status_code=404)
        return JSONResponse(settings.policy())

    async def change_policy(request: Request) -> Response:
        """What users may use, change and see: the admin's to say (spec 4.11)."""
        role = allowed(request, "admin")
        if isinstance(role, Response):
            return role
        if settings is None:
            return Response(status_code=404)
        asked = await _json_object(request)
        if asked is None:
            return Response(status_code=400)
        try:
            settings.change_policy(asked)
        except Refused as no_change:
            return JSONResponse({"setting": no_change.setting, "reason": no_change.reason}, status_code=409)
        # A setting users may no longer change falls back to the admin's value at once.
        for session in list(sessions.values()):
            await session.settings_changed({})
        # And a user on a browser that users may no longer use is no longer on it.
        show_out()
        return JSONResponse(settings.policy())

    # Settings (spec 10.2).

    def a_system_or_none(role: Role, system: Any) -> bool:
        """Whether a request names no system, or one of the browsers this person may use."""
        if system is None:
            return True
        known = (
            isinstance(system, str) and rooms is not None and any(room["id"] == system for room in rooms())
        )
        return known and may_use(role, system)

    async def read_settings(request: Request) -> Response:
        """The settings screen is drawn from this answer (spec 10.2)."""
        role = allowed(request, "admin", "user")
        if isinstance(role, Response):
            return role
        surface = request.query_params.get("surface", "web")
        system = request.query_params.get("system")
        if settings is None:
            return Response(status_code=404)
        if not known_surface(surface) or not a_system_or_none(role, system):
            return Response(status_code=400)
        return JSONResponse(settings.answer(surface, system, role))

    async def change_settings(request: Request) -> Response:
        role = allowed(request, "admin", "user")
        if isinstance(role, Response):
            return role
        if settings is None:
            return Response(status_code=404)
        asked = await _json_object(request)
        surface = asked.get("surface") if asked is not None else None
        changes = asked.get("changes") if asked is not None else None
        system = asked.get("system") if asked is not None else None
        if not isinstance(surface, str) or not known_surface(surface) or not isinstance(changes, dict):
            return Response(status_code=400)
        if not a_system_or_none(role, system):
            return Response(status_code=400)
        try:
            changed = settings.change(surface, changes, system, role)
        except Refused as no_change:
            # Nothing was changed: one refused change refuses them all.
            return JSONResponse({"setting": no_change.setting, "reason": no_change.reason}, status_code=409)
        if changed:
            for session in list(sessions.values()):
                await session.settings_changed(changed)
            if systems is not None and system is not None:
                # A browser that was turned on or off is started or ended.
                await systems.settings_changed(system)
        return JSONResponse(settings.answer(surface, system, role))

    # The browsers as systems (spec 9.17, 12.6).

    def a_system(request: Request, *roles: Role) -> tuple[Role, str] | Response:
        """Who asks and the system they name; or the refusal, for a system there is none of, or
        that this person may not use."""
        role = allowed(request, *roles)
        if isinstance(role, Response):
            return role
        system = request.path_params.get("system")
        if systems is None or not any(told["id"] == system for told in systems.described()):
            return Response(status_code=404)
        if not may_use(role, str(system)):
            return Response(status_code=404)
        return role, str(system)

    def told_to(role: Role, described: dict[str, Any]) -> dict[str, Any]:
        """A system as this person is told of it. Where its files are is the admin's to know."""
        if role == "admin":
            return described
        hidden = {"records"} if sees(role, "log") else {"records", "log"}
        return {name: value for name, value in described.items() if name not in hidden}

    async def list_systems(request: Request) -> Response:
        """The browsers of the window as systems to set up and manage (spec 9.17)."""
        role = allowed(request, "admin", "user")
        if isinstance(role, Response):
            return role
        if systems is None:
            return Response(status_code=404)
        listed = [told_to(role, one) for one in systems.described() if may_use(role, one["id"])]
        return JSONResponse({"systems": listed})

    async def manage_system(request: Request) -> Response:
        asking = a_system(request, "admin", "user")
        if isinstance(asking, Response):
            return asking
        role, system = asking
        assert systems is not None
        action = request.path_params["action"]
        if role != "admin" and action != "start":
            # A user starts the browser they prefer when it has stopped. Stopping one is the admin's.
            return Response(status_code=403)
        why_not = await systems.manage(system, action)
        if why_not is not None:
            return JSONResponse({"error": why_not}, status_code=409)
        return JSONResponse(
            {"systems": [told_to(role, one) for one in systems.described() if may_use(role, one["id"])]}
        )

    async def system_log(request: Request) -> Response:
        asking = a_system(request, "admin", "user")
        if isinstance(asking, Response):
            return asking
        role, system = asking
        assert systems is not None
        if not sees(role, "log"):
            return Response(status_code=403)
        return JSONResponse(await asyncio.to_thread(systems.log, system))

    def shown_to(role: Role, evals: dict[str, Any]) -> dict[str, Any]:
        """What a system's tasks took, as this person may see it (spec 12.6). What the admin
        keeps from users is taken out here, not merely left undrawn by the page."""
        may = {what: sees(role, what) for what in ("cost", "traces", "checklist")}
        shown = {**evals, "may": may}
        if not may["cost"]:
            shown["cost"] = None
        if not may["traces"]:
            shown["recent"] = []
        elif not may["cost"]:
            shown["recent"] = [{**task, "cost_usd": None} for task in evals.get("recent", [])]
        if not may["checklist"]:
            shown["checklist"] = None
        return shown

    async def system_evals(request: Request) -> Response:
        asking = a_system(request, "admin", "user")
        if isinstance(asking, Response):
            return asking
        role, system = asking
        assert systems is not None
        if not sees(role, "evaluations"):
            return Response(status_code=403)
        return JSONResponse(shown_to(role, await asyncio.to_thread(systems.evals, system)))

    async def overall_evals(request: Request) -> Response:
        """Every system's tasks as one: the admin's view of the whole (spec 12.6)."""
        role = allowed(request, "admin")
        if isinstance(role, Response):
            return role
        if systems is None:
            return Response(status_code=404)
        return JSONResponse(await asyncio.to_thread(systems.overall))

    async def system_trace(request: Request) -> Response:
        asking = a_system(request, "admin", "user")
        if isinstance(asking, Response):
            return asking
        role, system = asking
        assert systems is not None
        if not (sees(role, "evaluations") and sees(role, "traces")):
            return Response(status_code=403)
        trace = await asyncio.to_thread(systems.trace, system, request.path_params["task"])
        if trace is None:
            return Response(status_code=404)
        return JSONResponse(trace if sees(role, "cost") else {**trace, "cost_usd": None})

    async def rate_task(request: Request) -> Response:
        asking = a_system(request, "admin", "user")
        if isinstance(asking, Response):
            return asking
        role, system = asking
        assert systems is not None
        if not (sees(role, "evaluations") and sees(role, "traces")):
            return Response(status_code=403)
        asked = await _json_object(request)
        rating = asked.get("rating") if asked is not None else "?"
        if rating not in ("good", "bad", None):
            return Response(status_code=400)
        known = await asyncio.to_thread(systems.rate, system, request.path_params["task"], rating)
        return JSONResponse({"rating": rating}) if known else Response(status_code=404)

    async def check_system(request: Request) -> Response:
        """Runs the checklist of one browser: real steps on the demo site (spec 12.6)."""
        asking = a_system(request, "admin", "user")
        if isinstance(asking, Response):
            return asking
        role, system = asking
        assert systems is not None
        if not (sees(role, "evaluations") and sees(role, "checklist")):
            return Response(status_code=403)
        result = await systems.check(system)
        if isinstance(result, str):
            return JSONResponse({"error": result}, status_code=409)
        return JSONResponse(result)

    def may_run(role: Role) -> bool:
        return sees(role, "evaluations") and sees(role, "checklist")

    async def system_suite(request: Request) -> Response:
        """The task sets of one browser, and how its runs of them went (spec 12.7)."""
        asking = a_system(request, "admin", "user")
        if isinstance(asking, Response):
            return asking
        role, system = asking
        assert systems is not None
        if not may_run(role):
            return Response(status_code=403)
        return JSONResponse(await asyncio.to_thread(systems.suite, system))

    async def run_suite(request: Request) -> Response:
        asking = a_system(request, "admin", "user")
        if isinstance(asking, Response):
            return asking
        role, system = asking
        assert systems is not None
        if not may_run(role):
            return Response(status_code=403)
        asked = await _json_object(request) or {}
        name, trials, mode = asked.get("set"), asked.get("trials"), asked.get("mode")
        if not isinstance(name, str) or type(trials) is not int or mode not in ("agent", "reference"):
            return Response(status_code=400)
        why_not = systems.start_suite(system, name, trials, mode)
        if why_not is not None:
            return JSONResponse({"error": why_not}, status_code=409)
        return JSONResponse(await asyncio.to_thread(systems.suite, system), status_code=202)

    async def stop_suite(request: Request) -> Response:
        asking = a_system(request, "admin", "user")
        if isinstance(asking, Response):
            return asking
        role, system = asking
        assert systems is not None
        if not may_run(role):
            return Response(status_code=403)
        if not await systems.stop_suite(system):
            return JSONResponse({"error": "No run is under way on this browser."}, status_code=409)
        return JSONResponse(await asyncio.to_thread(systems.suite, system))

    async def overall_suite(request: Request) -> Response:
        """The newest run of each task set on each browser: the admin's view of the whole."""
        role = allowed(request, "admin")
        if isinstance(role, Response):
            return role
        if systems is None:
            return Response(status_code=404)
        return JSONResponse(await asyncio.to_thread(systems.suite_overall))

    async def clear_data(request: Request) -> Response:
        """Clear browsing data: the one setting that is an action (spec 10.2)."""
        role = allowed(request, "admin")
        if isinstance(role, Response):
            return role
        if settings is None:
            return Response(status_code=404)
        if CLEAR in config.settings.locked:
            return JSONResponse({"setting": CLEAR, "reason": "locked"}, status_code=409)
        return JSONResponse(await clear_browsing_data(config, sessions, settings))

    async def read_config(request: Request) -> Response:
        """What "About this deployment" lists."""
        role = allowed(request, "admin")
        if isinstance(role, Response):
            return role
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
            await socket.close(Close.NOT_THE_VIEWERS_ORIGIN)
            return
        await socket.accept()
        try:
            async with asyncio.timeout(config.server.auth_wait_s):
                first = command_of(await socket.receive())
        except (TimeoutError, WebSocketDisconnect):
            first = None
        role = role_of(first.get("token")) if first and first.get("type") == "auth" else None
        if role is None:
            await socket.close(Close.REFUSED)
            return
        name = socket.path_params["name"]
        # A browser the admin keeps from users is, for a user, not there.
        session = sessions.get(name) if may_use(role, name) else None
        if session is None:
            await socket.close(Close.NO_SUCH_SESSION)
            return
        given = first.get("token") if first else None
        door: asyncio.Future[int] = asyncio.get_running_loop().create_future()
        watching[socket] = (given, name, door)
        replay, subscriber = session.hub.subscribe()
        try:
            for item in replay:
                await send(socket, item)
            await send(socket, {"type": "caught_up", "ts": time.time()})
            await serve_viewer(
                socket,
                session,
                subscriber,
                config.server.command_backlog,
                door,
                # A visit also ends by itself, when its time is up: nothing it asks for is done then.
                lambda: must_leave(given, name),
            )
        except WebSocketDisconnect:
            pass
        finally:
            del watching[socket]
            session.hub.unsubscribe(subscriber)

    async def extension_socket(socket: WebSocket) -> None:
        """The extension dials in (spec 4.9). Only this product's extension may, and only with the token."""
        assert bridge is not None
        if socket.headers.get("origin") != browser_extension.ORIGIN:
            await socket.close(Close.NOT_THE_VIEWERS_ORIGIN)
            return
        await socket.accept()
        try:
            async with asyncio.timeout(config.server.auth_wait_s):
                first = command_of(await socket.receive())
        except (TimeoutError, WebSocketDisconnect):
            first = None
        # A pairing token lets it in once; the key it is given then lets it come back after a cut.
        admitted = bridge.admit(first) if first and first.get("type") == "auth" else None
        if admitted is None or first is None:
            await socket.close(Close.REFUSED)
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
            await socket.close(Close.REFUSED)
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
            Route("/admin", admin_page),
            Route("/api/sessions", list_sessions),
            Route("/api/auth", auth_state, methods=["GET"]),
            Route("/api/auth/sign-in", sign_in, methods=["POST"]),
            Route("/api/auth/password", set_password, methods=["POST"]),
            Route("/api/auth/sign-out", sign_out, methods=["POST"]),
            Route("/api/me", read_me, methods=["GET"]),
            Route("/api/me", change_me, methods=["PATCH"]),
            Route("/api/admin/policy", read_policy, methods=["GET"]),
            Route("/api/admin/policy", change_policy, methods=["PATCH"]),
            Route("/api/evals", overall_evals, methods=["GET"]),
            Route("/api/suite", overall_suite, methods=["GET"]),
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
            Route("/api/systems/{system}/suite", system_suite, methods=["GET"]),
            Route("/api/systems/{system}/suite", run_suite, methods=["POST"]),
            Route("/api/systems/{system}/suite/stop", stop_suite, methods=["POST"]),
            Route("/api/systems/{system}/{action}", manage_system, methods=["POST"]),
            *([Route(config.mcp.http_path, McpEndpoint(mcp, signed_in))] if mcp is not None else []),
            WebSocketRoute("/api/sessions/{name}/ws", viewer_socket),
            *bridged,
            Mount("/demo-site", StaticFiles(directory=package / "demo_site", html=True)),
            Mount("/", StaticFiles(directory=viewer, html=True)),
        ],
        middleware=[
            Middleware(TrustedHostMiddleware, allowed_hosts=hosts, www_redirect=False),
            Middleware(ResponseHeaders, embed_origins=config.viewer.embed_origins),
        ],
    )


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
