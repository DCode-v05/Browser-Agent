"""The check, with a person who is asked about risky steps (spec 18.4, 18.6, 18.7): what the fixed rules
notice about a step, and what that leads to."""

import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path
from typing import Any

import pytest
from fakes import FakeDriver

from bap_browser.config import Config
from bap_browser.driver import BrowserSession
from bap_browser.driver.base import Box, Located
from bap_browser.results import ToolResult
from bap_browser.service.session import ServiceSession
from bap_browser.tools import Toolkit

HERE = "https://shop.example/cart"
BOX = Box(10, 20, 80, 24)
Watched = Callable[..., Awaitable[tuple[ServiceSession, FakeDriver]]]


@pytest.fixture
async def watched(make_config: Callable[..., Config], tmp_path: Path) -> AsyncIterator[Watched]:
    """A session on a page of shop.example. With `viewers`, so many people watch it."""
    sessions: list[ServiceSession] = []

    async def start(*, viewers: int = 1, **sections: Any) -> tuple[ServiceSession, FakeDriver]:
        driver = FakeDriver()
        session = ServiceSession(make_config(tmp_path, **sections), driver)
        sessions.append(session)
        await session.start()
        WATCHING[session.name] = [session.hub.subscribe()[1] for _ in range(viewers)]
        driver.url = HERE
        return session, driver

    yield start
    for session in sessions:
        await session.close()


# The viewers of the session of each test, so that a test can have them leave.
WATCHING: dict[str, list[Any]] = {}


def leave(session: ServiceSession) -> None:
    """Every person who was watching closes their viewer."""
    for viewer in WATCHING.pop(session.name, []):
        session.hub.unsubscribe(viewer)


def told(session: ServiceSession, kind: str) -> list[dict[str, Any]]:
    """What viewers were told so far, read by one who looks and leaves again."""
    history, reader = session.hub.subscribe()
    session.hub.unsubscribe(reader)
    return [event for event in history if isinstance(event, dict) and event["type"] == kind]


def done(driver: FakeDriver, what: str) -> int:
    return len([call for call in driver.calls if call[0] == what])


async def asked(session: ServiceSession, count: int = 1) -> dict[str, Any]:
    """The question that is open now, once the session has put it."""
    async with asyncio.timeout(2):
        while len(told(session, "approval_requested")) < count:
            await asyncio.sleep(0)
    return told(session, "approval_requested")[-1]


async def answer(
    session: ServiceSession, call: "asyncio.Task[ToolResult]", how: str = "approve", count: int = 1
) -> tuple[dict[str, Any], ToolResult]:
    """Answers the open question, and gives it with the result of the call that waited for it."""
    request = await asked(session, count)
    await session.handle({"type": how, "id": request["id"], "scope": "once"})
    return request, await asyncio.wait_for(call, 2)


async def unasked(session: ServiceSession, name: str, arguments: dict[str, Any]) -> ToolResult:
    """Makes a call that no person is to be asked about."""
    before = len(told(session, "approval_requested"))
    result = await asyncio.wait_for(session.toolkit.call(name, arguments), 2)
    assert len(told(session, "approval_requested")) == before, "a person was asked"
    return result


def begin(session: ServiceSession, name: str, arguments: dict[str, Any]) -> "asyncio.Task[ToolResult]":
    return asyncio.create_task(session.toolkit.call(name, arguments))


# What a step does.


@pytest.mark.parametrize(
    ("control", "why"),
    [
        (Located("button", "Pay now", BOX), "this step pays for or orders something"),
        (Located("button", "अभी खरीदें", BOX), "this step pays for or orders something"),
        (Located("button", "Post", BOX), "this step sends something to other people"),
        (Located("link", "Delete account", BOX), "this step deletes something"),
        (Located("button", "Authorize", BOX), "this step gives access to something"),
        (Located("button", "Confirm seat", BOX), "this step makes something final"),
    ],
)
async def test_a_step_that_pays_sends_deletes_grants_or_confirms_is_asked_about_every_time(
    watched: Watched, control: Located, why: str
) -> None:
    session, driver = await watched()
    driver.elements["e20"] = control
    request, result = await answer(session, begin(session, "browser_click", {"ref": "e20"}))
    assert request["why"] == [why] and request["every_time"] is True
    assert not result.is_error and done(driver, "click") == 1
    # "Allow on this site" is not on offer for such a step: the next one is asked about again.
    _, again = await answer(session, begin(session, "browser_click", {"ref": "e20"}), "deny", count=2)
    assert again.is_error and again.text.startswith("The person did not allow this action.")
    assert done(driver, "click") == 1


@pytest.mark.parametrize(
    "control",
    [
        Located("button", "Next", BOX),
        Located("link", "Blog post", BOX),
        Located("button", "Apply filters", BOX),
        Located("textbox", "Send a message", BOX, kind="text"),
    ],
)
async def test_an_ordinary_control_is_pressed_without_a_question(watched: Watched, control: Located) -> None:
    session, driver = await watched()
    driver.elements["e20"] = control
    assert not (await unasked(session, "browser_click", {"ref": "e20"})).is_error


async def test_a_press_by_its_place_is_judged_by_the_control_it_lands_on(watched: Watched) -> None:
    session, driver = await watched()
    driver.at_point = Located("button", "Pay now", BOX)
    request, _ = await answer(session, begin(session, "browser_click", {"x": 40, "y": 30}), "deny")
    assert request["why"] == ["this step pays for or orders something"]
    assert done(driver, "click_at") == 0


async def test_enter_on_the_button_that_has_the_focus_presses_it(watched: Watched) -> None:
    session, driver = await watched()
    driver.focused = Located("button", "Delete account", BOX)
    request, _ = await answer(session, begin(session, "browser_press_key", {"keys": "Enter"}), "deny")
    assert request["why"] == ["this step deletes something"]
    # Another key presses nothing.
    assert not (await unasked(session, "browser_press_key", {"keys": "Tab"})).is_error


async def test_a_message_is_sent_by_enter_by_submit_and_by_the_button_of_its_form(watched: Watched) -> None:
    session, driver = await watched()
    sends = ["this step sends something to other people"]
    driver.elements["e20"] = Located("textbox", "Message", BOX, kind="text", multiline=True)
    driver.elements["e21"] = Located("textbox", "First name", BOX, kind="text")
    driver.elements["e22"] = Located("searchbox", "Search messages", BOX, kind="text", search=True)
    driver.elements["e23"] = Located(
        "button",
        "OK",
        BOX,
        sends_form=(("textbox", "Name", False, False), ("textbox", "Comment", True, False)),
    )
    driver.elements["e24"] = Located("button", "OK", BOX, sends_form=(("textbox", "Name", False, False),))

    request, _ = await answer(session, begin(session, "browser_press_key", {"keys": "Enter", "ref": "e20"}))
    assert request["why"] == sends
    typing = {"ref": "e20", "text": "See you at nine", "submit": True}
    request, _ = await answer(session, begin(session, "browser_type", typing), count=2)
    assert request["why"] == sends
    request, _ = await answer(session, begin(session, "browser_click", {"ref": "e23"}), count=3)
    assert request["why"] == sends

    for name, arguments in (
        ("browser_type", {"ref": "e20", "text": "See you at nine"}),
        ("browser_press_key", {"keys": "Enter", "ref": "e21"}),
        ("browser_press_key", {"keys": "Enter", "ref": "e22"}),
        ("browser_type", {"ref": "e22", "text": "invoices", "submit": True}),
        ("browser_click", {"ref": "e24"}),
    ):
        assert not (await unasked(session, name, arguments)).is_error, (name, arguments)


# Who is asked, and when nobody is there.


async def test_with_nobody_watching_a_question_a_rule_raised_is_refused_whatever_the_deployment_says(
    watched: Watched,
) -> None:
    session, driver = await watched(
        viewers=0,
        control={"approval_without_viewer": "allow"},
        safety={"action_policies": {"browser_hover": "confirm"}},
    )
    refused = await session.toolkit.call("browser_click", {"ref": "e7"})
    assert refused.is_error
    assert refused.text.startswith("This action needs a person's approval and no one is watching")
    assert done(driver, "click") == 0
    # A tool the deployment wants confirmed is the deployment's to wave through.
    assert not (await session.toolkit.call("browser_hover", {"ref": "e1"})).is_error


async def test_a_session_nobody_can_reach_refuses_what_a_rule_asks_about(make_config, tmp_path: Path) -> None:
    driver = FakeDriver()
    tools = Toolkit(
        BrowserSession(make_config(tmp_path, control={"approval_without_viewer": "allow"}), driver)
    )
    await tools.call("browser_snapshot", {})
    refused = await tools.call("browser_click", {"ref": "e7"})
    assert refused.is_error and "no one is watching" in refused.text


async def test_a_tool_the_deployment_denies_is_refused_before_anything_else(watched: Watched) -> None:
    session, driver = await watched(safety={"action_policies": {"browser_click": "deny"}})
    refused = await unasked(session, "browser_click", {"ref": "e7"})
    assert refused.text.startswith("browser_click is not allowed on this deployment.")
    assert done(driver, "click") == 0


async def test_every_decision_is_in_the_log_and_nothing_that_was_typed(
    watched: Watched, tmp_path: Path
) -> None:
    session, driver = await watched()
    driver.elements["e20"] = Located("textbox", "Message", BOX, kind="text", multiline=True)
    await unasked(session, "browser_snapshot", {})
    typing = {"ref": "e20", "text": "The code is 48151623", "submit": True}
    await answer(session, begin(session, "browser_type", typing), "deny")
    await answer(session, begin(session, "browser_click", {"ref": "e7"}), count=2)
    lines = [json.loads(line) for line in (tmp_path / "events.jsonl").read_text("utf-8").splitlines()]
    checks = [line["check"] for line in lines]
    assert [(check["stage"], check["outcome"], check["findings"]) for check in checks] == [
        ("rule", "run", []),
        ("person", "refuse", ["sending_step"]),
        ("person", "run", ["paying_step"]),
    ]
    assert all(isinstance(check["ms"], float) for check in checks)
    assert "48151623" not in (tmp_path / "events.jsonl").read_text("utf-8")


# What goes out.


@pytest.mark.parametrize(
    ("field", "what"),
    [
        (Located("textbox", "Password", BOX, secret=True, kind="text"), "a password"),
        (Located("textbox", "Secret word", BOX, kind="text", dots=True), "a password"),
        (Located("textbox", "", BOX, kind="text", autocomplete="one-time-code"), "a code"),
        (Located("textbox", "", BOX, kind="text", autocomplete="cc-number"), "a card number"),
        (Located("textbox", "Card number", BOX, kind="text"), "a card number"),
        (Located("textbox", "", BOX, kind="text", attributes=("otpCode",)), "a code"),
        (Located("textbox", "Aadhaar", BOX, kind="text"), "an identity or account number"),
    ],
)
async def test_typing_into_a_sensitive_field_is_a_persons_to_allow(
    watched: Watched, field: Located, what: str
) -> None:
    session, driver = await watched()
    driver.elements["e20"] = field
    request, result = await answer(
        session, begin(session, "browser_type", {"ref": "e20", "text": "hunter2!"})
    )
    assert request["why"] == [f"this step types {what} into a field"]
    assert "hunter2!" not in json.dumps(told(session, "approval_requested")), (
        "what is typed is shown to nobody"
    )
    assert not result.is_error and done(driver, "type") == 1


@pytest.mark.parametrize(
    "field",
    [
        Located("textbox", "PIN code", BOX, kind="text"),
        Located("textbox", "Shipping address", BOX, kind="text", attributes=("shipping", "spinner")),
        Located("textbox", "Your opinion", BOX, kind="text"),
    ],
)
async def test_a_field_that_only_sounds_sensitive_is_typed_into_without_a_question(
    watched: Watched, field: Located
) -> None:
    session, driver = await watched()
    driver.elements["e20"] = field
    assert not (await unasked(session, "browser_type", {"ref": "e20", "text": "560001"})).is_error


async def test_a_form_is_asked_about_when_one_of_its_fields_is_sensitive(watched: Watched) -> None:
    session, _ = await watched()
    filling = {"fields": [{"ref": "e3", "value": "ada@example.com"}, {"ref": "e8", "value": "hunter2!"}]}
    request, _ = await answer(session, begin(session, "browser_fill_form", filling), "deny")
    assert request["why"] == ["this step types a password into a field"]


async def test_on_the_cores_own_pages_a_made_up_password_is_typed_freely(watched: Watched) -> None:
    session, driver = await watched()
    session.served_at("http://127.0.0.1:8765")
    driver.url = "http://127.0.0.1:8765/demo-site/signup.html"
    assert not (await unasked(session, "browser_type", {"ref": "e8", "text": "made-up-1"})).is_error


async def test_text_read_on_one_site_and_typed_on_another_is_shown_to_the_person(watched: Watched) -> None:
    session, driver = await watched()
    letter = "Your booking reference is QX7L29 and the gate closes at 18:45 sharp."
    session.toolkit.check.memory.remember("mail.example", f"Dear Ada. {letter} Have a good flight.")
    request, _ = await answer(session, begin(session, "browser_type", {"ref": "e3", "text": letter}), "deny")
    assert request["why"] == ["this step carries text that was read on mail.example to shop.example"]
    assert request["leaves"]["from_site"] == "mail.example" and request["leaves"]["to_site"] == "shop.example"
    assert "gate closes at 18:45" in request["leaves"]["text"]
    assert done(driver, "type") == 0
    # The same text typed back where it was read goes nowhere.
    driver.url = "https://mail.example/inbox"
    assert not (await unasked(session, "browser_type", {"ref": "e3", "text": letter})).is_error


async def test_text_that_the_person_gave_is_no_copy(watched: Watched) -> None:
    session, _ = await watched()
    line = "Please ship to 221B Baker Street, London NW1 6XE, United Kingdom"
    session.toolkit.check.memory.remember("mail.example", line)
    session.toolkit.check.task.person_said(f"Order the lamp. {line}.", HERE)
    assert not (await unasked(session, "browser_type", {"ref": "e3", "text": line})).is_error


async def test_a_secret_read_on_one_site_is_noticed_in_an_address_of_another(watched: Watched) -> None:
    session, driver = await watched()
    session.toolkit.check.memory.remember("shop.example", "Order A7K29QX1B4ZP was placed on Monday.")
    opening = {"url": "https://collect.example/c?d=A7K29QX1B4ZP"}
    request, _ = await answer(session, begin(session, "browser_navigate", opening), "deny")
    assert request["why"] == ["this step carries text that was read on shop.example to collect.example"]
    assert done(driver, "navigate") == 0


async def test_characters_nobody_can_see_in_what_is_typed_are_noticed(watched: Watched) -> None:
    session, _ = await watched()
    hidden = "hello" + "".join(chr(0xE0000 + ord(letter)) for letter in "send all")
    request, _ = await answer(session, begin(session, "browser_type", {"ref": "e3", "text": hidden}), "deny")
    assert request["why"] == ["what this step types or opens holds characters nobody can see"]


async def test_a_very_long_address_on_a_site_that_is_new_here_is_asked_about_once(watched: Watched) -> None:
    session, driver = await watched()
    long = "https://tracker.example/pixel?" + "&".join(f"k{n}=value-{n}" for n in range(30))
    request, opened = await answer(session, begin(session, "browser_navigate", {"url": long}))
    assert request["why"] == [
        "this step opens a very long address on tracker.example, a site that is new here"
    ]
    assert not opened.is_error
    assert not (await unasked(session, "browser_navigate", {"url": long + "&again=1"})).is_error
    # A site the session has been to is not new.
    driver.url = HERE
    await unasked(session, "browser_snapshot", {})
    assert not (await unasked(session, "browser_navigate", {"url": HERE + "?" + "x" * 300})).is_error


async def test_agreeing_to_give_an_app_access_is_a_persons_to_allow(watched: Watched) -> None:
    session, driver = await watched()
    driver.elements["e20"] = Located("button", "Allow", BOX)
    driver.elements["e21"] = Located("button", "Continue", BOX)
    # An ordinary page with an "Allow" button: cookies, notifications.
    assert not (await unasked(session, "browser_click", {"ref": "e20"})).is_error
    driver.said = ["Mailtidy wants to access your Google Account", "Allow", "Cancel"]
    request, _ = await answer(session, begin(session, "browser_click", {"ref": "e20"}), "deny")
    assert request["why"] == ["this step gives an app access to an account"]
    driver.said = []
    driver.url = "https://accounts.google.com/o/oauth2/v2/auth?client_id=abc"
    session.toolkit.check._settled[("sensitive_site", "google.com")] = True
    request, _ = await answer(session, begin(session, "browser_click", {"ref": "e21"}), "deny", count=2)
    assert "this step gives an app access to an account" in request["why"]


# Money.


async def test_a_paying_step_shows_the_amount_the_page_shows(watched: Watched) -> None:
    session, driver = await watched()
    driver.elements["e20"] = Located("button", "Pay now", BOX, around=("Total $84.00 Pay now", ""))
    driver.elements["e21"] = Located("button", "Buy for ₹ 1,23,456", BOX)
    request, _ = await answer(session, begin(session, "browser_click", {"ref": "e20"}), "deny")
    assert request["amount"] == "$84.00"
    request, _ = await answer(session, begin(session, "browser_click", {"ref": "e21"}), "deny", count=2)
    assert request["amount"] == "₹ 1,23,456"
    request, _ = await answer(session, begin(session, "browser_click", {"ref": "e7"}), "deny", count=3)
    assert "amount" not in request


async def test_an_amount_over_the_cap_is_refused_and_no_amount_under_a_cap_is_asked(watched: Watched) -> None:
    session, driver = await watched(safeguards={"money": {"max_amount": 50, "max_session_total": 100}})
    driver.elements["e20"] = Located("button", "Pay $84.00", BOX)
    driver.elements["e21"] = Located("button", "Pay $40.00", BOX)
    over = await unasked(session, "browser_click", {"ref": "e20"})
    assert over.is_error and over.text.startswith(
        "Not done: the page shows $84.00, which is over the spending limit of 50 for one step."
    )
    request, _ = await answer(session, begin(session, "browser_click", {"ref": "e7"}), "deny")
    assert "a spending limit is set and the page shows no amount" in request["why"]
    # Two steps of forty are approved; a third would pass what the session may spend in all.
    for count in (2, 3):
        _, paid = await answer(session, begin(session, "browser_click", {"ref": "e21"}), count=count)
        assert not paid.is_error
    third = await unasked(session, "browser_click", {"ref": "e21"})
    assert "would take this session over its spending limit of 100" in third.text
    assert done(driver, "click") == 2


# Where the browser goes.


async def test_a_site_that_looks_like_a_protected_one_is_asked_about_once(watched: Watched) -> None:
    session, driver = await watched()
    opening = {"url": "https://paypa1.com/signin"}
    request, opened = await answer(session, begin(session, "browser_navigate", opening))
    assert request["why"] == ["paypa1.com looks like paypal.com and is not it"]
    assert not opened.is_error
    assert not (await unasked(session, "browser_snapshot", {})).is_error
    # A name the person pasted is measured like any other: they may have been sent it.
    session.toolkit.check.task.person_said("Sign in at paypal-secure-login.example", HERE)
    lure = {"url": "https://paypal-secure-login.example/"}
    request, _ = await answer(session, begin(session, "browser_navigate", lure), "deny", count=2)
    assert request["why"] == ["paypal-secure-login.example looks like paypal.com and is not it"]
    assert done(driver, "navigate") == 1


async def test_a_page_the_browser_was_brought_to_is_judged_at_the_agents_next_call(watched: Watched) -> None:
    session, driver = await watched()
    # A link, a redirect or a person's own hands: nothing asked the tool layer.
    driver.url = "https://amaz0n.com/deal"
    request, read = await answer(session, begin(session, "browser_snapshot", {}), "deny")
    assert request["why"] == ["amaz0n.com looks like amazon.com and is not it"]
    assert read.is_error and done(driver, "snapshot") == 0


async def test_a_sensitive_site_is_entered_with_a_yes_once_for_a_task(watched: Watched) -> None:
    session, driver = await watched()
    request, _ = await answer(session, begin(session, "browser_navigate", {"url": "https://www.paypal.com/"}))
    assert request["why"] == ["www.paypal.com is a money site"]
    assert not (await unasked(session, "browser_click", {"ref": "e1"})).is_error
    # Another task: the yes was for the last one.
    session.working(True, "Now pay the electricity bill")
    request, _ = await answer(session, begin(session, "browser_snapshot", {}), "deny", count=2)
    assert request["why"] == ["www.paypal.com is a money site"]
    assert driver.url == "https://www.paypal.com/"


async def test_on_a_sensitive_site_nothing_is_acted_on_when_the_person_has_left(watched: Watched) -> None:
    session, driver = await watched()
    await answer(session, begin(session, "browser_navigate", {"url": "https://www.paypal.com/"}))
    leave(session)
    left = await session.toolkit.call("browser_click", {"ref": "e1"})
    assert left.is_error
    assert left.text.startswith("Not done: www.paypal.com is a money site and nobody is watching.")
    assert not (await session.toolkit.call("browser_snapshot", {})).is_error, "reading is not acting"
    assert done(driver, "click") == 0


async def test_a_site_that_is_a_bare_number_is_a_weak_sign_and_no_person_is_asked_about_it(
    watched: Watched,
) -> None:
    session, driver = await watched()
    # In Auto Mode the reviewer weighs it (test_auto_mode.py). A person is not troubled with it.
    driver.url = "https://93.184.216.34/login"
    assert not (await unasked(session, "browser_type", {"ref": "e3", "text": "ada"})).is_error
    assert not (await unasked(session, "browser_click", {"ref": "e1"})).is_error


async def test_a_page_with_no_site_of_its_own_is_opened_with_a_yes_and_takes_no_password(
    watched: Watched,
) -> None:
    session, driver = await watched()
    request, _ = await answer(session, begin(session, "browser_navigate", {"url": "data:text/html,<p>hi"}))
    assert request["why"] == ["this step opens a page that has no site of its own"]
    driver.url = "blob:https://shop.example/0f6e"
    refused = await unasked(session, "browser_type", {"ref": "e8", "text": "hunter2!"})
    assert refused.text.startswith("Not done: this page has no site of its own and asks for a password.")
    assert done(driver, "type") == 0
