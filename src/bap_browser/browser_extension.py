"""The browser extension that ships with bap-browser: the chat in the browser's side panel, and on
each page a sign of who is driving (spec 9.15).

This module puts the extension's files where the browser loads them from, and tells the extension
where the session is. The extension drives nothing: the agent works through the driver as always.
"""

from __future__ import annotations

import json
import shutil
from importlib.resources import as_file, files
from pathlib import Path

from bap_browser.config import Config

# The id Chrome gives the extension. It follows from the key in the extension's manifest, so it is
# the same on every machine, and the service can name the extension as a page allowed to show the viewer.
EXTENSION_ID = "fjbcdokiffgniclpchjjboebdfabkoak"
ORIGIN = f"chrome-extension://{EXTENSION_ID}"
SESSION_FILE = "session.json"


def install(folder: Path) -> Path:
    """Copies the extension into a folder a browser can load it from. Returns that folder."""
    with as_file(files("bap_browser") / "extension") as source:
        shutil.copytree(source, folder, dirs_exist_ok=True)
    forget(folder)
    return folder


def with_extension(config: Config, folder: Path) -> Config:
    """The same configuration with the extension loaded into the browser, in a profile that is kept
    (the browser loads an extension only into such a profile), and with the extension allowed to show
    the viewer inside its side panel."""
    browser = config.browser.model_copy(
        update={
            "user_data_dir": config.browser.user_data_dir
            or str(Path(config.browser.kept_profile_dir).expanduser()),
            "args": [
                *config.browser.args,
                f"--disable-extensions-except={folder}",
                f"--load-extension={folder}",
            ],
        }
    )
    return may_show_viewer(config.model_copy(update={"browser": browser}))


def may_show_viewer(config: Config) -> Config:
    """The same configuration with the extension allowed to show the viewer inside its side panel."""
    viewer = config.viewer.model_copy(update={"embed_origins": [*config.viewer.embed_origins, ORIGIN]})
    return config.model_copy(update={"viewer": viewer})


def announce(
    folder: Path, viewer_address: str | None = None, *, bridge: str | None = None, token: str | None = None
) -> None:
    """Tells the extension where the session's viewer is and, for take-over Chrome, where it dials in
    as the bridge and with which token. The file carries the session's token, so it is removed again
    when the session ends."""
    told: dict[str, str] = {}
    if viewer_address is not None:
        # Inside the side panel the viewer is a guest: it drops its own product name.
        told["viewer"] = viewer_address.replace("/#", "/?embed=1#", 1)
    if bridge is not None:
        told["bridge"] = bridge
    if token is not None:
        # A pairing token: it lets the extension in once, and soon runs out.
        told["token"] = token
    (folder / SESSION_FILE).write_text(json.dumps(told), encoding="utf-8")


def forget(folder: Path) -> None:
    (folder / SESSION_FILE).unlink(missing_ok=True)
