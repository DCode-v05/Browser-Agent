"""The session service on a real port: the viewer's files, the API, and the viewer's WebSocket (spec 4.7 to 4.10)."""

import asyncio
import json
import time
import urllib.error
import urllib.request
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path
from typing import Any

import pytest
from fakes import FakeDriver
from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import ConnectionClosed, InvalidStatus

from bap_browser.config import Config
from bap_browser.service.server import Service
from bap_browser.service.session import ServiceSession

TOKEN = "a-token-made-up-for-these-tests"
Running = Callable[..., Awaitable[tuple[Service, ServiceSession, FakeDriver]]]


@pytest.fixture
async def running(make_config: Callable[..., Config], tmp_path: Path) -> AsyncIterator[Running]:
    """Starts a session on a fake browser and the service around it, and stops both after the test."""
    started: list[tuple[Service, ServiceSession]] = []

    async def start(**sections: Any) -> tuple[Service, ServiceSession, FakeDriver]:
        config = make_config(tmp_path, **sections)
        driver = FakeDriver()
        session = ServiceSession(config, driver, agent="Test agent")
        await session.start()
        service = Service(config, {"default": session}, token=TOKEN, port=0)
        await service.start()
        started.append((service, session))
        return service, session, driver

    yield start
    for service, session in started:
        await service.stop()
        await session.close()


def lowered(headers: Any) -> dict[str, str]:
    """Header names in lower case: their case carries no meaning."""
    return {name.lower(): value for name, value in headers.items()}


def fetch(url: str, **headers: str) -> tuple[int, dict[str, str], bytes]:
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, lowered(response.headers), response.read()
    except urllib.error.HTTPError as refused:
        return refused.code, lowered(refused.headers), refused.read()


async def get(url: str, **headers: str) -> tuple[int, dict[str, str], bytes]:
    return await asyncio.to_thread(fetch, url, **headers)


def socket_address(service: Service, session: str = "default") -> str:
    return service.address.replace("http://", "ws://") + f"/api/sessions/{session}/ws"


async def sign_in(socket: ClientConnection, token: str = TOKEN) -> None:
    await socket.send(json.dumps({"type": "auth", "token": token}))


async def received(socket: ClientConnection) -> Any:
    message = await asyncio.wait_for(socket.recv(), 3)
    return message if isinstance(message, bytes) else json.loads(message)


async def until_caught_up(socket: ClientConnection) -> list[Any]:
    """Everything the service sends a viewer that has just signed in, up to and including `caught_up`."""
    items: list[Any] = []
    while not (items and isinstance(items[-1], dict) and items[-1]["type"] == "caught_up"):
        items.append(await received(socket))
    return items


async def closed_with(socket: ClientConnection) -> int | None:
    with pytest.raises(ConnectionClosed):
        await asyncio.wait_for(socket.recv(), 5)
    return socket.close_code


async def test_it_says_it_is_alive_and_nothing_else(running: Running) -> None:
    service, _, _ = await running()
    status, _, body = await get(f"{service.address}/healthz")
    assert (status, body) == (200, b"")


async def test_the_viewer_is_served_and_may_not_be_shown_inside_another_site(running: Running) -> None:
    service, _, _ = await running()
    status, headers, body = await get(f"{service.address}/")
    assert status == 200 and b'<div id="root">' in body
    assert headers["content-security-policy"] == "frame-ancestors 'self'"
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["referrer-policy"] == "no-referrer"


async def test_a_listed_origin_may_show_the_viewer_inside_itself(running: Running) -> None:
    service, _, _ = await running(viewer={"embed_origins": ["https://app.example.com"]})
    _, headers, _ = await get(f"{service.address}/")
    assert headers["content-security-policy"] == "frame-ancestors 'self' https://app.example.com"


async def test_the_demo_site_is_served(running: Running) -> None:
    service, _, _ = await running()
    status, _, body = await get(f"{service.address}/demo-site/signup.html")
    assert status == 200 and b"Create your Northfield account" in body


async def test_the_api_needs_the_token(running: Running) -> None:
    service, _, _ = await running()
    sessions = f"{service.address}/api/sessions"
    assert (await get(sessions))[0] == 401
    assert (await get(sessions, Authorization="Bearer wrong"))[0] == 401
    assert (await get(sessions, Authorization=TOKEN))[0] == 401
    status, _, body = await get(sessions, Authorization=f"Bearer {TOKEN}")
    assert status == 200
    assert json.loads(body) == {"sessions": [{"id": "default", "state": "agent"}]}


async def test_a_request_for_another_host_is_refused(running: Running) -> None:
    service, _, _ = await running()
    assert (await get(f"{service.address}/healthz", Host="evil.example"))[0] == 400
    assert (await get(f"{service.address}/healthz", Host=f"localhost:{service.port}"))[0] == 200


async def test_the_viewer_address_carries_the_token_where_no_server_sees_it(running: Running) -> None:
    service, _, _ = await running()
    assert service.viewer_address == f"http://127.0.0.1:{service.port}/#token={TOKEN}"


async def test_a_viewer_that_signs_in_is_sent_what_happened_then_the_picture_then_caught_up(
    running: Running,
) -> None:
    service, session, driver = await running()
    await session.toolkit.call("browser_click", {"ref": "e1"})
    driver.on_frame(b"\xff\xd8 a picture")
    before = time.time()
    async with connect(socket_address(service)) as socket:
        await sign_in(socket)
        items = await until_caught_up(socket)
    kinds = [item["type"] if isinstance(item, dict) else "picture" for item in items]
    assert kinds == [
        "session_started",
        "tab_changed",
        "step_started",
        "step_finished",
        "picture",
        "caught_up",
    ]
    # A picture is one type byte and then the JPEG.
    assert items[4] == b"\x01\xff\xd8 a picture"
    assert before <= items[5]["ts"] <= time.time()


async def test_what_happens_next_reaches_every_viewer(running: Running) -> None:
    service, session, driver = await running()
    async with connect(socket_address(service)) as first, connect(socket_address(service)) as second:
        for socket in (first, second):
            await sign_in(socket)
            await until_caught_up(socket)
        await session.toolkit.call("browser_click", {"ref": "e1"})
        driver.on_frame(b"\xff\xd8 next")
        for socket in (first, second):
            assert (await received(socket))["label"] == 'Clicking "Go"'
            assert (await received(socket))["summary"] == 'Clicked "Go" (button)'
            assert await received(socket) == b"\x01\xff\xd8 next"


async def test_nothing_is_sent_before_the_token_and_a_wrong_one_closes_the_connection(
    running: Running,
) -> None:
    service, _, _ = await running()
    for first_message in (
        json.dumps({"type": "auth", "token": "wrong"}),
        json.dumps({"type": "auth"}),
        json.dumps({"type": "pause"}),
        json.dumps({"type": "auth", "token": 7}),
        "not json",
        b"\x01binary",
    ):
        async with connect(socket_address(service)) as socket:
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(socket.recv(), 0.1)
            await socket.send(first_message)
            assert await closed_with(socket) == 4401


async def test_a_viewer_that_never_signs_in_is_let_go(running: Running) -> None:
    service, _, _ = await running(server={"auth_wait_s": 1})
    async with connect(socket_address(service)) as socket:
        started = time.monotonic()
        assert await closed_with(socket) == 4401
        assert time.monotonic() - started < 3


async def test_a_page_of_another_site_cannot_open_the_connection(running: Running) -> None:
    service, _, _ = await running()
    with pytest.raises(InvalidStatus) as refused:
        async with connect(socket_address(service), origin="https://evil.example"):  # type: ignore[arg-type]
            pass
    assert refused.value.response.status_code == 403


async def test_the_viewers_own_origin_and_a_listed_one_are_accepted(running: Running) -> None:
    service, _, _ = await running(viewer={"embed_origins": ["https://app.example.com"]})
    for origin in (service.address, "https://app.example.com"):
        async with connect(socket_address(service), origin=origin) as socket:  # type: ignore[arg-type]
            await sign_in(socket)
            assert (await until_caught_up(socket))[-1]["type"] == "caught_up"


async def test_a_session_that_does_not_exist_is_said_so_only_after_signing_in(running: Running) -> None:
    service, _, _ = await running()
    async with connect(socket_address(service, "nobody")) as socket:
        await socket.send(json.dumps({"type": "auth", "token": "wrong"}))
        assert await closed_with(socket) == 4401
    async with connect(socket_address(service, "nobody")) as socket:
        await sign_in(socket)
        assert await closed_with(socket) == 4404


async def test_a_persons_commands_act_on_the_session(running: Running) -> None:
    service, session, driver = await running()
    async with connect(socket_address(service)) as socket:
        await sign_in(socket)
        await until_caught_up(socket)
        await socket.send(json.dumps({"type": "pause"}))
        assert (await received(socket)) == {
            "type": "control_changed",
            "state": "paused",
            "since": pytest.approx(time.time(), abs=5),
        }
        await socket.send(json.dumps({"type": "take_over"}))
        assert (await received(socket))["state"] == "person"
        await socket.send(json.dumps({"type": "pointer", "action": "down", "x": 40, "y": 30, "button": 0}))
        await socket.send(json.dumps({"type": "stop"}))
        assert (await received(socket))["type"] == "session_ended"
    assert session.control == "ended"
    assert ("pointer", ("down", 40, 30, "left")) in driver.calls


async def test_messages_that_make_no_sense_are_ignored_and_the_connection_stays(running: Running) -> None:
    service, session, _ = await running()
    async with connect(socket_address(service)) as socket:
        await sign_in(socket)
        await until_caught_up(socket)
        for nonsense in (
            "not json",
            "[1, 2]",
            '"pause"',
            "{}",
            b"\x00\x01",
            json.dumps({"type": "auth", "token": TOKEN}),
        ):
            await socket.send(nonsense)
        await socket.send(json.dumps({"type": "pause"}))
        assert (await received(socket))["state"] == "paused"
    assert session.control == "paused"


async def test_a_viewer_that_leaves_is_no_longer_counted(running: Running) -> None:
    service, session, _ = await running()
    async with connect(socket_address(service)) as socket:
        await sign_in(socket)
        await until_caught_up(socket)
        assert session.hub.viewers == 1
    for _ in range(100):
        if session.hub.viewers == 0:
            break
        await asyncio.sleep(0.01)
    assert session.hub.viewers == 0


async def test_the_token_is_made_up_when_none_is_given_and_never_the_same_twice(
    make_config: Callable[..., Config], tmp_path: Path
) -> None:
    config = make_config(tmp_path)
    one, two = Service(config, {}, port=0), Service(config, {}, port=0)
    assert len(one.token) >= 32 and one.token != two.token


async def test_the_token_can_come_from_the_environment(
    make_config: Callable[..., Config], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("BAP_BROWSER_TOKEN", "from-the-environment")
    assert Service(make_config(tmp_path), {}, port=0).token == "from-the-environment"
