"""An engine whose machine is elsewhere (spec 22.6.2): the link is named as the driver, and told
where the helper is and the pairing code in a file only the engine's user can read."""

from __future__ import annotations

import json
import os
import shutil
import sys
import urllib.request
from pathlib import Path

from bap_browser import private_file
from bap_browser.computer.link import FILE
from bap_browser.config_computer import Computer
from bap_browser.errors import BrowserError

LINK = "bap-browser-driver-link"
TOLD = "link.json"


def through_the_link(computer: Computer, home: Path) -> Computer:
    """The settings of computer use with the link in the driver's place. The pairing code is read
    from the variable the settings name, and written for the link alone."""
    code = os.environ.get(computer.helper_token_env, "")
    if not code:
        raise BrowserError(
            f"The pairing code of the helper on the other machine is not set. Put the code the helper "
            f"shows into {computer.helper_token_env}, in the environment or in `.env`.",
            reason="no pairing code",
        )
    link = shutil.which(LINK, path=str(Path(sys.executable).parent)) or shutil.which(LINK)
    if link is None:
        raise BrowserError(f"{LINK} is not installed beside the engine. Run `uv sync`.", reason="no link")
    private_file.write_json(home / TOLD, {"url": computer.helper_url.rstrip("/"), "code": code})
    os.environ[FILE] = str(home / TOLD)
    return computer.model_copy(update={"base": computer.base.model_copy(update={"driver_command": link})})


def forget(home: Path) -> None:
    """The work has ended: the code is kept nowhere."""
    (home / TOLD).unlink(missing_ok=True)
    os.environ.pop(FILE, None)


def system_of_the_machine(url: str, code: str, timeout_s: float) -> str | None:
    """Which system the machine elsewhere runs, as its driver's own program says: an app bundle is
    macOS, a program ending in .exe is Windows, any other is Linux. None when the helper does not say."""
    asked = urllib.request.Request(
        f"{url.rstrip('/')}/run",
        data=json.dumps({"argv": ["manifest"]}).encode(),
        headers={"Authorization": f"Bearer {code}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(asked, timeout=timeout_s) as answer:
            said = json.loads(json.loads(answer.read()).get("stdout") or "{}")
    except (OSError, ValueError, AttributeError):
        return None
    path = str(said.get("binary_path", ""))
    if not path:
        return None
    if ".app/Contents/" in path:
        return "darwin"
    if path.lower().endswith(".exe"):
        return "win32"
    return "linux"
