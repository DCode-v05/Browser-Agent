"""Computer use on a real contained desktop (spec 21, 22.6): through the driver inside the container,
the agent's tools open an app, type and save a file into the one shared folder.

The desktop runs in a container. Where this machine has no container program or the desktop's
image is not built, there is nothing to drive, and these are skipped with that reason.
"""

import asyncio
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

import pytest

from bap_browser.config import Computer
from bap_browser.driver.hermes_driver import HermesDriver
from bap_browser.errors import BrowserError
from bap_browser.evals.desktop_ground import A_PAGE, Desk
from bap_browser.evals.suite import DESKTOP_SETS, Progress, load_set, run_set
from bap_browser.service.session import ServiceSession
from bap_browser.tools.computer_tools import COMPUTER_TOOLS

IMAGE = Computer().image


def _image_is_here() -> bool:
    if shutil.which("docker") is None:
        return False
    listed = subprocess.run(["docker", "image", "ls", "-q", IMAGE], capture_output=True, check=False)
    return listed.returncode == 0 and bool(listed.stdout.strip())


pytestmark = pytest.mark.skipif(
    not _image_is_here(),
    reason=f"needs Docker and the desktop's image: docker build -t {IMAGE} -f deploy/desktop.Dockerfile deploy",
)


async def test_the_agent_writes_a_file_on_the_desktop_and_the_person_has_it(
    make_config, tmp_path: Path
) -> None:
    config = make_config(tmp_path, computer={"container_command": "docker"})
    session = ServiceSession(
        config,
        HermesDriver(config, "e2e"),
        name="computer",
        backend="contained_desktop",
        tools=COMPUTER_TOOLS,
    )
    await session.start()
    call = session.toolkit.call

    async def use(**arguments: Any) -> str:
        done = await call("computer_use", arguments)
        assert not done.is_error, done.text
        return done.text

    async def the_page() -> int:
        """The number of the place text goes into. A window that has just opened takes a moment."""
        async with asyncio.timeout(config.computer.app_open_wait_s):
            while True:
                found = A_PAGE.search(await use(action="capture", mode="ax", app="mousepad"))
                if found is not None:
                    return int(found.group(1))
                await asyncio.sleep(0.2)

    try:
        listed = await call("computer_list_apps", {})
        assert "Text editor" in listed.text and "Terminal" not in listed.text
        assert not (await call("computer_open_app", {"app": "Text editor"})).is_error
        await use(action="click", element=await the_page())
        typed = await use(action="type", text="Milk, eggs, bread")
        assert "Milk" not in typed
        await use(action="key", keys="ctrl+s")
        # The editor asks where to save: into the shared folder. The box is the window in front now.
        await use(action="wait", seconds=1)
        await use(action="capture", mode="ax", app="mousepad")
        await use(action="type", text="~/Files/list.txt")
        await use(action="wait", seconds=config.computer.settle_ms / 1000)
        await use(action="capture", mode="ax", app="mousepad")
        await use(action="key", keys="return")
        saved = Path(config.computer.folder) / "list.txt"
        async with asyncio.timeout(10):
            while not saved.exists():
                await asyncio.sleep(0.2)
        assert saved.read_text().strip() == "Milk, eggs, bread"

        seen = await call("computer_use", {"action": "capture", "mode": "vision"})
        assert seen.picture is not None
        # The window's title now names the file: something changed on the screen.
        assert "list.txt" in (await call("computer_list_apps", {})).text
    finally:
        await session.close()
    # Nothing of the desktop is left running.
    left = subprocess.run(
        ["docker", "ps", "-q", "--filter", "name=bap-browser-desktop-e2e"], capture_output=True, check=False
    )
    assert left.stdout.strip() == b""


async def test_the_desktop_has_no_network_unless_a_person_allows_it(make_config, tmp_path: Path) -> None:
    config = make_config(tmp_path, computer={"container_command": "docker"})
    driver = HermesDriver(config, "e2e-net")
    await driver.start()
    try:
        # With no network there is no route anywhere: the table has its heading line and nothing more.
        routes = await driver.desktop.run("cat", "/proc/net/route")
        assert len(routes.decode().strip().splitlines()) == 1, routes
    finally:
        await driver.close()


async def test_an_app_a_person_has_not_allowed_cannot_run_on_the_desktop_at_all(
    make_config, tmp_path: Path
) -> None:
    """The terminal is off: not only does the tool refuse it, its program cannot start, whatever
    opens it. The desktop's own menu holds nothing to open either."""
    config = make_config(tmp_path, computer={"container_command": "docker"})
    driver = HermesDriver(config, "e2e-apps")
    await driver.start()
    try:
        with pytest.raises(BrowserError, match="Permission denied"):
            await driver.desktop.run("sh", "-c", "xterm -version")
        assert b"mousepad" in await driver.desktop.run("sh", "-c", "command -v mousepad")
        menu = await driver.desktop.run("cat", "/home/agent/.config/openbox/menu.xml")
        assert b"<item" not in menu
    finally:
        await driver.close()


async def test_a_menu_item_that_opens_a_box_is_pressed_by_its_number_and_the_app_goes_on_answering(
    make_config, tmp_path: Path
) -> None:
    """Pressed through the accessibility bus, "Save As..." left the editor not answering for about 25
    seconds a step. On a desktop nobody sits at, the pointer presses what is named by its number."""
    config = make_config(tmp_path, computer={"container_command": "docker"})
    session = ServiceSession(
        config,
        HermesDriver(config, "e2e-menu"),
        name="computer",
        backend="contained_desktop",
        tools=COMPUTER_TOOLS,
    )
    await session.start()

    async def use(**arguments: Any) -> str:
        done = await session.toolkit.call("computer_use", arguments)
        assert not done.is_error, done.text
        return done.text

    def numbered(text: str, words: str) -> int:
        found = re.search(rf"#(\d+) [a-z ]+ '{re.escape(words)}", text)
        assert found is not None, text
        return int(found.group(1))

    try:
        assert not (await session.toolkit.call("computer_open_app", {"app": "Text editor"})).is_error
        async with asyncio.timeout(config.computer.app_open_wait_s):
            while (page := A_PAGE.search(await use(action="capture", mode="ax", app="mousepad"))) is None:
                await asyncio.sleep(0.2)
        await use(action="click", element=int(page.group(1)))
        await use(action="type", text="kept")
        closed = await use(action="capture", mode="ax", app="mousepad")
        # An item of a menu that is not open is not on the screen, and is not named.
        assert "Save As" not in closed and "not on the screen" in closed

        await use(action="click", element=numbered(closed, "File"))
        opened = await use(action="capture", mode="ax", app="mousepad")
        await use(action="click", element=numbered(opened, "Save As..."))

        began = time.perf_counter()
        await use(action="wait", seconds=1)
        await use(action="capture", mode="ax", app="mousepad")
        assert time.perf_counter() - began < 8, "the app stopped answering after the box opened"
        assert "Save As" in (await session.toolkit.call("computer_list_apps", {})).text
    finally:
        await session.close()


@pytest.mark.parametrize(
    "hung",
    ["pkill -STOP -x cua-driver", "(import -window 99999999 png:- >/dev/null 2>&1 &) ; sleep 1"],
    ids=["the driver hangs", "its picture of a window that has gone holds the screen"],
)
async def test_a_desktop_that_stops_answering_is_put_right_and_worked_on_after(
    make_config, tmp_path: Path, hung: str
) -> None:
    """Under a model the desktop in the container stopped answering, and every call after it timed
    out, a fresh driver's too: the driver's program for picturing a window was waiting for a window
    that had gone, with the screen held. Both that and a driver that hangs are made here."""
    config = make_config(tmp_path, computer={"container_command": "docker"})
    session = ServiceSession(
        config,
        HermesDriver(config, "e2e-stall"),
        name="computer",
        backend="contained_desktop",
        tools=COMPUTER_TOOLS,
    )
    await session.start()
    call = session.toolkit.call
    try:
        assert not (await call("computer_open_app", {"app": "Text editor"})).is_error
        assert not (
            await call("computer_use", {"action": "capture", "mode": "ax", "app": "mousepad"})
        ).is_error
        desktop = session.browser.started_driver.desktop  # pyright: ignore[reportOptionalMemberAccess, reportAttributeAccessIssue]
        await desktop.run("sh", "-c", hung)

        stalled = await call("computer_use", {"action": "capture", "mode": "ax", "app": "mousepad"})
        assert stalled.is_error and "The desktop stopped answering" in stalled.text, stalled.text

        began = time.perf_counter()
        again = await call("computer_use", {"action": "capture", "mode": "ax", "app": "mousepad"})
        # The editor was left open: its page is there, with no app to open again.
        assert not again.is_error and A_PAGE.search(again.text) is not None, again.text
        assert time.perf_counter() - began < 20, "the desktop was still slow after it was put right"
    finally:
        await session.close()


async def test_an_app_that_will_not_close_does_not_hold_the_next_task(make_config, tmp_path: Path) -> None:
    """A task set makes the desktop ready before each task. An app left stuck by the task before is
    ended by force, so the run goes on."""
    config = make_config(tmp_path, computer={"container_command": "docker"})
    session = ServiceSession(
        config,
        HermesDriver(config, "e2e-stuck"),
        name="computer",
        backend="contained_desktop",
        tools=COMPUTER_TOOLS,
    )
    await session.start()
    try:
        desktop = session.browser.started_driver.desktop  # pyright: ignore[reportOptionalMemberAccess, reportAttributeAccessIssue]
        # A program under the editor's name that takes no notice of being asked to end.
        stuck = "cp /bin/sleep /tmp/mousepad && (trap '' TERM; /tmp/mousepad 600 >/dev/null 2>&1 &) ; sleep 0.3; pgrep -x mousepad"
        assert (await desktop.run("sh", "-c", stuck)).strip()

        await Desk(session).ready(load_set("short", "desktop")[0])

        left = await desktop.run("sh", "-c", "pgrep -x mousepad || true")
        assert left.strip() == b""
    finally:
        await session.close()


@pytest.mark.parametrize("name", DESKTOP_SETS)
async def test_every_desktop_task_is_solved_by_its_reference_solution(
    make_config, tmp_path: Path, name: str
) -> None:
    """Each task of the desktop's sets can be done on a real desktop, and the checks see it done."""
    config = make_config(tmp_path, computer={"container_command": "docker"})
    session = ServiceSession(
        config,
        HermesDriver(config, f"e2e-{name}"),
        name="computer",
        backend="contained_desktop",
        tools=COMPUTER_TOOLS,
    )
    await session.start()
    try:
        tasks = load_set(name, "desktop")
        report = await run_set(
            session,
            Desk(session),
            name,
            trials=1,
            mode="reference",
            do=None,
            settings=session.config.evals,
            model="",
            progress=Progress(name, "reference", 1, len(tasks)),
            kind="desktop",
        )
    finally:
        await session.close()
    failed = {row["id"]: row["trials"][0]["why"] for row in report["tasks"] if not row["trials"][0]["passed"]}
    assert failed == {}
    assert report["totals"]["tasks"] == len(tasks)
    # A file of the person's beside Practice is never touched by a run.
    assert not (Path(config.computer.folder) / "Practice").exists() or report["tasks"]
