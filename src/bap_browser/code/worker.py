"""The worker that runs an agent's script (spec 7). It is started as a file of its own, in a process
of its own, with an empty environment, and talks to the core over its standard input and output,
one JSON object on each line.

It imports nothing but the standard library: it is not part of the core, and holds none of what the
core holds. A script reaches the browser only by asking the core for a step, and the core checks
each step as it checks a single tool call.

The check before a script runs is defence in depth, not a boundary: Python offers none inside a
process. The boundary is the micro VM in which the whole core runs (spec 7.4, 17.2).
"""

from __future__ import annotations

import ast
import asyncio
import builtins
import json
import math
import os
import re
import sys
import traceback
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

SCRIPT = "<script>"
ENTRY = "__script__"

# What a script may call by name (spec 7.2), besides what it defines itself.
BUILTINS: dict[str, Any] = {
    name: getattr(builtins, name)
    for name in (
        "len",
        "range",
        "str",
        "int",
        "float",
        "bool",
        "list",
        "dict",
        "set",
        "tuple",
        "sorted",
        "min",
        "max",
        "sum",
        "abs",
        "round",
        "enumerate",
        "zip",
        "any",
        "all",
        "isinstance",
        "repr",
        # To tell one failure from another in `except`.
        "Exception",
        "ValueError",
        "KeyError",
        "IndexError",
        "TypeError",
    )
}

# The three modules a script has are these functions of them and nothing else: the modules
# themselves hold other modules, and through those the whole machine.
MODULES: dict[str, SimpleNamespace] = {
    "re": SimpleNamespace(
        findall=re.findall,
        finditer=re.finditer,
        search=re.search,
        match=re.match,
        fullmatch=re.fullmatch,
        sub=re.sub,
        split=re.split,
        escape=re.escape,
        compile=re.compile,
        IGNORECASE=re.IGNORECASE,
        MULTILINE=re.MULTILINE,
        DOTALL=re.DOTALL,
        I=re.I,
        M=re.M,
        S=re.S,
    ),
    "json": SimpleNamespace(loads=json.loads, dumps=json.dumps),
    "math": SimpleNamespace(
        **{name: getattr(math, name) for name in dir(math) if not name.startswith("_")},
    ),
}
GIVEN = ("browser", "state", "print", "StepError")

# What no script may hold: imports, classes, and the statements that reach outside a function.
FORBIDDEN: dict[type[ast.AST], str] = {
    ast.Import: "a script cannot import; re, json and math are there already",
    ast.ImportFrom: "a script cannot import; re, json and math are there already",
    ast.ClassDef: "a script cannot define a class",
    ast.Global: "a script cannot use 'global'",
    ast.Nonlocal: "a script cannot use 'nonlocal'",
    ast.With: "a script cannot use 'with'",
    ast.AsyncWith: "a script cannot use 'with'",
    ast.AsyncFor: "a script cannot use 'async for'",
    ast.Match: "a script cannot use 'match'",
    ast.Delete: "a script cannot use 'del'",
}
# Attributes that lead from a value to the frames and the code behind it.
INNER_PREFIXES = ("_", "gi_", "cr_", "ag_", "f_", "tb_", "co_")
# Attributes that read other attributes by a name held in a string, or climb to `object`.
INNER_NAMES = frozenset({"format", "format_map", "mro"})


class Rejected(Exception):
    """A script that is not run, and why, in words for the agent."""


class StepError(Exception):
    """A step in the browser failed. The message is what the tool returned."""


def check(code: str) -> ast.Module:
    """The script, parsed, when it holds nothing a script may not (spec 7.4)."""
    try:
        tree = ast.parse(code, SCRIPT, "exec")
    except SyntaxError as wrong:
        raise Rejected(f"line {wrong.lineno}: {wrong.msg}") from None
    bound = set(BUILTINS) | set(MODULES) | set(GIVEN)
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            bound.add(node.id)
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            bound.add(node.name)
        elif isinstance(node, ast.arg):
            bound.add(node.arg)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            bound.add(node.name)
    for node in ast.walk(tree):
        line = f"line {getattr(node, 'lineno', '?')}: "
        for kind, why in FORBIDDEN.items():
            if isinstance(node, kind):
                raise Rejected(line + why)
        for name in _names_in(node):
            if name.startswith("_"):
                raise Rejected(
                    f"{line}the name '{name}' begins with an underscore, which a script cannot use"
                )
        if isinstance(node, ast.Attribute) and (
            node.attr.startswith(INNER_PREFIXES) or node.attr in INNER_NAMES
        ):
            raise Rejected(f"{line}a script cannot use the attribute '{node.attr}'")
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.decorator_list:
            raise Rejected(line + "a script cannot use a decorator")
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id not in bound:
            raise Rejected(f"{line}the name '{node.id}' is not available in a script")
    return tree


def _names_in(node: ast.AST) -> list[str]:
    """The names a node gives to something: a variable, a function, an argument."""
    if isinstance(node, ast.Name):
        return [node.id]
    if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
        return [node.name]
    if isinstance(node, ast.arg):
        return [node.arg]
    if isinstance(node, ast.keyword):
        return [node.arg] if node.arg else []
    if isinstance(node, ast.ExceptHandler):
        return [node.name] if node.name else []
    return []


def as_a_function(tree: ast.Module) -> ast.Module:
    """The script as the body of one async function, so that it can await a step. The value of its
    last expression is what the function returns."""
    body = list(tree.body)
    if body and isinstance(body[-1], ast.Expr):
        body[-1] = ast.copy_location(ast.Return(body[-1].value), body[-1])
    arguments = ast.arguments(posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[])
    entry = ast.AsyncFunctionDef(
        name=ENTRY, args=arguments, body=body or [ast.Pass()], decorator_list=[], type_params=[]
    )
    return ast.fix_missing_locations(ast.Module(body=[entry], type_ignores=[]))


class Printed:
    """What a script printed, kept up to a limit."""

    def __init__(self, limit: int) -> None:
        self._limit = limit
        self._parts: list[str] = []
        self._chars = 0
        self.cut = False

    def __call__(self, *values: Any, sep: str = " ", end: str = "\n") -> None:
        text = str(sep).join(str(value) for value in values) + str(end)
        room = self._limit - self._chars
        if len(text) > room:
            text, self.cut = text[: max(room, 0)], True
        self._parts.append(text)
        self._chars += len(text)

    def text(self) -> str:
        return "".join(self._parts)


def browser_for(methods: dict[str, list[str]], ask: Callable[[dict[str, Any]], dict[str, Any]]) -> Any:
    """The `browser` a script sees: one async method for each tool, which asks the core for the step."""

    def method(name: str, parameters: list[str]) -> Any:
        async def step(self: Any, *given: Any, **named: Any) -> str:
            if len(given) > len(parameters):
                raise TypeError(f"browser.{name} takes at most {len(parameters)} values without a name")
            arguments = dict(zip(parameters, given, strict=False))
            for key, value in named.items():
                if key in arguments:
                    raise TypeError(f"browser.{name} was given '{key}' twice")
                arguments[key] = value
            try:
                json.dumps(arguments)
            except (TypeError, ValueError):
                raise TypeError(f"browser.{name} takes text, numbers, lists and dictionaries") from None
            answer = ask({"call": name, "args": arguments})
            if answer.get("failed"):
                raise StepError(str(answer.get("text", "")))
            return str(answer.get("text", ""))

        step.__name__ = step.__qualname__ = name
        return step

    return type(
        "Browser", (), {"__slots__": (), **{name: method(name, list(p)) for name, p in methods.items()}}
    )()


def _line_of(error: BaseException) -> int | None:
    """The line of the script where an error came from."""
    lines = [frame.lineno for frame in traceback.extract_tb(error.__traceback__) if frame.filename == SCRIPT]
    return lines[-1] if lines else None


def run(
    job: dict[str, Any], state: dict[str, Any], ask: Callable[[dict[str, Any]], dict[str, Any]]
) -> dict[str, Any]:
    """Runs one script to its end. What comes back is what the core tells the agent."""
    limit = int(job.get("max_output_chars", 0))
    printed = Printed(limit)
    try:
        tree = as_a_function(check(str(job.get("code", ""))))
    except Rejected as no:
        return {"rejected": str(no)}
    names: dict[str, Any] = {
        "__builtins__": dict(BUILTINS),
        **MODULES,
        "browser": browser_for(job.get("methods", {}), ask),
        "state": state,
        "print": printed,
        "StepError": StepError,
    }
    done: dict[str, Any] = {}
    try:
        exec(compile(tree, SCRIPT, "exec"), names)
        value = asyncio.run(names[ENTRY]())
        if value is not None:
            # No more of it is sent than the agent will be shown.
            whole = json.dumps(value, default=repr, ensure_ascii=False)
            done["value"], done["value_cut"] = whole[:limit], len(whole) > limit
    except StepError as failed:
        done["step_failed"], done["line"] = str(failed), _line_of(failed)
    except RecursionError:
        done["error"] = "RecursionError: the script calls itself too deeply"
    except MemoryError:
        done["error"] = "MemoryError: the script used too much memory"
    except Exception as wrong:
        done["error"], done["line"] = f"{type(wrong).__name__}: {wrong}", _line_of(wrong)
    done["printed"], done["printed_cut"] = printed.text(), printed.cut
    return done


def limit_memory(megabytes: int) -> None:
    """A limit on what the worker may hold, where the system enforces one."""
    try:
        import resource

        limit = megabytes * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
    except (ImportError, ValueError, OSError):
        pass


def main() -> None:
    lines, out = sys.stdin.buffer, sys.stdout.buffer
    # Nothing a script prints, and nothing Python prints by itself, reaches the core's channel.
    sys.stdout = sys.stderr = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115

    def tell(message: dict[str, Any]) -> None:
        out.write(json.dumps(message, ensure_ascii=False).encode() + b"\n")
        out.flush()

    def ask(message: dict[str, Any]) -> dict[str, Any]:
        tell(message)
        line = lines.readline()
        if not line:
            # The core went away: there is nobody left to run for.
            raise SystemExit(0)
        return json.loads(line)

    state: dict[str, Any] = {}
    limited = False
    while line := lines.readline():
        job = json.loads(line)
        if not limited:
            limit_memory(int(job.get("max_memory_mb", 0)) or 512)
            limited = True
        tell({"done": run(job, state, ask)})


if __name__ == "__main__":
    main()
