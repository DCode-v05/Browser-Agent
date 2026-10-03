"""The sentences a person reads in the timeline (spec 9.7)."""

import pytest

from bap_browser.driver.base import Located
from bap_browser.tools.sentences import label_for, summary_for

BUTTON = Located("button", "Create account", None)
EMAIL = Located("textbox", "Email", None)


def test_opening_a_page_names_the_site_and_the_path_without_the_rest() -> None:
    arguments = {"url": "https://example.com/login?next=/account&token=abc#top"}
    assert label_for("browser_navigate", arguments, None) == "Opening example.com/login"
    assert summary_for("browser_navigate", arguments, None, None) == "Opened example.com/login"


@pytest.mark.parametrize(
    ("url", "shown"),
    [
        ("https://example.com/", "example.com"),
        ("http://127.0.0.1:8765/demo-site/signup.html", "127.0.0.1:8765/demo-site/signup.html"),
        ("about:blank", "about:blank"),
        ("example.com/pricing", "example.com/pricing"),
    ],
)
def test_an_address_is_shown_the_way_a_person_says_it(url: str, shown: str) -> None:
    assert summary_for("browser_navigate", {"url": url}, None, None) == f"Opened {shown}"


def test_reading_the_page() -> None:
    assert label_for("browser_snapshot", {}, None) == "Reading the page"
    assert summary_for("browser_snapshot", {}, None, None) == "Read the page"


def test_a_click_names_the_element_and_says_what_it_is() -> None:
    assert label_for("browser_click", {"ref": "e5"}, BUTTON) == 'Clicking "Create account"'
    assert summary_for("browser_click", {"ref": "e5"}, BUTTON, None) == 'Clicked "Create account" (button)'


def test_an_element_with_no_name_is_called_by_what_it_is() -> None:
    unnamed = Located("checkbox", "", None)
    assert label_for("browser_click", {"ref": "e5"}, unnamed) == "Clicking a checkbox"
    assert summary_for("browser_click", {"ref": "e5"}, unnamed, None) == "Clicked a checkbox"


def test_an_element_that_was_not_found_is_called_by_its_ref() -> None:
    assert label_for("browser_click", {"ref": "e5"}, None) == "Clicking e5"
    assert summary_for("browser_click", {"ref": "e5"}, None, None) == "Clicked e5"


def test_typing_gives_a_count_and_never_the_text() -> None:
    arguments = {"ref": "e3", "text": "ada@example.com"}
    assert label_for("browser_type", arguments, EMAIL) == 'Typing 15 characters into "Email"'
    assert summary_for("browser_type", arguments, EMAIL, None) == 'Typed 15 characters into "Email"'
    assert label_for("browser_type", {"ref": "e3", "text": "7"}, EMAIL) == 'Typing 1 character into "Email"'
    assert label_for("browser_type", {"text": "abc"}, None) == "Typing 3 characters"
    assert summary_for("browser_type", {"text": "abc"}, None, None) == "Typed 3 characters"


@pytest.mark.parametrize(
    ("tool", "arguments", "target", "reason", "sentence"),
    [
        ("browser_click", {"ref": "e7"}, Located("button", "Pay", None), "it is covered by a dialog",
         'Could not click "Pay": it is covered by a dialog'),
        ("browser_click", {"ref": "e7"}, None, "the page changed", "Could not click e7: the page changed"),
        ("browser_type", {"ref": "e3", "text": "x"}, EMAIL, "it is disabled or read-only",
         'Could not type into "Email": it is disabled or read-only'),
        ("browser_type", {"text": "x"}, None, "nothing is focused", "Could not type: nothing is focused"),
        ("browser_navigate", {"url": "http://10.0.0.5/admin"}, None, "private address",
         "Could not open 10.0.0.5/admin: private address"),
        ("browser_snapshot", {}, None, "the page changed", "Could not read the page: the page changed"),
        ("browser_click", {"reff": "e1"}, None, "missing argument 'ref'", "Could not click: missing argument 'ref'"),
    ],
)  # fmt: skip
def test_a_failed_step_says_what_could_not_be_done_and_why(
    tool: str, arguments: dict[str, str], target: Located | None, reason: str, sentence: str
) -> None:
    assert summary_for(tool, arguments, target, reason) == sentence


def test_a_tool_with_no_sentence_of_its_own_is_called_by_its_name() -> None:
    assert label_for("browser_fly", {}, None) == "browser_fly"
    assert summary_for("browser_fly", {}, None, None) == "browser_fly"
    assert summary_for("browser_fly", {}, None, "unknown tool") == "Could not run browser_fly: unknown tool"


def test_a_long_name_is_cut_so_the_row_stays_under_60_characters() -> None:
    long = Located(
        "link", "Read our complete guide to invoices, contracts and approvals for small teams", None
    )
    label = label_for("browser_click", {"ref": "e1"}, long)
    summary = summary_for("browser_click", {"ref": "e1"}, long, None)
    assert label.startswith('Clicking "Read our complete guide') and label.endswith('…"')
    assert summary.startswith('Clicked "Read our complete guide') and summary.endswith('…" (link)')
    assert len(label) < 60 and len(summary) < 60


def test_a_long_address_and_a_long_reason_are_cut_too() -> None:
    url = "https://example.com/" + "section/" * 20
    assert len(label_for("browser_navigate", {"url": url}, None)) < 60
    failed = summary_for(
        "browser_click", {"ref": "e1"}, BUTTON, "it is covered by " + "something very long " * 8
    )
    assert failed.startswith('Could not click "Create account": it is covered by')
    assert failed.endswith("…") and len(failed) < 60


def test_arguments_of_the_wrong_kind_do_not_break_a_sentence() -> None:
    assert label_for("browser_navigate", {"url": 7}, None) == "Opening a page"
    assert label_for("browser_type", {"text": None}, None) == "Typing"
    assert label_for("browser_click", {"ref": ["e1"]}, None) == "Clicking"
