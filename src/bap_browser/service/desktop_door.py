"""What the service opens on the machine it runs on, for a person at that machine: the desktop app
(spec 9.16), and the chat of one page in a window that stays above every other app (spec 22.3.1)."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from urllib.parse import quote

from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from bap_browser.config import Config
from bap_browser.desktop_app import DesktopApp
from bap_browser.errors import BapError
from bap_browser.service.accounts import Role
from bap_browser.service.session import ServiceSession

# The addresses a call from this machine itself comes from.
THIS_MACHINE = frozenset({"127.0.0.1", "::1", "localhost"})


def desktop_routes(
    desktop: DesktopApp | None,
    sessions: Mapping[str, ServiceSession],
    config: Config,
    allowed: Callable[..., Role | Response],
    may_use: Callable[[Role, str], bool],
    bearer: Callable[[Request], str | None],
) -> list[Route]:
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

    async def open_beside(request: Request) -> Response:
        """Opens the chat of one page in a window that stays above the other apps, signed in as
        whoever asks. Only for a person at this machine: a window opened here is of no use to
        somebody elsewhere."""
        role = allowed(request, "admin", "user")
        if isinstance(role, Response):
            return role
        name = request.path_params["name"]
        here = request.client is not None and request.client.host in THIS_MACHINE
        if not here or request.headers.get("x-forwarded-for"):
            return Response(status_code=404)
        if desktop is None or name not in sessions or not may_use(role, name):
            return Response(status_code=404)
        service = str(request.base_url).rstrip("/")
        chat = f"{service}/?session={quote(name)}&beside#token={bearer(request)}"
        try:
            opened = await asyncio.to_thread(desktop.chat_beside, chat, config.server.side_chat_width)
        except BapError as failed:
            return JSONResponse({"error": str(failed)}, status_code=409)
        return JSONResponse({"state": "opened" if opened else "open"})

    return [
        Route("/api/desktop", open_desktop, methods=["POST"]),
        Route("/api/sessions/{name}/beside", open_beside, methods=["POST"]),
    ]
