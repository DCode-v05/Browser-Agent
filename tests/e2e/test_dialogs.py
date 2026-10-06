"""Page dialogs in a real browser (spec 5.7): alert, confirm, prompt and "leave this page?"."""

import asyncio
import json
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from bap_browser.agent.models import ref_of
from bap_browser.config import Config
from bap_browser.driver import open_session
from bap_browser.tools import Toolkit


@asynccontextmanager
async def on_the_dialogs_page(
    make_config: Callable[..., Config], folder: Path, site: str, **browser: Any
) -> AsyncIterator[tuple[Toolkit, str]]:
    folder.mkdir(exist_ok=True)
    async with open_session(make_config(folder, browser=browser)) as session:
        tools = Toolkit(session)
        page = await tools.call("browser_navigate", {"url": f"{site}/dialogs.html"})
        yield tools, page.text


async def said(tools: Toolkit) -> str:
    text = (await tools.call("browser_get_text", {})).text
    return text.split("\n[tabs]")[0].splitlines()[-1]


async def test_a_dialog_interrupts_the_action_which_finishes_once_it_is_answered(
    make_config: Callable[..., Config], tmp_path: Path, site: str
) -> None:
    async with on_the_dialogs_page(make_config, tmp_path, site) as (tools, page):
        button = ref_of(page, 'button "Ask to proceed"')
        asked = await tools.call("browser_click", {"ref": button})
        assert not asked.is_error
        assert asked.text.startswith(
            "A confirm dialog ('Proceed?') opened, and the page waits for the answer. "
            "Answer it with browser_handle_dialog: what this call began is then finished."
        ), asked.text

        # While it is open, a tool that needs the page is refused, and is told why.
        for tool, arguments in (("browser_snapshot", {}), ("browser_click", {"ref": button})):
            refused = await tools.call(tool, arguments)
            assert refused.is_error
            assert refused.text.startswith(
                "A confirm dialog is open ('Proceed?') and blocks the page. "
                "Answer it first with browser_handle_dialog."
            ), refused.text
        # The tools that need nothing from the page still run.
        listed = await tools.call("browser_tabs", {"action": "list"})
        assert not listed.is_error and listed.text.startswith("1 tab, the active one marked *:")
        assert not (await tools.call("browser_console", {})).is_error

        answered = await tools.call("browser_handle_dialog", {"action": "accept"})
        assert not answered.is_error
        assert answered.text.startswith(
            f"Accepted the dialog 'Proceed?'.\nClicked {button} (button \"Ask to proceed\")"
        ), answered.text
        assert await said(tools) == "Proceeded"

        await tools.call("browser_click", {"ref": button})
        dismissed = await tools.call("browser_handle_dialog", {"action": "dismiss"})
        assert dismissed.text.startswith("Dismissed the dialog 'Proceed?'.\nClicked ")
        assert await said(tools) == "Stayed"

        nothing = await tools.call("browser_handle_dialog", {"action": "accept"})
        assert nothing.is_error and nothing.text.startswith("No dialog is open.")


async def test_an_alert_and_a_prompt(make_config: Callable[..., Config], tmp_path: Path, site: str) -> None:
    async with on_the_dialogs_page(make_config, tmp_path, site) as (tools, page):
        hello = await tools.call("browser_click", {"ref": ref_of(page, 'button "Say hello"')})
        assert hello.text.startswith("An alert dialog ('Hello there') opened")
        await tools.call("browser_handle_dialog", {"action": "accept"})
        assert await said(tools) == "The alert was closed"

        name = ref_of(page, 'button "Ask my name"')
        asked = await tools.call("browser_click", {"ref": name})
        assert asked.text.startswith("A prompt dialog ('Your name?') opened")
        await tools.call("browser_handle_dialog", {"action": "accept", "prompt_text": "Ada Lovelace"})
        assert await said(tools) == "Name: Ada Lovelace"

        # Accepted with no text, a prompt keeps what the page put in it.
        await tools.call("browser_click", {"ref": name})
        await tools.call("browser_handle_dialog", {"action": "accept"})
        assert await said(tools) == "Name: nobody"

        await tools.call("browser_click", {"ref": name})
        await tools.call("browser_handle_dialog", {"action": "dismiss"})
        assert await said(tools) == "No name"
    log = (tmp_path / "events.jsonl").read_text(encoding="utf-8")
    assert "Ada Lovelace" not in log, "what was entered in a prompt reached the log"
    answers = [json.loads(line) for line in log.splitlines() if '"browser_handle_dialog"' in line]
    assert answers[1]["args"] == {"action": "accept", "prompt_text": "<12 characters>"}


async def test_one_action_can_open_one_dialog_after_another(
    make_config: Callable[..., Config], tmp_path: Path, site: str
) -> None:
    async with on_the_dialogs_page(make_config, tmp_path, site) as (tools, page):
        first = await tools.call("browser_click", {"ref": ref_of(page, 'button "Ask twice"')})
        assert first.text.startswith("A confirm dialog ('First?') opened")
        second = await tools.call("browser_handle_dialog", {"action": "accept"})
        assert second.text.startswith(
            "Accepted the dialog 'First?'.\nA confirm dialog ('Second?') opened, and the page waits"
        ), second.text
        done = await tools.call("browser_handle_dialog", {"action": "dismiss"})
        assert done.text.startswith("Dismissed the dialog 'Second?'.\nClicked "), done.text
        assert await said(tools) == "First true, second false"


async def test_the_action_goes_on_to_where_the_answer_leads(
    make_config: Callable[..., Config], tmp_path: Path, site: str
) -> None:
    async with on_the_dialogs_page(make_config, tmp_path, site) as (tools, page):
        await tools.call("browser_click", {"ref": ref_of(page, 'button "Ask, then go on"')})
        answered = await tools.call("browser_handle_dialog", {"action": "accept"})
        assert f"\nNavigated to {site}/welcome.html?name=Onward" in answered.text, answered.text


async def test_an_answer_that_comes_late_does_not_fail_the_action_it_held_up(
    make_config: Callable[..., Config], tmp_path: Path, site: str
) -> None:
    quick = {"timeouts": {"action_ms": 500, "page_reply_ms": 500}}
    async with on_the_dialogs_page(make_config, tmp_path, site, **quick) as (tools, page):
        await tools.call("browser_click", {"ref": ref_of(page, 'button "Ask to proceed"')})
        # A model takes longer to answer than a click is given to finish.
        await asyncio.sleep(1.5)
        answered = await tools.call("browser_handle_dialog", {"action": "accept"})
        assert not answered.is_error
        assert "\nClicked " in answered.text and "did not answer" not in answered.text, answered.text
        assert await said(tools) == "Proceeded"


async def test_a_dialog_that_opens_between_calls_is_met_by_the_next_one(
    make_config: Callable[..., Config], tmp_path: Path, site: str
) -> None:
    async with on_the_dialogs_page(make_config, tmp_path, site) as (tools, page):
        clicked = await tools.call("browser_click", {"ref": ref_of(page, 'button "Ask in a moment"')})
        assert clicked.text.startswith("Clicked ")
        await asyncio.sleep(0.6)
        refused = await tools.call("browser_snapshot", {})
        assert refused.is_error and refused.text.startswith("A confirm dialog is open ('Still there?')")
        answered = await tools.call("browser_handle_dialog", {"action": "accept"})
        assert answered.text.startswith("Accepted the dialog 'Still there?'.\n[tabs]"), answered.text
        assert await said(tools) == "Still there"


async def test_a_dialog_nobody_answers_is_dismissed_and_the_agent_is_told(
    make_config: Callable[..., Config], tmp_path: Path, site: str
) -> None:
    async with on_the_dialogs_page(make_config, tmp_path, site, dialogs={"timeout_s": 1}) as (tools, page):
        button = ref_of(page, 'button "Ask to proceed"')
        await tools.call("browser_click", {"ref": button})
        await asyncio.sleep(1.5)
        read = await tools.call("browser_get_text", {})
        assert not read.is_error
        assert read.text.startswith(
            "[The dialog went away unanswered, and the action it had interrupted finished: "
            f'Clicked {button} (button "Ask to proceed")]\n'
        ), read.text
        assert read.text.endswith(
            "[events] a confirm dialog ('Proceed?') was dismissed: nobody answered it within 1 s"
        ), read.text
        assert "Stayed" in read.text


async def test_dialogs_can_be_answered_without_the_agent(
    make_config: Callable[..., Config], tmp_path: Path, site: str
) -> None:
    accepting = {"dialogs": {"policy": "auto_accept", "default_prompt_text": "Grace"}}
    async with on_the_dialogs_page(make_config, tmp_path / "a", site, **accepting) as (tools, page):
        clicked = await tools.call("browser_click", {"ref": ref_of(page, 'button "Ask to proceed"')})
        assert clicked.text.startswith("Clicked ")
        assert clicked.text.endswith(
            "[events] a confirm dialog ('Proceed?') opened and was accepted automatically"
        ), clicked.text
        assert await said(tools) == "Proceeded"
        await tools.call("browser_click", {"ref": ref_of(page, 'button "Ask my name"')})
        assert await said(tools) == "Name: Grace"

    dismissing = {"dialogs": {"policy": "auto_dismiss"}}
    async with on_the_dialogs_page(make_config, tmp_path / "b", site, **dismissing) as (tools, page):
        clicked = await tools.call("browser_click", {"ref": ref_of(page, 'button "Ask to proceed"')})
        assert clicked.text.endswith("opened and was dismissed automatically"), clicked.text
        assert await said(tools) == "Stayed"


async def test_leaving_a_page_that_asks_first(
    make_config: Callable[..., Config], tmp_path: Path, site: str
) -> None:
    async with on_the_dialogs_page(make_config, tmp_path, site) as (tools, page):
        await tools.call("browser_click", {"ref": ref_of(page, 'button "Guard this page"')})
        link = ref_of(page, 'link "Go elsewhere"')
        leaving = await tools.call("browser_click", {"ref": link})
        assert leaving.text.startswith(
            "A dialog that asks whether to leave the page opened, and the page waits for the answer."
        ), leaving.text
        refused = await tools.call("browser_snapshot", {})
        assert refused.text.startswith(
            "A dialog that asks whether to leave the page is open and blocks the page."
        ), refused.text
        stayed = await tools.call("browser_handle_dialog", {"action": "dismiss"})
        assert stayed.text.startswith("Dismissed the dialog that asked whether to leave the page.\n")
        assert (await tools.call("browser_snapshot", {})).text.startswith("Page: Dialogs\n")

        await tools.call("browser_click", {"ref": link})
        left = await tools.call("browser_handle_dialog", {"action": "accept"})
        assert f"\nNavigated to {site}/welcome.html?name=Elsewhere" in left.text, left.text
