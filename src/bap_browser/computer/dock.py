"""The dock: the program the engine starts in the driver's place when the desktop is the contained
one, in a container of its own (spec 22.2, arrangement B). Hermes' code starts the driver as a
program on its own machine and talks to it over a pipe; for the contained desktop it starts this
instead, which carries that pipe through `docker exec` into the container where the driver runs.
The container's name is in `BAP_BROWSER_DOCK_CONTAINER`.
"""

from __future__ import annotations

import os
import subprocess
import sys

CONTAINER = "BAP_BROWSER_DOCK_CONTAINER"
DRIVER = "cua-driver"


def main(arguments: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if arguments is None else arguments)
    container = os.environ.get(CONTAINER, "")
    if not container:
        print(f"The dock was not told its container: {CONTAINER} names none.", file=sys.stderr)
        return 2
    try:
        run = subprocess.run(["docker", "exec", "-i", container, DRIVER, *argv])
    except OSError as wrong:
        print(f"docker could not be run: {wrong}", file=sys.stderr)
        return 2
    return run.returncode


if __name__ == "__main__":
    sys.exit(main())
