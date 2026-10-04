"""The whole path: the reference agent works in a real browser while a person watches it in the real
viewer, pauses it, takes over, types into the page, hands back and reads the summary (spec 14.1, slice 4)."""

import asyncio
from collections.abc import Callable
from pathlib import Path

from fakes import FakeDriver
from playwright.async_api import Browser

from bap_browser.agent.demo import TASK, demo_script
from bap_browser.agent.loop import run_agent
from bap_browser.config import Config
from bap_browser.service.server import Service
from bap_browser.service.session import ServiceSession

SHOTS = Path(__file__).parents[2] / ".bap-browser" / "viewer-shots"
PICTURE_IS_DRAWN = (
    "() => { const c = document.querySelector('canvas.frame-picture'); if (!c) return false;"
    " const p = c.getContext('2d').getImageData(c.width / 2, c.height / 2, 1, 1).data; return p[3] > 0; }"
)


async def test_a_person_watches_the_agent_pauses_it_takes_over_and_reads_the_summary(
    browser: Browser, make_config: Callable[..., Config], tmp_path: Path
) -> None:
    config = make_config(tmp_path, agent={"provider": "scripted"})
    session = ServiceSession(config, agent="Reference agent")
    await session.start()
    service = Service(config, {session.name: session}, port=0)
    await service.start()
    page = await browser.new_page(viewport={"width": 1360, "height": 850})
    errors: list[str] = []
    page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
    page.on("pageerror", lambda error: errors.append(str(error)))

    async def shot(name: str) -> None:
        SHOTS.mkdir(parents=True, exist_ok=True)
        await page.screenshot(path=str(SHOTS / f"{name}.png"))

    steps_shown = page.locator(".rows .row")

    try:
        await page.goto(service.viewer_address)
        await page.get_by_role("heading", name="Agent is working").wait_for()
        # The token came in the address and is no longer shown there.
        assert page.url == f"{service.address}/"
        assert await page.get_by_text("Reference agent").count() == 1
        await asyncio.wait_for(session.hub.wait_for_viewer(), 5)

        agent = asyncio.create_task(
            run_agent(
                TASK,
                session.toolkit,
                demo_script(f"{service.address}/demo-site", pause_s=0.7),
                config.agent,
                ended=lambda: session.control == "ended",
            )
        )

        # Steps arrive as sentences, and the picture of the real page is drawn.
        await page.get_by_text('Typed 12 characters into "Full name"').first.wait_for()
        await page.wait_for_function(PICTURE_IS_DRAWN)
        assert await page.get_by_label("Address").text_content() == f"{service.address}/demo-site/signup.html"
        await shot("live-1-agent-working")

        # Pause holds the real agent: no new step arrives while it is paused.
        await page.get_by_role("button", name="Pause").click()
        await page.get_by_role("heading", name="Paused").wait_for()
        assert session.control == "paused"
        before = await steps_shown.count()
        await page.wait_for_timeout(1800)
        assert await steps_shown.count() == before
        await shot("live-2-paused")

        # Take over, click into the page through the picture, and type. It reaches the real page.
        await page.get_by_role("button", name="Take over").click()
        await page.get_by_role("heading", name="You're in control").wait_for()
        assert session.control == "person"
        remote = (await session.browser.driver()).page  # type: ignore[attr-defined]
        field = await remote.locator("#name").bounding_box()
        picture = await page.locator("canvas.frame-picture").bounding_box()
        assert field and picture
        scale = picture["width"] / 1280
        await page.mouse.click(
            picture["x"] + (field["x"] + field["width"] - 12) * scale,
            picture["y"] + (field["y"] + field["height"] / 2) * scale,
        )
        await page.keyboard.type(" Byron")
        await remote.wait_for_function("document.getElementById('name').value === 'Ada Lovelace Byron'")
        await shot("live-3-person-in-control")

        # Hand back: the agent goes on from where the person left the page, and finishes.
        await page.get_by_role("button", name="Hand back").click()
        await page.get_by_role("heading", name="Agent is working").wait_for()
        answer = await asyncio.wait_for(agent, 60)
        assert answer == 'The account was created. The page now shows "Welcome, Ada" with 3 open invoices.'
        await page.get_by_text('Clicked "Continue" (button)').first.wait_for()

        await session.close("agent")
        await page.get_by_role("group", name="Session ended").wait_for()
        await shot("live-4-ended")

        # What the person typed while in control was sent to no viewer and written to no log.
        told = repr([item for item in session.hub.subscribe()[0] if isinstance(item, dict)])
        assert "Byron" not in told
        assert "Byron" not in (tmp_path / "events.jsonl").read_text(encoding="utf-8")
        assert errors == []
    finally:
        # The service ends the viewer's connection before the page goes. A page that is closed first
        # cuts its connection, and on Windows Python's asyncio can then leave that socket open behind
        # the test (its transport raises ConnectionResetError before it closes the socket).
        await service.stop()
        await page.close()
        await session.close()


async def test_a_new_link_opened_in_a_tab_that_already_shows_the_viewer_is_taken(
    browser: Browser, make_config: Callable[..., Config], tmp_path: Path
) -> None:
    session = ServiceSession(make_config(tmp_path), FakeDriver(), agent="Reference agent")
    await session.start()
    service = Service(make_config(tmp_path), {session.name: session}, port=0)
    await service.start()
    page = await browser.new_page()
    try:
        await page.goto(f"{service.address}/#token=not-the-token")
        await page.get_by_role("heading", name="This link can't open the session").wait_for()
        # The right link differs only after the #, so the browser does not load the page again by itself.
        await page.goto(service.viewer_address)
        await page.get_by_text("Reference agent").wait_for()
        assert page.url == f"{service.address}/"
    finally:
        await service.stop()
        await page.close()
        await session.close()
