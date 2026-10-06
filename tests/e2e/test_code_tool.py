"""`browser_run` against a real browser (spec 7, 14.4): one call fills a form by the words on it and
collects from three pages."""

import json
from collections.abc import Callable
from pathlib import Path

from bap_browser.config import Config
from bap_browser.driver import open_session
from bap_browser.tools import Toolkit

SCRIPT = """
await browser.navigate("{site}/form.html")
await browser.type(find="Full name", text="Ada Lovelace")
await browser.click(find="I accept the terms")
after = await browser.click(find="Create account")
print("welcomed:", "Welcome, Ada Lovelace" in await browser.snapshot())

headings = []
for page in ("form.html", "welcome.html", "tools.html"):
    await browser.navigate("{site}/" + page)
    snap = await browser.snapshot(mode="all")
    headings += re.findall(r'heading "([^"]+)"', snap)[:1]
state["pages"] = len(headings)
headings
"""


async def test_one_call_fills_a_form_and_collects_from_three_pages(
    make_config: Callable[..., Config], tmp_path: Path, site: str
) -> None:
    async with open_session(make_config(tmp_path, code={"enabled": True})) as session:
        tools = Toolkit(session)
        result = await tools.call("browser_run", {"code": SCRIPT.format(site=site)})
        assert not result.is_error, result.text
        lines = result.text.splitlines()
        # One call where single tools would take fourteen.
        assert lines[0] == "Ran the script: 14 steps."
        assert "Printed:\nwelcomed: True" in result.text
        value = json.loads(next(line for line in lines if line.startswith("Value: ")).removeprefix("Value: "))
        assert value[:2] == ["Sign up", "Welcome"] and len(value) == 3
        assert lines[-1] == f"[tabs] t1* {site}/tools.html"
        # Each step is listed, in the words the tool itself answers with.
        steps = lines[lines.index("Steps (14):") + 1 :][:14]
        assert steps[0] == f"1. ok: Navigated to {site}/form.html"
        # The words named a label and a field. What was typed went into the field.
        assert steps[2] == '3. ok: Typed 12 characters into e2 (textbox "Full name")'
        assert steps[4] == '5. ok: Clicked e8 (checkbox "I accept the terms")'
        assert all(step.split(". ", 1)[1].startswith("ok: ") for step in steps)

        # What the script kept is there for the next one, and a failed step says where it stopped.
        again = await tools.call(
            "browser_run", {"code": 'n = state["pages"]\nawait browser.click(find="No such button")\nn'}
        )
        assert again.is_error
        assert again.text.splitlines()[0].startswith(
            "Step 2 failed at line 2 of the script: Nothing on the page"
        )

    log = [json.loads(line) for line in (tmp_path / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [line["tool"] for line in log].count("browser_run") == 2
    # What the script typed reached the page, and nothing that is kept.
    assert "Ada Lovelace" not in (tmp_path / "events.jsonl").read_text(encoding="utf-8")
