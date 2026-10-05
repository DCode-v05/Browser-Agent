"""The reference agent loop (spec 16.5), against a fake browser and a scripted model."""

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import pytest
from fakes import SNAPSHOT, FakeDriver

from bap_browser.agent.loop import Unfinished, run_agent
from bap_browser.agent.models import Message, Reply, Said, ScriptedModel, ToolCall, ToolOutput, ref_of
from bap_browser.config import Agent, Config
from bap_browser.driver import BrowserSession
from bap_browser.errors import StaleRef
from bap_browser.tools import TOOLS, ToolDefinition, Toolkit

SETTINGS = Agent(provider="scripted")


def kit(make_config: Callable[..., Config], folder: Path) -> tuple[Toolkit, FakeDriver]:
    driver = FakeDriver()
    return Toolkit(BrowserSession(make_config(folder), driver)), driver


def calls(name: str, **arguments: Any) -> Callable[[str], Reply]:
    return lambda page: Reply("", (ToolCall("c1", name, arguments),))


def says(text: str) -> Callable[[str], Reply]:
    return lambda page: Reply(text, ())


class Recording:
    """A model that answers from a list and remembers what it was shown."""

    def __init__(self, replies: Sequence[Reply]) -> None:
        self.replies = list(replies)
        self.seen: list[tuple[str, list[Message], list[str]]] = []

    async def complete(
        self, system: str, messages: Sequence[Message], tools: Sequence[ToolDefinition]
    ) -> Reply:
        self.seen.append((system, list(messages), [tool.name for tool in tools]))
        return self.replies.pop(0)


async def test_the_loop_runs_tool_calls_until_the_model_answers_without_one(
    make_config, tmp_path: Path
) -> None:
    tools, driver = kit(make_config, tmp_path)
    model = Recording(
        [
            Reply(
                "I will open the page.",
                (ToolCall("a", "browser_navigate", {"url": "https://93.184.216.34/"}),),
            ),
            Reply("", (ToolCall("b", "browser_click", {"ref": "e1"}),)),
            Reply("Done: the button was clicked.", ()),
        ]
    )
    said: list[str] = []
    answer = await run_agent("Click Go", tools, model, SETTINGS, on_text=said.append)
    assert answer == "Done: the button was clicked."
    assert [call[0] for call in driver.calls] == ["navigate", "snapshot", "click"]
    # What the model says while it works is passed on as it comes; the answer is returned.
    assert said == ["I will open the page."]


async def test_the_model_is_shown_the_task_the_tools_and_every_result(make_config, tmp_path: Path) -> None:
    tools, _ = kit(make_config, tmp_path)
    first = ToolCall("a", "browser_snapshot", {})
    model = Recording([Reply("", (first,)), Reply("It says Fake.", ())])
    await run_agent("What is on the page?", tools, model, SETTINGS)
    system, opening, offered = model.seen[0]
    assert "untrusted" in system and "browser_snapshot" in system
    assert opening == [Said("user", "What is on the page?")]
    assert offered == [tool.name for tool in TOOLS]
    _, later, _ = model.seen[1]
    assert later == [
        Said("user", "What is on the page?"),
        Said("assistant", "", (first,)),
        ToolOutput(first, f"{SNAPSHOT}\n[tabs] t1* about:blank", False),
    ]


async def test_a_failed_call_goes_back_to_the_model_as_a_result_and_the_loop_goes_on(
    make_config, tmp_path: Path
) -> None:
    tools, driver = kit(make_config, tmp_path)
    await tools.call("browser_snapshot", {})
    driver.fail_with = StaleRef("e9")
    bad = ToolCall("a", "browser_click", {"ref": "e9"})
    model = Recording([Reply("", (bad,)), Reply("The button is gone.", ())])
    assert await run_agent("Click it", tools, model, SETTINGS) == "The button is gone."
    result = model.seen[1][1][-1]
    assert isinstance(result, ToolOutput) and result.is_error
    assert result.text.startswith("Ref 'e9' is stale or unknown")


async def test_the_loop_stops_at_the_step_limit_and_says_so(make_config, tmp_path: Path) -> None:
    tools, driver = kit(make_config, tmp_path)
    forever = [Reply("", (ToolCall(str(n), "browser_snapshot", {}),)) for n in range(10)]
    with pytest.raises(Unfinished, match=r"^Stopped after 3 tool calls without finishing the task\.$"):
        await run_agent("Read", tools, Recording(forever), Agent(provider="scripted", max_steps=3))
    assert len(driver.calls) == 3


async def test_several_calls_in_one_reply_run_in_order_and_count_towards_the_limit(
    make_config, tmp_path: Path
) -> None:
    tools, driver = kit(make_config, tmp_path)
    three = tuple(ToolCall(str(n), "browser_click", {"ref": "e1"}) for n in range(3))
    with pytest.raises(Unfinished, match=r"^Stopped after 2 tool calls"):
        await run_agent(
            "Click", tools, Recording([Reply("", three)]), Agent(provider="scripted", max_steps=2)
        )
    assert len(driver.calls) == 2


async def test_the_loop_ends_when_the_session_has_been_ended(make_config, tmp_path: Path) -> None:
    tools, driver = kit(make_config, tmp_path)
    ended = False

    def end(page: str) -> Reply:
        nonlocal ended
        ended = True
        return Reply("", (ToolCall("b", "browser_click", {"ref": "e1"}),))

    model = ScriptedModel([calls("browser_snapshot"), end, says("never reached")])
    with pytest.raises(Unfinished, match=r"^The session was ended before the task was finished\.$"):
        await run_agent("Read", tools, model, SETTINGS, ended=lambda: ended)
    assert [call[0] for call in driver.calls] == ["snapshot"]


async def test_a_scripted_model_takes_refs_from_the_page_it_was_last_shown(
    make_config, tmp_path: Path
) -> None:
    tools, driver = kit(make_config, tmp_path)
    model = ScriptedModel(
        [
            calls("browser_navigate", url="https://93.184.216.34/"),
            lambda page: Reply("", (ToolCall("c2", "browser_click", {"ref": ref_of(page, 'button "Go"')}),)),
            # A result with no page in it does not replace the page the model last saw.
            lambda page: Reply("Clicked." if 'button "Go"' in page else "The page was lost.", ()),
        ]
    )
    assert await run_agent("Click Go", tools, model, SETTINGS) == "Clicked."
    assert driver.calls[-1] == ("click", {"ref": "e1", "button": "left", "count": 1, "modifiers": []})


async def test_a_script_that_runs_out_says_so_instead_of_failing(make_config, tmp_path: Path) -> None:
    tools, _ = kit(make_config, tmp_path)
    answer = await run_agent("Read", tools, ScriptedModel([calls("browser_snapshot")]), SETTINGS)
    assert answer == "The script has no more steps."


def test_a_ref_is_found_by_what_the_element_is_called() -> None:
    page = 'Page: Sign up\n- textbox "Full name" [ref=e3] [required]\n  - button "Create account" [ref=e12]'
    assert ref_of(page, 'textbox "Full name"') == "e3"
    assert ref_of(page, 'button "Create account"') == "e12"


async def test_a_session_that_has_ended_is_noticed_before_the_model_is_asked_again(
    make_config, tmp_path: Path
) -> None:
    tools, _ = kit(make_config, tmp_path)
    asked = 0
    ended = False

    class Counting:
        async def complete(
            self, system: str, messages: Sequence[Message], tools: Sequence[ToolDefinition]
        ) -> Reply:
            nonlocal asked, ended
            asked += 1
            ended = True
            return Reply("", (ToolCall("a", "browser_snapshot", {}),))

    with pytest.raises(Unfinished):
        await run_agent("Read", tools, Counting(), SETTINGS, ended=lambda: ended)
    with pytest.raises(Unfinished):
        await run_agent("Read", tools, Counting(), SETTINGS, ended=lambda: True)
    # The second run was over before it began: a model that is paid for by the call is not called.
    assert asked == 1
