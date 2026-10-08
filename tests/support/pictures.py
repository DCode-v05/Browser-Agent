"""Comparing two pictures as a person would see them.

A browser does not always draw the same page to the same bytes. The rounded corner of a native
control, drawn again after something was drawn over it, can come out one shade lighter or darker in
a pixel or two: on one machine and not on another. A test that asks for the same bytes then fails on
a machine where nothing a person could see has changed. These read the pixels, and say how far
apart two pictures are.
"""

from __future__ import annotations

import struct
import zlib

SIGNATURE = b"\x89PNG\r\n\x1a\n"
# How many numbers a pixel has, by the PNG colour type: grey, colour, grey with alpha, colour with alpha.
CHANNELS = {0: 1, 2: 3, 4: 2, 6: 4}
# A difference of this many shades out of 255 in one colour of one pixel is not seen by anyone.
SAME_TO_THE_EYE = 2


def rows_of(png: bytes) -> tuple[list[bytes], int]:
    """The rows of a PNG's pixels, and how many numbers a pixel has. For pictures of eight bits a
    colour that are not interlaced, which is what a browser gives."""
    if not png.startswith(SIGNATURE):
        raise ValueError("not a PNG")
    at, packed, width, height, channels = len(SIGNATURE), b"", 0, 0, 0
    while at < len(png):
        size, kind = struct.unpack(">I4s", png[at : at + 8])
        body = png[at + 8 : at + 8 + size]
        if kind == b"IHDR":
            width, height, depth, colour, _, _, interlaced = struct.unpack(">IIBBBBB", body)
            if depth != 8 or interlaced or colour not in CHANNELS:
                raise ValueError("a kind of PNG these do not read")
            channels = CHANNELS[colour]
        elif kind == b"IDAT":
            packed += body
        at += 12 + size
    raw, stride = zlib.decompress(packed), width * channels
    rows: list[bytes] = []
    above = bytearray(stride)
    for number in range(height):
        start = number * (stride + 1)
        row = _unfiltered(raw[start], bytearray(raw[start + 1 : start + 1 + stride]), above, channels)
        rows.append(bytes(row))
        above = row
    return rows, channels


def _unfiltered(kind: int, row: bytearray, above: bytearray, channels: int) -> bytearray:
    """One row as it is, from how PNG wrote it: each number as its difference from its neighbours."""
    for x in range(len(row)):
        left = row[x - channels] if x >= channels else 0
        up = above[x]
        corner = above[x - channels] if x >= channels else 0
        if kind == 1:
            guess = left
        elif kind == 2:
            guess = up
        elif kind == 3:
            guess = (left + up) // 2
        elif kind == 4:
            nearest = left + up - corner
            by = (abs(nearest - left), abs(nearest - up), abs(nearest - corner))
            guess = left if by[0] <= by[1] and by[0] <= by[2] else up if by[1] <= by[2] else corner
        else:
            guess = 0
        row[x] = (row[x] + guess) & 255
    return row


def furthest_apart(one: bytes, other: bytes) -> int:
    """The largest difference in any colour of any pixel between two PNGs of one size, in shades
    out of 255. Zero when a person and a machine would both call them the same."""
    first, channels = rows_of(one)
    second, other_channels = rows_of(other)
    if channels != other_channels or len(first) != len(second) or len(first[0]) != len(second[0]):
        raise ValueError("the two pictures are not of one size and kind")
    return max(
        (
            abs(a - b)
            for row, other_row in zip(first, second, strict=True)
            for a, b in zip(row, other_row, strict=True)
        ),
        default=0,
    )


def look_the_same(one: bytes, other: bytes) -> bool:
    """Whether nobody could tell the two pictures apart."""
    return furthest_apart(one, other) <= SAME_TO_THE_EYE


def a_png(rows: list[list[tuple[int, int, int]]]) -> bytes:
    """A PNG of the given pixels, for a test that needs a picture it knows."""
    width, height = len(rows[0]), len(rows)
    raw = b"".join(b"\x00" + bytes(number for pixel in row for number in pixel) for row in rows)

    def chunk(kind: bytes, body: bytes) -> bytes:
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))

    head = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return SIGNATURE + chunk(b"IHDR", head) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")
