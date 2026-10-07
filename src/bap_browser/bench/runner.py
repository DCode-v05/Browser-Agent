"""Runs the budget's lines and judges them (spec 11.2, 12.3).

A line is judged on the median of `bench.runs` runs after `bench.warmup` warm-up runs. At or below
the target, or within the tolerance above it, is OK. Above that and at or below the fail limit is a
warning. Above the fail limit, or with a 95th percentile of twice the fail limit or more, it fails.
"""

from __future__ import annotations

import functools
import json
import statistics
import threading
import time
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path
from typing import Any, Literal

from bap_browser.bench.scenarios import SCENARIOS, Scenario, ScenarioFailed, Stage
from bap_browser.config import Config
from bap_browser.driver import open_session
from bap_browser.errors import BapError, ConfigError
from bap_browser.tools import Toolkit

State = Literal["OK", "WARN", "FAIL", "NOT RUN", "ERROR"]
STATES: tuple[State, ...] = ("OK", "WARN", "FAIL", "NOT RUN", "ERROR")
# A median this far above the target still counts as OK (spec 11.2, rule 3).
TOLERANCE = 1.05
# The 95th percentile must stay under this many times the fail limit (rule 4).
P95_LIMIT = 2


@dataclass(frozen=True)
class Line:
    id: str
    tool: str
    scenario: str
    target_ms: float
    fail_ms: float


@dataclass(frozen=True)
class Measured:
    line: str
    browser: str
    state: State
    median_ms: float | None = None
    p95_ms: float | None = None
    target_ms: float = 0
    fail_ms: float = 0
    note: str = ""

    @property
    def row(self) -> str:
        """`line id | browser | median | p95 | target | fail | state` (spec 12.3)."""
        time_of = lambda value: "-" if value is None else f"{value:.1f}"  # noqa: E731
        said = f"{self.state} ({self.note})" if self.note else self.state
        return (
            f"{self.line:<22} | {self.browser:<9} | {time_of(self.median_ms):>7} | {time_of(self.p95_ms):>7} | "
            f"{self.target_ms:>6g} | {self.fail_ms:>5g} | {said}"
        )


def load_budget(path: Path) -> list[Line]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return [Line(**{name: row[name] for name in Line.__annotations__}) for row in data["lines"]]
    except (OSError, ValueError, KeyError, TypeError) as failed:
        raise ConfigError(f"the budget file {path} could not be read: {failed}") from None


def judge(line: Line, browser: str, samples_ms: Sequence[float]) -> Measured:
    median = statistics.median(samples_ms)
    ordered = sorted(samples_ms)
    p95 = ordered[min(len(ordered) - 1, round(0.95 * (len(ordered) - 1)))]
    if median > line.fail_ms or p95 >= P95_LIMIT * line.fail_ms:
        state: State = "FAIL"
    elif median > line.target_ms * TOLERANCE:
        state = "WARN"
    else:
        state = "OK"
    return Measured(line.id, browser, state, median, p95, line.target_ms, line.fail_ms)


class QuietPages(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        """The bench's pages write nothing to its output."""


@contextmanager
def pages() -> Iterator[str]:
    """The bench's own small pages, served from this machine for as long as the bench runs."""
    folder = Path(str(files("bap_browser"))) / "bench" / "pages"
    server = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(QuietPages, directory=str(folder)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


async def run(
    config: Config, lines: Sequence[Line], browsers: Sequence[str], only: Sequence[str] = ()
) -> list[Measured]:
    """Every line on every browser. A line is never left out: one that cannot be timed says why."""
    settings = config.bench
    out: list[Measured] = []
    with pages() as site:
        for channel in browsers:
            browser = config.browser.model_copy(update={"channel": channel, "headless": True})
            # The bench measures the tools, not a person's answer: nothing waits for an approval.
            quiet = config.logging.model_copy(update={"event_log": None})
            on_this = config.model_copy(update={"browser": browser, "logging": quiet})
            for line in lines:
                if only and line.id not in only:
                    continue
                scenario = SCENARIOS.get(line.id)
                if scenario is None:
                    out.append(_unmeasured(line, channel, "NOT RUN", "no scenario yet"))
                    continue
                try:
                    samples = await _time(on_this, site, scenario, settings.warmup, settings.runs)
                except (ScenarioFailed, BapError) as failed:
                    out.append(_unmeasured(line, channel, "ERROR", str(failed).splitlines()[0][:80]))
                    continue
                out.append(judge(line, channel, samples))
    return out


def _unmeasured(line: Line, browser: str, state: State, note: str) -> Measured:
    return Measured(line.id, browser, state, target_ms=line.target_ms, fail_ms=line.fail_ms, note=note)


async def _time(config: Config, site: str, scenario: Scenario, warmup: int, runs: int) -> list[float]:
    """One browser for the line, so that no line is slowed or sped up by the one before it."""
    samples: list[float] = []
    # A line is measured by calling one tool far more often than any agent does: the limits of a
    # task are not what is being measured (spec 18.8).
    unhurried = config.limits.model_copy(update={"max_calls": 0, "max_calls_per_minute": 0})
    async with open_session(config.model_copy(update={"limits": unhurried})) as session:
        stage = Stage(Toolkit(session), site, {})
        await scenario.once(stage)
        for index in range(warmup + runs):
            await scenario.before(stage)
            began = time.perf_counter()
            await scenario.timed(stage)
            took = (time.perf_counter() - began) * 1000 / scenario.share
            await scenario.after(stage)
            if index >= warmup:
                samples.append(took)
    return samples


def report(measured: Sequence[Measured]) -> str:
    head = f"{'line':<22} | {'browser':<9} | {'median':>7} | {'p95':>7} | target |  fail | state"
    counts = ", ".join(f"{sum(m.state == state for m in measured)} {state}" for state in STATES)
    return "\n".join([head, *(m.row for m in measured), counts])


def save(measured: Sequence[Measured], folder: Path, now: float | None = None) -> Path:
    """Writes the run where the next one can find it, to be compared as before and after."""
    folder.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(now))
    path = folder / f"{stamp}.json"
    path.write_text(json.dumps({"results": [asdict(m) for m in measured]}, indent=2) + "\n", encoding="utf-8")
    return path


def failed_before(folder: Path) -> set[tuple[str, str]]:
    """The lines that failed in the run before this one. A failure counts once it is seen in two
    runs one after the other (spec 11.2, rule 6)."""
    earlier = sorted(folder.glob("*.json")) if folder.is_dir() else []
    if not earlier:
        return set()
    try:
        results = json.loads(earlier[-1].read_text(encoding="utf-8"))["results"]
        return {(row["line"], row["browser"]) for row in results if row["state"] == "FAIL"}
    except (OSError, ValueError, KeyError, TypeError):
        return set()


def blocking(measured: Sequence[Measured], before: set[tuple[str, str]]) -> list[Measured]:
    """The failures that count: the ones that failed in the run before as well."""
    return [m for m in measured if m.state == "FAIL" and (m.line, m.browser) in before]
