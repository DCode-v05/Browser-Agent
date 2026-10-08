"""The bad patterns of this codebase, found by reading the code, not by running it.

An agent copies what it finds. A workaround that is in the repository today is the way things are
done here tomorrow. Each rule below names one pattern that must not spread. What is already in the
code is counted in `patterns_baseline.json`: that count may go down and may never go up.

    uv run python scripts/patterns.py            # check
    uv run python scripts/patterns.py --lower    # after a clean-up: write the lower counts
    uv run python scripts/patterns.py --list     # every place a rule matches, baseline or not

The rules, why each is one, and where a correction belongs: `docs/bad-patterns.md`.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASELINE = Path(__file__).with_name("patterns_baseline.json")

SRC = "src/bap_browser"
VIEWER = "viewer/src"
# Folders that are built or installed, not written.
NOT_OURS = ("viewer_dist", "node_modules", "__pycache__", "/dist/")
# A file longer than this is hard for a reader with little context to hold, a person or an agent.
LONGEST_PYTHON_FILE = 700
LONGEST_VIEWER_FILE = 500
SAMPLES = "test_patterns.py"
# Long because it is a list, not because it does much: every string a person reads.
LISTS = ("wording.ts",)

RULES = {
    "suppression": "A check is silenced on this line. Fix what the check found.",
    "workaround-comment": "A comment excuses a workaround. Fix the cause; the comment will be copied as precedent.",
    "private-import": "A name that begins with _ is imported from another module. Make it public there, or do not use it.",
    "layer": "A lower layer imports a higher one. See LAYERS in scripts/patterns.py.",
    "tunable-outside-config": "A tunable number outside config.py (Python) or options.ts (viewer).",
    "broad-except": "`except Exception` catches what was never thought of. Catch the errors that are expected. It is right only at a boundary named in BOUNDARIES.",
    "skipped-test": "A test is skipped. A test that does not run proves nothing. One that cannot run somewhere says where, with `skipif`.",
    "fixed-wait-in-test": "A test waits a fixed time of a second or more. Wait for the thing itself.",
    "duplicate-code": "The same function is written in two files. Keep one, and use it from both.",
    "literal-in-viewer": "A string a person reads is written into a component. It belongs in viewer/src/wording.ts.",
    "large-file": "The file is over the size a reader can hold. Split it before adding to it.",
    "tracked-link": "A symbolic link is in the repository. It points at one machine's folders.",
}

SUPPRESSIONS = re.compile(
    r"#\s*(pyright:\s*ignore|type:\s*ignore|noqa\b|ruff:\s*noqa)|eslint-disable|@ts-ignore|@ts-expect-error"
)
EXCUSES = re.compile(
    r"\b(hack|hacky|workaround|work[- ]around|temporary|temporarily|for now|band-?aid|kludge|todo|fixme|xxx)\b",
    re.IGNORECASE,
)
A_COMMENT = {
    ".py": re.compile(r"(?<![\"'])#(.*)$"),
    ".ts": re.compile(r"//(.*)$|/\*(.*)"),
    ".tsx": re.compile(r"//(.*)$|/\*(.*)"),
}
SKIPS = re.compile(r"pytest\.skip\(|mark\.skip\b(?!if)|mark\.xfail|\b(it|test|describe)\.(skip|only|todo)\(")
# A second or more, written as a number. A short sleep in a loop that looks again is not a fixed wait.
FIXED_WAITS = re.compile(r"wait_for_timeout\(|\b(time|asyncio)\.sleep\(\s*[1-9][0-9]*(\.[0-9]+)?\s*\)")
# What a person reads or hears of an element, written as text and not taken from the list of strings.
A_READ_ATTRIBUTE = re.compile(r'\b(aria-label|title|alt|placeholder)="[^"{}]*[A-Za-z]{2}[^"]*"')
TEXT_IN_A_TAG = re.compile(r">\s*[A-Z][A-Za-z]+(?: [A-Za-z']+)*[.:…]?\s*<")
# A function shorter than this is too small to call a copy.
SHORTEST_COPY = 3

# Where anything at all may go wrong and must not go further: `except Exception` is right here, and
# nowhere else. Each is one function, with the reason it is a boundary.
BOUNDARIES = {
    ("src/bap_browser/tools/toolkit.py", "_outcome"): "an agent's call must never take the service down",
    ("src/bap_browser/code/worker.py", "run"): "the script is the agent's own: anything may go wrong in it",
    ("src/bap_browser/doctor.py", "_try"): "it reports why a browser did not launch, whatever the reason",
    (
        "src/bap_browser/driver/playwright_driver.py",
        "_judge_request",
    ): "an address that cannot be judged is not loaded",
}
A_VIEWER_NUMBER = re.compile(r"^(export )?const [A-Z][A-Z0-9_]* = -?[0-9][0-9_.]*;")

# Which part of the engine may use which. A part may import only parts on a lower line. A new
# import upward fails the check: the boundary is held by the import graph, not by a reader's care.
LAYERS = (
    ("errors", "results", "env_file", "address", "private_file"),
    ("config", "keys"),
    ("policy", "config_doc", "desktop_app", "browser_extension"),
    ("driver", "code", "settings"),
    ("tools",),
    ("service",),
    ("evals",),
    ("agent",),
    ("mcp", "bench", "doctor"),
    ("cli",),
    ("__main__",),
)
RANK = {unit: rank for rank, units in enumerate(LAYERS) for unit in units}


@dataclass(frozen=True)
class Found:
    rule: str
    path: str
    line: int
    text: str


def _files(root: Path, folder: str, *endings: str) -> Iterator[Path]:
    for path in sorted((root / folder).rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_file() and path.suffix in endings and not any(part in relative for part in NOT_OURS):
            yield path


def _is_test(path: Path) -> bool:
    return ".test." in path.name or path.name == "test-setup.ts" or path.name.startswith("test_")


def _unit(root: Path, path: Path) -> str:
    parts = path.relative_to(root / SRC).parts
    return parts[0] if len(parts) > 1 else path.stem


def _python(root: Path, path: Path, product: bool) -> Iterator[Found]:
    relative, text = path.relative_to(root).as_posix(), path.read_text(encoding="utf-8")
    lines = text.splitlines()
    for number, line in enumerate(lines, 1):
        if product and SUPPRESSIONS.search(line):
            yield Found("suppression", relative, number, line.strip())
        comment = A_COMMENT[".py"].search(line)
        if comment and EXCUSES.search(comment.group(1)):
            yield Found("workaround-comment", relative, number, line.strip())
        if not product and SKIPS.search(line):
            yield Found("skipped-test", relative, number, line.strip())
        if not product and FIXED_WAITS.search(line):
            yield Found("fixed-wait-in-test", relative, number, line.strip())
    if product and len(lines) > LONGEST_PYTHON_FILE:
        yield Found("large-file", relative, len(lines), f"{len(lines)} lines, over {LONGEST_PYTHON_FILE}")
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return
    if product:
        yield from _broad_excepts(tree, relative, lines)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("bap_browser"):
            for name in node.names:
                if name.name.startswith("_") and not name.name.startswith("__"):
                    yield Found("private-import", relative, node.lineno, f"{node.module}.{name.name}")
            if product:
                yield from _layer(root, path, node)
    if product and path.name != "config.py":
        for node in tree.body:
            if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Constant):
                continue
            value = node.value.value
            if isinstance(value, int | float) and not isinstance(value, bool):
                yield Found("tunable-outside-config", relative, node.lineno, lines[node.lineno - 1].strip())


def _broad_excepts(tree: ast.Module, relative: str, lines: list[str]) -> Iterator[Found]:
    """Every `except Exception` that is not in a function named as a boundary."""
    at_a_boundary: set[int] = set()
    for function in ast.walk(tree):
        if (
            isinstance(function, ast.FunctionDef | ast.AsyncFunctionDef)
            and (relative, function.name) in BOUNDARIES
        ):
            at_a_boundary |= {id(node) for node in ast.walk(function)}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler) or id(node) in at_a_boundary:
            continue
        caught = node.type
        if caught is None or (isinstance(caught, ast.Name) and caught.id in ("Exception", "BaseException")):
            yield Found("broad-except", relative, node.lineno, lines[node.lineno - 1].strip())


def _copies(root: Path) -> Iterator[Found]:
    """Functions of the engine that are the same, statement for statement, in two files."""
    seen: dict[str, list[tuple[str, int, str]]] = defaultdict(list)
    for path in _files(root, SRC, ".py"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            # What a function says of itself is not what it does.
            does = [
                one
                for one in node.body
                if not (isinstance(one, ast.Expr) and isinstance(one.value, ast.Constant))
            ]
            if len(does) >= SHORTEST_COPY:
                written = ast.dump(ast.Module(body=does, type_ignores=[]))
                seen[written].append((path.relative_to(root).as_posix(), node.lineno, node.name))
    for places in seen.values():
        if len({path for path, _, _ in places}) > 1:
            first = places[0]
            for path, line, name in places[1:]:
                yield Found("duplicate-code", path, line, f"{name} is the same as {first[2]} in {first[0]}")


def _layer(root: Path, path: Path, node: ast.ImportFrom) -> Iterator[Found]:
    parts = (node.module or "").split(".")
    here, there = _unit(root, path), parts[1] if len(parts) > 1 else ""
    # The package's own top (its version) is anyone's to read.
    if not there or there == here or here not in RANK or there not in RANK:
        return
    if RANK[there] >= RANK[here]:
        relative = path.relative_to(root).as_posix()
        yield Found("layer", relative, node.lineno, f"{here} imports {there}")


def _viewer(root: Path, path: Path) -> Iterator[Found]:
    relative, lines = path.relative_to(root).as_posix(), path.read_text(encoding="utf-8").splitlines()
    test = _is_test(path)
    for number, line in enumerate(lines, 1):
        if not test and SUPPRESSIONS.search(line):
            yield Found("suppression", relative, number, line.strip())
        comment = A_COMMENT[path.suffix].search(line)
        if comment and EXCUSES.search(comment.group(1) or comment.group(2) or ""):
            yield Found("workaround-comment", relative, number, line.strip())
        if test and SKIPS.search(line):
            yield Found("skipped-test", relative, number, line.strip())
        if not test and path.name != "options.ts" and A_VIEWER_NUMBER.match(line):
            yield Found("tunable-outside-config", relative, number, line.strip())
        if (
            not test
            and path.suffix == ".tsx"
            and (A_READ_ATTRIBUTE.search(line) or TEXT_IN_A_TAG.search(line))
        ):
            yield Found("literal-in-viewer", relative, number, line.strip())
    if not test and path.name not in LISTS and len(lines) > LONGEST_VIEWER_FILE:
        yield Found("large-file", relative, len(lines), f"{len(lines)} lines, over {LONGEST_VIEWER_FILE}")


def _links(root: Path) -> Iterator[Found]:
    listed = subprocess.run(["git", "ls-files", "-s"], cwd=root, capture_output=True, text=True, check=False)
    for line in listed.stdout.splitlines():
        mode, _, rest = line.partition(" ")
        if mode == "120000":
            yield Found("tracked-link", rest.split("\t", 1)[-1], 1, "a symbolic link")


def scan(root: Path = ROOT) -> list[Found]:
    """Every place in the repository that a rule matches."""
    found: list[Found] = []
    for path in _files(root, SRC, ".py"):
        found += _python(root, path, product=True)
    for path in _files(root, "tests", ".py"):
        # The test of these rules holds a sample of each pattern, as text. It is not read for them.
        if path.name != SAMPLES:
            found += _python(root, path, product=False)
    for path in _files(root, VIEWER, ".ts", ".tsx"):
        found += _viewer(root, path)
    found += _copies(root)
    found += _links(root)
    return found


Counts = dict[str, dict[str, int]]


def counted(found: list[Found]) -> Counts:
    counts: Counts = defaultdict(dict)
    for one in found:
        # A file is over the size or it is not: its length is not a count to keep under.
        counts[one.rule][one.path] = 1 if one.rule == "large-file" else counts[one.rule].get(one.path, 0) + 1
    return {rule: dict(sorted(paths.items())) for rule, paths in sorted(counts.items())}


def judge(found: list[Found], allowed: Counts) -> tuple[list[str], list[str]]:
    """What is new, and what the baseline still allows that is no longer there."""
    counts = counted(found)
    new: list[str] = []
    stale: list[str] = []
    for rule in sorted(set(counts) | set(allowed)):
        for path in sorted(set(counts.get(rule, {})) | set(allowed.get(rule, {}))):
            now, before = counts.get(rule, {}).get(path, 0), allowed.get(rule, {}).get(path, 0)
            if now > before:
                where = [
                    f"    {one.path}:{one.line}  {one.text[:110]}"
                    for one in found
                    if (one.rule, one.path) == (rule, path)
                ]
                new.append(
                    f"{rule}: {path} has {now}, the baseline allows {before}. {RULES[rule]}\n"
                    + "\n".join(where)
                )
            elif now < before:
                stale.append(f"{rule}: {path} has {now}, the baseline still allows {before}")
    return new, stale


def read_baseline(path: Path = BASELINE) -> Counts:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--lower", action="store_true", help="write the counts that went down to the baseline"
    )
    parser.add_argument("--list", action="store_true", help="print every place a rule matches")
    asked = parser.parse_args(arguments)
    found = scan()
    if asked.list:
        for one in found:
            print(f"{one.rule}: {one.path}:{one.line}  {one.text[:120]}")
        return 0
    new, stale = judge(found, read_baseline())
    if new:
        print("New bad patterns. Fix them; the baseline is not raised to let them in.\n")
        print("\n\n".join(new))
        return 1
    if stale and asked.lower:
        BASELINE.write_text(json.dumps(counted(found), indent=2) + "\n", encoding="utf-8")
        print(f"The baseline is lowered: {len(stale)} entries.")
        return 0
    if stale:
        print("Something was cleaned up and the baseline still allows it. Lower it:\n")
        print("    uv run python scripts/patterns.py --lower\n")
        print("\n".join(stale))
        return 1
    total = sum(count for paths in counted(found).values() for count in paths.values())
    print(f"No new bad pattern. {total} from before are in the baseline, to be cleaned up.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
