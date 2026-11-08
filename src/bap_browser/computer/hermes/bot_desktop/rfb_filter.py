# MIT License, Copyright (c) 2025 Nous Research. Changed only by scripts/take_hermes.py.
"""Byte-level RFB client→server gate for the Bot Desktop WebSocket bridge.

noVNC's ``viewOnly`` is a UI hint; anyone holding the socket could still inject input. The bridge
parses the client stream and forwards only non-input messages from viewers that do not hold the
lease. RFB messages do not align with WebSocket frames, so this is a stateful stream parser fed
arbitrary chunks (RFC 6143 §7.5 layouts; TigerVNC's EnableContinuousUpdates 150, Fence 248 and
SetDesktopSize 251 are framed too. 150 and 248 pass through untouched since they carry no input; QEMU
Extended KeyEvent 255 is keyboard input — noVNC switches to it as soon as Xvnc advertises the
pseudo-encoding — so it is gated like KeyEvent; SetDesktopSize resizes the bot's framebuffer under the
agent (Xvnc runs -AcceptSetDesktopSize), so it is gated like input: only the lease holder may send it).

Xvnc runs ``-SecurityTypes None``, so the handshake is fixed-size: 12-byte version, 1-byte security
choice, then ``ClientInit`` (1 byte). ``ServerInit`` is server→client and never crosses this filter.
"""

from __future__ import annotations

from typing import Callable

_INPUT_TYPES = {4, 5, 6, 251, 255}

_FIXED = {
    0: 20,
    3: 10,
    4: 8,
    5: 6,
    150: 10,
    255: 12,
}
_SET_ENCODINGS = 2
_CLIENT_CUT_TEXT = 6
_FENCE = 248
_SET_DESKTOP_SIZE = 251

_MAX_CUT_TEXT = 256 * 1024


class RfbClientFilter:
    """Feed client bytes with :meth:`feed`; get back the bytes allowed to reach Xvnc.

    ``allow_input`` is consulted per message so a lease flip mid-stream applies to the very next
    key or pointer event.
    """

    def __init__(self, allow_input: Callable[[], bool]) -> None:
        self._allow_input = allow_input
        self._buf = bytearray()
        self._handshake_left = 12 + 1 + 1

    def feed(self, chunk: bytes) -> bytes:
        self._buf += chunk
        out = bytearray()
        if self._handshake_left:
            take = min(self._handshake_left, len(self._buf))
            if take:
                head = bytes(self._buf[:take])
                if self._handshake_left - take == 0 and take >= 1:
                    head = head[:-1] + b"\x01"
                out += head
                del self._buf[:take]
                self._handshake_left -= take
            if self._handshake_left:
                return bytes(out)
        while self._buf:
            length = self._message_length()
            if length is None or len(self._buf) < length:
                break
            msg = bytes(self._buf[:length])
            del self._buf[:length]
            if msg[0] in _INPUT_TYPES and not self._allow_input():
                continue
            out += msg
        return bytes(out)

    def _message_length(self) -> int | None:
        t = self._buf[0]
        if t in _FIXED:
            return _FIXED[t]
        if t == _SET_ENCODINGS:
            if len(self._buf) < 4:
                return None
            n = int.from_bytes(self._buf[2:4], "big")
            return 4 + 4 * n
        if t == _CLIENT_CUT_TEXT:
            if len(self._buf) < 8:
                return None
            n = int.from_bytes(self._buf[4:8], "big", signed=True)
            if abs(n) > _MAX_CUT_TEXT:
                raise ValueError("clipboard message too large")
            return 8 + abs(n)
        if t == _FENCE:
            if len(self._buf) < 9:
                return None
            return 9 + self._buf[8]
        if t == _SET_DESKTOP_SIZE:
            if len(self._buf) < 8:
                return None
            return 8 + 16 * self._buf[6]
        raise ValueError(f"unknown RFB client message type {t}")
