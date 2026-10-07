"""A hosted model: OpenAI's Responses API, spoken over plain HTTPS so that no client library is needed.

Nothing is kept on the provider's side (`store: false`). The conversation is sent again on every
turn, with each of the model's own turns exactly as the provider returned it, sealed reasoning
included, as the provider's guide for stateless use asks.
"""

from __future__ import annotations

import base64
import json
from collections.abc import Sequence
from typing import Any

from bap_browser.agent.models import Message, Reply, ToolCall, ToolOutput, Usage
from bap_browser.config import Agent
from bap_browser.errors import ModelError
from bap_browser.safeguards.model import LONGEST_REFUSAL, ModelClient, output_text, tokens_of
from bap_browser.tools import ToolDefinition


class OpenAIModel:
    def __init__(self, settings: Agent, client: ModelClient) -> None:
        self._settings = settings
        self._client = client
        """How a request reaches the provider: its time limit, its further tries, its breaker (spec 18.8)."""
        self._turns: list[list[dict[str, Any]]] = []
        """What the provider returned for each of the model's turns, in order."""

    def use(self, settings: Agent) -> None:
        """Takes the settings as they are now: a person may have chosen another model (spec 10.2)."""
        self._settings = settings
        self._client.use(settings)

    async def complete(
        self, system: str, messages: Sequence[Message], tools: Sequence[ToolDefinition]
    ) -> Reply:
        settings = self._settings
        body = {
            "model": settings.model,
            "instructions": system,
            "input": self._input(messages),
            "tools": [
                {
                    "type": "function",
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.input_schema,
                    # Strict mode wants every argument required; these tools have optional ones.
                    "strict": False,
                }
                for tool in tools
            ],
            "max_output_tokens": settings.max_tokens,
            "store": False,
            "include": ["reasoning.encrypted_content"],
        }
        answer = await self._client.post(body)
        output = [item for item in answer.get("output") or [] if isinstance(item, dict)]
        if answer.get("status") == "failed":
            reason = (answer.get("error") or {}).get("message") or "no reason was given"
            raise ModelError(f"The model could not answer: {str(reason)[:LONGEST_REFUSAL]}")
        text = output_text(answer)
        calls = tuple(
            ToolCall(str(item.get("call_id")), str(item.get("name")), _arguments(item.get("arguments")))
            for item in output
            if item.get("type") == "function_call"
        )
        if not text and not calls:
            raise ModelError(
                "The model's reply was cut off before it said anything. "
                f"Raise agent.max_tokens ({settings.max_tokens}) in config.json."
            )
        self._turns.append(output)
        tokens = tokens_of(answer)
        return Reply(text, calls, None if tokens is None else Usage(*tokens))

    def _input(self, messages: Sequence[Message]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        turn = 0
        # The conversation is sent again on every turn. Only the newest picture goes with it: an
        # older one has been seen, and would be paid for again each time.
        newest = next(
            (m for m in reversed(messages) if isinstance(m, ToolOutput) and m.picture is not None), None
        )
        for message in messages:
            if isinstance(message, ToolOutput):
                output: str | list[dict[str, str]] = message.text
                if message is newest and message.picture is not None:
                    data = base64.b64encode(message.picture.data).decode("ascii")
                    output = [
                        {"type": "input_text", "text": message.text},
                        {"type": "input_image", "image_url": f"data:{message.picture.mime};base64,{data}"},
                    ]
                items.append({"type": "function_call_output", "call_id": message.call.id, "output": output})
            elif message.role == "user":
                items.append({"role": "user", "content": message.text})
            else:
                if turn < len(self._turns):
                    items += self._turns[turn]
                else:
                    items += _written_out(message.text, message.tool_calls)
                turn += 1
        return items


def _arguments(text: Any) -> dict[str, Any]:
    """What the model wants to pass to a tool. Anything that is not an object becomes no arguments,
    and the tool then says which one is missing."""
    try:
        arguments = json.loads(text)
    except (ValueError, TypeError):
        return {}
    return arguments if isinstance(arguments, dict) else {}


def _written_out(text: str, calls: Sequence[ToolCall]) -> list[dict[str, Any]]:
    """A turn of the model's that this object did not receive itself, in the provider's form."""
    items: list[dict[str, Any]] = [{"role": "assistant", "content": text}] if text else []
    items += [
        {
            "type": "function_call",
            "call_id": call.id,
            "name": call.name,
            "arguments": json.dumps(call.arguments),
        }
        for call in calls
    ]
    return items
