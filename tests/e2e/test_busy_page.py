"""A page that stops answering must fail a call, never hold it (review finding I1)."""

import re
import time
from collections.abc import Callable
from pathlib import Path

from bap_browser.config import Config
from bap_browser.driver import open_session
from bap_browser.tools import Toolkit


def ref_of(text: str, element: str) -> str:
    match = re.search(re.escape(f"- {element}") + r" \[ref=(e\d+)\]", text)
    assert match, f"{element!r} not in:\n{text}"
    return match.group(1)


async def test_a_page_too_busy_to_answer_fails_the_call_instead_of_holding_it(
    make_config: Callable[..., Config], tmp_path: Path, site: str
) -> None:
    config = make_config(tmp_path, browser={"timeouts": {"page_reply_ms": 400}})
    async with open_session(config) as session:
        tools = Toolkit(session)
        page = await tools.call("browser_navigate", {"url": f"{site}/busy.html"})
        started = time.perf_counter()
        # The click starts four seconds in which the page answers nothing.
        clicked = await tools.call("browser_click", {"ref": ref_of(page.text, 'button "Work"')})
        read = await tools.call("browser_snapshot", {})
        elapsed = time.perf_counter() - started
        assert not clicked.is_error, clicked.text
        assert read.is_error
        assert read.text.startswith("The page did not answer within 0.4 s. It may be busy or still loading.")
        assert read.text.endswith(f"[tabs] t1* {site}/busy.html")
        assert elapsed < 3, f"the calls took {elapsed:.1f} s while the page was busy for 4 s"
        # Once the page answers again, so do the tools.
        await (await session.driver()).page.wait_for_function("true", timeout=10000)  # type: ignore[attr-defined]
        assert not (await tools.call("browser_snapshot", {})).is_error


async def test_a_click_whose_handler_keeps_the_page_busy_is_answered_within_the_action_limit(
    make_config: Callable[..., Config], tmp_path: Path, site: str
) -> None:
    config = make_config(tmp_path, browser={"timeouts": {"action_ms": 800, "page_reply_ms": 400}})
    async with open_session(config) as session:
        tools = Toolkit(session)
        page = await tools.call("browser_navigate", {"url": f"{site}/slow_handler.html"})
        started = time.perf_counter()
        clicked = await tools.call("browser_click", {"ref": ref_of(page.text, 'button "Think"')})
        elapsed = time.perf_counter() - started
        assert clicked.is_error
        assert clicked.text.startswith("The page did not answer within 0.8 s after the click.")
        assert elapsed < 3, f"the click took {elapsed:.1f} s while the page was busy for 4 s"
        await (await session.driver()).page.wait_for_function("true", timeout=10000)  # type: ignore[attr-defined]
        assert not (await tools.call("browser_snapshot", {})).is_error


async def test_a_kept_profile_is_driven_like_a_fresh_one(
    make_config: Callable[..., Config], tmp_path: Path, site: str
) -> None:
    config = make_config(tmp_path, browser={"user_data_dir": str(tmp_path / "profile")})
    async with open_session(config) as session:
        tools = Toolkit(session)
        page = await tools.call("browser_navigate", {"url": f"{site}/slow_handler.html"})
        assert not page.is_error and 'button "Think"' in page.text
        driver = await session.driver()
        assert re.fullmatch(r"Chromium \d+\.\d+\.\d+\.\d+", driver.description())
        assert driver.is_alive()
    assert not driver.is_alive()
    assert (tmp_path / "profile").is_dir(), "the profile is kept"
