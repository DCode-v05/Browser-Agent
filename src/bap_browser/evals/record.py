"""The record of each task a browser of the window does (spec 12.6): how long it took, where the
time went, how many steps, how many tokens and what they cost, how it ended, and the trace of it.

One line for each task goes to `<evals.dir>/<system>/tasks.jsonl`. The file is for the person
alone to read. What is typed into a page never reaches it: a step is kept by its tool's name, its
time and whether it worked.
"""

from __future__ import annotations

import json
import os
import secrets
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from bap_browser.agent.loop import Tools
from bap_browser.agent.models import Message, Model, ModelError, Reply
from bap_browser.config import Agent, Evals
from bap_browser.results import ToolResult
from bap_browser.tools import ToolDefinition

Outcome = Literal["answered", "failed", "stopped", "step_limit", "ended"]
"""How a task ended: the agent answered; the model could not; a person stopped it; it ran out of
steps; the session was ended under it."""
OUTCOMES: tuple[Outcome, ...] = ("answered", "failed", "stopped", "step_limit", "ended")
TASKS = "tasks.jsonl"
RATINGS = "ratings.json"
CHECKS = "checks.json"
Rating = Literal["good", "bad"]


@dataclass
class Span:
    """One thing a task spent time on: a reply of the model, or a step in the browser."""

    kind: Literal["model", "tool"]
    name: str
    at_ms: float
    """When it began, counted from the start of the task."""
    ms: float
    ok: bool = True
    waited_ms: float = 0.0
    """For a step: how much of its time was a wait for a person."""
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class TaskRecord:
    id: str
    system: str
    backend: str
    model: str
    started: float
    task: str = ""
    """The task in the person's words, cut short. Empty where the log is turned off."""
    answer: str = ""
    outcome: Outcome = "ended"
    duration_ms: float = 0.0
    steps: int = 0
    steps_failed: int = 0
    model_calls: int = 0
    model_ms: float = 0.0
    tool_ms: float = 0.0
    waited_ms: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    tokens_known: bool = False
    """Whether the model said how many tokens it used. A scripted model does not."""
    cost_usd: float | None = None
    spans: list[Span] = field(default_factory=list[Span])


def cost_of(sent: int, written: int, prices: Agent) -> float | None:
    """What a number of tokens cost, in dollars. None where the deployment gave no price."""
    if prices.input_price_per_million <= 0 and prices.output_price_per_million <= 0:
        return None
    dollars = sent * prices.input_price_per_million + written * prices.output_price_per_million
    return round(dollars / 1_000_000, 6)


class Recorder:
    """Keeps the records of one browser of the window."""

    def __init__(self, settings: Evals, system: str, backend: str) -> None:
        self._settings = settings
        self.system = system
        self._backend = backend
        self.folder = Path(settings.dir) / system

    def begin(
        self,
        task: str,
        agent: Agent,
        *,
        keep_words: bool,
        waited_s: Callable[[], float],
        redact: Callable[[str], str] = lambda text: text,
    ) -> Trace:
        """Starts the record of one task. `keep_words` is whether the task's own words may be
        kept; `waited_s` gives how long the session has waited for a person in all."""
        record = TaskRecord(
            id=secrets.token_hex(6),
            system=self.system,
            backend=self._backend,
            model=agent.model,
            started=round(time.time(), 3),
            task=redact(task)[: self._settings.max_task_chars] if keep_words else "",
        )
        return Trace(self, record, agent, keep_words=keep_words, waited_s=waited_s, redact=redact)

    def keep(self, record: TaskRecord) -> None:
        if not self._settings.enabled:
            return
        line = json.dumps(asdict(record), ensure_ascii=False)
        self.folder.mkdir(parents=True, exist_ok=True)
        handle = os.open(self.folder / TASKS, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        with os.fdopen(handle, "a", encoding="utf-8") as file:
            file.write(line + "\n")

    def tasks(self) -> list[dict[str, Any]]:
        """The newest records, oldest first. A line that cannot be read is passed over."""
        try:
            lines = (self.folder / TASKS).read_text(encoding="utf-8").splitlines()
        except OSError:
            return []
        records: list[dict[str, Any]] = []
        for line in lines[-self._settings.max_tasks_read :]:
            try:
                record = json.loads(line)
            except ValueError:
                continue
            if isinstance(record, dict) and isinstance(record.get("id"), str):
                records.append(record)
        return records

    def ratings(self) -> dict[str, Rating]:
        """What a person said of the answers: good or bad, by task."""
        return {
            task: rating for task, rating in _read(self.folder / RATINGS).items() if rating in ("good", "bad")
        }

    def rate(self, task: str, rating: Rating | None) -> bool:
        """Keeps a person's word on one answer. False when there is no such task."""
        if not any(record["id"] == task for record in self.tasks()):
            return False
        ratings: dict[str, Any] = dict(self.ratings())
        if rating is None:
            ratings.pop(task, None)
        else:
            ratings[task] = rating
        _write(self.folder / RATINGS, ratings)
        return True

    def checklist(self) -> dict[str, Any] | None:
        """The checklist as it was last run, or None when it never was."""
        return _read(self.folder / CHECKS) or None

    def keep_checklist(self, result: Mapping[str, Any]) -> None:
        _write(self.folder / CHECKS, result)


class Trace:
    """One task while it runs. The model and the tools it is given are timed through it."""

    def __init__(
        self,
        recorder: Recorder,
        record: TaskRecord,
        agent: Agent,
        *,
        keep_words: bool,
        waited_s: Callable[[], float],
        redact: Callable[[str], str],
    ) -> None:
        self._recorder = recorder
        self.record = record
        self._agent = agent
        self._keep_words = keep_words
        self._waited_s = waited_s
        self._redact = redact
        self._began = time.perf_counter()
        self._done = False

    def _since(self, moment: float) -> float:
        return round((moment - self._began) * 1000, 1)

    def model(self, inner: Model) -> Model:
        return _TimedModel(inner, self)

    def tools(self, inner: Tools) -> Tools:
        return _TimedTools(inner, self)

    def replied(self, began: float, reply: Reply | None) -> None:
        record, ms = self.record, round((time.perf_counter() - began) * 1000, 1)
        span = Span("model", self._agent.model, self._since(began), ms, ok=reply is not None)
        if reply is not None and reply.usage is not None:
            span.input_tokens, span.output_tokens = reply.usage.input_tokens, reply.usage.output_tokens
            record.tokens_known = True
            record.input_tokens += span.input_tokens
            record.output_tokens += span.output_tokens
        record.model_calls += 1
        record.model_ms = round(record.model_ms + ms, 1)
        record.spans.append(span)

    def stepped(self, began: float, waited_before: float, name: str, result: ToolResult) -> None:
        record, ms = self.record, round((time.perf_counter() - began) * 1000, 1)
        # A step that waited for a person is not slow: the wait is taken out of its time.
        waited = min(round((self._waited_s() - waited_before) * 1000, 1), ms)
        record.spans.append(
            Span("tool", name, self._since(began), ms, ok=not result.is_error, waited_ms=max(waited, 0.0))
        )
        record.steps += 1
        record.steps_failed += result.is_error
        record.waited_ms = round(record.waited_ms + max(waited, 0.0), 1)
        record.tool_ms = round(record.tool_ms + ms - max(waited, 0.0), 1)

    def finish(self, outcome: Outcome, answer: str = "") -> TaskRecord:
        """Closes the record and keeps it. Asked twice, it is kept once."""
        record = self.record
        if self._done:
            return record
        self._done = True
        record.outcome = outcome
        record.duration_ms = round((time.perf_counter() - self._began) * 1000, 1)
        if self._keep_words:
            record.answer = self._redact(answer)[: self._recorder._settings.max_task_chars]  # pyright: ignore[reportPrivateUsage]
        if record.tokens_known:
            record.cost_usd = cost_of(record.input_tokens, record.output_tokens, self._agent)
        self._recorder.keep(record)
        return record


class _TimedModel:
    def __init__(self, inner: Model, trace: Trace) -> None:
        self._inner = inner
        self._trace = trace

    async def complete(
        self, system: str, messages: Sequence[Message], tools: Sequence[ToolDefinition]
    ) -> Reply:
        began = time.perf_counter()
        try:
            reply = await self._inner.complete(system, messages, tools)
        except ModelError:
            self._trace.replied(began, None)
            raise
        self._trace.replied(began, reply)
        return reply


class _TimedTools:
    def __init__(self, inner: Tools, trace: Trace) -> None:
        self._inner = inner
        self._trace = trace

    def definitions(self) -> list[ToolDefinition]:
        return self._inner.definitions()

    async def call(self, name: str, arguments: Mapping[str, Any] | None = None) -> ToolResult:
        began, waited = time.perf_counter(), self._trace._waited_s()  # pyright: ignore[reportPrivateUsage]
        result = await self._inner.call(name, arguments)
        self._trace.stepped(began, waited, name, result)
        return result


def _read(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _write(path: Path, data: Mapping[str, Any]) -> None:
    """For the person alone to read, and never left half written."""
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + ".partial")
    handle = os.open(partial, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(handle, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False)
    os.replace(partial, path)
