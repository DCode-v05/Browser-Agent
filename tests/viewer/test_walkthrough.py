"""A person using the built viewer: the full run, the dialogs, the settings, the keyboard, motion."""

from collections.abc import Awaitable, Callable
from typing import Any

import pytest

# Test files cannot import each other (pytest's importlib mode), so the fixture's type is spelled here.
OpenView = Callable[..., Awaitable[Any]]
SIZES = ["desktop", "phone"]

GROUPS = ["Browser", "Approvals", "Sites", "Files", "Privacy", "Live view", "Appearance", "Advanced"]


async def test_the_full_run_from_start_to_summary(open_view: OpenView) -> None:
    # Twenty times faster than it was recorded, so the test does not wait on the agent's pauses.
    view = await open_view("demo=signup&pace=0.05")
    page = view.page
    await page.get_by_role("button", name="Allow once").click()
    await page.get_by_text("Allowed once", exact=True).wait_for()
    await page.get_by_role("group", name="Verification needed").wait_for()
    await page.get_by_role("button", name="Take over").click()
    await page.get_by_text("You're in control. The agent is waiting. Nothing you type is recorded.").wait_for()
    await page.get_by_role("img", name="Live browser view").click()
    await page.keyboard.type("481516")
    await page.get_by_role("button", name="Done").click()
    await page.get_by_role("group", name="Session ended").wait_for(timeout=15_000)
    assert await page.get_by_text("The agent closed it.").is_visible()
    assert await page.get_by_text("idle 12 s").is_visible()
    assert view.errors == []


async def test_denying_an_approval_shows_the_step_as_failed(open_view: OpenView) -> None:
    view = await open_view("demo=signup&pace=0.05")
    await view.page.get_by_role("button", name="Deny").click()
    await view.page.get_by_role("log", name="Steps").get_by_text("Could not upload cv.pdf: a person did not approve it").wait_for()
    assert await view.page.get_by_role("log", name="Steps").get_by_text("Failed", exact=True).count() == 1
    assert view.errors == []


async def test_stop_asks_first_and_the_safe_answer_has_the_focus(open_view: OpenView) -> None:
    view = await open_view("state=agent")
    page = view.page
    await page.get_by_role("button", name="Stop session").click()
    confirm = page.get_by_role("alertdialog", name="Stop this session?")
    await confirm.wait_for()
    assert await page.evaluate("document.activeElement.textContent") == "Keep running"
    await view.shot("stop-confirm-light-desktop")
    assert await view.accessibility_violations() == []
    await page.keyboard.press("Escape")
    assert await confirm.count() == 0
    assert await page.evaluate("document.activeElement.textContent") == "Stop session"


async def test_the_step_drawer_shows_the_evidence(open_view: OpenView) -> None:
    view = await open_view("state=ended")
    page = view.page
    await page.get_by_role("button", name='Clicked "Create account" (button)').click()
    drawer = page.get_by_role("dialog", name="Step 8")
    await drawer.wait_for()
    picture = drawer.get_by_role("img", name="The browser at step 8")
    assert await picture.evaluate("image => image.complete && image.naturalWidth > 0")
    await view.shot("step-drawer-light-desktop")
    assert await view.accessibility_violations() == []
    await page.keyboard.press("Escape")
    assert await drawer.count() == 0


@pytest.mark.parametrize("size", SIZES)
@pytest.mark.parametrize("theme", ["light", "dark"])
async def test_every_settings_group_is_clean_and_fits(open_view: OpenView, theme: str, size: str) -> None:
    view = await open_view(f"state=agent&theme={theme}", size)
    page = view.page
    await page.get_by_role("button", name="Open settings").click()
    dialog = page.get_by_role("dialog", name="Settings")
    await dialog.get_by_role("tab", name="Browser").wait_for()
    for group in GROUPS:
        await dialog.get_by_role("tab", name=group).click()
        await dialog.get_by_role("heading", name=group).wait_for()
        if group == "Advanced":
            await dialog.get_by_text("0.1.0").wait_for()
        await view.shot(f"settings-{group.lower().replace(' ', '-')}-{theme}-{size}")
        assert await view.sideways_overflow() == 0, group
        assert await view.accessibility_violations() == [], group
        if size == "phone":
            await dialog.get_by_role("button", name="Back").click()
    assert view.errors == []


async def test_the_desktop_set_shows_what_needs_the_persons_machine(open_view: OpenView) -> None:
    view = await open_view("state=agent&surface=desktop")
    page = view.page
    await page.get_by_role("button", name="Open settings").click()
    dialog = page.get_by_role("dialog", name="Settings")
    await dialog.get_by_text("My Chrome", exact=True).wait_for()
    assert await dialog.get_by_text("Show the built-in browser").count() == 1
    await dialog.get_by_role("tab", name="Files").click()
    await dialog.get_by_text("Download folder").wait_for()
    await view.shot("settings-files-desktop-surface")
    assert await view.accessibility_violations() == []


async def test_a_setting_changes_what_the_viewer_does(open_view: OpenView) -> None:
    view = await open_view("state=agent")
    page = view.page
    assert await page.locator(".target").count() == 1
    await page.get_by_role("button", name="Open settings").click()
    dialog = page.get_by_role("dialog", name="Settings")
    await dialog.get_by_role("tab", name="Live view").click()
    await dialog.get_by_role("switch", name="Show where the agent is acting").click()
    await dialog.get_by_text("Saved", exact=True).wait_for()
    await page.keyboard.press("Escape")
    assert await page.locator(".target").count() == 0


async def test_the_keyboard_reaches_every_control_and_shows_where_it_is(open_view: OpenView) -> None:
    view = await open_view("state=agent")
    page = view.page
    reached: list[str] = []
    for _ in range(12):
        await page.keyboard.press("Tab")
        # After the last control the focus leaves the page for the browser's own controls.
        if await page.evaluate("document.activeElement === document.body"):
            break
        name = await page.evaluate("(document.activeElement.getAttribute('aria-label') || document.activeElement.textContent || '').trim()")
        reached.append(name)
        outline = await page.evaluate("getComputedStyle(document.activeElement).outlineStyle")
        assert outline == "solid", f"no focus ring on {name!r}"
    for control in ("Open settings", "Pause", "Take over", "Stop session"):
        assert control in reached, reached
    assert reached.index("Pause") < reached.index("Take over") < reached.index("Stop session")


async def test_the_keys_of_the_keyboard_map_work(open_view: OpenView) -> None:
    view = await open_view("state=agent")
    page = view.page
    await page.keyboard.press("p")
    await page.get_by_role("heading", name="Paused").wait_for()
    await page.keyboard.press("p")
    await page.get_by_role("heading", name="Agent is working").wait_for()
    await page.keyboard.press("f")
    assert await page.locator(".app").get_attribute("data-view") == "full"
    assert await page.get_by_role("button", name="Stop session").is_visible(), "stop stays one action away in full view"
    await page.keyboard.press("f")
    await page.keyboard.press("t")
    await page.get_by_text("You're in control. The agent is waiting. Nothing you type is recorded.").wait_for()


async def test_with_reduced_motion_nothing_animates(open_view: OpenView) -> None:
    moving = await open_view("state=agent")
    assert await moving.page.locator(".live-dot").evaluate("dot => getComputedStyle(dot).animationName") == "live"
    still = await open_view("state=agent", reduced_motion=True)
    assert await still.page.locator(".live-dot").evaluate("dot => getComputedStyle(dot).animationName") == "none"
    assert await still.page.locator(".frame-label").evaluate("label => getComputedStyle(label).animationName") == "none"


async def test_only_opacity_and_transform_are_animated(open_view: OpenView) -> None:
    view = await open_view("state=waiting_approval")
    animated = await view.page.evaluate(
        "() => [...document.styleSheets].flatMap((sheet) => [...sheet.cssRules])"
        ".filter((rule) => rule.type === CSSRule.KEYFRAMES_RULE)"
        ".flatMap((rule) => [...rule.cssRules].flatMap((frame) => [...frame.style]))"
    )
    assert set(animated) <= {"opacity", "transform"}, animated
    transitions = await view.page.evaluate(
        "() => [...new Set([...document.querySelectorAll('*')].map((el) => getComputedStyle(el).transitionProperty))]"
    )
    assert set(transitions) <= {"all", "none", "transform", "opacity"}, transitions
