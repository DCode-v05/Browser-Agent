"""Clear browsing data (spec 10.2): the cookies and site data of the cloud browser are deleted, and
that browser's open sessions end first, as the settings screen says before it is done.

A session with a fresh profile holds its data only while it runs, so ending it is all there is to
do. A kept profile is a folder, and is deleted once no browser is using it.
"""

from __future__ import annotations

import asyncio
import shutil
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from bap_browser.config import Config
from bap_browser.service.session import ServiceSession
from bap_browser.settings.kinds import CLOUD
from bap_browser.settings.store import SettingsStore

CLEAR = "clear_browsing_data"
# What the summary of an ended session says, in place of "You stopped it."
ENDED_TO_CLEAR = "It was ended to clear the browsing data."
# What a Chromium profile holds. A folder with neither is not one, and is left alone.
MARKS_OF_A_PROFILE = ("Local State", "Default")


def looks_like_a_profile(folder: Path) -> bool:
    """Whether a folder is a browser's profile. Only such a folder is ever deleted: the
    configuration names the folder, and a wrong name must not cost a person their files."""
    return folder.is_dir() and any((folder / mark).exists() for mark in MARKS_OF_A_PROFILE)


async def clear_browsing_data(
    config: Config, sessions: Mapping[str, ServiceSession], settings: SettingsStore
) -> dict[str, Any]:
    """Ends the cloud browser's sessions and deletes its kept profile. Says what was done."""
    # The profile a new session of the cloud browser would use, whether or not one is open now.
    kept = {settings.apply_to(config, CLOUD).browser.user_data_dir}
    ended = 0
    for session in list(sessions.values()):
        if session.backend != CLOUD or session.control == "ended":
            continue
        kept.add(session.config.browser.user_data_dir)
        # The browser has closed, and let go of its profile, when this returns.
        await session.close("person", ENDED_TO_CLEAR)
        ended += 1
    cleared = [named for named in kept if named and await asyncio.to_thread(_delete, named)]
    return {"sessions_ended": ended, "profile_cleared": bool(cleared)}


def _delete(named: str) -> bool:
    folder = Path(named).expanduser()
    if not looks_like_a_profile(folder):
        return False
    shutil.rmtree(folder, ignore_errors=True)
    return not folder.exists()
