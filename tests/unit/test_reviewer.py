"""The reviewer (spec 18.4): what a model's rating of a step leads to, decided in code."""

import json
from pathlib import Path

import pytest

from bap_browser.errors import ModelError
from bap_browser.safeguards.reviewer import (
    HELD_HIGH,
    INSTRUCTIONS,
    VERDICT_SCHEMA,
    Shown,
    Verdict,
    question,
    read_verdict,
    risk_held,
    ruling,
    why_refused,
)

SPEC = Path(__file__).parents[2] / "docs" / "bap-browser-spec.md"

# The table of 18.4, row by row: the risk, then what each answer to "asked for" leads to.
TABLE = {
    "low": {"exactly": "run", "in_substance": "run", "loosely": "run", "no": "run"},
    "medium": {"exactly": "run", "in_substance": "run", "loosely": "ask", "no": "ask"},
    "high": {"exactly": "ask", "in_substance": "ask", "loosely": "refuse", "no": "refuse"},
    "critical": {"exactly": "refuse", "in_substance": "refuse", "loosely": "refuse", "no": "refuse"},
}


def verdict(risk: str = "low", asked_for: str = "exactly", category: str = "none") -> Verdict:
    return read_verdict(
        {"risk": risk, "asked_for": asked_for, "category": category, "reason": "Because."}, 120
    )


@pytest.mark.parametrize("risk", TABLE)
@pytest.mark.parametrize("asked_for", ["exactly", "in_substance", "loosely", "no"])
def test_the_table_turns_a_rating_into_what_happens(risk: str, asked_for: str) -> None:
    assert ruling(verdict(risk, asked_for), held_high=False, page_flagged=False) == TABLE[risk][asked_for]


def test_on_a_flagged_page_a_step_nobody_asked_for_is_treated_one_step_harder() -> None:
    assert ruling(verdict("low", "no"), held_high=False, page_flagged=True) == "ask"
    assert ruling(verdict("medium", "no"), held_high=False, page_flagged=True) == "refuse"
    # What was asked for is not made harder by the page it is on.
    assert ruling(verdict("low", "loosely"), held_high=False, page_flagged=True) == "run"
    assert ruling(verdict("medium", "exactly"), held_high=False, page_flagged=True) == "run"


@pytest.mark.parametrize("risk", ["low", "medium"])
@pytest.mark.parametrize("asked_for", ["exactly", "in_substance", "loosely", "no"])
def test_a_step_of_a_kind_no_model_may_let_run_is_never_run_whatever_the_model_says(
    risk: str, asked_for: str
) -> None:
    expected = "ask" if asked_for in ("exactly", "in_substance") else "refuse"
    # The fixed rules found that the step pays, sends, deletes, grants or carries text across sites.
    assert ruling(verdict(risk, asked_for), held_high=True, page_flagged=False) == expected
    # Or the model itself named such a category, and gave it a low risk.
    for category in HELD_HIGH:
        assert ruling(verdict(risk, asked_for, category), held_high=False, page_flagged=False) == expected


def test_the_floor_only_ever_raises_a_risk() -> None:
    assert risk_held(verdict("low", category="pays"), held_high=False) == "high"
    assert risk_held(verdict("medium"), held_high=True) == "high"
    assert risk_held(verdict("critical", category="pays"), held_high=True) == "critical"
    assert risk_held(verdict("low", category="leaves_task"), held_high=False) == "low"


@pytest.mark.parametrize(
    "answer",
    [
        {},
        {"risk": "low", "asked_for": "exactly", "category": "none"},
        {"risk": "tiny", "asked_for": "exactly", "category": "none", "reason": "x"},
        {"risk": "low", "asked_for": "yes", "category": "none", "reason": "x"},
        {"risk": "low", "asked_for": "exactly", "category": "harmless", "reason": "x"},
        {"risk": "low", "asked_for": "exactly", "category": "none", "reason": 7},
        {"risk": ["low"], "asked_for": "exactly", "category": "none", "reason": "x"},
    ],
)
def test_an_answer_that_is_not_of_the_shape_asked_for_counts_as_no_answer(answer: dict) -> None:
    with pytest.raises(ModelError):
        read_verdict(answer, 120)


def test_the_models_sentence_is_made_one_line_and_cut() -> None:
    read = read_verdict(
        {"risk": "low", "asked_for": "no", "category": "none", "reason": "One\n  two. " + "x" * 300}, 120
    )
    assert read.reason.startswith("One two. x") and len(read.reason) == 120


def test_why_a_step_was_refused_is_said_in_the_engines_own_words() -> None:
    assert why_refused(verdict("high", "no", "sends")) == (
        "this step would send something to other people, and the task did not ask for it"
    )
    assert why_refused(verdict("critical", "exactly", "shares_data")) == (
        "this step would carry what was read on one site to another, "
        "and that is too grave to be done on a check's word"
    )
    assert why_refused(verdict("critical", "no", "other")) == (
        "the check judged this step too risky for what the task asked for"
    )


def test_the_instructions_are_the_specs_word_for_word() -> None:
    spec = SPEC.read_text(encoding="utf-8")
    assert INSTRUCTIONS in spec.replace("\r\n", "\n")


def test_the_shape_asked_for_can_be_fixed_by_the_provider() -> None:
    assert VERDICT_SCHEMA["additionalProperties"] is False
    assert sorted(VERDICT_SCHEMA["required"]) == sorted(VERDICT_SCHEMA["properties"])


def test_everything_a_page_or_the_agent_wrote_is_between_the_calls_own_marks() -> None:
    given = json.loads(
        question(
            token="q3x9vd",
            task="Check in for flight SK4821.",
            task_from="person",
            earlier=["Open the airline's site."],
            named=["skylark-air.example"],
            added=["maps.example"],
            own_browser=False,
            steps_so_far=[("browser_navigate", "skylark-air.example", "Opened skylark-air.example/checkin")],
            step=Shown(
                "browser_type",
                "skylark-air.example",
                None,
                "textbox",
                "Booking reference",
                "ABC123",
                None,
            ),
            findings=[
                {"id": "cross_site_text", "detail": "text read on mail.example", "sample": "ABC123"},
                {"id": "consequential_word", "detail": "pressing this control confirms something"},
            ],
            page_flagged=False,
        )
    )
    assert given == {
        "mark": "q3x9vd",
        "task": "Check in for flight SK4821.",
        "task_from": "person",
        "earlier_messages": ["Open the airline's site."],
        "sites": {"named": ["skylark-air.example"], "added": ["maps.example"]},
        "own_browser": False,
        "steps_so_far": [
            {
                "tool": "browser_navigate",
                "site": "skylark-air.example",
                "what": "<<data q3x9vd>>Opened skylark-air.example/checkin<<end q3x9vd>>",
            }
        ],
        "step": {
            "tool": "browser_type",
            "site": "skylark-air.example",
            "does": None,
            "control": {"role": "textbox", "name": "<<data q3x9vd>>Booking reference<<end q3x9vd>>"},
            "typed": {"chars": 6, "text": "<<data q3x9vd>>ABC123<<end q3x9vd>>"},
            "address": None,
        },
        "findings": [
            {
                "id": "cross_site_text",
                "detail": "text read on mail.example",
                "sample": "<<data q3x9vd>>ABC123<<end q3x9vd>>",
            },
            {"id": "consequential_word", "detail": "pressing this control confirms something"},
        ],
        "page_flagged": False,
    }


def test_a_step_with_no_control_and_a_navigation_are_shown_as_they_are() -> None:
    given = json.loads(
        question(
            token="aaaaaa",
            task="Read the news",
            task_from="agent",
            earlier=[],
            named=[],
            added=["news.example"],
            own_browser=True,
            steps_so_far=[],
            step=Shown("browser_navigate", "other.example", address="https://other.example/a?b=c"),
            findings=[{"id": "site_outside_task", "detail": "the site is not one of the task's"}],
            page_flagged=True,
        )
    )
    assert given["step"] == {
        "tool": "browser_navigate",
        "site": "other.example",
        "does": None,
        "control": None,
        "typed": None,
        "address": "<<data aaaaaa>>https://other.example/a?b=c<<end aaaaaa>>",
    }
    assert given["task_from"] == "agent" and given["own_browser"] is True and given["page_flagged"] is True
