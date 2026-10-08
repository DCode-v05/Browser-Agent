"""What is put around the service's own answers: who may reach MCP over HTTP, and the headers
every answer carries.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from starlette.datastructures import Headers
from starlette.responses import Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

# A request that is refused is read no further than this before it is answered.
LARGEST_REFUSED_REQUEST = 64 * 1024


class McpEndpoint:
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
