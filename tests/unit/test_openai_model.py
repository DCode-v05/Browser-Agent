"""The hosted model: OpenAI's Responses API, spoken over plain HTTPS (spec 16.5)."""

import socket
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from fakes import SNAPSHOT, FakeDriver
from model_stand_in import ModelStandIn, called, response, said, thought

from bap_browser.agent.loop import run_agent
from bap_browser.agent.models import Reply, Said, ToolCall, ToolOutput
from bap_browser.agent.openai_model import OpenAIModel
from bap_browser.config import Agent, CheckModel, Config
from bap_browser.driver import BrowserSession
from bap_browser.errors import ModelError
from bap_browser.safeguards.model import ModelClient
from bap_browser.tools import TOOLS, Toolkit

KEY = "sk-test-not-a-real-key"


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


def model(stand_in: ModelStandIn, **settings: object) -> OpenAIModel:
    return hosted(Agent(base_url=stand_in.base_url, **settings))  # type: ignore[arg-type]


def hosted(settings: Agent) -> OpenAIModel:
    return OpenAIModel(settings, ModelClient(settings, CheckModel(), KEY, "loop"))


async def test_the_request_is_what_the_provider_documents(provider) -> None:
    stand_in = provider(response(said("Hello.")))
    reply = await model(stand_in, max_tokens=900).complete("Be brief.", [Said("user", "Say hello")], TOOLS)
    assert reply == Reply("Hello.")
    (request,) = stand_in.requests
    assert request["path"] == "/v1/responses"
    assert request["authorization"] == f"Bearer {KEY}"
    body = request["body"]
    assert body["model"] == "gpt-5.6-luna"
    assert body["instructions"] == "Be brief."
    assert body["input"] == [{"role": "user", "content": "Say hello"}]
    assert body["max_output_tokens"] == 900
    # Nothing is kept on the provider's side, so what the model thought has to come back sealed.
    assert body["store"] is False
    assert body["include"] == ["reasoning.encrypted_content"]
    assert [tool["name"] for tool in body["tools"]] == [tool.name for tool in TOOLS]
    click = next(tool for tool in body["tools"] if tool["name"] == "browser_click")
    ours = next(tool for tool in TOOLS if tool.name == "browser_click")
    assert click["type"] == "function" and click["strict"] is False
    assert click["description"] == ours.description
    assert click["parameters"] == ours.input_schema


async def test_text_and_tool_calls_are_read_from_the_reply(provider) -> None:
    stand_in = provider(
        response(
            thought("rs_1"),
            said("I will open it."),
            called("call_a", "browser_navigate", '{"url": "https://example.com/"}'),
            called("call_b", "browser_snapshot", "{}"),
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


async def test_the_next_request_carries_the_whole_turn_back_and_each_result(provider) -> None:
    first = [thought("rs_1"), called("call_a", "browser_snapshot", "{}")]
    stand_in = provider(response(*first), response(said("Done.")))
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
    assert stand_in.requests[1]["body"]["input"] == [
        {"role": "user", "content": "Read the page"},
        # Exactly as the provider sent them, the sealed thought included.
        *first,
        {"type": "function_call_output", "call_id": "call_a", "output": "Page: Fake"},
    ]


async def test_a_turn_the_model_did_not_send_is_written_out_from_the_conversation(provider) -> None:
    stand_in = provider(response(said("Done.")))
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
    assert stand_in.requests[0]["body"]["input"] == [
        {"role": "user", "content": "Click"},
        {"role": "assistant", "content": "Clicking."},
        {"type": "function_call", "call_id": "call_x", "name": "browser_click", "arguments": '{"ref": "e1"}'},
        {"type": "function_call_output", "call_id": "call_x", "output": "Clicked e1"},
    ]


@pytest.mark.parametrize("arguments", ["{not json", "[1, 2]", '"text"', ""])
async def test_arguments_that_are_not_an_object_become_none_so_the_tool_can_say_what_is_missing(
    provider, arguments: str
) -> None:
    stand_in = provider(response(called("call_a", "browser_click", arguments)))
    reply = await model(stand_in).complete("", [Said("user", "Click")], TOOLS)
    assert reply.tool_calls == (ToolCall("call_a", "browser_click", {}),)


async def test_a_refused_key_is_said_plainly_and_nothing_of_the_key_is_repeated(provider) -> None:
    stand_in = provider(
        (401, {"error": {"message": f"Incorrect API key provided: {KEY[:8]}***", "type": "auth"}})
    )
    with pytest.raises(ModelError) as failed:
        await model(stand_in).complete("", [Said("user", "Hi")], TOOLS)
    assert str(failed.value) == (
        "The model provider did not accept the key (HTTP 401). Check OPENAI_API_KEY in your .env file."
    )
    assert KEY[:8] not in str(failed.value)


async def test_another_refusal_passes_on_what_the_provider_said(provider) -> None:
    stand_in = provider(
        (429, {"error": {"message": "Rate limit reached for gpt-5.6-luna.", "type": "rate_limit"}}),
        (404, {"error": {"message": "The model `gpt-9` does not exist.", "type": "invalid_request_error"}}),
        (500, {"unexpected": "shape"}),
    )
    # Further tries are the client's affair (test_model_client.py). Here each refusal is the last word.
    refused = model(stand_in, retries=0)
    for expected in (
        "The model provider answered HTTP 429: Rate limit reached for gpt-5.6-luna.",
        "The model provider answered HTTP 404: The model `gpt-9` does not exist.",
        "The model provider answered HTTP 500.",
    ):
        with pytest.raises(ModelError) as failed:
            await refused.complete("", [Said("user", "Hi")], TOOLS)
        assert str(failed.value) == expected


async def test_a_provider_that_cannot_be_reached_is_said_so() -> None:
    with socket.socket() as unused:
        unused.bind(("127.0.0.1", 0))
        port = unused.getsockname()[1]
    unreachable = hosted(Agent(base_url=f"http://127.0.0.1:{port}/v1", request_timeout_s=5, retries=0))
    with pytest.raises(ModelError, match=r"^The model provider could not be reached: "):
        await unreachable.complete("", [Said("user", "Hi")], TOOLS)


async def test_a_reply_that_failed_or_was_cut_off_before_it_said_anything_is_an_error(provider) -> None:
    stand_in = provider(
        response(status="failed", error={"code": "server_error", "message": "The model had a problem."}),
        response(thought("rs_1"), status="incomplete", incomplete_details={"reason": "max_output_tokens"}),
    )
    small = model(stand_in, max_tokens=64)
    with pytest.raises(ModelError, match=r"^The model could not answer: The model had a problem\.$"):
        await small.complete("", [Said("user", "Hi")], TOOLS)
    with pytest.raises(ModelError, match=r"cut off before it said anything.*agent\.max_tokens \(64\)"):
        await small.complete("", [Said("user", "Hi")], TOOLS)


async def test_the_loop_runs_a_task_with_the_hosted_model(
    provider, make_config: Callable[..., Config], tmp_path: Path
) -> None:
    stand_in = provider(
        response(called("call_a", "browser_snapshot", "{}")),
        response(said("The page has one button, Go.")),
    )
    driver = FakeDriver()
    tools = Toolkit(BrowserSession(make_config(tmp_path), driver))
    answer = await run_agent("What is on the page?", tools, model(stand_in), Agent())
    assert answer == "The page has one button, Go."
    # The model was shown the page the tool returned.
    assert stand_in.requests[1]["body"]["input"][-1] == {
        "type": "function_call_output",
        "call_id": "call_a",
        "output": f"{SNAPSHOT}\n[tabs] t1* about:blank",
    }
