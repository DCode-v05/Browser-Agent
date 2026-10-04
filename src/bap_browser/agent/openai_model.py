"""A hosted model: OpenAI's Responses API, spoken over plain HTTPS so that no client library is needed.

Nothing is kept on the provider's side (`store: false`). The conversation is sent again on every
turn, with each of the model's own turns exactly as the provider returned it, sealed reasoning
included, as the provider's guide for stateless use asks.
"""

from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request
from collections.abc import Sequence
from typing import Any

from bap_browser.agent.models import Message, ModelError, Reply, ToolCall, ToolOutput
from bap_browser.config import Agent
from bap_browser.tools import ToolDefinition

# The provider's own explanation of a refusal is passed on, but not at any length.
LONGEST_REFUSAL = 300


class OpenAIModel:
    def __init__(self, settings: Agent, api_key: str) -> None:
        self._settings = settings
        self._key = api_key
        self._turns: list[list[dict[str, Any]]] = []
        """What the provider returned for each of the model's turns, in order."""

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
        answer = await asyncio.to_thread(self._post, body)
        output = [item for item in answer.get("output") or [] if isinstance(item, dict)]
        if answer.get("status") == "failed":
            reason = (answer.get("error") or {}).get("message") or "no reason was given"
            raise ModelError(f"The model could not answer: {str(reason)[:LONGEST_REFUSAL]}")
        text = "".join(
            part.get("text", "")
            for item in output
            if item.get("type") == "message"
            for part in item.get("content") or []
            if isinstance(part, dict) and part.get("type") == "output_text"
        )
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
        return Reply(text, calls)

    def _input(self, messages: Sequence[Message]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        turn = 0
        for message in messages:
            if isinstance(message, ToolOutput):
                items.append(
                    {"type": "function_call_output", "call_id": message.call.id, "output": message.text}
                )
            elif message.role == "user":
                items.append({"role": "user", "content": message.text})
            else:
                if turn < len(self._turns):
                    items += self._turns[turn]
                else:
                    items += _written_out(message.text, message.tool_calls)
                turn += 1
        return items

    def _post(self, body: dict[str, Any]) -> dict[str, Any]:
        settings = self._settings
        request = urllib.request.Request(
            f"{settings.base_url.rstrip('/')}/responses",
            data=json.dumps(body).encode(),
            headers={"Authorization": f"Bearer {self._key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=settings.request_timeout_s) as reply:
                answer = json.loads(reply.read())
        except urllib.error.HTTPError as refused:
            # The refusal holds the connection it came on until it is closed.
            with refused:
                raise ModelError(self._refusal(refused)) from None
        except (urllib.error.URLError, TimeoutError, OSError) as failed:
            reason = getattr(failed, "reason", failed)
            raise ModelError(f"The model provider could not be reached: {reason}") from None
        except ValueError:
            raise ModelError("The model provider's answer could not be read.") from None
        if not isinstance(answer, dict):
            raise ModelError("The model provider's answer could not be read.")
        return answer

    def _refusal(self, refused: urllib.error.HTTPError) -> str:
        if refused.code == 401:
            # The provider's own message repeats part of the key. It is not passed on.
            return (
                "The model provider did not accept the key (HTTP 401). "
                f"Check {self._settings.api_key_env} in your .env file."
            )
        try:
            said = json.loads(refused.read())["error"]["message"]
        except (ValueError, KeyError, TypeError):
            return f"The model provider answered HTTP {refused.code}."
        return f"The model provider answered HTTP {refused.code}: {str(said)[:LONGEST_REFUSAL]}"


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
