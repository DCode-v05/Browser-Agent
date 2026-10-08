"""A stand-in for the model provider's API: a real HTTP server on this machine that answers from a list.

It is the one thing these tests fake, because the real one is another company's service. Replies are
shaped as the provider's reference documents them.
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


def said(text: str) -> dict[str, Any]:
    return {
        "type": "message",
        "id": "msg_1",
        "role": "assistant",
        "status": "completed",
        "content": [{"type": "output_text", "text": text, "annotations": []}],
    }


def called(call_id: str, name: str, arguments: str) -> dict[str, Any]:
    return {
        "type": "function_call",
        "id": f"fc_{call_id}",
        "call_id": call_id,
        "name": name,
        "arguments": arguments,
        "status": "completed",
    }


def thought(item_id: str) -> dict[str, Any]:
    return {"type": "reasoning", "id": item_id, "summary": [], "encrypted_content": f"sealed-{item_id}"}


def response(*output: dict[str, Any], status: str = "completed", **extra: Any) -> dict[str, Any]:
    return {
        "id": "resp_1",
        "object": "response",
        "status": status,
        "error": None,
        "output": list(output),
    } | extra


def spent(sent: int, written: int) -> dict[str, Any]:
    """The `usage` of a response: the tokens the provider counted."""
    return {"input_tokens": sent, "output_tokens": written, "total_tokens": sent + written}


@dataclass(frozen=True)
class Slow:
    """A reply that is held back for so many seconds, as a provider under load does."""

    seconds: float
    reply: Any


class ModelStandIn:
    """Answers each request with the next reply.

    A reply is a response body; or (status, body) for a refusal; or (status, body, headers); or any
    of these inside `Slow`.
    """

    def __init__(self, *replies: Any) -> None:
        self.replies = list(replies)
        self.requests: list[dict[str, Any]] = []
        """Each request as it arrived: `path`, `authorization`, and `body`."""
        self._closing = threading.Event()
        stand_in = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                length = int(self.headers.get("Content-Length", "0"))
                stand_in.requests.append(
                    {
                        "path": self.path,
                        "authorization": self.headers.get("Authorization"),
                        "body": json.loads(self.rfile.read(length)),
                    }
                )
                reply = stand_in.replies.pop(0)
                if isinstance(reply, Slow):
                    stand_in._closing.wait(reply.seconds)
                    reply = reply.reply
                status, body, *more = reply if isinstance(reply, tuple) else (200, reply)
                data = json.dumps(body).encode()
                try:
                    self.send_response(status)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(data)))
                    for name, value in (more[0] if more else {}).items():
                        self.send_header(name, value)
                    self.end_headers()
                    self.wfile.write(data)
                except OSError:
                    # The caller stopped waiting for a slow reply and hung up.
                    self.close_connection = True

            def log_message(self, format: str, *args: Any) -> None:
                """The stand-in writes nothing to the test output."""

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        self.base_url = f"http://127.0.0.1:{self._server.server_port}/v1"

    def close(self) -> None:
        self._closing.set()
        self._server.shutdown()
        self._server.server_close()
        self._thread.join()
