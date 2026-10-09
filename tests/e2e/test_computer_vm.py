"""The desktop of computer use in the micro VM (spec 21.1, arrangement 2): the VM's image, started as a
container standing in for the VM, serves the desktop's tools over MCP on HTTP to an agent outside it.

Where this machine has no Docker or the image is not built, there is nothing to reach, and these are
skipped with that reason.
"""

import asyncio
import secrets
import shutil
import subprocess
import urllib.request
from collections.abc import AsyncIterator
from typing import Any

import httpx2
import pytest
from mcp import Client
from mcp.client import streamable_http

IMAGE = "bap-browser-computer:latest"
SERVE = ["uv", "run", "--project", "/app", "--no-sync", "bap-browser", "serve", "--desktop"]


def _image_is_here() -> bool:
    if shutil.which("docker") is None:
        return False
    listed = subprocess.run(["docker", "image", "ls", "-q", IMAGE], capture_output=True, check=False)
    return listed.returncode == 0 and bool(listed.stdout.strip())


pytestmark = pytest.mark.skipif(
    not _image_is_here(),
    reason=f"needs Docker and the VM's image: docker build --build-arg DESKTOP=true -f deploy/Dockerfile -t {IMAGE} .",
)


@pytest.fixture
async def vm() -> AsyncIterator[tuple[str, str, str]]:
    """The VM's image, running: its address, its token, its container's name."""
    token, name = secrets.token_urlsafe(24), f"bap-browser-vm-{secrets.token_hex(3)}"
    started = subprocess.run(
        [
            "docker",
            "run",
            "-d",
            "--rm",
            "--name",
            name,
            "-p",
            "127.0.0.1::8765",
            "-e",
            f"BAP_BROWSER_TOKEN={token}",
            IMAGE,
            *SERVE,
        ],
        capture_output=True,
        check=False,
    )
    assert started.returncode == 0, started.stderr.decode()
    try:
        port = subprocess.run(
            ["docker", "port", name, "8765"], capture_output=True, check=True
        ).stdout.decode()
        address = "http://" + port.strip().splitlines()[0]
        async with asyncio.timeout(90):
            while True:
                try:
                    await asyncio.to_thread(urllib.request.urlopen, f"{address}/healthz", timeout=2)
                    break
                except OSError:
                    await asyncio.sleep(0.2)
        yield address, token, name
    finally:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True, check=False)


async def test_an_agent_outside_the_vm_works_on_its_desktop(vm: tuple[str, str, str]) -> None:
    address, token, name = vm
    async with (
        # The client's own HTTP library, which its signature names: it carries the token.
        httpx2.AsyncClient(headers={"Authorization": f"Bearer {token}"}, timeout=30) as http,
        Client(streamable_http.streamable_http_client(f"{address}/mcp", http_client=http)) as client,
    ):
        names = {tool.name for tool in (await client.list_tools()).tools}
        assert "computer_screenshot" in names and not any(name.startswith("browser_") for name in names)

        async def call(tool: str, arguments: dict[str, Any]) -> str:
            result = await client.call_tool(tool, arguments)
            return " ".join(getattr(part, "text", "") for part in result.content)

        listed = await call("computer_list_apps", {})
        assert "Text editor" in listed and "Terminal" not in listed
        assert "Opened Text editor" in await call("computer_open_app", {"app": "Text editor"})
        await call("computer_click", {"x": 640, "y": 400})
        await call("computer_type", {"text": "made in the VM"})
        await call("computer_press_key", {"keys": "Control+s"})
        await call("computer_wait", {"seconds": 1})
        await call("computer_type", {"text": "~/Files/vm.txt", "submit": True})
        await call("computer_wait", {"seconds": 1})
        shot = await client.call_tool("computer_screenshot", {})
        assert any(getattr(part, "type", "") == "image" for part in shot.content)
    saved = subprocess.run(
        ["docker", "exec", name, "cat", "/home/pwuser/Files/vm.txt"], capture_output=True, check=False
    )
    assert saved.stdout.decode().strip() == "made in the VM", saved.stderr.decode()


async def test_without_a_key_the_vm_runs_and_joins_no_tailnet(vm: tuple[str, str, str]) -> None:
    _, _, name = vm
    running = subprocess.run(
        ["docker", "exec", name, "pgrep", "-x", "tailscaled"], capture_output=True, check=False
    )
    assert running.returncode == 1, "Tailscale runs with no key given"


def test_a_key_that_is_refused_stops_the_vm_with_the_reason() -> None:
    """Fails loudly: a VM that was meant to join a tailnet and could not does not serve anything."""
    ended = subprocess.run(
        ["docker", "run", "--rm", "-e", "TS_AUTHKEY=tskey-auth-k0000000000-notarealkey", IMAGE, *SERVE],
        capture_output=True,
        check=False,
        timeout=120,
    )
    said = ended.stderr.decode()
    assert ended.returncode == 3, said
    assert "could not join the tailnet" in said
    assert "notarealkey" not in said, "the key was written out"
    assert "Viewer:" not in said, "the service started anyway"
