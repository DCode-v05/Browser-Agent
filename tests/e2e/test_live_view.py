"""Live pictures of the browser, and a person's mouse and keyboard reaching the page (spec 4.8, 4.5)."""

import asyncio
import re
import struct
import time
from collections.abc import AsyncIterator, Callable

import pytest

from bap_browser.config import Config, QualityLevel
from bap_browser.driver.playwright_driver import PlaywrightDriver

STANDARD = QualityLevel(max_fps=24, jpeg_quality=70, max_width=1280)


@pytest.fixture
async def live(
    make_config: Callable[..., Config], tmp_path_factory: pytest.TempPathFactory
) -> AsyncIterator[PlaywrightDriver]:
    instance = PlaywrightDriver(make_config(tmp_path_factory.mktemp("data")))
    await instance.start()
    yield instance
    await instance.close()


async def until(condition: Callable[[], bool], what: str, timeout: float = 8.0) -> None:
    deadline = time.monotonic() + timeout
    while not condition():
        assert time.monotonic() < deadline, f"timed out waiting until {what}"
        await asyncio.sleep(0.02)


def jpeg_size(data: bytes) -> tuple[int, int]:
    """Width and height from the frame header of a JPEG."""
    position = 2
    while position < len(data):
        marker, length = struct.unpack(">HH", data[position : position + 4])
        if 0xFFC0 <= marker <= 0xFFCF and marker not in (0xFFC4, 0xFFC8, 0xFFCC):
            height, width = struct.unpack(">HH", data[position + 5 : position + 9])
            return width, height
        position += 2 + length
    raise AssertionError("not a JPEG with a frame header")


def ref_of(snapshot: str, element: str) -> str:
    match = re.search(re.escape(f"- {element}") + r" \[ref=(e\d+)\]", snapshot)
    assert match, f"{element!r} not in:\n{snapshot}"
    return match.group(1)


async def test_the_picture_arrives_as_a_jpeg_in_the_shape_of_the_page(
    live: PlaywrightDriver, site: str
) -> None:
    await live.navigate(f"{site}/form.html")
    frames: list[bytes] = []
    await live.start_frames(frames.append, STANDARD)
    await until(lambda: len(frames) > 0, "the first picture arrived")
    assert frames[0][:2] == b"\xff\xd8"
    assert jpeg_size(frames[0]) == (1280, 800)


async def test_a_lower_level_sends_a_smaller_picture(live: PlaywrightDriver, site: str) -> None:
    await live.navigate(f"{site}/form.html")
    frames: list[bytes] = []
    await live.start_frames(frames.append, QualityLevel(max_fps=8, jpeg_quality=50, max_width=800))
    await until(lambda: len(frames) > 0, "the first picture arrived")
    assert jpeg_size(frames[0]) == (800, 500)


async def test_a_new_picture_follows_every_change_and_survives_a_navigation(
    live: PlaywrightDriver, site: str
) -> None:
    await live.navigate(f"{site}/form.html")
    frames: list[bytes] = []
    await live.start_frames(frames.append, STANDARD)
    await until(lambda: len(frames) > 0, "the first picture arrived")

    seen = len(frames)
    page = await live.snapshot(mode="interactive", ref=None, max_chars=20000, include_bboxes=False)
    await live.type_text(ref_of(page, 'textbox "Full name"'), "Ada Lovelace")
    await until(lambda: len(frames) > seen, "a picture followed the typing")

    seen = len(frames)
    await live.navigate(f"{site}/welcome.html")
    await until(lambda: len(frames) > seen, "a picture followed the navigation")
    assert frames[-1] != frames[0]


async def test_the_rate_is_limited(live: PlaywrightDriver, site: str) -> None:
    await live.navigate(f"{site}/moving.html")
    frames: list[bytes] = []
    await live.start_frames(frames.append, QualityLevel(max_fps=4, jpeg_quality=50, max_width=800))
    await until(lambda: len(frames) > 0, "the first picture arrived")
    started, first = time.monotonic(), len(frames)
    await until(lambda: time.monotonic() - started >= 1.5, "a second and a half passed")
    arrived = len(frames) - first
    # The page moves on every frame of the browser, dozens of times a second. The browser keeps at
    # most two pictures on their way, and each acknowledgement lets one more out: 1.5 s at four a
    # second is seven acknowledgements at most, so nine pictures at most.
    assert 3 <= arrived <= 9, f"{arrived} pictures in 1.5 s at 4 a second"


async def test_pictures_stop_when_they_are_stopped(live: PlaywrightDriver, site: str) -> None:
    await live.navigate(f"{site}/moving.html")
    frames: list[bytes] = []
    await live.start_frames(frames.append, STANDARD)
    await until(lambda: len(frames) > 2, "pictures were arriving")
    await live.stop_frames()
    await live.page.evaluate(
        "new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done)))"
    )
    seen = len(frames)
    await live.page.evaluate("new Promise((done) => setTimeout(done, 300))")
    assert len(frames) == seen


async def test_a_persons_click_reaches_the_page(live: PlaywrightDriver, site: str) -> None:
    await live.navigate(f"{site}/form.html")
    box = await live.page.locator('input[name="terms"]').bounding_box()
    assert box is not None
    x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    await live.pointer("move", x, y, "left")
    await live.pointer("down", x, y, "left")
    await live.pointer("up", x, y, "left")
    assert await live.page.is_checked('input[name="terms"]')


async def test_a_persons_typing_reaches_the_page(live: PlaywrightDriver, site: str) -> None:
    await live.navigate(f"{site}/form.html")
    box = await live.page.locator("#name").bounding_box()
    assert box is not None
    x, y = box["x"] + 20, box["y"] + box["height"] / 2
    await live.pointer("down", x, y, "left")
    await live.pointer("up", x, y, "left")

    async def press(key: str) -> None:
        await live.key("down", key)
        await live.key("up", key)

    await live.key("down", "Shift")
    await press("A")
    await live.key("up", "Shift")
    # The last two are a letter the keyboard Playwright knows does not have, and a key name that is no key at all.
    for key in ("d", "a", "x", "Backspace", " ", "é", "Dead", "₹"):
        await press(key)
    assert await live.page.input_value("#name") == "Ada é₹"


async def test_a_persons_wheel_scrolls_the_page(live: PlaywrightDriver, site: str) -> None:
    await live.navigate(f"{site}/big.html?n=300")
    await live.wheel(400, 300, 0, 600)
    await live.page.wait_for_function("scrollY > 0", timeout=5000)
    assert await live.page.evaluate("scrollY") == 600
