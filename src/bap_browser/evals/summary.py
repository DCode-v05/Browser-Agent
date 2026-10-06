"""What the records of a browser's tasks add up to (spec 12.6): latency, where the time goes, cost,
the model, and how the tasks ended."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

from bap_browser.config import Evals
from bap_browser.evals.record import OUTCOMES, Recorder

# A record as the window lists it: everything but the trace, which is asked for by itself.
LISTED = (
    "id",
    "started",
    "task",
    "answer",
    "outcome",
    "model",
    "duration_ms",
    "steps",
    "steps_failed",
    "model_calls",
    "model_ms",
    "tool_ms",
    "waited_ms",
    "input_tokens",
    "output_tokens",
    "tokens_known",
    "cost_usd",
)


def percentile(values: Sequence[float], share: float) -> float | None:
    """The value below which `share` of the values lie, by nearest rank. None for no values."""
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, math.ceil(share * len(ordered)) - 1))]


def _times(values: Sequence[float]) -> dict[str, Any]:
    return {
        "count": len(values),
        "p50_ms": percentile(values, 0.5),
        "p95_ms": percentile(values, 0.95),
        "max_ms": max(values) if values else None,
    }


def _number(record: Mapping[str, Any], name: str) -> float:
    value = record.get(name)
    return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else 0.0


def _spans(record: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    spans = record.get("spans")
    return [span for span in spans if isinstance(span, dict)] if isinstance(spans, list) else []


def summarise(recorder: Recorder, settings: Evals, model: str) -> dict[str, Any]:
    """Everything the window shows of one browser's tasks. `model` is the one it uses now."""
    records = recorder.tasks()
    ratings = recorder.ratings()
    outcomes = {name: sum(record.get("outcome") == name for record in records) for name in OUTCOMES}
    answered = outcomes["answered"]

    tool_ms: list[float] = []
    model_ms: list[float] = []
    by_tool: dict[str, dict[str, Any]] = {}
    for record in records:
        for span in _spans(record):
            # What a step waited for a person is not the browser's time.
            ms = max(_number(span, "ms") - _number(span, "waited_ms"), 0.0)
            if span.get("kind") == "model":
                model_ms.append(ms)
                continue
            tool_ms.append(ms)
            tool = by_tool.setdefault(str(span.get("name")), {"times": [], "failed": 0})
            tool["times"].append(ms)
            tool["failed"] += span.get("ok") is False

    spent = {
        name: sum(_number(record, name) for record in records)
        for name in ("model_ms", "tool_ms", "waited_ms")
    }
    in_all = sum(spent.values())
    known = [record for record in records if record.get("tokens_known") is True]
    priced = [record for record in known if isinstance(record.get("cost_usd"), int | float)]
    cost = round(sum(_number(record, "cost_usd") for record in priced), 6) if priced else None
    steps = sum(_number(record, "steps") for record in records)
    rated = [ratings[record["id"]] for record in records if record["id"] in ratings]

    return {
        "system": recorder.system,
        "model": model,
        "models_used": sorted({str(record.get("model")) for record in records if record.get("model")}),
        "tasks": {
            "count": len(records),
            **outcomes,
            # Of the tasks that ran to an end of their own. None before there is one.
            "success_rate": round(answered / len(records), 3) if records else None,
            "steps": int(steps),
            "steps_failed": int(sum(_number(record, "steps_failed") for record in records)),
            "steps_per_task": round(steps / len(records), 1) if records else None,
            "rated_good": rated.count("good"),
            "rated_bad": rated.count("bad"),
        },
        "latency": {
            "tool": _times(tool_ms),
            "model": _times(model_ms),
            "by_tool": [
                {"tool": name, **_times(tool["times"]), "failed": tool["failed"]}
                for name, tool in sorted(by_tool.items(), key=lambda item: -len(item[1]["times"]))
            ],
        },
        "time": {
            "task": _times([_number(record, "duration_ms") for record in records]),
            # Where the time of the tasks went, as shares of the whole.
            "model_share": round(spent["model_ms"] / in_all, 3) if in_all else None,
            "tool_share": round(spent["tool_ms"] / in_all, 3) if in_all else None,
            "waiting_share": round(spent["waited_ms"] / in_all, 3) if in_all else None,
        },
        "cost": {
            "tasks_counted": len(known),
            "input_tokens": int(sum(_number(record, "input_tokens") for record in known)),
            "output_tokens": int(sum(_number(record, "output_tokens") for record in known)),
            # None where the deployment gave no price (`agent.input_price_per_million`).
            "usd": cost,
            "usd_per_task": round(cost / len(priced), 6) if cost is not None and priced else None,
        },
        "recent": [
            {**{name: record.get(name) for name in LISTED}, "rating": ratings.get(record["id"])}
            for record in reversed(records[-settings.recent_tasks :])
        ],
        "checklist": recorder.checklist(),
    }


def trace_of(recorder: Recorder, task: str) -> dict[str, Any] | None:
    """One task with its trace: every reply of the model and every step, in order."""
    for record in reversed(recorder.tasks()):
        if record["id"] == task:
            return {**record, "rating": recorder.ratings().get(task)}
    return None
