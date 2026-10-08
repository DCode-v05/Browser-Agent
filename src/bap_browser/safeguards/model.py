"""The model client (spec 18.8): one call to the provider over plain HTTPS.

A call has a time limit. A failed call is tried again after a wait that grows and is uneven. After
several failed calls in a row no call is made for a while. The cost of every call is counted. The
reference loop, the reviewer and the scan each have a client of their own, so one that fails does
not stop the others.
"""

from __future__ import annotations

import asyncio
import json
import random
import time
import urllib.error
import urllib.request
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Literal

from bap_browser.config import Agent
from bap_browser.config_safeguards import CheckModel
from bap_browser.errors import ModelError

Use = Literal["loop", "reviewer", "scan"]

# What the provider answers when the account, not the moment, is the trouble. Waiting does not mend it.
NOT_A_MATTER_OF_WAITING = ("insufficient_quota", "billing")
NOT_THE_JSON = "The model's answer was not the JSON asked for."


class Spend:
    """What the engine's own model calls have cost in one session, in US dollars."""

    def __init__(self) -> None:
        self.usd = 0.0

    def add(self, sent: int, written: int, input_price: float, output_price: float) -> None:
        self.usd += (sent * input_price + written * output_price) / 1_000_000


@dataclass(frozen=True)
class _Failed(Exception):
    """One try that failed: what to say, whether another try could mend it, and the wait asked for."""

    said: str
    again: bool
    wait_s: float | None = None


class ModelClient:
    def __init__(
        self,
        agent: Agent,
        checks: CheckModel,
        key: str,
        use: Use,
        *,
        spend: Spend | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        clock: Callable[[], float] = time.monotonic,
        chance: Callable[[], float] = random.random,
    ) -> None:
        self._agent = agent
        self._checks = checks
        self._key = key
        self._use: Use = use
        self._spend = spend
        self._sleep = sleep
        self._clock = clock
        self._chance = chance
        self._failed_in_a_row = 0
        self._rests_until: float | None = None

    def use(self, agent: Agent) -> None:
        """Takes the settings as they are now: a person may have chosen another model (spec 10.2)."""
        self._agent = agent

    @property
    def model(self) -> str:
        return self._agent.model if self._use == "loop" else self._checks.name or self._agent.model

    @property
    def resting(self) -> bool:
        """True while the breaker is open: calls failed in a row, and none is made for now."""
        return self._rests_until is not None and self._clock() < self._rests_until

    async def post(self, body: dict[str, Any]) -> dict[str, Any]:
        """The provider's answer to one request. Raises ModelError when there is none to be had."""
        checks = self._checks
        if self.resting:
            raise ModelError(
                f"The model cannot be reached: the last {self._failed_in_a_row} calls failed. "
                f"No call is made for {checks.breaker_cooldown_s} seconds."
            )
        retries = self._agent.retries if self._use == "loop" else checks.retries
        tried = 0
        while True:
            try:
                answer = await self._try(body)
            except _Failed as failed:
                wait = failed.wait_s
                if wait is not None and wait > checks.retry_after_max_s:
                    self._count_a_failure()
                    raise ModelError(
                        f"The model provider asked for a wait of {wait:g} seconds, which is too long."
                    ) from None
                if not failed.again or tried == retries:
                    self._count_a_failure()
                    raise ModelError(failed.said) from None
                await self._sleep(self._backoff(tried) if wait is None else wait)
                tried += 1
                continue
            self._failed_in_a_row, self._rests_until = 0, None
            self._count_the_cost(answer)
            return answer

    async def ask(
        self, instructions: str, given: str, *, name: str, schema: dict[str, Any]
    ) -> dict[str, Any]:
        """One question of the reviewer or the scan, answered as JSON of the shape `schema`."""
        checks = self._checks
        body: dict[str, Any] = {
            "model": self.model,
            "instructions": instructions,
            "input": given,
            "max_output_tokens": checks.max_tokens,
            "store": False,
        }
        if checks.reasoning_effort:
            body["reasoning"] = {"effort": checks.reasoning_effort}
        body["text"] = {"format": {"type": "json_schema", "name": name, "schema": schema, "strict": True}}
        try:
            answer = json.loads(output_text(await self.post(body)))
        except ValueError:
            raise ModelError(NOT_THE_JSON) from None
        if not isinstance(answer, dict):
            raise ModelError(NOT_THE_JSON)
        return answer

    def _backoff(self, tried: int) -> float:
        """The wait before another try, in seconds: it doubles, and up to half of itself is added by chance."""
        checks = self._checks
        wait = min(checks.backoff_max_ms, checks.backoff_base_ms * 2**tried)
        return min(checks.backoff_max_ms, wait + self._chance() * wait / 2) / 1000

    def _count_a_failure(self) -> None:
        self._failed_in_a_row += 1
        if self._failed_in_a_row >= self._checks.breaker_failures:
            self._rests_until = self._clock() + self._checks.breaker_cooldown_s

    def _count_the_cost(self, answer: dict[str, Any]) -> None:
        tokens = tokens_of(answer)
        if self._spend is None or tokens is None:
            return
        agent, checks = self._agent, self._checks
        own = self._use != "loop"
        input_price = checks.input_price_per_million if own else None
        output_price = checks.output_price_per_million if own else None
        self._spend.add(
            *tokens,
            agent.input_price_per_million if input_price is None else input_price,
            agent.output_price_per_million if output_price is None else output_price,
        )

    async def _try(self, body: dict[str, Any]) -> dict[str, Any]:
        limit = self._agent.request_timeout_s if self._use == "loop" else self._checks.timeout_s
        try:
            # The limit on the connection holds for each wait on it; this one holds for the whole answer.
            return await asyncio.wait_for(asyncio.to_thread(self._send, body, limit), limit)
        except TimeoutError:
            raise _Failed(f"The model provider did not answer within {limit} seconds.", True) from None

    def _send(self, body: dict[str, Any], limit: float) -> dict[str, Any]:
        request = urllib.request.Request(
            f"{self._agent.base_url.rstrip('/')}/responses",
            data=json.dumps(body).encode(),
            headers={"Authorization": f"Bearer {self._key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=limit) as reply:
                answer = json.loads(reply.read())
        except urllib.error.HTTPError as refused:
            # The refusal holds the connection it came on until it is closed.
            with refused:
                raise self._refusal(refused) from None
        except TimeoutError:
            raise _Failed(f"The model provider did not answer within {limit} seconds.", True) from None
        except (urllib.error.URLError, OSError) as failed:
            reason = getattr(failed, "reason", failed)
            if isinstance(reason, TimeoutError):
                raise _Failed(f"The model provider did not answer within {limit} seconds.", True) from None
            raise _Failed(f"The model provider could not be reached: {reason}", True) from None
        except ValueError:
            raise _Failed("The model provider's answer could not be read.", True) from None
        if not isinstance(answer, dict):
            raise _Failed("The model provider's answer could not be read.", True)
        return answer

    def _refusal(self, refused: urllib.error.HTTPError) -> _Failed:
        code = refused.code
        if code == 401:
            # The provider's own message repeats part of the key. It is not passed on.
            return _Failed(
                "The model provider did not accept the key (HTTP 401). "
                f"Check {self._agent.api_key_env} in your .env file.",
                False,
            )
        try:
            error = json.loads(refused.read())["error"]
            said, kind = error["message"], f"{error.get('code')} {error.get('type')}"
        except (ValueError, KeyError, TypeError, AttributeError):
            said, kind = None, ""
        words = f"The model provider answered HTTP {code}"
        words += "." if said is None else f": {str(said)[: self._agent.refusal_chars]}"
        waiting_mends_it = code in (408, 409, 429) or code >= 500
        if code == 429 and any(mark in kind for mark in NOT_A_MATTER_OF_WAITING):
            waiting_mends_it = False
        return _Failed(words, waiting_mends_it, _seconds(refused.headers.get("Retry-After")))


def output_text(answer: dict[str, Any]) -> str:
    """What the model wrote, from an answer of the Responses API. Empty when it wrote nothing."""
    return "".join(
        part.get("text", "")
        for item in answer.get("output") or []
        if isinstance(item, dict) and item.get("type") == "message"
        for part in item.get("content") or []
        if isinstance(part, dict) and part.get("type") == "output_text"
    )


def tokens_of(answer: dict[str, Any]) -> tuple[int, int] | None:
    """The tokens of one answer, sent and written, as the provider counted them. None when it did not say."""
    said = answer.get("usage")
    if not isinstance(said, dict):
        return None
    sent, written = said.get("input_tokens"), said.get("output_tokens")
    if not isinstance(sent, int) or not isinstance(written, int) or isinstance(sent, bool):
        return None
    return sent, written


def _seconds(header: str | None) -> float | None:
    """The wait a `Retry-After` header asks for, when it gives one as a number of seconds."""
    try:
        seconds = float(header or "")
    except ValueError:
        return None
    return seconds if seconds >= 0 else None
