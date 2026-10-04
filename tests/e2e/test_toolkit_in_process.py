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
    async with open_session(make_config(tmp_path)) as session:
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
