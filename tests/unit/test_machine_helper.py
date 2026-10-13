"""The helper a person runs on their own machine, so that an engine elsewhere can drive it over the
tailnet (spec 22.6.2): who it lets in, what it passes on, and what it says of it."""

from __future__ import annotations

import json
import socket
import subprocess
import sys
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import uvicorn
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from bap_browser.service.machine_helper import Helper, helper_app

CODE = "the-pairing-code"
FROM_THE_VM = "100.64.0.7"
A_STRANGER = "100.64.0.99"
# A driver that answers `manifest`, says `--help`, and on `mcp` gives back every line it is sent.
A_DRIVER = """
import json, sys
if sys.argv[1:] == ["manifest"]:
    print(json.dumps({"binary_version": "0.21.0", "mcp_invocation": {"command": "/somewhere/cua-driver", "args": ["mcp"]}}))
elif sys.argv[1:2] == ["mcp"]:
    for line in sys.stdin:
        started = "started with: " + " ".join(sys.argv[2:])
        print(started if line.strip() == "started with?" else "back: " + line.rstrip(), flush=True)
else:
    print("asked: " + " ".join(sys.argv[1:]))
"""


def whois(address: str) -> set[str]:
    """Who Tailscale says an address is: the engine's VM, or a machine nobody allowed."""
    return {FROM_THE_VM: {"tag:bap-vm"}, A_STRANGER: {"tag:printer"}}.get(address, set())


@pytest.fixture
def said() -> list[str]:
    return []


def a_helper(tmp_path: Path, said: list[str], *, tailnet: bool, endpoint: str = "") -> Helper:
    program = tmp_path / "driver.py"
    program.write_text(A_DRIVER, encoding="utf-8")
    return Helper(
        endpoint=endpoint,
        driver=[sys.executable, str(program)],
        code=CODE,
        allowed=("tag:bap-vm",),
        tailnet=tailnet,
        who=whois,
        say=said.append,
        run_timeout_s=20,
        message_bytes=2**24,
    )


def asking(code: str = CODE, forwarded: str | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {code}"}
    return headers | ({"X-Forwarded-For": forwarded} if forwarded else {})


def test_the_engine_on_the_tailnet_with_the_code_is_let_in(tmp_path: Path, said: list[str]) -> None:
    client = TestClient(helper_app(a_helper(tmp_path, said, tailnet=True)))

    answer = client.post("/run", json={"argv": ["manifest"]}, headers=asking(forwarded=FROM_THE_VM))

    assert answer.status_code == 200
    assert json.loads(answer.json()["stdout"])["binary_version"] == "0.21.0"


def test_a_wrong_code_is_refused_whoever_asks(tmp_path: Path, said: list[str]) -> None:
    client = TestClient(helper_app(a_helper(tmp_path, said, tailnet=True)))

    answer = client.post("/run", json={"argv": ["manifest"]}, headers=asking("a guess", FROM_THE_VM))

    assert answer.status_code == 401


def test_a_machine_of_the_tailnet_that_was_not_allowed_is_refused(tmp_path: Path, said: list[str]) -> None:
    client = TestClient(helper_app(a_helper(tmp_path, said, tailnet=True)))

    answer = client.post("/run", json={"argv": ["manifest"]}, headers=asking(forwarded=A_STRANGER))

    assert answer.status_code == 403


def test_a_call_that_did_not_come_through_the_tailnet_is_refused(tmp_path: Path, said: list[str]) -> None:
    client = TestClient(helper_app(a_helper(tmp_path, said, tailnet=True)))

    answer = client.post("/run", json={"argv": ["manifest"]}, headers=asking())

    assert answer.status_code == 403


def test_a_helper_for_this_machine_alone_takes_nothing_that_came_from_elsewhere(
    tmp_path: Path, said: list[str]
) -> None:
    client = TestClient(helper_app(a_helper(tmp_path, said, tailnet=False)), client=("127.0.0.1", 50000))

    here = client.post("/run", json={"argv": ["manifest"]}, headers=asking())
    from_elsewhere = client.post("/run", json={"argv": ["manifest"]}, headers=asking(forwarded=FROM_THE_VM))

    assert here.status_code == 200
    assert from_elsewhere.status_code == 403


@pytest.mark.parametrize("argv", [["update", "--apply"], ["telemetry", "enable"], ["skills", "install"], []])
def test_only_what_the_engine_needs_of_the_driver_is_run(
    argv: list[str], tmp_path: Path, said: list[str]
) -> None:
    client = TestClient(helper_app(a_helper(tmp_path, said, tailnet=True)))

    answer = client.post("/run", json={"argv": argv}, headers=asking(forwarded=FROM_THE_VM))

    assert answer.status_code == 400


def test_what_the_engine_sends_reaches_the_driver_and_its_answers_come_back(
    tmp_path: Path, said: list[str]
) -> None:
    client = TestClient(helper_app(a_helper(tmp_path, said, tailnet=True)))

    with client.websocket_connect("/mcp", headers=asking(forwarded=FROM_THE_VM)) as link:
        link.send_text('{"method": "tools/list"}')
        first = link.receive_text()
        link.send_text('{"method": "ping"}')
        second = link.receive_text()

    assert first.strip() == 'back: {"method": "tools/list"}'
    assert second.strip() == 'back: {"method": "ping"}'


def test_the_person_is_told_what_is_done_and_never_what_is_typed(tmp_path: Path, said: list[str]) -> None:
    client = TestClient(helper_app(a_helper(tmp_path, said, tailnet=True)))
    typing = {
        "method": "tools/call",
        "params": {"name": "type_text", "arguments": {"text": "hunter2 is mine"}},
    }

    with client.websocket_connect("/mcp", headers=asking(forwarded=FROM_THE_VM)) as link:
        link.send_text(json.dumps(typing))
        link.receive_text()

    told = "\n".join(said)
    assert "type_text" in told
    assert "hunter2" not in told


def test_the_live_connection_is_refused_without_the_code(tmp_path: Path, said: list[str]) -> None:
    client = TestClient(helper_app(a_helper(tmp_path, said, tailnet=True)))

    with (
        pytest.raises(WebSocketDisconnect),
        client.websocket_connect("/mcp", headers=asking("a guess", FROM_THE_VM)) as link,
    ):
        link.receive_text()


def test_after_the_person_stops_it_nothing_more_is_done(tmp_path: Path, said: list[str]) -> None:
    helper = a_helper(tmp_path, said, tailnet=True)
    client = TestClient(helper_app(helper))

    helper.stop()
    answer = client.post("/run", json={"argv": ["manifest"]}, headers=asking(forwarded=FROM_THE_VM))

    assert answer.status_code == 423


# A helper that holds the engine to the apps its person allows (spec 22.7): every way to the driver
# goes to the one the helper started with that list, and to no other.

THE_HELD_ONE = "/somewhere/held.sock"


def test_an_engine_held_to_the_allowed_apps_converses_with_the_driver_that_holds_it(
    tmp_path: Path, said: list[str]
) -> None:
    client = TestClient(helper_app(a_helper(tmp_path, said, tailnet=True, endpoint=THE_HELD_ONE)))

    with client.websocket_connect("/mcp", headers=asking(forwarded=FROM_THE_VM)) as link:
        link.send_text("started with?")
        started = link.receive_text().strip()

    assert started == f"started with: --embedded --socket {THE_HELD_ONE}"


def test_a_single_call_of_a_held_engine_goes_to_the_driver_that_holds_it(
    tmp_path: Path, said: list[str]
) -> None:
    client = TestClient(helper_app(a_helper(tmp_path, said, tailnet=True, endpoint=THE_HELD_ONE)))

    answer = client.post(
        "/run", json={"argv": ["call", "list_windows"]}, headers=asking(forwarded=FROM_THE_VM)
    )

    assert answer.json()["stdout"].strip() == f"asked: call list_windows --socket {THE_HELD_ONE}"


def test_a_held_engine_cannot_stop_the_driver_that_holds_it(tmp_path: Path, said: list[str]) -> None:
    client = TestClient(helper_app(a_helper(tmp_path, said, tailnet=True, endpoint=THE_HELD_ONE)))

    answer = client.post("/run", json={"argv": ["stop"]}, headers=asking(forwarded=FROM_THE_VM))

    assert answer.status_code == 400


def test_an_engine_that_is_not_held_reaches_the_driver_as_it_is(tmp_path: Path, said: list[str]) -> None:
    client = TestClient(helper_app(a_helper(tmp_path, said, tailnet=True)))

    with client.websocket_connect("/mcp", headers=asking(forwarded=FROM_THE_VM)) as link:
        link.send_text("started with?")
        started = link.receive_text().strip()

    assert started == "started with:"


def test_the_driver_that_holds_the_engine_is_started_afresh_for_each_session_and_not_under_one(
    tmp_path: Path, said: list[str]
) -> None:
    """A driver that has run a while refuses an app that was closed and opened again (seen on macOS).
    Each session of an engine gets a fresh one; a second conversation of the same session, the
    viewer's beside the agent's, shares it."""
    helper = a_helper(tmp_path, said, tailnet=True)
    started: list[str] = []

    def afresh() -> str:
        started.append(f"/somewhere/held-{len(started) + 1}.sock")
        return started[-1]

    helper.renew = afresh
    client = TestClient(helper_app(helper))

    def asked(link: Any) -> str:
        link.send_text("started with?")
        return link.receive_text().strip()

    with client.websocket_connect("/mcp", headers=asking(forwarded=FROM_THE_VM)) as agents:
        first = asked(agents)
        with client.websocket_connect("/mcp", headers=asking(forwarded=FROM_THE_VM)) as viewers:
            beside = asked(viewers)
    with client.websocket_connect("/mcp", headers=asking(forwarded=FROM_THE_VM)) as next_session:
        second = asked(next_session)

    assert first == beside == "started with: --embedded --socket /somewhere/held-1.sock"
    assert second == "started with: --embedded --socket /somewhere/held-2.sock"


# The link: the program the engine starts in the driver's place.


@pytest.fixture
def served(tmp_path: Path, said: list[str]) -> Iterator[str]:
    """The helper on a port of this machine, for this machine alone. Its address."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    config = uvicorn.Config(
        helper_app(a_helper(tmp_path, said, tailnet=False)), host="127.0.0.1", port=port, log_level="error"
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    ends = time.monotonic() + 10
    while not server.started and time.monotonic() < ends:
        time.sleep(0.02)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=10)


def the_link(tmp_path: Path, address: str, code: str, *argv: str, typed: str = "") -> Any:
    file = tmp_path / "link.json"
    file.write_text(json.dumps({"url": address, "code": code}), encoding="utf-8")
    return subprocess.run(
        [sys.executable, "-m", "bap_browser.computer.link", *argv],
        input=typed,
        capture_output=True,
        text=True,
        timeout=30,
        env={**__import__("os").environ, "BAP_BROWSER_LINK_FILE": str(file)},
        check=False,
    )


def test_the_link_asks_the_driver_on_the_other_machine_and_names_itself_as_the_way_in(
    tmp_path: Path, served: str
) -> None:
    ran = the_link(tmp_path, served, CODE, "manifest")

    manifest = json.loads(ran.stdout)
    assert ran.returncode == 0, ran.stderr
    assert manifest["binary_version"] == "0.21.0"
    # A path on the other machine means nothing here: the engine must come back through the link.
    assert manifest["mcp_invocation"] == {"command": "cua-driver", "args": ["mcp"]}


def test_the_link_carries_the_conversation_with_the_driver_both_ways(tmp_path: Path, served: str) -> None:
    ran = the_link(tmp_path, served, CODE, "mcp", typed='{"id": 1}\n{"id": 2}\n')

    assert ran.stdout.splitlines() == ['back: {"id": 1}', 'back: {"id": 2}']


def test_the_link_with_a_wrong_code_says_so_and_does_nothing(tmp_path: Path, served: str) -> None:
    ran = the_link(tmp_path, served, "a guess", "manifest")

    assert ran.returncode != 0
    assert "pairing code" in ran.stderr
    assert "a guess" not in ran.stderr
