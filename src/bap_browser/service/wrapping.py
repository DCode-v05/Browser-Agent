"""What is put around the service's own answers: who may reach MCP over HTTP, which tools an
agent finds there, and the headers every answer carries.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from starlette.datastructures import Headers
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from bap_browser.tools.registry import tools_hash

# A request that is refused is read no further than this before it is answered.
LARGEST_REFUSED_REQUEST = 64 * 1024


class McpEndpoint:
    """The tools over MCP, for an agent in another process. It is let in by the service's token,
    sent as a bearer token, like the API."""

    def __init__(self, handle: ASGIApp, signed_in: Callable[[Any], bool], origins: set[str]) -> None:
        self._handle = handle
        self._signed_in = signed_in
        self._origins = origins

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        headers = Headers(scope=scope)
        origin = headers.get("origin")
        # A browser says which page sends a request. A web page that is not the viewer's own has no
        # business with the tools, whatever token it holds. An agent that is no browser says nothing.
        own = {f"http://{headers.get('host', '')}", f"https://{headers.get('host', '')}"}
        if origin is not None and origin not in own | self._origins:
            await self._refuse(Response(status_code=403), scope, receive, send)
            return
        scheme, _, given = headers.get("authorization", "").partition(" ")
        if scheme.lower() != "bearer" or not self._signed_in(given):
            refusal = Response(status_code=401, headers={"WWW-Authenticate": "Bearer"})
            await self._refuse(refusal, scope, receive, send)
            return
        await self._handle(scope, receive, send)

    @staticmethod
    async def _refuse(refusal: Response, scope: Scope, receive: Receive, send: Send) -> None:
        # What was sent is read first. An answer that closes the connection over a request still
        # unread reaches the sender as a broken connection, not as a refusal.
        read = 0
        while read < LARGEST_REFUSED_REQUEST:
            message = await receive()
            read += len(message.get("body", b""))
            if message["type"] != "http.request" or not message.get("more_body"):
                break
        await refusal(scope, receive, send)


def tools_on_offer(
    sessions: Mapping[str, Any], allowed: Callable[..., Any], may_use: Callable[[Any, str], bool]
) -> Callable[[Request], Awaitable[Response]]:
    """The answer of `/api/tools` (spec 18.9): the tools each session offers, and one value that
    changes when any of them does. `allowed` says who asks, and `may_use` which sessions are theirs."""

    async def answer(request: Request) -> Response:
        role = allowed(request, "admin", "user")
        if isinstance(role, Response):
            return role
        offered = {
            name: {
                "hash": tools_hash(session.toolkit.definitions()),
                "tools": [tool.name for tool in session.toolkit.definitions()],
            }
            for name, session in sessions.items()
            if may_use(role, name)
        }
        return JSONResponse({"sessions": offered})

    return answer


class ResponseHeaders:
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
