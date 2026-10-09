"""The helper on a person's Mac and the engine's driver that asks it (spec 21.13), over real HTTP. The
Mac's own hands are a stand-in that keeps what it was asked: nothing here moves a real pointer."""

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
import uvicorn

from bap_browser.config import Computer
from bap_browser.driver.mac_driver import MacDriver
from bap_browser.driver.mac_hands import FLAGS, chord
from bap_browser.errors import BrowserError
from bap_browser.service.mac_helper import STOPPED, Helper, helper_app, pairing_file, write_pairing

TOKEN = "a-token-only-the-test-knows"
PICTURE = b"\x89PNG\r\n\x1a\n" + bytes(24)


class StandInHands:
    def __init__(self) -> None:
        self.did: list[tuple[str, Any]] = []
        self.at = (500.0, 400.0)
        self.permitted: tuple[bool, bool] = (True, True)

    def screen(self) -> tuple[int, int]:
        return 1440, 900

    def allowed(self) -> tuple[bool, bool]:
        return self.permitted

    def pointer_at(self) -> tuple[float, float]:
        return self.at

    def picture(self, width: int, jpeg_quality: int | None, region: Any = None) -> bytes:
        self.did.append(("picture", (width, jpeg_quality, region)))
        return PICTURE

    def click(self, x: float, y: float, button: str, count: int, flags: int) -> None:
        self.did.append(("click", (x, y, button, count, flags)))

    def move(self, x: float, y: float) -> None:
        self.did.append(("move", (x, y)))

    def press(self, x: float, y: float, button: str, down: bool) -> None:
        self.did.append(("press", (x, y, button, down)))

    def drag(self, start: Any, end: Any) -> None:
        self.did.append(("drag", (start, end)))

    def type_text(self, text: str) -> None:
        self.did.append(("type", text))

    def key(self, code: int, flags: int, down: bool | None) -> None:
        self.did.append(("key", (code, flags, down)))

    def scroll(self, lines_x: int, lines_y: int) -> None:
        self.did.append(("scroll", (lines_x, lines_y)))

    def open_app(self, name: str) -> None:
        self.did.append(("open", name))

    def front(self) -> str:
        return "TextEdit"


@pytest.fixture
async def mac(
    make_config, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[tuple[MacDriver, StandInHands]]:
    hands = StandInHands()
    helper = Helper(hands, TOKEN, ["text_editor", "calculator"], 3.0)
    server = uvicorn.Server(uvicorn.Config(helper_app(helper), host="127.0.0.1", port=0, log_level="warning"))
    import asyncio

    serving = asyncio.create_task(server.serve())
    while not server.started:
        await asyncio.sleep(0.01)
    port = server.servers[0].sockets[0].getsockname()[1]
    monkeypatch.setenv("BAP_BROWSER_HELPER_TOKEN", TOKEN)
    config = make_config(
        tmp_path, computer={"runs": "mac", "helper_url": f"http://127.0.0.1:{port}", "settle_ms": 0}
    )
    yield MacDriver(config), hands
    server.should_exit = True
    await serving


async def test_the_engine_drives_the_mac_through_the_helper(mac: tuple[MacDriver, StandInHands]) -> None:
    driver, hands = mac
    await driver.start()
    assert await driver.viewport() == (1440, 900) and driver.description() == "The person's Mac, 1440 by 900"
    await driver.click_at(120, 48, button="left", click_count=2, modifiers=["Meta"])
    await driver.type_text(None, "hunter2 and more", clear=False, submit=True, slowly=False)
    await driver.press_key("Meta+s", repeat=1, ref=None)
    await driver.turn_wheel("down", 2, (300, 200))
    await driver.drag((10, 20), (30, 40))
    shot = await driver.screenshot(full_page=False, annotate=False)
    assert shot.picture.data == PICTURE and (shot.width, shot.height) == (1440, 900)
    assert hands.did == [
        ("click", (120.0, 48.0, "left", 2, FLAGS["cmd"])),
        ("type", "hunter2 and more"),
        ("key", (*chord("Enter"), None)),
        ("key", (1, FLAGS["cmd"], None)),
        ("move", (300.0, 200.0)),
        ("scroll", (0, 2 * Computer().scroll_notches_per_step)),
        ("drag", ((10.0, 20.0), (30.0, 40.0))),
        ("picture", (1440, None, None)),
    ]


async def test_the_helper_answers_no_other_token(
    mac: tuple[MacDriver, StandInHands], monkeypatch: pytest.MonkeyPatch, make_config, tmp_path: Path
) -> None:
    driver, _ = mac
    monkeypatch.setenv("BAP_BROWSER_HELPER_TOKEN", "someone-else")
    config = make_config(tmp_path, computer={"runs": "mac", "helper_url": driver.link.url})
    with pytest.raises(BrowserError, match="did not take the token"):
        await MacDriver(config).start()


async def test_a_mac_that_has_not_allowed_it_says_what_to_allow(mac: tuple[MacDriver, StandInHands]) -> None:
    driver, hands = mac
    hands.permitted = (False, True)
    with pytest.raises(BrowserError, match="not allowed the helper Screen Recording"):
        await driver.start()


async def test_the_pointer_in_the_corner_stops_the_helper_for_good(
    mac: tuple[MacDriver, StandInHands],
) -> None:
    driver, hands = mac
    await driver.start()
    hands.at = (1.0, 2.0)
    with pytest.raises(BrowserError, match="stopped the helper"):
        await driver.click_at(200, 200, button="left", click_count=1, modifiers=[])
    hands.at = (700.0, 500.0)
    with pytest.raises(BrowserError, match=STOPPED[:30]):
        await driver.press_key("Enter", repeat=1, ref=None)
    assert [kind for kind, _ in hands.did] == [], "something was done after the stop"


async def test_the_helper_opens_only_the_apps_the_person_named(mac: tuple[MacDriver, StandInHands]) -> None:
    driver, hands = mac
    await driver.start()
    await driver.link.act(do="open", app="calculator")
    with pytest.raises(BrowserError, match="did not allow that app"):
        await driver.link.act(do="open", app="terminal")
    assert ("open", "Calculator") in hands.did and not [
        one for one in hands.did if one == ("open", "Terminal")
    ]


def test_the_admin_chooses_this_mac_as_where_the_agent_works(make_config, tmp_path: Path) -> None:
    from bap_browser.driver.mac_driver import desktop_driver_for
    from bap_browser.settings.store import SettingsStore

    store = SettingsStore(make_config(tmp_path))
    store.systems, store.backends = ("computer",), {"computer": "contained_desktop"}
    choice = next(
        setting
        for group in store.answer("web", "computer")["groups"]
        for setting in group["settings"]
        if setting["id"] == "computer_runs"
    )
    assert [one["value"] for one in choice["choices"]] == ["container", "mac"]
    assert choice["value"] == "container" and choice["applies"] == "next_session"
    store.change("web", {"computer_runs": "mac"}, "computer")
    config = store.apply_to(make_config(tmp_path), "contained_desktop", "computer")
    assert isinstance(desktop_driver_for(config), MacDriver)


async def test_the_helper_pairs_through_a_private_file_and_nothing_is_copied(
    mac: tuple[MacDriver, StandInHands], make_config, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The helper on this Mac leaves its address and token where only this user can read them."""
    driver, _ = mac
    monkeypatch.delenv("BAP_BROWSER_HELPER_TOKEN")
    config = make_config(tmp_path, computer={"runs": "mac"})
    pairing = pairing_file(config)
    write_pairing(pairing, driver.link.url, TOKEN)
    assert pairing.stat().st_mode & 0o777 == 0o600
    paired = MacDriver(config)
    await paired.start()
    assert paired.link.url == driver.link.url
    pairing.unlink()
    with pytest.raises(BrowserError, match="Start the helper"):
        await MacDriver(config).start()


def test_on_a_mac_the_agent_is_told_it_works_on_the_persons_own_mac(make_config, tmp_path: Path) -> None:
    from bap_browser.agent.loop import instructions_for

    mac = instructions_for(make_config(tmp_path, computer={"runs": "mac"}))
    assert "person's own Mac" in mac and "Command" in mac and "Practice" not in mac
    linux = instructions_for(make_config(tmp_path))
    assert "small Linux desktop" in linux


def test_the_window_starts_the_helper_in_terminal_with_the_apps_the_admin_allows(
    make_config, tmp_path: Path
) -> None:
    from bap_browser.driver.mac_driver import start_helper_in_terminal

    config = make_config(tmp_path, computer={"apps": {"files": False, "terminal": False}})
    ran: list[list[str]] = []
    script = start_helper_in_terminal(config, Path("/Users/ada/My Project"), ran.append)
    assert ran == [["open", "-a", "Terminal", str(script)]]
    assert script.stat().st_mode & 0o777 == 0o700
    lines = script.read_text().splitlines()
    assert lines[0] == "#!/bin/sh"
    assert "cd '/Users/ada/My Project'" in lines[1]
    assert lines[-1] == "exec uv run bap-browser helper --allow text_editor,calculator"


def test_with_no_app_allowed_the_helper_is_not_started(make_config, tmp_path: Path) -> None:
    from bap_browser.driver.mac_driver import start_helper_in_terminal

    apps = {"text_editor": False, "files": False, "calculator": False, "terminal": False}
    ran: list[list[str]] = []
    with pytest.raises(BrowserError, match="Allow at least one app"):
        start_helper_in_terminal(make_config(tmp_path, computer={"apps": apps}), tmp_path, ran.append)
    assert ran == []


async def test_the_page_connects_by_itself_once_the_helper_has_paired(make_config, tmp_path: Path) -> None:
    import asyncio

    from bap_browser.agent.studio import Room, paired_or_asked

    config = make_config(tmp_path, computer={"runs": "mac", "helper_poll_s": 0.01})
    room = Room("computer", "contained_desktop")
    waiting = asyncio.create_task(paired_or_asked(room, config))
    await asyncio.sleep(0.05)
    assert not waiting.done(), "it went on with no helper"
    write_pairing(pairing_file(config), "http://127.0.0.1:8796", TOKEN)
    await asyncio.wait_for(waiting, 2)


async def test_the_admin_starts_the_helper_from_the_window_only_for_this_mac(
    make_config, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import sys

    from bap_browser.agent.studio import Studio
    from bap_browser.settings.store import SettingsStore

    monkeypatch.setattr(sys, "platform", "darwin")
    config = make_config(tmp_path)
    settings = SettingsStore(config)
    studio = Studio(config, settings, lambda service: None, tmp_path)  # pyright: ignore[reportArgumentType]
    opened: list[Path] = []
    studio.open_helper = lambda given, folder, run=None: opened.append(folder) or folder  # pyright: ignore[reportAttributeAccessIssue]
    assert await studio.manage("computer", "helper") == 'Choose "This Mac" under Where the agent works first.'
    settings.change("web", {"computer_runs": "mac"}, "computer")
    assert await studio.manage("computer", "helper") is None
    assert opened == [Path.cwd()]
    assert next(page for page in studio.pages() if page["id"] == "computer")["runs"] == "mac"
