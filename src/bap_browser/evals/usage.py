"""What the model's use came to, for each of the four systems and in all (spec 12.6): tasks, model
calls, tokens and cost. Made from the records of the tasks, and kept in one file beside them."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from bap_browser.config import Agent
from bap_browser.private_file import write_json

USAGE = "usage.json"
TASKS = "tasks.jsonl"
# The four systems, as a person knows them, in the order the window shows them.
SYSTEMS = {
    "cloud": "Remote use (Cloud browser)",
    "chrome": "Browser use (My Chrome)",
    "builtin": "Built-in browser",
    "computer": "Computer use",
}


def records_of(folder: Path) -> list[dict[str, Any]]:
    """Every task a system kept. A line that cannot be read is passed over."""
    try:
        lines = (folder / TASKS).read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    found: list[dict[str, Any]] = []
    for line in lines:
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if isinstance(record, dict):
            found.append(record)
    return found


def cost_now(record: dict[str, Any], prices: Agent | None) -> float | None:
    """A task's cost: as it was kept, or at today's price for its model where it was kept before
    the price was set. None where its model has no price here."""
    kept = record.get("cost_usd")
    if isinstance(kept, int | float):
        return float(kept)
    if prices is None or record.get("model") != prices.model or not record.get("tokens_known"):
        return None
    if prices.input_price_per_million <= 0 and prices.output_price_per_million <= 0:
        return None
    sent, written = int(record.get("input_tokens", 0)), int(record.get("output_tokens", 0))
    return (sent * prices.input_price_per_million + written * prices.output_price_per_million) / 1_000_000


def added(records: list[dict[str, Any]], prices: Agent | None) -> dict[str, Any]:
    tally: dict[str, Any] = {
        "tasks": 0,
        "model_calls": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cost_usd": 0.0,
        "tokens_unknown": 0,
        "cost_unknown": 0,
        "by_model": {},
    }
    for record in records:
        sent, written = int(record.get("input_tokens", 0)), int(record.get("output_tokens", 0))
        cost = cost_now(record, prices)
        tally["tasks"] += 1
        tally["model_calls"] += int(record.get("model_calls", 0))
        tally["input_tokens"] += sent
        tally["output_tokens"] += written
        tally["tokens_unknown"] += 0 if record.get("tokens_known") else 1
        tally["cost_unknown"] += 1 if cost is None else 0
        tally["cost_usd"] += cost or 0.0
        model = str(record.get("model") or "unknown")
        one = tally["by_model"].setdefault(
            model, {"tasks": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}
        )
        one["tasks"] += 1
        one["input_tokens"] += sent
        one["output_tokens"] += written
        one["cost_usd"] = round(one["cost_usd"] + (cost or 0.0), 6)
    tally["cost_usd"] = round(tally["cost_usd"], 6)
    return tally


def usage_of(evals_dir: Path, prices: Agent | None = None) -> dict[str, Any]:
    """The four systems' use, each and in all."""
    systems = {
        system: {"name": name, **added(records_of(evals_dir / system), prices)}
        for system, name in SYSTEMS.items()
    }
    total = added([record for system in SYSTEMS for record in records_of(evals_dir / system)], prices)
    total.pop("by_model")
    return {"systems": systems, "total": total}


def keep_usage(evals_dir: Path, prices: Agent | None = None) -> dict[str, Any]:
    """Writes the four systems' use to the file beside their records, and gives it."""
    used = usage_of(evals_dir, prices)
    write_json(evals_dir / USAGE, used)
    return used
