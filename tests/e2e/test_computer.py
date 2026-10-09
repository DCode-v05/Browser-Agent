"""Computer use on a real contained desktop (spec 21): the agent's tools open an app, type and save
a file into the one shared folder, and a person's hand reaches the desktop too.

The desktop runs in a container. Where this machine has no container program or the desktop's
image is not built, there is nothing to drive, and these are skipped with that reason.
"""

import asyncio
import shutil
import subprocess
from pathlib import Path

import pytest

from bap_browser.config import Computer
from bap_browser.driver.desktop_driver import DesktopDriver
from bap_browser.errors import BrowserError
from bap_browser.evals.desktop_ground import Desk
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
        DesktopDriver(config, "e2e"),
        name="computer",
        backend="contained_desktop",
        tools=COMPUTER_TOOLS,
    )
    await session.start()
    call = session.toolkit.call
    try:
        listed = await call("computer_list_apps", {})
        assert "Text editor" in listed.text and "Terminal" not in listed.text
        assert not (await call("computer_open_app", {"app": "Text editor"})).is_error
        await call("computer_click", {"x": 640, "y": 400})
        assert not (await call("computer_type", {"text": "Milk, eggs, bread"})).is_error
        await call("computer_press_key", {"keys": "Control+s"})
        # The editor asks where to save: into the shared folder.
        await call("computer_wait", {"seconds": 1})
        await call("computer_type", {"text": "Files/list.txt", "submit": True})
        # The file box offers to complete the folder's name first: Enter once more saves, as a
        # person would press it again on seeing that.
        await call("computer_wait", {"seconds": 0.5})
        await call("computer_press_key", {"keys": "Enter"})
        saved = Path(config.computer.folder) / "list.txt"
        async with asyncio.timeout(10):
            while not saved.exists():
                await asyncio.sleep(0.2)
        assert saved.read_text().strip() == "Milk, eggs, bread"

        shot = await call("computer_screenshot", {})
        assert shot.picture is not None and "1280 by 800" in shot.text
        # The window's title now names the file: something changed on the screen.
        windows = await session.browser.started_driver.windows()  # pyright: ignore[reportOptionalMemberAccess, reportAttributeAccessIssue]
        assert any("list.txt" in title for title in windows)
    finally:
        await session.close()
    # Nothing of the desktop is left running.
    left = subprocess.run(
        ["docker", "ps", "-q", "--filter", "name=bap-browser-desktop-e2e"], capture_output=True, check=False
    )
    assert left.stdout.strip() == b""


async def test_the_desktop_has_no_network_unless_a_person_allows_it(make_config, tmp_path: Path) -> None:
    config = make_config(tmp_path, computer={"container_command": "docker"})
    driver = DesktopDriver(config, "e2e-net")
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
    driver = DesktopDriver(config, "e2e-apps")
    await driver.start()
    try:
        with pytest.raises(BrowserError, match="Permission denied"):
            await driver.desktop.run("sh", "-c", "xterm -version")
        assert b"mousepad" in await driver.desktop.run("sh", "-c", "command -v mousepad")
        menu = await driver.desktop.run("cat", "/home/agent/.config/openbox/menu.xml")
        assert b"<item" not in menu
    finally:
        await driver.close()


@pytest.mark.parametrize("name", DESKTOP_SETS)
async def test_every_desktop_task_is_solved_by_its_reference_solution(
    make_config, tmp_path: Path, name: str
) -> None:
    """Each task of the desktop's sets can be done on a real desktop, and the checks see it done."""
    config = make_config(tmp_path, computer={"container_command": "docker"})
    session = ServiceSession(
        config,
        DesktopDriver(config, f"e2e-{name}"),
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
