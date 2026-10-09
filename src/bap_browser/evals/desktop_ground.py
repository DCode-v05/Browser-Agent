"""Where the desktop's task sets are done (spec 21.8): the folder Practice inside the shared folder.

Before each task the apps are closed, Practice is emptied and given the task's files. Afterwards
the files in it are read for the checks. Nothing outside Practice is touched: the rest of the
shared folder is the person's.
"""

from __future__ import annotations

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
# The steps a reference solution of the desktop is written in, and the tool each one is.
STEPS = {
    "app": "computer_open_app",
    "click": "computer_click",
    "type": "computer_type",
    "submit": "computer_type",
    "key": "computer_press_key",
    "wait": "computer_wait",
}


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


def arguments_of(step: Sequence[Any]) -> tuple[str, dict[str, Any]]:
    """One step of a reference solution as the tool call it is."""
    kind, *rest = step
    if kind not in STEPS:
        raise LostStep(f"a reference solution of the desktop has no step named {kind}")
    match kind:
        case "app":
            given: dict[str, Any] = {"app": rest[0]}
        case "click":
            given = {"x": rest[0], "y": rest[1]}
        case "type":
            given = {"text": rest[0]}
        case "submit":
            given = {"text": rest[0], "submit": True}
        case "key":
            given = {"keys": rest[0]}
        case _:
            given = {"seconds": rest[0]}
    return STEPS[kind], given


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
        await self.driver().desktop.run("sh", "-c", f"for app in {names}; do pkill -x $app; done; true")
        prepare(self.shared(), task.seed)

    async def solve(self, steps: Sequence[Sequence[Any]]) -> tuple[str, int]:
        answer, done = "", 0
        for step in steps:
            if step[0] == "answer":
                answer = str(step[1])
                continue
            done += 1
            result = await own_call(self._session, *arguments_of(step))
            if result.is_error:
                raise LostStep(result.text.split("\n", 1)[0][:160])
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
