"""What a picture says about itself: its size, read from its first bytes."""

from __future__ import annotations

import struct

from bap_browser.errors import BrowserError
from bap_browser.results import Picture

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
# The JPEG markers that open a frame, which is where the size is written.
JPEG_FRAMES = frozenset(range(0xC0, 0xD0)) - {0xC4, 0xC8, 0xCC}
# The JPEG markers that stand alone, with no length after them.
JPEG_ALONE = frozenset({0x01, *range(0xD0, 0xDA)})


def size_of(picture: Picture) -> tuple[int, int]:
    """The width and height of a PNG or JPEG picture, in its own pixels."""
    data = picture.data
    if data.startswith(PNG_SIGNATURE) and len(data) >= 24:
        width, height = struct.unpack(">II", data[16:24])
        return width, height
    at = 2
    while data.startswith(b"\xff\xd8") and at + 9 <= len(data):
        if data[at] != 0xFF:
            at += 1
            continue
        marker = data[at + 1]
        if marker in JPEG_FRAMES:
            height, width = struct.unpack(">HH", data[at + 5 : at + 9])
            return width, height
        at += (
            2 if marker in JPEG_ALONE or marker == 0xFF else 2 + struct.unpack(">H", data[at + 2 : at + 4])[0]
        )
    raise BrowserError("The browser gave a picture that could not be read.", reason="the picture is broken")
