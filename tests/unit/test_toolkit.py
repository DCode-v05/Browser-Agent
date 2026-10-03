import asyncio
import json
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from fakes import SNAPSHOT, FakeDriver

from bap_browser.config import Config
from bap_browser.driver import BrowserSession
from bap_browser.driver.base import Box, TabInfo
from bap_browser.errors import StaleRef
from bap_browser.tools import Toolkit


def kit(make_config: Callable[..., Config], folder: Path, **sections: Any) -> tuple[Toolkit, FakeDriver]:
    driver = FakeDriver()
    return Toolkit(BrowserSession(make_config(folder, **sections), driver)), driver


async def test_navigate_returns_the_snapshot_and_the_tab_list(make_config, tmp_path: Path) -> None:
    tools, driver = kit(make_config, tmp_path)
    result = await tools.call("browser_navigate", {"url": "https://93.184.216.34/"})
    assert not result.is_error
    assert (
        result.text == f"Navigated to https://93.184.216.34/\n{SNAPSHOT}\n[tabs] t1* https://93.184.216.34/"
    )
    assert driver.started == 1


async def test_an_address_with_no_scheme_gets_https(make_config, tmp_path: Path) -> None:
    tools, driver = kit(make_config, tmp_path)
    await tools.call("browser_navigate", {"url": "93.184.216.34/path"})
    assert driver.calls[0] == ("navigate", "https://93.184.216.34/path")


async def test_a_blocked_address_is_refused_before_the_browser_starts(make_config, tmp_path: Path) -> None:
    tools, driver = kit(make_config, tmp_path, safety={"block_private_networks": True})
    result = await tools.call("browser_navigate", {"url": "http://10.0.0.5"})
    assert result.is_error
    assert (
        result.text
        == "navigation to http://10.0.0.5 blocked: private address (safety.block_private_networks)"
    )
    assert driver.started == 0


async def test_navigation_without_a_snapshot_when_the_setting_is_off(make_config, tmp_path: Path) -> None:
    tools, _ = kit(make_config, tmp_path, browser={"snapshot": {"after_navigation": False}})
    result = await tools.call("browser_navigate", {"url": "https://93.184.216.34/"})
    assert result.text == "Navigated to https://93.184.216.34/\n[tabs] t1* https://93.184.216.34/"


async def test_snapshot_uses_the_defaults_and_cannot_raise_the_cap(make_config, tmp_path: Path) -> None:
    tools, driver = kit(make_config, tmp_path)
    await tools.call("browser_snapshot", {})
    await tools.call(
        "browser_snapshot", {"mode": "all", "ref": "e7", "max_chars": 500, "include_bboxes": True}
    )
    await tools.call("browser_snapshot", {"max_chars": 999999})
    assert [call[1] for call in driver.calls] == [
        {"mode": "interactive", "ref": None, "max_chars": 20000, "bboxes": False},
        {"mode": "all", "ref": "e7", "max_chars": 500, "bboxes": True},
        {"mode": "interactive", "ref": None, "max_chars": 20000, "bboxes": False},
    ]


async def test_click_says_what_was_clicked_and_where_the_page_went(make_config, tmp_path: Path) -> None:
    tools, _ = kit(make_config, tmp_path)
    stayed = await tools.call("browser_click", {"ref": "e1"})
    assert stayed.text == 'Clicked e1 (button "Go")\n[tabs] t1* about:blank'
    moved = await tools.call("browser_click", {"ref": "e2", "button": "right", "click_count": 2})
    assert moved.text.startswith('Clicked e2 (button "Go")\nNavigated to https://example.com/next\n[tabs] ')


async def test_action_tools_add_a_snapshot_when_the_setting_is_on(make_config, tmp_path: Path) -> None:
    tools, _ = kit(make_config, tmp_path, browser={"snapshot": {"after_action": True}})
    result = await tools.call("browser_click", {"ref": "e1"})
    assert result.text == f'Clicked e1 (button "Go")\n{SNAPSHOT}\n[tabs] t1* about:blank'


async def test_type_reports_a_count_and_never_the_text(make_config, tmp_path: Path) -> None:
    tools, driver = kit(make_config, tmp_path)
    result = await tools.call("browser_type", {"ref": "e3", "text": "ada@example.com", "submit": True})
    assert result.text == 'Typed 15 characters into e3 (textbox "Email")\n[tabs] t1* about:blank'
    assert driver.calls[0] == (
        "type",
        {"ref": "e3", "text": "ada@example.com", "clear": True, "submit": True, "slowly": False},
    )
    focused = await tools.call("browser_type", {"text": "x"})
    assert focused.text.startswith('Typed 1 characters into the focused element (textbox "Email")')


async def test_bad_calls_are_results_not_crashes(make_config, tmp_path: Path) -> None:
    tools, driver = kit(make_config, tmp_path)
    cases = {
        (
            "browser_fly",
            (),
        ): "Unknown tool 'browser_fly'. Available: browser_click, browser_navigate, browser_snapshot, browser_type.",
        ("browser_click", (("reff", "e1"),)): "browser_click: missing argument 'ref'",
        ("browser_click", (("ref", "e1"), ("speed", 2))): "browser_click: unknown argument 'speed'",
        ("browser_click", (("ref", "button 3"),)): "browser_click: bad value for 'ref'",
        ("browser_click", (("ref", "e1"), ("click_count", 9))): "browser_click: bad value for 'click_count'",
        ("browser_type", (("ref", "e1"),)): "browser_type: missing argument 'text'",
    }
    for (name, arguments), expected in cases.items():
        result = await tools.call(name, dict(arguments))
        assert result.is_error
        assert result.text.startswith(expected), result.text
    assert driver.started == 0


async def test_a_failure_from_the_browser_is_a_result_with_the_state_block(
    make_config, tmp_path: Path
) -> None:
    tools, driver = kit(make_config, tmp_path)
    await tools.call("browser_snapshot", {})
    driver.fail_with = StaleRef("e9")
    result = await tools.call("browser_click", {"ref": "e9"})
    assert result.is_error
    assert result.text == (
        "Ref 'e9' is stale or unknown (the page changed or navigated). "
        "Take a new snapshot and use a fresh ref.\n[tabs] t1* about:blank"
    )


async def test_an_unexpected_failure_does_not_stop_the_toolkit(make_config, tmp_path: Path, caplog) -> None:
    tools, driver = kit(make_config, tmp_path)
    driver.fail_with = RuntimeError("boom")
    result = await tools.call("browser_click", {"ref": "e1"})
    assert result.is_error
    assert result.text.startswith("browser_click failed unexpectedly (RuntimeError).")
    assert "boom" in caplog.text
    driver.fail_with = None
    assert not (await tools.call("browser_click", {"ref": "e1"})).is_error


async def test_results_are_redacted(make_config, tmp_path: Path) -> None:
    tools, _ = kit(make_config, tmp_path, safety={"redact_patterns": ["example\\.com"]})
    result = await tools.call("browser_snapshot", {})
    assert "example.com" not in result.text
    assert "URL: https://[REDACTED]/" in result.text


async def test_calls_run_one_at_a_time(make_config, tmp_path: Path) -> None:
    tools, driver = kit(make_config, tmp_path)
    await asyncio.gather(*(tools.call("browser_click", {"ref": "e1"}) for _ in range(5)))
    assert driver.most_at_once == 1
    assert driver.started == 1


async def test_every_call_is_logged_with_typed_text_replaced_by_its_length(
    make_config, tmp_path: Path
) -> None:
    tools, _ = kit(make_config, tmp_path, safety={"redact_patterns": ["tok-[a-z]+"]})
    secret = "pässwörd 😀 hunter2"
    await tools.call("browser_type", {"ref": "e3", "text": secret})
    await tools.call("browser_navigate", {"url": "https://93.184.216.34/?key=tok-abc"})
    await tools.call("browser_click", {"reff": "e1"})
    log = (tmp_path / "events.jsonl").read_text(encoding="utf-8")
    assert "hunter2" not in log and "pässwörd" not in log and "tok-abc" not in log
    lines = [json.loads(line) for line in log.splitlines()]
    assert [line["tool"] for line in lines] == ["browser_type", "browser_navigate", "browser_click"]
    assert lines[0]["args"] == {"ref": "e3", "text": f"<{len(secret)} characters>"}
    assert lines[0]["ok"] is True and lines[2]["ok"] is False
    assert lines[1]["args"] == {"url": "https://93.184.216.34/?key=[REDACTED]"}
    assert set(lines[0]) == {"ts", "tool", "args", "ok", "ms", "chars", "result"}


async def test_the_log_can_be_turned_off_and_arguments_left_out(make_config, tmp_path: Path) -> None:
    off, _ = kit(make_config, tmp_path, logging={"event_log": None})
    await off.call("browser_snapshot", {})
    assert not (tmp_path / "events.jsonl").exists()
    quiet_folder = tmp_path / "quiet folder"
    quiet_folder.mkdir()
    quiet, _ = kit(
        make_config,
        quiet_folder,
        logging={"event_log": str(quiet_folder / "log" / "e.jsonl"), "log_tool_args": False},
    )
    await quiet.call("browser_type", {"ref": "e3", "text": "abc"})
    line = json.loads((quiet_folder / "log" / "e.jsonl").read_text(encoding="utf-8"))
    assert "args" not in line


class Seen:
    """Records what the toolkit reports, the way the session service will receive it."""

    def __init__(self) -> None:
        self.events: list[tuple[Any, ...]] = []
        self.sizes: list[int] = []

    def step_started(self, step: int, tool: str, label: str, target: Box | None) -> None:
        self.events.append(("started", step, tool, label, target))

    def step_finished(
        self, step: int, ok: bool, ms: float, chars: int, summary: str, tabs: Sequence[TabInfo]
    ) -> None:
        assert ms >= 0
        self.sizes.append(chars)
        self.events.append(("finished", step, ok, summary, [tab.url for tab in tabs]))

    def navigation_blocked(self, url: str, reason: str) -> None:
        self.events.append(("blocked", url, reason))


def watched(
    make_config: Callable[..., Config], folder: Path, **sections: Any
) -> tuple[Toolkit, FakeDriver, Seen]:
    driver, seen = FakeDriver(), Seen()
    return Toolkit(BrowserSession(make_config(folder, **sections), driver), observer=seen), driver, seen


async def test_each_call_is_reported_as_a_step_that_starts_and_then_finishes(
    make_config, tmp_path: Path
) -> None:
    tools, _, seen = watched(make_config, tmp_path)
    opened = await tools.call("browser_navigate", {"url": "https://93.184.216.34/"})
    await tools.call("browser_click", {"ref": "e1"})
    assert seen.events == [
        ("started", 1, "browser_navigate", "Opening 93.184.216.34", None),
        ("finished", 1, True, "Opened 93.184.216.34", ["https://93.184.216.34/"]),
        ("started", 2, "browser_click", 'Clicking "Go"', Box(10, 20, 80, 24)),
        ("finished", 2, True, 'Clicked "Go" (button)', ["https://93.184.216.34/"]),
    ]
    assert seen.sizes[0] == len(opened.text)


async def test_a_typing_step_never_carries_its_text(make_config, tmp_path: Path) -> None:
    tools, _, seen = watched(make_config, tmp_path)
    await tools.call("browser_snapshot", {})
    await tools.call("browser_type", {"ref": "e3", "text": "ada@example.com"})
    assert seen.events[2:] == [
        ("started", 2, "browser_type", 'Typing 15 characters into "Email"', Box(10, 60, 200, 24)),
        ("finished", 2, True, 'Typed 15 characters into "Email"', ["about:blank"]),
    ]
    assert "ada@example.com" not in repr(seen.events)


async def test_a_failed_step_says_why_in_words_for_a_person(make_config, tmp_path: Path) -> None:
    tools, driver, seen = watched(make_config, tmp_path)
    await tools.call("browser_snapshot", {})
    driver.fail_with = StaleRef("e9")
    await tools.call("browser_click", {"ref": "e9"})
    assert seen.events[2:] == [
        ("started", 2, "browser_click", "Clicking e9", None),
        ("finished", 2, False, "Could not click e9: the page changed", ["about:blank"]),
    ]


async def test_a_blocked_address_is_a_step_and_is_reported_as_blocked(make_config, tmp_path: Path) -> None:
    tools, driver, seen = watched(make_config, tmp_path, safety={"block_private_networks": True})
    await tools.call("browser_navigate", {"url": "http://10.0.0.5/admin"})
    assert seen.events == [
        ("started", 1, "browser_navigate", "Opening 10.0.0.5/admin", None),
        ("blocked", "http://10.0.0.5/admin", "private address"),
        ("finished", 1, False, "Could not open 10.0.0.5/admin: private address", []),
    ]
    assert driver.started == 0


async def test_a_call_that_cannot_run_is_still_a_step(make_config, tmp_path: Path) -> None:
    tools, driver, seen = watched(make_config, tmp_path)
    await tools.call("browser_fly", {})
    await tools.call("browser_click", {"reff": "e1"})
    assert seen.events == [
        ("started", 1, "browser_fly", "browser_fly", None),
        ("finished", 1, False, "Could not run browser_fly: unknown tool", []),
        ("started", 2, "browser_click", "Clicking", None),
        ("finished", 2, False, "Could not click: missing argument 'ref'", []),
    ]
    assert driver.started == 0


async def test_an_unexpected_failure_is_reported_without_its_details(
    make_config, tmp_path: Path, caplog
) -> None:
    tools, driver, seen = watched(make_config, tmp_path)
    await tools.call("browser_snapshot", {})
    driver.fail_with = RuntimeError("boom at /secret/path")
    await tools.call("browser_click", {"ref": "e1"})
    assert seen.events[-1] == (
        "finished",
        2,
        False,
        'Could not click "Go": something went wrong',
        ["about:blank"],
    )
    assert "boom" in caplog.text


async def test_what_is_reported_is_redacted(make_config, tmp_path: Path) -> None:
    tools, _, seen = watched(make_config, tmp_path, safety={"redact_patterns": ["93\\.184\\.216\\.34"]})
    await tools.call("browser_navigate", {"url": "https://93.184.216.34/"})
    assert seen.events[0][3] == "Opening [REDACTED]"
    assert seen.events[1][3] == "Opened [REDACTED]"
