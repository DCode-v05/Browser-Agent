import json
import re
from collections.abc import Callable
from pathlib import Path

from bap_browser.config import Config
from bap_browser.driver import open_session
from bap_browser.tools import Toolkit


def ref_of(text: str, element: str) -> str:
    match = re.search(re.escape(f"- {element}") + r" \[ref=(e\d+)\]", text)
    assert match, f"{element!r} not in:\n{text}"
    return match.group(1)


async def test_an_agent_in_the_same_process_fills_and_submits_the_form(
    make_config: Callable[..., Config], tmp_path: Path, site: str
) -> None:
    async with open_session(make_config(tmp_path)) as session:
        tools = Toolkit(session)
        assert session.started_driver is None, "the browser must not start before the first tool call"
        page = await tools.call("browser_navigate", {"url": f"{site}/form.html"})
        assert page.text.startswith(f"Navigated to {site}/form.html\nPage: Sign up\n")
        assert page.text.endswith(f"[tabs] t1* {site}/form.html")

        typed = await tools.call(
            "browser_type", {"ref": ref_of(page.text, 'textbox "Full name"'), "text": "Ada Lovelace"}
        )
        assert typed.text.startswith("Typed 12 characters into ")
        await tools.call("browser_click", {"ref": ref_of(page.text, 'checkbox "I accept the terms"')})
        clicked = await tools.call("browser_click", {"ref": ref_of(page.text, 'button "Create account"')})
        assert f"Navigated to {site}/welcome.html?name=Ada%20Lovelace" in clicked.text

        after = await tools.call("browser_snapshot", {})
        assert 'heading "Welcome, Ada Lovelace"' in after.text
        stale = await tools.call("browser_click", {"ref": ref_of(page.text, 'button "Create account"')})
        assert stale.is_error and "is stale or unknown" in stale.text

    lines = [
        json.loads(line) for line in (tmp_path / "events.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [line["tool"] for line in lines][:2] == ["browser_navigate", "browser_type"]
    assert "Ada Lovelace" not in json.dumps(lines[1], ensure_ascii=False), "typed text reached the log"


async def test_what_is_typed_stays_out_of_the_log_and_out_of_element_names(
    make_config: Callable[..., Config], tmp_path: Path, site: str
) -> None:
    card, note = "4111 1111 1111 1111", "my pin is 9731"
    # Nobody watches here, and a card number is a person's to allow (spec 18.6). This test is about
    # what is kept of what was typed, so the deployment waves that question through.
    unasked = {"outgoing": {"sensitive_fields": False}}
    async with open_session(make_config(tmp_path, safeguards=unasked)) as session:
        tools = Toolkit(session)
        page = await tools.call("browser_navigate", {"url": f"{site}/richtext.html"})
        await tools.call("browser_type", {"ref": ref_of(page.text, 'textbox "Card number"'), "text": card})
        box = ref_of(page.text, "textbox")
        await tools.call("browser_type", {"ref": box, "text": note})
        again = await tools.call("browser_type", {"ref": box, "text": "second", "clear": False})
        # The agent may see what a field holds; that is how it checks its own work.
        filled = await tools.call("browser_snapshot", {})
        assert f'value="{card}"' in filled.text
    assert again.text.startswith(f"Typed 6 characters into {box} (textbox)\n"), again.text
    log = (tmp_path / "events.jsonl").read_text(encoding="utf-8")
    assert card not in log and note not in log and "9731" not in log


async def test_a_page_cannot_make_a_result_as_long_as_it_likes(
    make_config: Callable[..., Config], tmp_path: Path, site: str
) -> None:
    async with open_session(make_config(tmp_path)) as session:
        tools = Toolkit(session)
        page = await tools.call("browser_navigate", {"url": f"{site}/long_address.html"})
        clicked = await tools.call("browser_click", {"ref": ref_of(page.text, 'button "Grow"')})
        read = await tools.call("browser_snapshot", {"max_chars": 500})
    assert len(clicked.text) < 1000, len(clicked.text)
    assert len(read.text) < 1000, len(read.text)


async def test_a_browser_that_went_away_is_said_to_be_gone_and_a_navigation_starts_a_new_one(
    make_config: Callable[..., Config], tmp_path: Path, site: str
) -> None:
    async with open_session(make_config(tmp_path)) as session:
        tools = Toolkit(session)
        page = await tools.call("browser_navigate", {"url": f"{site}/form.html"})
        browser = (await session.driver()).page.context.browser  # type: ignore[attr-defined]
        await browser.close()

        gone = await tools.call("browser_click", {"ref": ref_of(page.text, 'button "Create account"')})
        assert gone.is_error
        assert gone.text == "The browser closed. Open a page with browser_navigate to start it again."

        again = await tools.call("browser_navigate", {"url": f"{site}/form.html"})
        assert again.text.startswith(f"Navigated to {site}/form.html\nPage: Sign up\n")
        # The new browser's elements get new refs: one from the browser that closed can never match.
        old = ref_of(page.text, 'button "Create account"')
        assert ref_of(again.text, 'button "Create account"') != old


async def test_a_form_is_filled_in_one_call_and_submitted_with_a_key(
    make_config: Callable[..., Config], tmp_path: Path, site: str
) -> None:
    # A password is a person's to allow (spec 18.6), and nobody watches here: see the test above.
    unasked = {"outgoing": {"sensitive_fields": False}}
    async with open_session(make_config(tmp_path, safeguards=unasked)) as session:
        tools = Toolkit(session)
        page = (await tools.call("browser_navigate", {"url": f"{site}/form.html"})).text
        name = ref_of(page, 'textbox "Full name"')
        fields = [
            {"ref": name, "value": "Ada Lovelace"},
            {"ref": ref_of(page, 'textbox "Password"'), "value": "hunter2-secret"},
            {"ref": ref_of(page, 'combobox "Country"'), "value": "India"},
            {"ref": ref_of(page, 'radio "Pro"'), "value": True},
            {"ref": ref_of(page, 'checkbox "I accept the terms"'), "value": True},
        ]
        filled = await tools.call("browser_fill_form", {"fields": fields})
        refs = [field["ref"] for field in fields]
        assert filled.text.startswith(
            f"Filled: {refs[0]}, {refs[1]}, {refs[2]}=India, {refs[3]}=checked, {refs[4]}=checked\n"
        ), filled.text
        found = await tools.call("browser_find", {"query": "country"})
        assert 'combobox "Country"' in found.text and 'value="India"' in found.text
        text = await tools.call("browser_get_text", {})
        assert "hunter2-secret" not in text.text and "Sign up" in text.text
        pressed = await tools.call("browser_press_key", {"keys": "enter", "ref": name})
        assert pressed.text.startswith(
            f'Pressed Enter on {name} (textbox "Full name")\nNavigated to {site}/welcome.html'
        )
        back = await tools.call("browser_go_back", {})
        assert back.text.startswith(f"Navigated to {site}/form.html\nPage: Sign up\n")
        gone = await tools.call("browser_wait", {"text": "Sign up", "timeout_s": 5})
        assert gone.text.startswith("The text is on the page.")
    log = (tmp_path / "events.jsonl").read_text(encoding="utf-8")
    assert "hunter2-secret" not in log and "Ada Lovelace" not in log
