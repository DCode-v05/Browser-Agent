"""Every state of the viewer, in both themes, at desktop and phone width (spec 9.3, 9.9, 12.5)."""

from collections.abc import Awaitable, Callable
from typing import Any

import pytest

# Test files cannot import each other (pytest's importlib mode), so the fixture's type is spelled here.
OpenView = Callable[..., Awaitable[Any]]
SIZES = ["desktop", "phone"]

STATES = [
    "no_agent",
    "empty",
    "agent",
    "waiting_approval",
    "person_requested",
    "person",
    "person_unasked",
    "paused",
    "blocked",
    "dialog",
    "denied",
    "ended",
    "disconnected",
    "stale",
    "own_browser",
]
THEMES = ["light", "dark"]


@pytest.mark.parametrize("size", SIZES)
@pytest.mark.parametrize("theme", THEMES)
@pytest.mark.parametrize("state", STATES)
async def test_a_state_is_clean_readable_and_fits(
    open_view: OpenView, state: str, theme: str, size: str
) -> None:
    view = await open_view(f"state={state}&theme={theme}", size)
    await view.shot(f"{state}-{theme}-{size}")
    assert view.errors == []
    assert await view.sideways_overflow() == 0
    assert await view.accessibility_violations() == []


@pytest.mark.parametrize(
    "state", ["agent", "waiting_approval", "person_requested", "person", "paused", "blocked"]
)
async def test_who_is_driving_is_said_in_words_on_the_picture(open_view: OpenView, state: str) -> None:
    view = await open_view(f"state={state}")
    label = view.page.locator(".frame-label")
    assert (await label.inner_text()).strip() != ""
    assert await label.locator("svg").count() == 1, "every state has an icon as well as a colour"


async def test_the_picture_is_drawn_and_its_target_is_outlined(open_view: OpenView) -> None:
    view = await open_view("state=agent")
    await view.page.wait_for_function(
        "() => { const c = document.querySelector('canvas.frame-picture');"
        " const p = c.getContext('2d').getImageData(c.width / 2, c.height / 2, 1, 1).data; return p[3] > 0; }"
    )
    frame = await view.page.locator(".frame").bounding_box()
    target = await view.page.locator(".target").bounding_box()
    assert frame and target
    assert frame["x"] < target["x"] and target["x"] + target["width"] < frame["x"] + frame["width"]
    assert frame["y"] < target["y"] and target["y"] + target["height"] < frame["y"] + frame["height"]


async def test_the_picture_keeps_the_browsers_shape(open_view: OpenView) -> None:
    for size in SIZES:
        view = await open_view("state=agent", size)
        box = await view.page.locator("canvas.frame-picture").bounding_box()
        assert box
        assert abs(box["width"] / box["height"] - 1280 / 800) < 0.02, size


async def test_inside_a_client_the_product_name_is_dropped(open_view: OpenView) -> None:
    assert await (await open_view("state=agent")).page.get_by_text("bap-browser", exact=True).count() == 1
    assert (
        await (await open_view("state=agent&embed")).page.get_by_text("bap-browser", exact=True).count() == 0
    )


async def test_at_twice_the_text_size_the_layout_reflows_to_one_column(browser, viewer_url: str) -> None:
    # 200% zoom on a 1360 px wide window lays the page out at 680 px.
    page = await browser.new_page(viewport={"width": 680, "height": 425})
    try:
        await page.goto(f"{viewer_url}?state=waiting_approval")
        await page.wait_for_selector(".app")
        assert (
            await page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
            == 0
        )
        browser_box = await page.locator(".browser").bounding_box()
        activity_box = await page.locator(".activity").bounding_box()
        assert browser_box and activity_box
        assert activity_box["y"] >= browser_box["y"] + browser_box["height"], (
            "the activity column sits under the browser"
        )
        assert await page.get_by_role("button", name="Allow once").is_visible()
    finally:
        await page.close()
