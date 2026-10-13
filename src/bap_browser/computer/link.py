"""The link: the program an engine starts in the driver's place when the machine to drive is
elsewhere (spec 22.6.2).

Hermes' code starts the driver as a program on its own machine and talks to it over a pipe. For a
machine elsewhere it starts this instead. Whatever it is asked, it asks of the helper on that
machine, and gives back what the driver there said. The helper's address and the pairing code are
in a file only the engine's user can read, named by `BAP_BROWSER_LINK_FILE`.
"""

from __future__ import annotations

import io
import json
import os
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from websockets.exceptions import InvalidStatus, WebSocketException
from websockets.sync.client import connect

FILE = "BAP_BROWSER_LINK_FILE"
REFUSALS = {
    401: "The helper refused the pairing code. Read the code the helper shows, and give it to the engine again.",
    403: "The helper does not allow this machine. Its owner allows machines by their Tailscale tag or login.",
    423: "The person stopped the helper. They start it again when the engine may go on.",
}
NO_HELPER = "The helper on the other machine could not be reached at {url}: {wrong}"
# Sent to the helper when the engine has no more to say.
NO_MORE = ""


def refusal(status: int) -> str:
    return REFUSALS.get(status, f"The helper answered {status}.")


def reached_from_here(manifest: str) -> str:
    """What the driver says of itself, with its own path taken out. It names where it is on its own
    machine, or inside its own container. From the engine the way to it is the program the engine
    started in its place: the link, or the dock."""
    said = json.loads(manifest)
    said["mcp_invocation"] = {"command": "cua-driver", "args": ["mcp"]}
    return json.dumps(said) + "\n"


def ask(url: str, code: str, argv: list[str]) -> int:
    """Has the driver on the other machine run one command, and prints what it printed."""
    asked = urllib.request.Request(
        f"{url}/run",
        data=json.dumps({"argv": argv}).encode(),
        headers={"Authorization": f"Bearer {code}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(asked) as answer:
            done: dict[str, Any] = json.loads(answer.read())
    except urllib.error.HTTPError as wrong:
        print(refusal(wrong.code), file=sys.stderr)
        return 2
    except (urllib.error.URLError, OSError) as wrong:
        print(NO_HELPER.format(url=url, wrong=wrong), file=sys.stderr)
        return 2
    said = str(done.get("stdout", ""))
    if argv == ["manifest"] and done.get("returncode") == 0:
        said = reached_from_here(said)
    sys.stdout.write(said)
    sys.stderr.write(str(done.get("stderr", "")))
    return int(done.get("returncode", 1))


def converse(url: str, code: str, with_it: list[str]) -> int:
    """Carries the engine's conversation with the driver: lines in from the engine, lines out to it."""
    there = url.replace("http", "ws", 1) + "/mcp?argv=" + urllib.parse.quote(json.dumps(with_it))
    try:
        socket = connect(there, additional_headers={"Authorization": f"Bearer {code}"}, max_size=None)
    except InvalidStatus as wrong:
        print(refusal(wrong.response.status_code), file=sys.stderr)
        return 2
    except (WebSocketException, OSError) as wrong:
        print(NO_HELPER.format(url=url, wrong=wrong), file=sys.stderr)
        return 2

    def answers() -> None:
        try:
            for line in socket:
                text = line if isinstance(line, str) else line.decode("utf-8", errors="replace")
                sys.stdout.write(text if text.endswith("\n") else text + "\n")
                sys.stdout.flush()
        except WebSocketException:
            return

    coming_back = threading.Thread(target=answers, daemon=True)
    coming_back.start()
    try:
        for line in sys.stdin:
            socket.send(line)
        socket.send(NO_MORE)
        coming_back.join()
    except WebSocketException:
        return 1
    finally:
        socket.close()
    return 0


def main(arguments: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if arguments is None else arguments)
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8", errors="replace")
    try:
        where = json.loads(Path(os.environ[FILE]).read_text(encoding="utf-8"))
        url, code = str(where["url"]).rstrip("/"), str(where["code"])
    except (KeyError, OSError, ValueError):
        print(f"The link was not told where the helper is: {FILE} names no readable file.", file=sys.stderr)
        return 2
    if argv[:1] == ["mcp"]:
        return converse(url, code, argv[1:])
    return ask(url, code, argv)


if __name__ == "__main__":
    sys.exit(main())
