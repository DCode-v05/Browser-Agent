"""Screenshots in a real browser (spec 5.5). A picture is taken only when a call asks for one."""

import struct
from collections.abc import Callable
from pathlib import Path

import pytest

from bap_browser.agent.models import ref_of
from bap_browser.config import Config
from bap_browser.driver import open_session
from bap_browser.driver.playwright_driver import PlaywrightDriver
from bap_browser.errors import BadInput
from bap_browser.results import Picture
from bap_browser.tools import Toolkit

PNG = b"\x89PNG\r\n\x1a\n"


def size_of(picture: Picture) -> tuple[int, int]:
    """The width and height a PNG picture says it has."""
    assert picture.mime == "image/png" and picture.data.startswith(PNG)
    width, height = struct.unpack(">II", picture.data[16:24])
    return width, height


async def test_a_picture_of_what_the_browser_shows(driver: PlaywrightDriver, site: str) -> None:
    await driver.navigate(f"{site}/tools.html")
    shot = await driver.screenshot(full_page=False, annotate=False)
    assert (shot.width, shot.height, shot.scaled) == (1280, 800, False)
    assert size_of(shot.picture) == (1280, 800)


async def test_a_picture_of_the_whole_page_is_made_to_fit(driver: PlaywrightDriver, site: str) -> None:
    await driver.navigate(f"{site}/tools.html")
    shot = await driver.screenshot(full_page=True, annotate=False)
    # The page is far taller than the longest side a picture may have.
    assert shot.scaled and shot.height == 1568 and shot.width < 1280
    assert size_of(shot.picture) == (shot.width, shot.height)
    # The page is where it was: taking the picture scrolled nothing.
    assert await driver.page.evaluate("scrollY") == 0


async def test_a_region_of_the_last_screenshot_at_full_resolution(
    driver: PlaywrightDriver, site: str
) -> None:
    await driver.navigate(f"{site}/tools.html")
    whole = await driver.screenshot(full_page=True, annotate=False)
    page_height = await driver.page.evaluate("document.documentElement.scrollHeight")
    shrunk = whole.height / page_height
    # A tenth of the picture's height, across its whole width, is a tenth of the page at its real size.
    closer = await driver.zoom((0, 0, whole.width, whole.height / 10))
    assert closer.width == 1280 and closer.height == pytest.approx(whole.height / 10 / shrunk, abs=1)
    assert size_of(closer.picture) == (closer.width, closer.height)

    with pytest.raises(BadInput, match=f"inside the last screenshot, which is {whole.width} by 1568"):
        await driver.zoom((0, 0, whole.width + 1, 10))
    with pytest.raises(BadInput, match="x0 less than x1"):
        await driver.zoom((50, 0, 50, 10))


async def test_a_region_needs_a_screenshot_to_be_a_region_of(
    make_config: Callable[..., Config], tmp_path: Path, site: str
) -> None:
    fresh = PlaywrightDriver(make_config(tmp_path))
    await fresh.start()
    try:
        await fresh.navigate(f"{site}/tools.html")
        with pytest.raises(BadInput, match="Take a screenshot first"):
            await fresh.zoom((0, 0, 10, 10))
    finally:
        await fresh.close()


async def test_on_a_dense_screen_a_picture_is_still_one_pixel_to_a_page_pixel(
    make_config: Callable[..., Config], tmp_path: Path, site: str
) -> None:
    dense = PlaywrightDriver(make_config(tmp_path, browser={"device_scale_factor": 2}))
    await dense.start()
    try:
        await dense.navigate(f"{site}/tools.html")
        shot = await dense.screenshot(full_page=False, annotate=False)
        assert size_of(shot.picture) == (1280, 800)
        assert dense.page_point(650, 60) == (650, 60)
        # The closer picture holds every pixel the screen has for the region.
        closer = await dense.zoom((600, 40, 700, 80))
        assert size_of(closer.picture) == (200, 80) == (closer.width, closer.height)
        # Taking pictures left the screen the browser emulates as it was.
        screen = await dense.page.evaluate("[devicePixelRatio, innerWidth, innerHeight]")
        assert screen == [2, 1280, 800]
    finally:
        await dense.close()


async def test_a_point_of_a_picture_that_was_made_smaller_is_a_point_of_the_page(
    make_config: Callable[..., Config], tmp_path: Path, site: str
) -> None:
    config = make_config(tmp_path, browser={"viewport": {"width": 2000, "height": 1000}})
    async with open_session(config) as session:
        tools = Toolkit(session)
        await tools.call("browser_navigate", {"url": f"{site}/tools.html"})
        shot = await tools.call("browser_screenshot", {})
        assert shot.picture is not None and size_of(shot.picture) == (1568, 784)
        assert shot.text.startswith(
            "Screenshot of what the browser shows, 1568 by 784 pixels. "
            "x and y of a click are pixels of this picture.\n[tabs]"
        ), shot.text
        # The button is at 650, 60 on the page, which is 510, 47 in the picture.
        clicked = await tools.call("browser_click", {"x": 510, "y": 47})
        assert clicked.text.startswith('Clicked (510, 47) (button "Spot")'), clicked.text
        assert "Spotted with 1 click" in (await tools.call("browser_get_text", {})).text


async def test_the_screenshot_tools(make_config: Callable[..., Config], tmp_path: Path, site: str) -> None:
    async with open_session(make_config(tmp_path)) as session:
        tools = Toolkit(session)
        page = await tools.call("browser_navigate", {"url": f"{site}/tools.html"})
        assert page.picture is None, "no picture unless a call asks for one"

        early = await tools.call("browser_zoom", {"region": [0, 0, 100, 100]})
        assert early.is_error and early.picture is None
        assert early.text.startswith("Take a screenshot first: the region is given in its pixels.")

        plain = await tools.call("browser_screenshot", {})
        assert plain.picture is not None and size_of(plain.picture) == (1280, 800)

        whole = await tools.call("browser_screenshot", {"full_page": True})
        assert whole.picture is not None
        assert whole.text.startswith("Screenshot of the whole page, ")
        assert "To click by x and y, take a screenshot of what the browser shows first." in whole.text
        # A picture of the whole page is not what a click by x and y is measured in.
        assert (await tools.call("browser_click", {"x": 650, "y": 60})).text.startswith(
            'Clicked (650, 60) (button "Spot")'
        )

        marked = await tools.call("browser_screenshot", {"annotate": True})
        assert marked.picture is not None and marked.picture.data != plain.picture.data
        # The refs drawn on the picture are the refs of the page that follows it.
        assert "Each ref is drawn at its element.\nPage: Tools\n" in marked.text
        assert ref_of(marked.text, 'button "Spot"') == ref_of(page.text, 'button "Spot"')

        closer = await tools.call("browser_zoom", {"region": [600, 40, 700, 80]})
        assert closer.picture is not None and size_of(closer.picture) == (100, 40)
        assert closer.text.startswith(
            "The region (600, 40) to (700, 80) of the last screenshot, 100 by 40 pixels."
        )
        outside = await tools.call("browser_zoom", {"region": [0, 0, 5000, 10]})
        assert outside.is_error and "must lie inside the last screenshot" in outside.text
        short = await tools.call("browser_zoom", {"region": [0, 0, 10]})
        assert short.is_error and short.text.startswith("browser_zoom: bad value for 'region'")

    log = (tmp_path / "events.jsonl").read_text(encoding="utf-8")
    assert "PNG" not in log and "iVBOR" not in log, "a picture reached the log"


async def test_the_labels_of_a_marked_picture_do_not_stay_in_the_page(
    driver: PlaywrightDriver, site: str
) -> None:
    await driver.navigate(f"{site}/tools.html")
    await driver.snapshot(mode="interactive", ref=None, max_chars=20000, include_bboxes=False)
    before = await driver.page.evaluate("document.documentElement.childElementCount")
    plain = await driver.screenshot(full_page=False, annotate=False)
    marked = await driver.screenshot(full_page=False, annotate=True)
    assert marked.picture.data != plain.picture.data
    assert await driver.page.evaluate("document.documentElement.childElementCount") == before
    again = await driver.screenshot(full_page=False, annotate=False)
    assert again.picture.data == plain.picture.data, "the labels were still drawn"


async def test_a_picture_in_the_other_format(
    make_config: Callable[..., Config], tmp_path: Path, site: str
) -> None:
    config = make_config(tmp_path, browser={"screenshot": {"format": "jpeg", "jpeg_quality": 60}})
    photo = PlaywrightDriver(config)
    await photo.start()
    try:
        await photo.navigate(f"{site}/tools.html")
        shot = await photo.screenshot(full_page=False, annotate=False)
        assert shot.picture.mime == "image/jpeg" and shot.picture.data.startswith(b"\xff\xd8")
    finally:
        await photo.close()
