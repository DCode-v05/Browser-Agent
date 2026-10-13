"""Where the desktop's task sets are done (spec 21.8): the folder Practice inside the shared folder.

Before each task the apps are closed, Practice is emptied and given the task's files. Afterwards
the files in it are read for the checks. Nothing outside Practice is touched: the rest of the
shared folder is the person's.
"""

from __future__ import annotations

import re
import shutil
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from bap_browser.driver.contained_desktop import APPS
from bap_browser.driver.desktop_driver import DesktopDriver
from bap_browser.errors import BrowserError
from bap_browser.evals.suite import EvalTask, LostStep, own_call
from bap_browser.service.session import ServiceSession

PRACTICE = "Practice"
# The steps a reference solution of the desktop is written in.
STEPS = frozenset({"app", "page", "type", "submit", "key", "wait"})
THE_TOOL = "computer_use"
# A line of a capture that names a place text goes into: its number.
A_PAGE = re.compile(r"#(\d+) \S*(?:text|Edit|edit|entry|Document|document|AXTextArea)\S*")
# The keys a solution names, as Hermes' tool names them.
THEIR_KEYS = {"control": "ctrl", "enter": "return"}


def their_keys(keys: str) -> str:
    """A key or a chord as Hermes' tool takes it: `Control+s` is `ctrl+s`."""
    return "+".join(THEIR_KEYS.get(part.lower(), part.lower()) for part in keys.split("+"))


def prepare(shared: Path, seed: Mapping[str, Any]) -> None:
    """Empties Practice inside the shared folder and puts the task's files in it."""
    practice = shared / PRACTICE
    if practice.exists():
        shutil.rmtree(practice)
    practice.mkdir(parents=True)
    files: Mapping[str, str] = seed.get("files", {})
    for name, text in files.items():
        (practice / name).write_text(text, encoding="utf-8")


def practice_state(shared: Path, chars: int) -> dict[str, Any]:
    """The files in Practice: their names, and what each holds, by its name with `_` for the dot."""
    practice = shared / PRACTICE
    found = sorted(path for path in practice.iterdir() if path.is_file()) if practice.is_dir() else []
    return {
        "names": [path.name for path in found],
        "files": {
            path.name.replace(".", "_"): path.read_text(encoding="utf-8", errors="replace")[:chars]
            for path in found
        },
    }


class Desk:
    """The desktop as the ground of a set."""

    def __init__(self, session: ServiceSession) -> None:
        self._session = session

    def driver(self) -> DesktopDriver:
        driver = self._session.browser.started_driver
        if not isinstance(driver, DesktopDriver):
            raise BrowserError("This session has no desktop.", reason="this is not a desktop")
        return driver

    def shared(self) -> Path:
        folder = self.driver().desktop.folder
        if folder is None:
            raise BrowserError(
                "The desktop's task sets need its shared folder. Turn on Share a folder with the desktop.",
                reason="no folder is shared",
            )
        return folder

    async def ready(self, task: EvalTask) -> None:
        # The apps are closed first: none holds a file of the last task open.
        names = " ".join(app.command for app in APPS)
        # Each is waited for until it is gone. An app that is opened while its last run is still
        # ending hands its window to that run over the session's bus, and then there is none.
        gone = f"for app in {names}; do pkill -x $app; while pgrep -x $app >/dev/null; do sleep 0.1; done; done; true"
        await self.driver().desktop.run("sh", "-c", gone)
        prepare(self.shared(), task.seed)

    async def _do(self, name: str, arguments: Mapping[str, Any]) -> str:
        result = await own_call(self._session, name, arguments)
        if result.is_error:
            raise LostStep(result.text.split("\n", 1)[0][:160])
        return result.text

    async def _look(self, app: str) -> str:
        """A capture of the app's window in front. What is typed or pressed next goes to that window:
        a box that has just opened, such as the one that asks where to save, is the one in front."""
        return await self._do(THE_TOOL, {"action": "capture", "mode": "ax", "app": app})

    async def _the_page(self, app: str) -> re.Match[str]:
        """The place text goes into, in the app's window. An app that has just been opened takes a
        moment to show it, so it is looked for until it is there or the wait for an app is over."""
        settings = self._session.config.computer
        looks = max(1, int(settings.app_open_wait_s * 1000 / settings.app_poll_ms))
        for _ in range(looks):
            found = A_PAGE.search(await self._look(app))
            if found is not None:
                return found
            await self._do(THE_TOOL, {"action": "wait", "seconds": settings.app_poll_ms / 1000})
        raise LostStep(f"{app} shows no place to type into")

    async def solve(self, steps: Sequence[Sequence[Any]]) -> tuple[str, int]:
        """Does the steps of a reference solution with the tools an agent has: Hermes' one tool, and
        ours that opens an app. What it answers, and how many steps it took."""
        answer, done, app = "", 0, ""
        for step in steps:
            kind, *rest = step
            if kind == "answer":
                answer = str(rest[0])
                continue
            if kind not in STEPS:
                raise LostStep(f"a reference solution of the desktop has no step named {kind}")
            done += 1
            match kind:
                case "app":
                    await self._do("computer_open_app", {"app": rest[0]})
                    app = next(one.command for one in APPS if one.name == rest[0])
                case "page":
                    # The place the text goes: found among the app's elements, and clicked by its number.
                    found = await self._the_page(app)
                    await self._do(THE_TOOL, {"action": "click", "element": int(found.group(1))})
                case "type" | "submit":
                    await self._look(app)
                    await self._do(THE_TOOL, {"action": "type", "text": rest[0]})
                    if kind == "submit":
                        # A box that completes what is typed takes Enter for itself while it is still
                        # working. It is given a moment, and looked at again, before Enter.
                        settle = self._session.config.computer.settle_ms / 1000
                        await self._do(THE_TOOL, {"action": "wait", "seconds": settle})
                        await self._look(app)
                        await self._do(THE_TOOL, {"action": "key", "keys": "return"})
                case "key":
                    await self._look(app)
                    await self._do(THE_TOOL, {"action": "key", "keys": their_keys(rest[0])})
                case _:
                    await self._do(THE_TOOL, {"action": "wait", "seconds": rest[0]})
        return answer, done

    async def state(self) -> Any:
        try:
            windows = await self.driver().windows()
        except BrowserError:
            return None
        chars = self._session.config.evals.desktop_file_chars
        return {
            **practice_state(self.shared(), chars),
            "terminal": any("xterm" in title for title in windows),
        }

    async def keep_place(self) -> None:
        """A desktop has no place to go back to."""

    async def back(self) -> None:
        """A desktop has no place to go back to."""
