"""The service's way to open the desktop app (spec 9.16): for whoever holds the token, and no one else."""

import asyncio
import json
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path

from fakes import FakeDriver

from bap_browser.config import Config
from bap_browser.desktop_app import DesktopApp
from bap_browser.errors import BapError
from bap_browser.service.server import Service
from bap_browser.service.session import ServiceSession

TOKEN = "a-token-for-the-tests-0123456789abcdef"


class AppThatCounts(DesktopApp):
    """A desktop app that opens nothing, and says how often it was asked to."""

    def __init__(self, tmp_path: Path, *, there: bool = True) -> None:
        super().__init__(tmp_path, tmp_path / "desktop-service.json", close_wait_s=1)
        self._there = there
        self.asked = 0
        self.beside: list[tuple[str, int]] = []

    @property
    def there(self) -> bool:
        return self._there

    def start(self) -> bool:
        if not self._there:
            raise BapError("The desktop app is not installed.")
        self.asked += 1
        return self.asked == 1

    def chat_beside(self, address: str, width: int) -> bool:
        if not self._there:
            raise BapError("The desktop app is not installed.")
        self.beside.append((address, width))
        return len(self.beside) == 1


def ask(url: str, *, method: str = "GET", token: str | None = None) -> tuple[int, bytes]:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    request = urllib.request.Request(url, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as refused:
        return refused.code, refused.read()


async def served(
    make_config: Callable[..., Config], tmp_path: Path, desktop: DesktopApp | None
) -> tuple[Service, ServiceSession]:
    session = ServiceSession(make_config(tmp_path), FakeDriver(), agent="Test agent")
    await session.start()
    service = Service(make_config(tmp_path), {"default": session}, token=TOKEN, port=0, desktop=desktop)
    await service.start()
    return service, session


async def test_the_window_is_told_there_is_an_app_and_opens_it_once(
    make_config: Callable[..., Config], tmp_path: Path
) -> None:
    app = AppThatCounts(tmp_path)
    service, session = await served(make_config, tmp_path, app)
    try:
        status, body = await asyncio.to_thread(ask, f"{service.address}/api/sessions", token=TOKEN)
        assert status == 200 and json.loads(body)["desktop"] is True

        door = f"{service.address}/api/desktop"
        # Opening a program on the person's machine is for the person alone.
        assert (await asyncio.to_thread(ask, door, method="POST"))[0] == 401
        assert (await asyncio.to_thread(ask, door, method="POST", token="wrong"))[0] == 401
        assert app.asked == 0
        # A link that is merely followed opens nothing: there is no such page to get.
        assert (await asyncio.to_thread(ask, door, token=TOKEN))[0] == 404
        assert app.asked == 0

        status, body = await asyncio.to_thread(ask, door, method="POST", token=TOKEN)
        assert (status, json.loads(body)) == (200, {"state": "opened"})
        status, body = await asyncio.to_thread(ask, door, method="POST", token=TOKEN)
        assert (status, json.loads(body)) == (200, {"state": "open"})
    finally:
        await service.stop()
        await session.close()


async def test_an_app_that_is_not_installed_is_not_offered_and_says_why_it_did_not_open(
    make_config: Callable[..., Config], tmp_path: Path
) -> None:
    service, session = await served(make_config, tmp_path, AppThatCounts(tmp_path, there=False))
    try:
        status, body = await asyncio.to_thread(ask, f"{service.address}/api/sessions", token=TOKEN)
        assert status == 200 and json.loads(body)["desktop"] is False
        status, body = await asyncio.to_thread(
            ask, f"{service.address}/api/desktop", method="POST", token=TOKEN
        )
        assert (status, json.loads(body)) == (409, {"error": "The desktop app is not installed."})
    finally:
        await service.stop()
        await session.close()


async def test_a_service_with_no_app_has_none_to_open(
    make_config: Callable[..., Config], tmp_path: Path
) -> None:
    service, session = await served(make_config, tmp_path, None)
    try:
        status, body = await asyncio.to_thread(ask, f"{service.address}/api/sessions", token=TOKEN)
        assert status == 200 and "desktop" not in json.loads(body)
        assert (await asyncio.to_thread(ask, f"{service.address}/api/desktop", method="POST", token=TOKEN))[
            0
        ] == 404
    finally:
        await service.stop()
        await session.close()


async def test_a_person_at_this_machine_opens_the_chat_above_the_other_apps(
    make_config: Callable[..., Config], tmp_path: Path
) -> None:
    """The chat of a page, in a window that stays above every app (spec 22.3.1). It is signed in as
    whoever asked for it, and shows that page's chat alone."""
    app = AppThatCounts(tmp_path)
    service, session = await served(make_config, tmp_path, app)
    try:
        door = f"{service.address}/api/sessions/default/beside"
        assert (await asyncio.to_thread(ask, door, method="POST"))[0] == 401
        assert (await asyncio.to_thread(ask, door, token=TOKEN))[0] in (404, 405)
        assert app.beside == []

        status, body = await asyncio.to_thread(ask, door, method="POST", token=TOKEN)
        assert (status, json.loads(body)) == (200, {"state": "opened"})
        assert app.beside == [(f"{service.address}/?session=default&beside#token={TOKEN}", 400)]
        status, body = await asyncio.to_thread(ask, door, method="POST", token=TOKEN)
        assert (status, json.loads(body)) == (200, {"state": "open"})

        nowhere = f"{service.address}/api/sessions/no-such-page/beside"
        assert (await asyncio.to_thread(ask, nowhere, method="POST", token=TOKEN))[0] == 404
    finally:
        await service.stop()
        await session.close()


async def test_a_person_elsewhere_is_not_given_a_window_on_this_machine(
    make_config: Callable[..., Config], tmp_path: Path
) -> None:
    """A window opened here is of no use to somebody at another machine, and is signed in as them."""
    app = AppThatCounts(tmp_path)
    service, session = await served(make_config, tmp_path, app)
    try:
        door = f"{service.address}/api/sessions/default/beside"
        request = urllib.request.Request(
            door, method="POST", headers={"Authorization": f"Bearer {TOKEN}", "X-Forwarded-For": "100.64.0.7"}
        )

        def asked() -> int:
            try:
                with urllib.request.urlopen(request, timeout=5) as response:
                    return response.status
            except urllib.error.HTTPError as refused:
                return refused.code

        assert await asyncio.to_thread(asked) == 404
        assert app.beside == []
    finally:
        await service.stop()
        await session.close()
