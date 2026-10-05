"""The tools over MCP on HTTP, for an agent in another process (spec 4.4, 4.7)."""

import asyncio
import json
import urllib.error
import urllib.request
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fakes import FakeDriver
from mcp import Client
from mcp.client.streamable_http import (
    create_mcp_http_client,  # pyright: ignore[reportPrivateImportUsage]
    streamable_http_client,
)

from bap_browser.config import Config
from bap_browser.mcp.server import build_server
from bap_browser.service.server import Service
from bap_browser.service.session import ServiceSession
from bap_browser.tools import TOOLS

TOKEN = "a-token-made-up-for-these-tests"


@asynccontextmanager
async def serving(config: Config) -> AsyncIterator[tuple[Service, ServiceSession]]:
    session = ServiceSession(config, FakeDriver(), agent="Test agent")
    await session.start()
    service = Service(
        config,
        {session.name: session},
        token=TOKEN,
        port=0,
        mcp=build_server(session.toolkit, config.mcp.server_name),
    )
    await service.start()
    try:
        yield service, session
    finally:
        await service.stop()
        await session.close()


def post(url: str, **headers: str) -> int:
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}).encode()
    asked = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream", **headers}
    request = urllib.request.Request(url, data=body, headers=asked, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=5) as answer:
            return answer.status
    except urllib.error.HTTPError as refused:
        with refused:
            return refused.code


async def test_an_agent_with_the_token_is_offered_the_tools_and_a_person_sees_what_it_does(
    make_config: Callable[..., Config], tmp_path: Path
) -> None:
    async with serving(make_config(tmp_path)) as (service, session):
        assert service.mcp_address == f"{service.address}/mcp"
        async with (
            create_mcp_http_client(headers={"Authorization": f"Bearer {TOKEN}"}) as http,
            Client(streamable_http_client(service.mcp_address, http_client=http)) as client,
        ):
            listed = await client.list_tools()
            assert [tool.name for tool in listed.tools] == [tool.name for tool in TOOLS]
            read = await client.call_tool("browser_snapshot", {})
            assert not read.is_error and read.content[0].text.startswith("Page: ")  # type: ignore[union-attr]
            bad = await client.call_tool("browser_click", {"ref": "not a ref"})
            assert bad.is_error
        # The same session a person is watching: each call was a step in the viewer.
        told: list[Any] = [item for item in session.hub.subscribe()[0] if isinstance(item, dict)]
        steps = [event for event in told if event["type"] == "step_finished"]
        assert [step["ok"] for step in steps] == [True, False]


async def test_nothing_is_offered_without_the_token(
    make_config: Callable[..., Config], tmp_path: Path
) -> None:
    async with serving(make_config(tmp_path)) as (service, _):
        assert await asyncio.to_thread(post, service.mcp_address) == 401
        assert await asyncio.to_thread(post, service.mcp_address, Authorization="Bearer not-the-token") == 401
        assert await asyncio.to_thread(post, service.mcp_address, Authorization=f"Basic {TOKEN}") == 401
        assert await asyncio.to_thread(post, service.mcp_address, Authorization=f"Bearer {TOKEN}") == 200


async def test_a_service_that_was_not_asked_to_has_no_mcp_endpoint(
    make_config: Callable[..., Config], tmp_path: Path
) -> None:
    config = make_config(tmp_path)
    session = ServiceSession(config, FakeDriver())
    await session.start()
    service = Service(config, {session.name: session}, token=TOKEN, port=0)
    await service.start()
    try:
        assert await asyncio.to_thread(post, f"{service.address}/mcp", Authorization=f"Bearer {TOKEN}") in (
            404,
            405,
        )
    finally:
        await service.stop()
        await session.close()


async def test_the_path_is_the_configured_one(make_config: Callable[..., Config], tmp_path: Path) -> None:
    async with serving(make_config(tmp_path, mcp={"http_path": "/tools"})) as (service, _):
        assert service.mcp_address == f"{service.address}/tools"
        assert await asyncio.to_thread(post, service.mcp_address, Authorization=f"Bearer {TOKEN}") == 200
