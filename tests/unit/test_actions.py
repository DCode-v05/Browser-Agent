"""What a step does, told by the name of the control it presses (spec 18.4)."""

import pytest

from bap_browser.config_safeguards import Actions
from bap_browser.safeguards.actions import class_of, holds, is_message_box

ACTIONS = Actions()


@pytest.mark.parametrize(
    ("name", "kind"),
    [
        ("Pay now", "pays"),
        ("Pay $84.00", "pays"),
        ("Complete payment", "pays"),
        ("BUY", "pays"),
        ("Place order", "pays"),
        ("Place  order", "pays"),
        ("Proceed to checkout", "pays"),
        ("Check out", "pays"),
        ("Book now", "pays"),
        ("Top up wallet", "pays"),
        ("अभी भुगतान करें", "pays"),
        ("खरीदें", "pays"),
        ("Send", "sends"),
        ("Send message", "sends"),
        ("Post", "sends"),
        ("Submit application", "sends"),
        ("Publish", "sends"),
        ("Tweet", "sends"),
        ("संदेश भेजें", "sends"),
        ("Delete account", "deletes"),
        ("Remove item", "deletes"),
        ("Clear all", "deletes"),
        ("Unsubscribe", "deletes"),
        ("Cancel order", "deletes"),
        ("हटाएं", "deletes"),
        ("Authorize app", "grants"),
        ("Grant access", "grants"),
        ("Confirm seat", "commits"),
        ("पुष्टि करें", "commits"),
    ],
)
def test_a_control_is_classed_by_what_its_name_says_it_does(name: str, kind: str) -> None:
    assert class_of(name, ACTIONS) == kind


@pytest.mark.parametrize(
    "name",
    [
        "Next",
        "Search",
        # Wizards say these at every step: they are not what makes a step final.
        "Finish",
        "Proceed",
        "Complete profile",
        # Words that open something more often than they send it are not in the lists.
        "Reply",
        "Share",
        "Apply filters",
        "Open menu",
        "Window seat",
        # A word is matched whole: these only hold the letters of one.
        "Paypal",
        "Display options",
        "Resend-code-later-1buyer",
        "Postal code",
        "Sender name",
        "Border",
        "Orders",
        "Removed items",
        "Completed",
        "",
    ],
)
def test_a_name_that_only_holds_the_letters_of_such_a_word_is_not_classed(name: str) -> None:
    assert class_of(name, ACTIONS) is None


def test_a_name_that_says_two_things_takes_the_graver_one() -> None:
    assert class_of("Confirm and pay", ACTIONS) == "pays"
    assert class_of("Confirm and send", ACTIONS) == "sends"
    assert class_of("Delete and confirm", ACTIONS) == "deletes"


@pytest.mark.parametrize(
    ("name", "kind"),
    [("Blog post", None), ("Confirm your email", None), ("Pay now", "pays"), ("Delete", "deletes")],
)
def test_a_link_goes_somewhere_so_it_is_classed_only_when_it_pays_deletes_or_grants(
    name: str, kind: str | None
) -> None:
    assert class_of(name, ACTIONS, role="link") == kind


def test_a_field_that_is_typed_into_is_not_classed_by_its_name() -> None:
    assert class_of("Send a message", ACTIONS, role="textbox") is None
    assert class_of("Send a message", ACTIONS, role="button") == "sends"


def test_the_deployments_own_words_make_a_step_one_that_commits() -> None:
    assert class_of("Escalate ticket", ACTIONS) is None
    assert class_of("Escalate ticket", ACTIONS, ["escalate"]) == "commits"
    # A word that is in a class keeps that class.
    assert class_of("Pay", ACTIONS, ["pay"]) == "pays"


def test_a_word_is_found_whatever_its_case_and_a_word_of_another_script_anywhere() -> None:
    assert holds("PLACE ORDER", ["place order"])
    assert holds("Pay.", ["pay"])
    assert holds("(send)", ["send"])
    assert not holds("resend", ["send"])
    assert holds("कृपयाभेजेंअभी", ["भेजें"])


@pytest.mark.parametrize(
    ("role", "texts", "multiline", "search", "expected"),
    [
        ("textbox", ["Message"], False, False, True),
        ("textbox", ["Write a comment"], False, False, True),
        ("textbox", ["To"], False, False, True),
        ("textbox", [""], True, False, True),
        ("textbox", ["First name"], False, False, False),
        ("textbox", ["Tomato"], False, False, False),
        ("searchbox", ["Search messages"], False, False, False),
        ("textbox", ["Search messages"], False, True, False),
    ],
)
def test_a_message_box_is_a_field_a_message_is_written_in(
    role: str, texts: list[str], multiline: bool, search: bool, expected: bool
) -> None:
    assert is_message_box(role, texts, ACTIONS, multiline=multiline, search=search) is expected
