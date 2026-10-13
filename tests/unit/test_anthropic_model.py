"""The hosted model: Anthropic's Messages API, spoken over plain HTTPS (spec 16.5)."""

import socket
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from fakes import SNAPSHOT, FakeDriver
from model_stand_in import ModelStandIn, claude_message, claude_text, claude_thought, claude_tool_use

from bap_browser.agent.anthropic_model import AnthropicModel
from bap_browser.agent.loop import run_agent
from bap_browser.agent.models import Reply, Said, ToolCall, ToolOutput
from bap_browser.config import Agent, Config
from bap_browser.config_safeguards import CheckModel
from bap_browser.driver import BrowserSession
from bap_browser.errors import ModelError
from bap_browser.safeguards.model import ModelClient
from bap_browser.tools import TOOLS, Toolkit

KEY = "sk-ant-test-not-a-real-key"


@pytest.fixture
def provider() -> Iterator[Callable[..., ModelStandIn]]:
    started: list[ModelStandIn] = []

    def start(*replies: object) -> ModelStandIn:
        stand_in = ModelStandIn(*replies)  # type: ignore[arg-type]
        started.append(stand_in)
        return stand_in

    yield start
    for stand_in in started:
        stand_in.close()


def model(stand_in: ModelStandIn, **settings: object) -> AnthropicModel:
    given = {"provider": "anthropic", "api_key_env": "CLAUDE_API_KEY", "model": "claude-opus-5-5", **settings}
    return hosted(Agent(base_url=stand_in.base_url, **given))  # type: ignore[arg-type]


def hosted(settings: Agent) -> AnthropicModel:
    return AnthropicModel(settings, ModelClient(settings, CheckModel(), KEY, "loop"))


async def test_the_request_is_what_the_provider_documents(provider) -> None:
    stand_in = provider(claude_message(claude_text("Hello.")))
    reply = await model(stand_in, max_tokens=900).complete("Be brief.", [Said("user", "Say hello")], TOOLS)
    assert reply == Reply("Hello.")
    (request,) = stand_in.requests
    assert request["path"] == "/v1/messages"
    assert request["api_key"] == KEY
    assert request["anthropic_version"] == "2023-06-01"
    body = request["body"]
    assert body["model"] == "claude-opus-5-5"
    assert body["system"] == "Be brief."
    assert body["messages"] == [{"role": "user", "content": "Say hello"}]
    assert body["max_tokens"] == 900
    assert [tool["name"] for tool in body["tools"]] == [tool.name for tool in TOOLS]
    click = next(tool for tool in body["tools"] if tool["name"] == "browser_click")
    ours = next(tool for tool in TOOLS if tool.name == "browser_click")
    assert "type" not in click
    assert click["description"] == ours.description
    assert click["input_schema"] == ours.input_schema


async def test_text_and_tool_calls_are_read_from_the_reply(provider) -> None:
    stand_in = provider(
        claude_message(
            claude_thought("t_1"),
            claude_text("I will open it."),
            claude_tool_use("call_a", "browser_navigate", {"url": "https://example.com/"}),
            claude_tool_use("call_b", "browser_snapshot", {}),
            stop_reason="tool_use",
        )
    )
    reply = await model(stand_in).complete("", [Said("user", "Open example.com")], TOOLS)
    assert reply == Reply(
        "I will open it.",
        (
            ToolCall("call_a", "browser_navigate", {"url": "https://example.com/"}),
            ToolCall("call_b", "browser_snapshot", {}),
        ),
    )


async def test_the_next_request_carries_the_whole_turn_back_thinking_included(provider) -> None:
    first = [claude_thought("t_1"), claude_tool_use("call_a", "browser_snapshot", {})]
    stand_in = provider(claude_message(*first, stop_reason="tool_use"), claude_message(claude_text("Done.")))
    kept = model(stand_in)
    task = Said("user", "Read the page")
    reply = await kept.complete("", [task], TOOLS)
    done = await kept.complete(
        "",
        [
            task,
            Said("assistant", reply.text, reply.tool_calls),
            ToolOutput(reply.tool_calls[0], "Page: Fake", False),
        ],
        TOOLS,
    )
    assert done == Reply("Done.")
    assert stand_in.requests[1]["body"]["messages"] == [
        {"role": "user", "content": "Read the page"},
        # Exactly as the provider sent them, the thinking block included.
        {"role": "assistant", "content": first},
        {
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": "call_a", "content": [claude_text("Page: Fake")]}
            ],
        },
    ]


async def test_two_tool_results_of_one_turn_go_in_one_message(provider) -> None:
    calls = (
        ToolCall("call_a", "browser_navigate", {}),
        ToolCall("call_b", "browser_snapshot", {}),
    )
    stand_in = provider(claude_message(claude_text("Done.")))
    await model(stand_in).complete(
        "",
        [
            Said("user", "Go"),
            Said("assistant", "Going.", calls),
            ToolOutput(calls[0], "Navigated", False),
            ToolOutput(calls[1], "Page: Fake", False),
        ],
        TOOLS,
    )
    assert stand_in.requests[0]["body"]["messages"][-1] == {
        "role": "user",
        "content": [
            {"type": "tool_result", "tool_use_id": "call_a", "content": [claude_text("Navigated")]},
            {"type": "tool_result", "tool_use_id": "call_b", "content": [claude_text("Page: Fake")]},
        ],
    }


async def test_a_turn_the_model_did_not_send_is_written_out_from_the_conversation(provider) -> None:
    stand_in = provider(claude_message(claude_text("Done.")))
    call = ToolCall("call_x", "browser_click", {"ref": "e1"})
    await model(stand_in).complete(
        "",
        [
            Said("user", "Click"),
            Said("assistant", "Clicking.", (call,)),
            ToolOutput(call, "Clicked e1", False),
        ],
        TOOLS,
    )
    assert stand_in.requests[0]["body"]["messages"] == [
        {"role": "user", "content": "Click"},
        {
            "role": "assistant",
            "content": [claude_text("Clicking."), claude_tool_use("call_x", "browser_click", {"ref": "e1"})],
        },
        {
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": "call_x", "content": [claude_text("Clicked e1")]}
            ],
        },
    ]


async def test_a_refused_key_is_said_plainly_and_nothing_of_the_key_is_repeated(provider) -> None:
    stand_in = provider(
        (401, {"type": "error", "error": {"type": "authentication_error", "message": "invalid x-api-key"}})
    )
    with pytest.raises(ModelError) as failed:
        await model(stand_in).complete("", [Said("user", "Hi")], TOOLS)
    assert str(failed.value) == (
        "The model provider did not accept the key (HTTP 401). Check CLAUDE_API_KEY in your .env file."
    )


async def test_another_refusal_passes_on_what_the_provider_said(provider) -> None:
    stand_in = provider(
        (
            429,
            {"type": "error", "error": {"type": "rate_limit_error", "message": "Rate limit reached."}},
        )
    )
    refused = model(stand_in, retries=0)
    with pytest.raises(ModelError, match=r"HTTP 429: Rate limit reached\."):
        await refused.complete("", [Said("user", "Hi")], TOOLS)


async def test_a_provider_that_cannot_be_reached_is_said_so() -> None:
    with socket.socket() as unused:
        unused.bind(("127.0.0.1", 0))
        port = unused.getsockname()[1]
    unreachable = hosted(
        Agent(base_url=f"http://127.0.0.1:{port}/v1", provider="anthropic", request_timeout_s=5, retries=0)
    )
    with pytest.raises(ModelError, match=r"^The model provider could not be reached: "):
        await unreachable.complete("", [Said("user", "Hi")], TOOLS)


async def test_a_refusal_or_a_reply_cut_off_before_it_said_anything_is_an_error(provider) -> None:
    stand_in = provider(
        claude_message(stop_reason="refusal", stop_details={"type": "refusal", "category": "cyber"}),
        claude_message(claude_thought("t_1"), stop_reason="max_tokens"),
    )
    small = model(stand_in, max_tokens=64)
    with pytest.raises(ModelError, match=r"^The model could not answer: cyber$"):
        await small.complete("", [Said("user", "Hi")], TOOLS)
    with pytest.raises(ModelError, match=r"cut off before it said anything.*agent\.max_tokens \(64\)"):
        await small.complete("", [Said("user", "Hi")], TOOLS)


async def test_the_loop_runs_a_task_with_the_hosted_model(
    provider, make_config: Callable[..., Config], tmp_path: Path
) -> None:
    stand_in = provider(
        claude_message(claude_tool_use("call_a", "browser_snapshot", {}), stop_reason="tool_use"),
        claude_message(claude_text("The page has one button, Go.")),
    )
    driver = FakeDriver()
    tools = Toolkit(BrowserSession(make_config(tmp_path), driver))
    answer = await run_agent("What is on the page?", tools, model(stand_in), Agent(provider="anthropic"))
    assert answer == "The page has one button, Go."
    assert stand_in.requests[1]["body"]["messages"][-1] == {
        "role": "user",
        "content": [
            {
                "type": "tool_result",
                "tool_use_id": "call_a",
                "content": [claude_text(f"{SNAPSHOT}\n[tabs] t1* about:blank")],
            }
        ],
    }
