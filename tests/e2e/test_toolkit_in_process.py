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
