"""The gate: every check of this repository, in one order, stopping at the first that fails.

There is one way to know that a change is ready, and this is it. CI runs the same checks.

    uv run python scripts/gate.py           # everything
    uv run python scripts/gate.py --quick   # everything but the tests that start a browser

The order is cheapest first, so that a mistake is told in seconds. `docs/agent-pathway.md` says
where the gate stands in the making of a change.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# The words a tool says its result in.
RESULT = re.compile(r"\b(passed|failed|built|errors?|formatted|No new|Tests)\b")
# What a stage printed last, shown when it fails.
LINES_SHOWN = 40


@dataclass(frozen=True)
class Stage:
    name: str
    command: tuple[str, ...]
    needs_a_browser: bool = False


def _npm(folder: str, script: str) -> tuple[str, ...]:
    return ("npm", "--prefix", folder, "run", script)


STAGES = (
    Stage("bad patterns", ("uv", "run", "python", "scripts/patterns.py")),
    Stage("format", ("uv", "run", "ruff", "format", "--check", ".")),
    Stage("lint", ("uv", "run", "ruff", "check", ".")),
    Stage("types", ("uv", "run", "pyright")),
    Stage("viewer types", _npm("viewer", "typecheck")),
    Stage("viewer lint", _npm("viewer", "lint")),
    Stage("viewer tests", _npm("viewer", "test")),
    Stage("viewer build", _npm("viewer", "build")),
    Stage("unit and service tests", ("uv", "run", "pytest", "-q", "tests/unit", "tests/service")),
    Stage("tests in a real browser", ("uv", "run", "pytest", "-q", "tests/e2e", "tests/viewer"), True),
)


def run(stage: Stage) -> tuple[bool, float, str]:
    """Runs one stage. Whether it passed, how long it took, and what it printed."""
    program = shutil.which(stage.command[0])
    if program is None:
        return False, 0.0, f"{stage.command[0]} is not installed"
    began = time.perf_counter()
    done = subprocess.run(
        [program, *stage.command[1:]], cwd=ROOT, capture_output=True, text=True, check=False
    )
    return done.returncode == 0, time.perf_counter() - began, (done.stdout + done.stderr).strip()


def _its_word(said: str) -> str:
    """The line in which a stage says how it went: the last that counts or names a result, or else
    the last it printed."""
    lines = [line.strip() for line in said.splitlines() if line.strip()]
    telling = [line for line in lines if RESULT.search(line)]
    return (telling or lines or [""])[-1]


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--quick", action="store_true", help="leave out the tests that start a browser")
    asked = parser.parse_args(arguments)
    stages = [stage for stage in STAGES if not (asked.quick and stage.needs_a_browser)]
    for number, stage in enumerate(stages, 1):
        print(f"[{number}/{len(stages)}] {stage.name} ...", end=" ", flush=True)
        passed, took, said = run(stage)
        # The last line a stage printed is its own word on how it went: shown, never assumed.
        last = _its_word(said)
        print(f"{'passed' if passed else 'FAILED'} in {took:.0f} s. {last[:100]}")
        if not passed:
            print(f"\n{' '.join(stage.command)}\n")
            print("\n".join(said.splitlines()[-LINES_SHOWN:]))
            print(f"\nThe gate stopped at stage {number} of {len(stages)}: {stage.name}.")
            return 1
    left_out = (
        " The tests in a real browser were left out: run the whole gate before a pull request."
        if asked.quick
        else ""
    )
    print(f"\nThe gate is passed: {len(stages)} stages.{left_out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
