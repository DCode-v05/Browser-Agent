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
from bap_browser.service.mac_helper import STOPPED, Helper, helper_app

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
