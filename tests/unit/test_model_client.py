"""The model client (spec 18.8): a time limit, further tries, a breaker for each use, the cost counted."""

from collections.abc import Callable, Iterator
from typing import Any

import pytest
from model_stand_in import ModelStandIn, Slow, response, said, spent

from bap_browser.config import Agent
from bap_browser.config_safeguards import CheckModel
from bap_browser.errors import ModelError
from bap_browser.safeguards.model import ModelClient, Spend, Use

KEY = "sk-test-not-a-real-key"
BUSY = (500, {"error": {"message": "The server had a problem.", "type": "server_error"}})
SLOW_DOWN = {"error": {"message": "Slow down.", "type": "rate_limit", "code": "slow_down"}}
VERDICT = {
    "type": "object",
    "properties": {"risk": {"type": "string"}},
    "required": ["risk"],
    "additionalProperties": False,
}


@pytest.fixture
def provider() -> Iterator[Callable[..., ModelStandIn]]:
    started: list[ModelStandIn] = []

    def start(*replies: Any) -> ModelStandIn:
        stand_in = ModelStandIn(*replies)
        started.append(stand_in)
        return stand_in

    yield start
    for stand_in in started:
        stand_in.close()


class Waits:
    """Stands in for the clock: a wait is written down and takes no time."""

    def __init__(self) -> None:
        self.taken: list[float] = []
        self.now = 1000.0

    async def sleep(self, seconds: float) -> None:
        self.taken.append(seconds)
        self.now += seconds

    def clock(self) -> float:
        return self.now


def client(
    stand_in: ModelStandIn,
    waits: Waits,
    use: Use = "loop",
    *,
    agent: dict[str, Any] | None = None,
    checks: dict[str, Any] | None = None,
    spend: Spend | None = None,
    chance: float = 0.0,
) -> ModelClient:
    return ModelClient(
        Agent(base_url=stand_in.base_url, **(agent or {})),
        CheckModel(**(checks or {})),
        KEY,
        use,
        spend=spend,
        sleep=waits.sleep,
        clock=waits.clock,
        chance=lambda: chance,
    )


async def test_a_call_that_fails_is_tried_again_after_a_wait(provider) -> None:
    stand_in, waits = provider(BUSY, response(said("Hello."))), Waits()
    answer = await client(stand_in, waits).post({"model": "m"})
    assert answer["output"][0]["content"][0]["text"] == "Hello."
    assert len(stand_in.requests) == 2
    assert waits.taken == [0.5]


async def test_each_wait_is_longer_and_uneven_and_none_passes_the_longest(provider) -> None:
    stand_in, waits = provider(BUSY, BUSY, BUSY, BUSY, response(said("At last."))), Waits()
    patient = client(
        stand_in,
        waits,
        agent={"retries": 4},
        checks={"backoff_base_ms": 1000, "backoff_max_ms": 5000},
        chance=1.0,
    )
    await patient.post({})
    # A second, two, four, eight: each with up to half of itself added, and never more than five.
    assert waits.taken == [1.5, 3.0, 5.0, 5.0]


async def test_after_the_last_try_the_failure_is_the_providers_own_words(provider) -> None:
    stand_in, waits = provider(BUSY, BUSY, BUSY), Waits()
    with pytest.raises(ModelError) as failed:
        await client(stand_in, waits).post({})
    assert str(failed.value) == "The model provider answered HTTP 500: The server had a problem."
    assert len(stand_in.requests) == 3  # agent.retries is 2


async def test_the_reviewer_and_the_scan_try_once_more_only(provider) -> None:
    stand_in, waits = provider(BUSY, BUSY, BUSY), Waits()
    with pytest.raises(ModelError):
        await client(stand_in, waits, "reviewer").post({})
    assert len(stand_in.requests) == 2  # safeguards.model.retries is 1


async def test_the_wait_the_provider_asks_for_is_the_wait(provider) -> None:
    stand_in = provider((429, SLOW_DOWN, {"Retry-After": "7"}), response(said("Now.")))
    waits = Waits()
    await client(stand_in, waits).post({})
    assert waits.taken == [7.0]


async def test_a_wait_longer_than_allowed_is_a_failure(provider) -> None:
    stand_in, waits = (
        provider((429, SLOW_DOWN, {"Retry-After": "31"}), response(said("Never read."))),
        Waits(),
    )
    with pytest.raises(ModelError, match=r"asked for a wait of 31 seconds"):
        await client(stand_in, waits).post({})
    assert len(stand_in.requests) == 1 and waits.taken == []


@pytest.mark.parametrize(
    "refusal",
    [
        (401, {"error": {"message": "Incorrect API key provided.", "type": "auth"}}),
        (403, {"error": {"message": "Not allowed.", "type": "auth"}}),
        (400, {"error": {"message": "Unknown parameter.", "type": "invalid_request_error"}}),
        (404, {"error": {"message": "The model does not exist.", "type": "invalid_request_error"}}),
        (429, {"error": {"message": "You exceeded your quota.", "code": "insufficient_quota"}}),
        (429, {"error": {"message": "Billing limit reached.", "type": "billing_hard_limit_reached"}}),
    ],
    ids=["key", "forbidden", "bad-request", "no-such-model", "quota", "billing"],
)
async def test_what_another_try_cannot_mend_is_not_tried_again(provider, refusal) -> None:
    stand_in, waits = provider(refusal, response(said("Never read."))), Waits()
    with pytest.raises(ModelError):
        await client(stand_in, waits).post({})
    assert len(stand_in.requests) == 1 and waits.taken == []


async def test_a_refused_key_is_said_plainly_and_nothing_of_the_key_is_repeated(provider) -> None:
    stand_in = provider((401, {"error": {"message": f"Incorrect API key provided: {KEY[:8]}***"}}))
    with pytest.raises(ModelError) as failed:
        await client(stand_in, Waits()).post({})
    assert str(failed.value) == (
        "The model provider did not accept the key (HTTP 401). Check OPENAI_API_KEY in your .env file."
    )


async def test_an_answer_slower_than_the_time_limit_is_a_failure(provider) -> None:
    stand_in, waits = provider(Slow(30, response(said("Too late.")))), Waits()
    hurried = client(stand_in, waits, "reviewer", checks={"timeout_s": 1, "retries": 0})
    with pytest.raises(ModelError) as failed:
        await hurried.post({})
    assert str(failed.value) == "The model provider did not answer within 1 seconds."


async def test_an_answer_that_is_not_json_is_a_failure_that_is_tried_again(provider) -> None:
    stand_in, waits = provider(["not", "an", "object"], response(said("Hello."))), Waits()
    await client(stand_in, waits).post({})
    assert len(stand_in.requests) == 2


async def test_after_failed_calls_in_a_row_no_call_is_made_for_a_while(provider) -> None:
    stand_in, waits = provider(BUSY, BUSY, BUSY, response(said("Back."))), Waits()
    guarded = client(stand_in, waits, agent={"retries": 0})
    for _ in range(3):
        with pytest.raises(ModelError, match="HTTP 500"):
            await guarded.post({})
    assert guarded.resting
    with pytest.raises(ModelError) as failed:
        await guarded.post({})
    assert str(failed.value) == (
        "The model cannot be reached: the last 3 calls failed. No call is made for 60 seconds."
    )
    assert len(stand_in.requests) == 3
    waits.now += 60
    assert not guarded.resting
    await guarded.post({})
    assert len(stand_in.requests) == 4


async def test_one_answer_between_failures_starts_the_count_again(provider) -> None:
    stand_in, waits = provider(BUSY, BUSY, response(said("Fine.")), BUSY, BUSY), Waits()
    guarded = client(stand_in, waits, agent={"retries": 0})
    for fails in (True, True, False, True, True):
        if fails:
            with pytest.raises(ModelError):
                await guarded.post({})
        else:
            await guarded.post({})
    assert not guarded.resting


async def test_each_use_has_a_breaker_of_its_own(provider) -> None:
    stand_in, waits = provider(BUSY, BUSY, BUSY, response(said("Reviewed."))), Waits()
    loop = client(stand_in, waits, agent={"retries": 0})
    reviewer = client(stand_in, waits, "reviewer")
    for _ in range(3):
        with pytest.raises(ModelError):
            await loop.post({})
    assert loop.resting and not reviewer.resting
    await reviewer.post({})


async def test_the_cost_of_every_call_is_counted(provider) -> None:
    stand_in = provider(
        response(said("One."), usage=spent(1_000_000, 500_000)),
        response(said("Two."), usage=spent(2_000_000, 0)),
        response(said("No count given.")),
    )
    spend, waits = Spend(), Waits()
    prices = {"input_price_per_million": 2.0, "output_price_per_million": 8.0}
    loop = client(stand_in, waits, agent=prices, spend=spend)
    reviewer = client(stand_in, waits, "reviewer", agent=prices, spend=spend)
    await loop.post({})
    assert spend.usd == pytest.approx(6.0)
    # The checks cost what the agent's model costs, unless they are given a model and prices of their own.
    await reviewer.post({})
    assert spend.usd == pytest.approx(10.0)
    await loop.post({})
    assert spend.usd == pytest.approx(10.0)


async def test_checks_with_a_model_of_their_own_have_prices_of_their_own(provider) -> None:
    stand_in = provider(response(said("One."), usage=spent(1_000_000, 1_000_000)))
    spend = Spend()
    scan = client(
        stand_in,
        Waits(),
        "scan",
        agent={"input_price_per_million": 2.0, "output_price_per_million": 8.0},
        checks={"name": "small-model", "input_price_per_million": 0.5, "output_price_per_million": 1.0},
        spend=spend,
    )
    assert scan.model == "small-model"
    await scan.post({})
    assert spend.usd == pytest.approx(1.5)


async def test_with_no_price_nothing_is_counted(provider) -> None:
    stand_in, spend = provider(response(said("One."), usage=spent(1000, 1000))), Spend()
    await client(stand_in, Waits(), spend=spend).post({})
    assert spend.usd == 0


async def test_a_question_asks_for_json_of_a_shape_with_little_thought(provider) -> None:
    stand_in = provider(response(said('{"risk": "low"}')))
    reviewer = client(stand_in, Waits(), "reviewer")
    answer = await reviewer.ask("Judge this step.", '{"step": 1}', name="verdict", schema=VERDICT)
    assert answer == {"risk": "low"}
    (request,) = stand_in.requests
    assert request["path"] == "/v1/responses"
    assert request["authorization"] == f"Bearer {KEY}"
    assert request["body"] == {
        "model": "gpt-5.6-luna",
        "instructions": "Judge this step.",
        "input": '{"step": 1}',
        "max_output_tokens": 1500,
        "store": False,
        "reasoning": {"effort": "low"},
        "text": {"format": {"type": "json_schema", "name": "verdict", "schema": VERDICT, "strict": True}},
    }


async def test_a_model_without_such_a_setting_is_sent_none(provider) -> None:
    stand_in = provider(response(said('{"risk": "low"}')))
    plain = client(stand_in, Waits(), "scan", checks={"reasoning_effort": "", "max_tokens": 300})
    await plain.ask("Judge.", "{}", name="verdict", schema=VERDICT)
    body = stand_in.requests[0]["body"]
    assert "reasoning" not in body and body["max_output_tokens"] == 300


@pytest.mark.parametrize(
    "reply",
    [
        response(said("I would say low.")),
        response(said('["low"]')),
        response(status="incomplete", incomplete_details={"reason": "max_output_tokens"}),
        response(status="failed", error={"code": "server_error", "message": "A problem."}),
    ],
    ids=["prose", "a-list", "cut-off", "failed"],
)
async def test_an_answer_that_is_not_the_json_asked_for_is_a_failure(provider, reply) -> None:
    stand_in = provider(reply)
    with pytest.raises(ModelError, match=r"^The model's answer was not the JSON asked for\.$"):
        await client(stand_in, Waits(), "reviewer").ask("Judge.", "{}", name="verdict", schema=VERDICT)
