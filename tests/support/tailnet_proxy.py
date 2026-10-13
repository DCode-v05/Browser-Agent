"""A proxy as Tailscale gives a machine with no network device of its own (userspace mode): a name of
the tailnet is known to it and to nothing else on the machine. This one knows every name as a port
of this machine, and keeps the names it was asked for."""

from __future__ import annotations

import contextlib
import socket
import socketserver
import threading
from collections.abc import Iterator
from urllib.parse import urlsplit

END_OF_HEAD = b"\r\n\r\n"
CHUNK = 65536


def carried(one: socket.socket, other: socket.socket) -> None:
    with contextlib.suppress(OSError):
        while data := one.recv(CHUNK):
            other.sendall(data)
    with contextlib.suppress(OSError):
        other.shutdown(socket.SHUT_WR)


class Asked(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        asker: socket.socket = self.request
        head = b""
        while END_OF_HEAD not in head:
            more = asker.recv(CHUNK)
            if not more:
                return
            head += more
        first, _, rest = head.partition(b"\r\n")
        verb, target, version = first.decode("latin-1").split(" ")
        if verb == "CONNECT":
            name, _, port = target.rpartition(":")
            sent_on = head.partition(END_OF_HEAD)[2]
        else:
            parts = urlsplit(target)
            name, port = parts.hostname or "", str(parts.port or 80)
            path = parts.path + (f"?{parts.query}" if parts.query else "")
            sent_on = f"{verb} {path} {version}\r\n".encode("latin-1") + rest
        names: list[str] = self.server.names  # type: ignore[attr-defined]
        names.append(name)
        with socket.create_connection(("127.0.0.1", int(port))) as there:
            if verb == "CONNECT":
                asker.sendall(b"HTTP/1.1 200 Connection established\r\n\r\n")
            there.sendall(sent_on)
            back = threading.Thread(target=carried, args=(there, asker), daemon=True)
            back.start()
            carried(asker, there)
            back.join()


class Proxy(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True


@contextlib.contextmanager
def a_tailnet_proxy() -> Iterator[tuple[str, list[str]]]:
    """The proxy's address, and the names it is asked for as they come."""
    with Proxy(("127.0.0.1", 0), Asked) as proxy:
        names: list[str] = []
        proxy.names = names  # type: ignore[attr-defined]
        thread = threading.Thread(target=proxy.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"http://127.0.0.1:{proxy.server_address[1]}", names
        finally:
            proxy.shutdown()
            thread.join()
