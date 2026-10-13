"""`bap-browser sets`: the task sets of a browser, run with no window (spec 12.7).

A nightly job runs them this way. The browser is the cloud browser of the window, the practice site
is served as the window serves it, and each report is kept where the window reads it.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from bap_browser.agent.command import do_task
from bap_browser.agent.loop import Model
from bap_browser.agent.room_configs import cloud_config
from bap_browser.config import Config
from bap_browser.errors import ConfigError
from bap_browser.evals.suite import SETS, Lab, Mode, Progress, Reports, load_set, run_set, suite_recorder
from bap_browser.service.server import Service
from bap_browser.service.session import ServiceSession

SYSTEM, BACKEND = "cloud", "remote_headless"


def said_of(report: dict[str, Any]) -> str:
    """One run in a line: how many tries passed, how many could not run, and the set's own number."""
    totals = report["totals"]
    ran = totals["trials"] - totals["errors"]
    share = f" ({round(totals['pass_rate'] * 100)}%)" if totals["pass_rate"] is not None else ""
    line = f"{report['set']}: {totals['passed']} of {ran} tries passed{share}."
    if totals["errors"]:
        line += f" {totals['errors']} could not run."
    if totals["attacks"]:
        line += f" {totals['attacks_followed']} of {totals['attacks']} planted instructions followed."
    if totals["ask_recall"] is not None:
        line += (
            f" Asked before {round(totals['ask_recall'] * 100)}% of the risky steps, and without need "
            f"before {round((totals['needless_asks'] or 0) * 100)}% of the harmless ones."
        )
    if totals["input_tokens"]:
        line += f" {totals['input_tokens']:,} tokens in, {totals['output_tokens']:,} out."
    return line


async def run_sets(
    config: Config,
    model_for: Callable[[Service], Model] | None,
    names: Sequence[str],
    *,
    trials: int,
    mode: Mode,
    tell: Callable[[str], None] = lambda line: None,
) -> list[dict[str, Any]]:
    """Runs the named sets, one after the other, in one browser. The report of each."""
    unknown = [name for name in names if name not in SETS]
    if unknown:
        raise ConfigError(f"There is no task set named {unknown[0]}. The sets are: {', '.join(SETS)}.")
    if not 1 <= trials <= config.evals.suite_max_trials:
        raise ConfigError(f"A task is tried between 1 and {config.evals.suite_max_trials} times.")
    given = cloud_config(config)
    session = ServiceSession(given, name=SYSTEM, backend=BACKEND)
    service = Service(given, {session.name: session}, port=0)
    recorder, kept = suite_recorder(config.evals, SYSTEM, BACKEND), Reports(config.evals, SYSTEM)
    reports: list[dict[str, Any]] = []
    await session.start()
    await service.start()
    try:
        for name in names:

            async def do(words: str) -> Any:
                assert model_for is not None
                # Each task is a conversation of its own, with a model client of its own.
                return await do_task(words, session, model_for(service), session.config, [], recorder)

            report = await run_set(
                session,
                Lab(session, service.address),
                name,
                trials=trials,
                mode=mode,
                do=do if mode == "agent" else None,
                settings=config.evals,
                model=config.agent.model,
                progress=Progress(name, mode, trials, len(load_set(name))),
            )
            kept.keep(report)
            reports.append(report)
            tell(said_of(report))
    finally:
        await session.close()
        await service.stop()
    return reports
