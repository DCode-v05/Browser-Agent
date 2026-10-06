"""The core's side of the code tool (spec 7): it starts the worker, hands it a script, and does each
step the script asks for as a tool call of its own, with the same checks as any other.

The worker is a process apart, with an empty environment. It holds nothing of the core's, and is
ended and started again when a script computes for longer than it may.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import re
import sys
import tempfile
import time
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from bap_browser.config import Code
from bap_browser.results import ToolResult

WORKER = Path(__file__).with_name("worker.py")
# The methods of `browser` in a script (spec 7.2): these tools, where the deployment offers them.
IN_A_SCRIPT = (
    "navigate",
    "go_back",
    "go_forward",
    "reload",
    "snapshot",
    "get_text",
    "find",
    "screenshot",
    "click",
    "hover",
    "drag",
    "type",
    "fill_form",
    "select_option",
    "set_checked",
    "press_key",
    "scroll",
    "scroll_to",
    "wait",
    "handle_dialog",
    "tabs",
    "console",
    "network",
    "downloads",
    "evaluate",
    "upload_file",
)
# These take `find="…"` in place of a ref: the best match for the words is looked up first.
FIND_FIRST = frozenset({"click", "type"})
# A line of what `browser_find` answers: the kind of element, its name, and its ref when it has one.
FOUND = re.compile(r'^- (\w+)(?: "((?:[^"\\]|\\.)*)")?.*?\[ref=((?:f\d+)?e\d+)\]', re.MULTILINE)
# What can be typed into. `browser.type(find=…)` takes the best match among these.
TAKES_TEXT = frozenset({"textbox", "searchbox", "combobox", "spinbutton"})
NOT_UNDONE = "Earlier steps were carried out and are not undone."
# What the worker needs from the environment to start at all. Nothing else is handed to it.
KEPT_IN_THE_ENVIRONMENT = ("SYSTEMROOT",)
# How long one line of a step may be when it is listed in the result.
STEP_LINE_CHARS = 120
# What a script printed and its value come back in one message, each character written as up to six.
ROOM_FOR_A_RESULT = 12

Step = Callable[[str, dict[str, Any]], Awaitable[ToolResult]]


@dataclass(frozen=True)
class Ran:
    """What a script came to: the text for the agent, and why it failed, in a few words, when it did."""

    text: str
    failure: str | None = None
    steps: int = 0


class _WorkerLost(Exception):
    """The worker ended, or sent what the core does not take."""


class ScriptRunner:
    def __init__(
        self, settings: Callable[[], Code], step: Step, methods: Callable[[], Mapping[str, list[str]]]
    ) -> None:
        """`settings` gives the limits as they are now. `step` runs one tool call. `methods` gives
        the tools a script may use now, each with the names of its arguments in order."""
        self._settings = settings
        self._step = step
        self._methods = methods
        self._worker: asyncio.subprocess.Process | None = None
        # One script at a time: the worker runs one, and `state` is one.
        self._turn = asyncio.Lock()
        # The worker was ended, so what earlier scripts kept in `state` is gone.
        self._state_lost = False

    async def run(self, code: str, timeout_s: int | None) -> Ran:
        settings = self._settings()
        if len(code) > settings.max_code_chars:
            return Ran(
                f"The script was not run: it is longer than {settings.max_code_chars} characters.",
                "the script is too long",
            )
        budget = float(min(timeout_s or settings.timeout_s, settings.max_timeout_s))
        async with self._turn:
            try:
                return await self._run(code, budget, settings)
            except asyncio.CancelledError:
                # Whoever asked has gone. The script must not go on by itself.
                await self._end_worker()
                raise

    async def _run(self, code: str, budget: float, settings: Code) -> Ran:
        methods = {name: list(names) for name, names in self._methods().items()}
        steps: list[tuple[bool, str]] = []
        state_lost, self._state_lost = self._state_lost, False
        try:
            worker = await self._started(settings)
            await self._tell(
                worker,
                {
                    "code": code,
                    "methods": methods,
                    "max_output_chars": settings.max_output_chars,
                    "max_memory_mb": settings.max_memory_mb,
                },
            )
            left = budget
            while True:
                waited_since = time.monotonic()
                try:
                    # Only the script's own computing counts. A step in the browser has its own limits.
                    async with asyncio.timeout(left):
                        message = await self._hear(worker)
                except TimeoutError:
                    await self._end_worker()
                    return self._report(
                        {"error": f"it computed for longer than {budget:g} s and was stopped"},
                        steps,
                        state_lost,
                    )
                left = max(left - (time.monotonic() - waited_since), 0.0)
                if isinstance(message.get("done"), dict):
                    return self._report(message["done"], steps, state_lost)
                await self._tell(worker, await self._do(message, methods, steps, settings))
        except _WorkerLost as lost:
            await self._end_worker()
            return self._report({"error": str(lost)}, steps, state_lost)

    async def _do(
        self,
        asked: Mapping[str, Any],
        methods: Mapping[str, list[str]],
        steps: list[tuple[bool, str]],
        settings: Code,
    ) -> dict[str, Any]:
        """One step a script asked for, done as a tool call. What comes back goes to the script."""
        name, arguments = asked.get("call"), asked.get("args")
        if not isinstance(name, str) or name not in methods or not isinstance(arguments, dict):
            raise _WorkerLost("the worker asked for something that is not a step")
        arguments = {str(key): value for key, value in arguments.items()}
        if len(steps) >= settings.max_steps:
            return {
                "failed": True,
                "text": f"This script has done {settings.max_steps} steps, the most one script may. "
                "Do the rest in another call.",
            }
        if name in FIND_FIRST and "find" in arguments:
            words = arguments.pop("find")
            if arguments.get("ref") is not None or not isinstance(words, str) or not words.strip():
                return {"failed": True, "text": f'browser.{name} takes find="…" or ref=…, one of the two.'}
            found = await self._call("find", {"query": words}, steps)
            ref = None if found.is_error else _best(found.text, words, typing=name == "type")
            if ref is None:
                nothing = f'Nothing on the page matches "{words}".'
                # The step the script asked for was not done, and is listed as that.
                steps.append((False, nothing))
                return {"failed": True, "text": nothing}
            arguments["ref"] = ref
            if len(steps) >= settings.max_steps:
                return {"failed": True, "text": f"This script has done {settings.max_steps} steps."}
        result = await self._call(name, arguments, steps)
        return {"failed": result.is_error, "text": result.text}

    async def _call(self, name: str, arguments: dict[str, Any], steps: list[tuple[bool, str]]) -> ToolResult:
        result = await self._step(f"browser_{name}", arguments)
        first_line = result.text.split("\n", 1)[0]
        steps.append((not result.is_error, first_line[:STEP_LINE_CHARS]))
        return result

    def _report(self, done: Mapping[str, Any], steps: list[tuple[bool, str]], state_lost: bool) -> Ran:
        """The result of a script (spec 7.3), in the order an agent reads it."""
        if isinstance(done.get("rejected"), str):
            return Ran(f"The script was not run: {done['rejected']}.", "the script was not run")
        count = "no steps" if not steps else "1 step" if len(steps) == 1 else f"{len(steps)} steps"
        where = f" at line {done['line']}" if isinstance(done.get("line"), int) else ""
        undone = f" {NOT_UNDONE}" if steps else ""
        failure: str | None = None
        # What came of it comes first, in one line. What the script printed can hold anything a page says.
        if isinstance(done.get("step_failed"), str):
            failure = "a step failed"
            said = done["step_failed"].split("\n", 1)[0].rstrip()
            if not said.endswith((".", "!", "?")):
                said += "."
            failed = max((n for n, (ok, _) in enumerate(steps, 1) if not ok), default=None)
            which = f"Step {failed} failed" if failed else "A step failed"
            parts = [f"{which}{where} of the script: {said}{undone}"]
        elif isinstance(done.get("error"), str):
            failure = "the script stopped"
            parts = [f"The script stopped{where}: {done['error']}.{undone}"]
        else:
            parts = [f"Ran the script: {count}."]
        printed = str(done.get("printed") or "")
        if printed:
            cut = "\n[cut: the script printed more than is returned]" if done.get("printed_cut") else ""
            parts.append(f"Printed:\n{printed.rstrip()}{cut}")
        if isinstance(done.get("value"), str):
            parts.append(f"Value: {done['value']}" + (" [cut]" if done.get("value_cut") else ""))
        if steps:
            listed = [f"{n}. {'ok' if ok else 'FAILED'}: {line}" for n, (ok, line) in enumerate(steps, 1)]
            parts.append(f"Steps ({len(steps)}):\n" + "\n".join(listed))
        if state_lost:
            parts.append("The worker was started again since the last script, so `state` was empty.")
        return Ran("\n".join(parts), failure, len(steps))

    async def _started(self, settings: Code) -> asyncio.subprocess.Process:
        """The worker, started on the first use and used again after that."""
        if self._worker is not None and self._worker.returncode is None:
            return self._worker
        try:
            self._worker = await asyncio.create_subprocess_exec(
                sys.executable,
                # Isolated, and without the site packages: the worker is the standard library alone.
                "-I",
                "-S",
                str(WORKER),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
                # No secret reaches it, and no token: it is handed almost nothing.
                env={name: os.environ[name] for name in KEPT_IN_THE_ENVIRONMENT if name in os.environ},
                cwd=tempfile.gettempdir(),
                limit=settings.max_message_chars + ROOM_FOR_A_RESULT * settings.max_output_chars,
            )
        except OSError as failed:
            raise _WorkerLost(f"the worker could not be started ({failed})") from failed
        return self._worker

    async def _tell(self, worker: asyncio.subprocess.Process, message: Mapping[str, Any]) -> None:
        assert worker.stdin is not None
        try:
            worker.stdin.write(json.dumps(message, ensure_ascii=False).encode() + b"\n")
            await worker.stdin.drain()
        except (ConnectionError, RuntimeError) as gone:
            raise _WorkerLost("the worker ended") from gone

    async def _hear(self, worker: asyncio.subprocess.Process) -> dict[str, Any]:
        assert worker.stdout is not None
        try:
            line = await worker.stdout.readline()
        except (ValueError, asyncio.LimitOverrunError) as too_long:
            raise _WorkerLost("the script handed over more at once than is taken") from too_long
        if not line:
            raise _WorkerLost("the worker ended, which happens when a script uses too much memory")
        try:
            message = json.loads(line)
        except ValueError as unreadable:
            raise _WorkerLost("the worker sent something that could not be read") from unreadable
        if not isinstance(message, dict):
            raise _WorkerLost("the worker sent something that could not be read")
        return message

    async def _end_worker(self) -> None:
        """Ends the worker at once. The next script gets a new one, with an empty `state`."""
        worker, self._worker = self._worker, None
        if worker is None:
            return
        self._state_lost = True
        if worker.returncode is None:
            with contextlib.suppress(ProcessLookupError):
                worker.kill()
        await _gone(worker)

    async def close(self) -> None:
        """Ends the worker for good, when the session ends."""
        worker, self._worker = self._worker, None
        if worker is None:
            return
        if worker.returncode is None:
            with contextlib.suppress(ProcessLookupError):
                worker.kill()
        await _gone(worker)


def _best(found: str, words: str, *, typing: bool) -> str | None:
    """The ref of the best match that can be acted on, when its name holds every word asked for.

    `browser_find` also lists what matches in part, for an agent to read and choose from. Nobody
    reads here: the script acts on what is taken, so a match in part is not taken. The words of a
    label match too, and come first, but a label is not typed into: for typing, a field goes first."""
    wanted = words.lower().split()
    matches = [
        (role, ref)
        for role, name, ref in FOUND.findall(found)
        if all(word in name.lower() for word in wanted)
    ]
    if typing:
        matches = [match for match in matches if match[0] in TAKES_TEXT] or matches
    return matches[0][1] if matches else None


async def _gone(worker: asyncio.subprocess.Process) -> None:
    """Waits for an ended worker, and lets go of the pipes to it."""
    if worker.stdin is not None:
        worker.stdin.close()
    await worker.wait()
    # The transport holds the pipes. Left to the collector, it warns that it was never closed.
    transport = getattr(worker, "_transport", None)
    if transport is not None:
        transport.close()
