"""The checklist of one browser of the window (spec 12.6): a short run of real steps on the demo
site that says, line by line, whether this browser does what the agent needs of it.

Each step is a tool call like any other: it passes the same checks, is written to the log, and is a
row of the timeline a person watches. Nothing is typed that is not made up.
"""

from __future__ import annotations

import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

from bap_browser.config import Evals
from bap_browser.results import ToolResult
from bap_browser.service.session import ServiceSession

State = Literal["ok", "failed", "skipped"]
# The cloud metadata address, which the address policy refuses whatever a deployment allows (spec 8.1).
METADATA = "http://169.254.169.254/latest/meta-data/"
A_REF = re.compile(r"\[ref=((?:f\d+)?e\d+)\]")
A_FIELD = re.compile(r'^- textbox "[^"]*".*?\[ref=((?:f\d+)?e\d+)\]', re.MULTILINE)
MADE_UP_NAME = "Ada Lovelace"


@dataclass
class Check:
    id: str
    title: str
    state: State
    detail: str = ""
    ms: float | None = None


class _Run:
    def __init__(self, session: ServiceSession) -> None:
        self._session = session
        self.checks: list[Check] = []
        self.step_ms: list[float] = []

    async def call(self, name: str, arguments: dict[str, Any]) -> tuple[ToolResult, float]:
        began = time.perf_counter()
        result = await self._session.toolkit.call(name, arguments)
        ms = round((time.perf_counter() - began) * 1000, 1)
        self.step_ms.append(ms)
        return result, ms

    def add(self, check: str, title: str, ok: bool, detail: str = "", ms: float | None = None) -> bool:
        self.checks.append(Check(check, title, "ok" if ok else "failed", "" if ok else detail, ms))
        return ok

    def skip(self, check: str, title: str, why: str) -> None:
        self.checks.append(Check(check, title, "skipped", why))


def _first_line(result: ToolResult) -> str:
    return result.text.split("\n", 1)[0][:200]


async def run_checklist(session: ServiceSession, site: str, settings: Evals) -> dict[str, Any]:
    """Runs the checklist on a session that is the agent's and is doing nothing. `site` is the
    address of the service's own demo site."""
    run = _Run(session)
    log = Path(session.config.logging.event_log) if session.config.logging.event_log else None
    log_before = log.stat().st_size if log is not None and log.is_file() else 0
    before = next((tab.url for tab in await session.toolkit.tabs() if tab.active), "")
    began = time.time()

    tabs, ms = await run.call("browser_tabs", {"action": "list"})
    run.add("answers", "The browser answers", not tabs.is_error, _first_line(tabs), ms)

    opened, ms = await run.call("browser_navigate", {"url": f"{site}/demo-site/start.html"})
    on_site = run.add("opens", "Opens a page", not opened.is_error, _first_line(opened), ms)

    if on_site:
        await _on_the_site(run, site)
    else:
        for check, title in LATER_ON_THE_SITE:
            run.skip(check, title, "the demo site did not open")

    refused, ms = await run.call("browser_navigate", {"url": METADATA})
    run.add(
        "refuses",
        "Refuses the cloud metadata address",
        refused.is_error and "blocked" in refused.text.lower(),
        "it was not refused: " + _first_line(refused),
        ms,
    )

    slowest = max(run.step_ms)
    run.add(
        "fast",
        f"Every step within {settings.step_budget_ms} ms",
        slowest <= settings.step_budget_ms,
        f"the slowest step took {slowest:.0f} ms",
        slowest,
    )
    if log is None:
        run.skip("logged", "Writes its log", "the log is turned off for this browser")
    else:
        grew = log.is_file() and log.stat().st_size > log_before
        run.add("logged", "Writes its log", grew, f"nothing was added to {log}")
    if session.hub.viewers > 0:
        run.add(
            "person", "A person can be asked", session.browser.ask_person is not None, "nobody can be asked"
        )
    else:
        run.skip("person", "A person can be asked", "no one is watching this browser")

    # The browser goes back to where it was, for whatever the agent does next.
    if before and before != METADATA:
        await session.toolkit.call("browser_navigate", {"url": before})
    passed = sum(check.state == "ok" for check in run.checks)
    failed = sum(check.state == "failed" for check in run.checks)
    return {
        "ran": round(began, 3),
        "duration_ms": round((time.time() - began) * 1000, 1),
        "passed": passed,
        "failed": failed,
        "skipped": len(run.checks) - passed - failed,
        "checks": [asdict(check) for check in run.checks],
    }


LATER_ON_THE_SITE = (
    ("reads", "Reads the page"),
    ("finds", "Finds an element by its words"),
    ("acts", "Clicks, and the page follows"),
    ("types", "Types into a field"),
    ("picture", "Takes a picture"),
)


async def _on_the_site(run: _Run, site: str) -> None:
    read, ms = await run.call("browser_snapshot", {"mode": "all"})
    run.add("reads", "Reads the page", not read.is_error and "Northfield" in read.text, _first_line(read), ms)

    found, ms = await run.call("browser_find", {"query": "create an account"})
    link = None if found.is_error else A_REF.search(found.text)
    run.add("finds", "Finds an element by its words", link is not None, _first_line(found), ms)

    followed = False
    if link is None:
        run.skip("acts", "Clicks, and the page follows", "the link was not found")
    else:
        clicked, ms = await run.call("browser_click", {"ref": link.group(1)})
        followed = not clicked.is_error and "signup" in clicked.text
        run.add("acts", "Clicks, and the page follows", followed, _first_line(clicked), ms)
    if followed:
        await _types(run)
    else:
        run.skip("types", "Types into a field", "the page with the form did not open")

    picture, ms = await run.call("browser_screenshot", {})
    run.add("picture", "Takes a picture", picture.picture is not None, _first_line(picture), ms)


async def _types(run: _Run) -> None:
    form, _ = await run.call("browser_snapshot", {})
    field = None if form.is_error else A_FIELD.search(form.text)
    if field is None:
        run.add("types", "Types into a field", False, "the form has no field to type into")
        return
    typed, ms = await run.call("browser_type", {"ref": field.group(1), "text": MADE_UP_NAME})
    run.add("types", "Types into a field", not typed.is_error, _first_line(typed), ms)
