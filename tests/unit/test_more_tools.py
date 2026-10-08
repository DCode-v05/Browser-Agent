"""The tools beyond navigate, snapshot, click and type: what each asks of the driver and what it answers."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from fakes import SNAPSHOT, FakeDriver, QuietObserver

from bap_browser.config import Config
from bap_browser.driver import BrowserSession
from bap_browser.driver.base import Box
from bap_browser.errors import BrowserError
from bap_browser.tools import Toolkit

TABS = "\n[tabs] t1* about:blank"


class Seen(QuietObserver):
    def __init__(self) -> None:
        self.events: list[tuple[Any, ...]] = []

    def step_started(self, step: int, tool: str, label: str, target: Box | None) -> None:
        self.events.append(("started", label, target))

    def step_finished(self, step: int, ok: bool, ms: float, chars: int, summary: str, tabs: Any) -> None:
        self.events.append(("finished", ok, summary))

    def navigation_blocked(self, url: str, reason: str) -> None:
        self.events.append(("blocked", url, reason))


def kit(
    make_config: Callable[..., Config], folder: Path, **sections: Any
) -> tuple[Toolkit, FakeDriver, Seen]:
    driver, seen = FakeDriver(), Seen()
    return Toolkit(BrowserSession(make_config(folder, **sections), driver), observer=seen), driver, seen


async def said(tools: Toolkit, name: str, arguments: dict[str, Any] | None = None) -> str:
    result = await tools.call(name, arguments or {})
    assert result.text.endswith(TABS), result.text
    return ("ERROR: " if result.is_error else "") + result.text.removesuffix(TABS)


async def test_back_and_forward_return_the_page_or_say_there_is_none(make_config, tmp_path: Path) -> None:
    tools, driver, _ = kit(make_config, tmp_path)
    assert await said(tools, "browser_go_back") == "No previous page in history."
    assert await said(tools, "browser_go_forward") == "No next page in history."
    driver.next_address = "https://example.com/before"
    assert await said(tools, "browser_go_back") == f"Navigated to https://example.com/before\n{SNAPSHOT}"
    assert await said(tools, "browser_reload") == f"Reloaded about:blank\n{SNAPSHOT}"


async def test_text_is_capped_by_the_setting_and_says_what_is_left_out(make_config, tmp_path: Path) -> None:
    tools, driver, _ = kit(make_config, tmp_path, browser={"text": {"max_chars": 12}})
    assert await said(tools, "browser_get_text", {"max_chars": 7}) == (
        "Welcome\n… 18 more characters not shown. Give a ref to read one part of the page."
    )
    await tools.call("browser_get_text", {"ref": "e1", "max_chars": 999})
    assert [call[1] for call in driver.calls] == [
        {"ref": None, "max_chars": 7},
        {"ref": "e1", "max_chars": 12},
    ]


async def test_find_lists_matches_and_keeps_to_the_limits(make_config, tmp_path: Path) -> None:
    tools, driver, _ = kit(make_config, tmp_path, browser={"find": {"default_limit": 1, "max_limit": 2}})
    assert await said(tools, "browser_find", {"query": "go"}) == (
        '1 of 2 matches, best first:\n- button "Go" [ref=e1]'
    )
    assert await said(tools, "browser_find", {"query": "go", "limit": 40}) == (
        '2 matches, best first:\n- button "Go" [ref=e1]\n- link "Go home" [ref=e2]'
    )
    assert (await said(tools, "browser_find", {"query": "zebra"})).startswith("No element matches.")
    assert [call[1]["limit"] for call in driver.calls] == [1, 2, 1]


async def test_a_click_and_a_hover_at_a_point(make_config, tmp_path: Path) -> None:
    tools, driver, seen = kit(make_config, tmp_path)
    await tools.call("browser_snapshot")
    assert await said(tools, "browser_click", {"x": 320, "y": 240.5}) == 'Clicked (320, 240.5) (button "Go")'
    assert await said(tools, "browser_hover", {"x": 10, "y": 20}) == "Hovering over (10, 20)"
    assert await said(tools, "browser_hover", {"ref": "e1"}) == 'Hovering over e1 (button "Go")'
    assert driver.calls[1:] == [
        ("click_at", {"x": 320, "y": 240.5, "button": "left", "count": 1}),
        ("hover_at", (10, 20)),
        ("hover", "e1"),
    ]
    # The pointer a person sees goes to the point.
    assert seen.events[2:] == [
        ("started", "Clicking the page at 320, 240.5", Box(320, 240.5, 0, 0)),
        ("finished", True, "Clicked the page at 320, 240.5"),
        ("started", "Pointing at the page at 10, 20", Box(10, 20, 0, 0)),
        ("finished", True, "Pointed at the page at 10, 20"),
        ("started", 'Pointing at "Go"', Box(10, 20, 80, 24)),
        ("finished", True, 'Pointed at "Go"'),
    ]


async def test_scrolling_goes_by_steps_of_the_setting(make_config, tmp_path: Path) -> None:
    tools, driver, seen = kit(make_config, tmp_path, browser={"input": {"scroll_step_px": 300}})
    assert await said(tools, "browser_scroll", {"direction": "down", "amount": 2}) == (
        "Scrolled down 2. Position 600px of 3200px."
    )
    assert await said(tools, "browser_scroll", {"direction": "up"}) == (
        "Nothing scrolled up. Position 0px of 3200px."
    )
    assert await said(tools, "browser_scroll", {"direction": "right", "ref": "e1"}) == (
        "Scrolled right 1 inside e1. Position 300px of 1280px."
    )
    await tools.call("browser_scroll", {"direction": "down", "x": 5, "y": 6})
    assert [call[1] for call in driver.calls] == [
        {"dx": 0, "dy": 600, "ref": None, "at": None},
        {"dx": 0, "dy": -300, "ref": None, "at": None},
        {"dx": 300, "dy": 0, "ref": "e1", "at": None},
        {"dx": 0, "dy": 300, "ref": None, "at": (5, 6)},
    ]
    assert seen.events[0] == ("started", "Scrolling down", None)
    assert seen.events[1] == ("finished", True, "Scrolled down")
    assert (await said(tools, "browser_scroll", {"direction": "down", "amount": 21})).startswith("ERROR: ")
    assert await said(tools, "browser_scroll_to", {"ref": "e1"}) == 'Scrolled e1 (button "Go") into view.'


async def test_key_presses_are_named_unless_they_type_a_character(make_config, tmp_path: Path) -> None:
    tools, driver, seen = kit(make_config, tmp_path, browser={"input": {"key_repeat_max": 5}})
    assert await said(tools, "browser_press_key", {"keys": "ctrl+a"}) == "Pressed Control+a"
    assert await said(tools, "browser_press_key", {"keys": "down", "repeat": 3, "ref": "e3"}) == (
        'Pressed ArrowDown 3 times on e3 (textbox "Email")'
    )
    assert await said(tools, "browser_press_key", {"keys": "x"}) == "Pressed a character key"
    assert await said(tools, "browser_press_key", {"keys": "Enter", "repeat": 6}) == (
        "ERROR: repeat is at most 5."
    )
    refused = await said(tools, "browser_press_key", {"keys": "hunter2"})
    assert refused.startswith("ERROR: That is not a key name.") and "hunter2" not in refused
    assert [call[1]["keys"] for call in driver.calls] == ["Control+a", "ArrowDown", "x"]
    assert [event[-1] for event in seen.events] == [
        None,
        "Pressed Control+a",
        Box(10, 60, 200, 24),
        "Pressed ArrowDown",
        None,
        "Pressed a key",
        None,
        "Could not press Enter: too many repeats",
        None,
        "Could not press a key: the key name is not known",
    ]
    log = (tmp_path / "events.jsonl").read_text(encoding="utf-8")
    assert "hunter2" not in log
    logged = [json.loads(line)["args"]["keys"] for line in log.splitlines()]
    assert logged == ["ctrl+a", "down", "<1 characters>", "Enter", "<7 characters>"]


async def test_dropdowns_and_checkboxes(make_config, tmp_path: Path) -> None:
    tools, _, seen = kit(make_config, tmp_path)
    await tools.call("browser_snapshot")
    assert await said(tools, "browser_select_option", {"ref": "e6", "values": ["india"]}) == (
        'Selected "India" in e6 (combobox "Country")'
    )
    assert await said(tools, "browser_set_checked", {"ref": "e5", "checked": True}) == "e5 is now checked."
    assert await said(tools, "browser_set_checked", {"ref": "e5", "checked": False}) == (
        "e5 is now not checked."
    )
    assert [event[1:] for event in seen.events[2:]] == [
        ('Choosing an option in "Country"', Box(10, 120, 200, 24)),
        (True, 'Chose an option in "Country"'),
        ('Checking "Terms"', Box(10, 90, 16, 16)),
        (True, 'Checked "Terms"'),
        ('Clearing "Terms"', Box(10, 90, 16, 16)),
        (True, 'Cleared "Terms"'),
    ]


async def test_a_form_is_filled_field_by_field_the_way_each_is_filled(make_config, tmp_path: Path) -> None:
    tools, driver, seen = kit(make_config, tmp_path)
    await tools.call("browser_snapshot")
    fields = [
        {"ref": "e3", "value": "ada@example.com"},
        {"ref": "e5", "value": True},
        {"ref": "e6", "value": "india"},
    ]
    assert await said(tools, "browser_fill_form", {"fields": fields}) == "Filled: e3, e5=checked, e6=India"
    assert driver.calls[1:] == [
        ("type", {"ref": "e3", "text": "ada@example.com", "clear": True, "submit": False, "slowly": False}),
        ("set_checked", {"ref": "e5", "checked": True}),
        ("select_option", {"ref": "e6", "values": ["india"]}),
    ]
    assert seen.events[2:] == [("started", "Filling 3 fields", None), ("finished", True, "Filled 3 fields")]
    log = (tmp_path / "events.jsonl").read_text(encoding="utf-8")
    assert "ada@example.com" not in log and "india" not in log
    assert json.loads(log.splitlines()[-1])["args"] == {
        "fields": [
            {"ref": "e3", "value": "<15 characters>"},
            {"ref": "e5", "value": True},
            {"ref": "e6", "value": "<5 characters>"},
        ]
    }


async def test_a_form_that_stops_part_way_says_what_was_filled(make_config, tmp_path: Path) -> None:
    tools, driver, seen = kit(make_config, tmp_path)
    await tools.call("browser_snapshot")
    wrong_kind = [{"ref": "e3", "value": "Ada"}, {"ref": "e5", "value": "yes"}, {"ref": "e6", "value": "x"}]
    assert await said(tools, "browser_fill_form", {"fields": wrong_kind}) == (
        "ERROR: Filled: e3. Stopped at e5: e5 is a checkbox or a radio button: its value is true or false."
    )
    assert await said(tools, "browser_fill_form", {"fields": [{"ref": "e1", "value": "Ada"}]}) == (
        "ERROR: Stopped at e1: e1 is not a form field. Use browser_click for buttons and links."
    )
    assert (await said(tools, "browser_fill_form", {"fields": [{"ref": "e9", "value": "Ada"}]})).startswith(
        "ERROR: Stopped at e9: Ref 'e9' is stale or unknown"
    )
    driver.fail_with = BrowserError("Could not act on e5: it is covered.", reason="it is covered")
    await tools.call("browser_fill_form", {"fields": [{"ref": "e5", "value": True}]})
    assert seen.events[-1] == ("finished", False, "Could not fill the form: it is covered")


async def test_waiting_is_for_one_thing_and_never_longer_than_the_ceiling(
    make_config, tmp_path: Path
) -> None:
    tools, driver, seen = kit(make_config, tmp_path, browser={"timeouts": {"wait_max_s": 2}})
    assert await said(tools, "browser_wait", {"text": "Done"}) == "The text is on the page."
    assert await said(tools, "browser_wait", {"text_gone": "Loading", "timeout_s": 1}) == "The text is gone."
    assert await said(tools, "browser_wait", {"text": "never", "timeout_s": 60}) == (
        "ERROR: Waited 2 s for the text to appear, and it did not. Read the page with browser_snapshot."
    )
    assert await said(tools, "browser_wait", {"load_state": "networkidle"}) == "The page reached networkidle."
    assert await said(tools, "browser_wait", {"seconds": 0.01}) == "Waited 0.01 s."
    assert [call[1] for call in driver.calls] == [
        {"text": "Done", "gone": False, "timeout_s": 2},
        {"text": "Loading", "gone": True, "timeout_s": 1},
        {"text": "never", "gone": False, "timeout_s": 2},
        {"state": "networkidle", "timeout_s": 2},
    ]
    assert (await said(tools, "browser_wait", {"text": "a", "seconds": 1})).startswith(
        "ERROR: browser_wait: "
    )
    # What is waited for may be something the agent typed: a person is told only that it waits.
    assert seen.events[0] == ("started", "Waiting for text to appear", None)
    assert seen.events[5] == ("finished", False, "Could not wait for text to appear: the wait ran out")
    assert "Done" not in (tmp_path / "events.jsonl").read_text(encoding="utf-8")


async def test_a_wait_in_seconds_is_cut_to_the_ceiling_and_starts_no_browser(
    make_config, tmp_path: Path
) -> None:
    tools, driver, _ = kit(make_config, tmp_path, browser={"timeouts": {"wait_max_s": 0}})
    assert (await tools.call("browser_wait", {"seconds": 30})).text == "Waited 0 s."
    assert driver.started == 0
