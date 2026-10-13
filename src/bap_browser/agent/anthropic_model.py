"""A hosted model: Anthropic's Messages API, spoken over plain HTTPS so that no client library is needed.

Every content block of the model's own turn, a thinking block included, is sent back exactly as the
provider returned it: Claude's own turn is bound to the conversation that produced it.
"""

from __future__ import annotations

import base64
from collections.abc import Sequence
from typing import Any

from bap_browser.agent.models import HostedModel, Message, Reply, ToolCall, ToolOutput, Usage
from bap_browser.errors import ModelError
from bap_browser.safeguards.model import tokens_of
from bap_browser.tools import ToolDefinition


class AnthropicModel(HostedModel):
    async def complete(
        self, system: str, messages: Sequence[Message], tools: Sequence[ToolDefinition]
    ) -> Reply:
        settings = self._settings
        body = {
            "model": settings.model,
            "system": system,
            "messages": self._messages(messages),
            "tools": [
                {"name": tool.name, "description": tool.description, "input_schema": tool.input_schema}
                for tool in tools
            ],
            "max_tokens": settings.max_tokens,
        }
        answer = await self._client.post(body)
        if answer.get("stop_reason") == "refusal":
            details = answer.get("stop_details") or {}
            reason = details.get("explanation") or details.get("category") or "no reason was given"
            raise ModelError(f"The model could not answer: {str(reason)[: settings.refusal_chars]}")
        content = [item for item in answer.get("content") or [] if isinstance(item, dict)]
        text = "".join(item.get("text", "") for item in content if item.get("type") == "text")
        calls = tuple(
            ToolCall(str(item.get("id")), str(item.get("name")), _arguments(item.get("input")))
            for item in content
            if item.get("type") == "tool_use"
        )
        if not text and not calls:
            raise ModelError(
                "The model's reply was cut off before it said anything. "
                f"Raise agent.max_tokens ({settings.max_tokens}) in config.json."
            )
        self._turns.append(content)
        tokens = tokens_of(answer)
        return Reply(text, calls, None if tokens is None else Usage(*tokens))

    def _messages(self, messages: Sequence[Message]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        turn = 0
        # Only the newest picture goes with the conversation: an older one has been seen, and
        # would be paid for again each time.
        newest = next(
            (m for m in reversed(messages) if isinstance(m, ToolOutput) and m.picture is not None), None
        )
        for message in messages:
            if isinstance(message, ToolOutput):
                block = _tool_result(message, with_its_picture=message is newest)
                if items and _holds_tool_results(items[-1]):
                    items[-1]["content"].append(block)
                else:
                    items.append({"role": "user", "content": [block]})
            elif message.role == "user":
                items.append({"role": "user", "content": message.text})
            else:
                if turn < len(self._turns):
                    items.append({"role": "assistant", "content": self._turns[turn]})
                else:
                    items.append(
                        {"role": "assistant", "content": _written_out(message.text, message.tool_calls)}
                    )
                turn += 1
        return items


def _arguments(value: Any) -> dict[str, Any]:
    """What the model wants to pass to a tool. Anything that is not an object becomes no arguments,
    and the tool then says which one is missing."""
    return value if isinstance(value, dict) else {}


def _tool_result(message: ToolOutput, *, with_its_picture: bool) -> dict[str, Any]:
    content: list[dict[str, Any]] = [{"type": "text", "text": message.text}]
    if with_its_picture and message.picture is not None:
        data = base64.b64encode(message.picture.data).decode("ascii")
        content.append(
            {"type": "image", "source": {"type": "base64", "media_type": message.picture.mime, "data": data}}
        )
    block = {"type": "tool_result", "tool_use_id": message.call.id, "content": content}
    if message.is_error:
        block["is_error"] = True
    return block


def _holds_tool_results(item: dict[str, Any]) -> bool:
    """Whether an item is a user turn of tool results alone: another of this turn's joins it,
    since the provider wants every result of one turn in a single message."""
    content = item.get("content")
    return (
        item.get("role") == "user"
        and isinstance(content, list)
        and bool(content)
        and all(isinstance(part, dict) and part.get("type") == "tool_result" for part in content)
    )


def _written_out(text: str, calls: Sequence[ToolCall]) -> list[dict[str, Any]]:
    """A turn of the model's that this object did not receive itself, in the provider's form."""
    items: list[dict[str, Any]] = [{"type": "text", "text": text}] if text else []
    items += [
        {"type": "tool_use", "id": call.id, "name": call.name, "input": call.arguments} for call in calls
    ]
    return items
