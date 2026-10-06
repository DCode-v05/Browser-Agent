"""Clear browsing data (spec 10.2): the cloud browser's sessions end, its kept profile is deleted, and
nothing else is touched."""

import asyncio
import json
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

from fakes import FakeDriver

from bap_browser.config import Config
from bap_browser.service.browsing_data import ENDED_TO_CLEAR, looks_like_a_profile
from bap_browser.service.server import Service
from bap_browser.service.session import ServiceSession
from bap_browser.settings import SettingsStore

TOKEN = "a-token-for-the-tests-0123456789abcdef"
MakeConfig = Callable[..., Config]


def a_profile(folder: Path) -> Path:
    """A folder as Chromium leaves one: what marks it as a profile, and a cookie."""
    (folder / "Default").mkdir(parents=True)
    (folder / "Local State").write_text("{}", encoding="utf-8")
    (folder / "Default" / "Cookies").write_text("signed in", encoding="utf-8")
    return folder


def post(url: str, token: str | None = TOKEN) -> tuple[int, Any]:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    request = urllib.request.Request(url, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as refused:
        return refused.code, json.loads(refused.read() or b"null")


async def test_the_cloud_browsers_sessions_end_and_its_kept_profile_is_deleted(
    make_config: MakeConfig, tmp_path: Path
) -> None:
    profile = a_profile(tmp_path / "kept-profile")
    config = make_config(tmp_path, browser={"user_data_dir": str(profile)})
    settings = SettingsStore(config)
    cloud = ServiceSession(config, FakeDriver(), name="cloud", settings=settings)
    # The built-in browser keeps a profile of its own, which this does not touch.
    own = a_profile(tmp_path / "built-in-browser")
    built_in_config = config.model_copy(
        update={"browser": config.browser.model_copy(update={"user_data_dir": str(own)})}
    )
    built_in = ServiceSession(
        built_in_config, FakeDriver(), name="builtin", backend="bundled_chromium", settings=settings
    )
    await cloud.start()
    await built_in.start()
    service = Service(config, {"cloud": cloud, "builtin": built_in}, token=TOKEN, port=0, settings=settings)
    await service.start()
    try:
        door = f"{service.address}/api/browsing-data/clear"
        # Deleting a person's sign-ins is for the person alone.
        assert (await asyncio.to_thread(post, door, None))[0] == 401
        assert (await asyncio.to_thread(post, door, "wrong"))[0] == 401
        assert cloud.control == "agent" and profile.exists()

        assert await asyncio.to_thread(post, door) == (200, {"sessions_ended": 1, "profile_cleared": True})
        assert cloud.control == "ended" and not profile.exists()
        ended = [item for item in cloud.hub.subscribe()[0] if isinstance(item, dict)][-1]
        assert ended["type"] == "session_ended" and ended["reason"] == "person"
        # The summary says why, in place of "You stopped it."
        assert ended["detail"] == ENDED_TO_CLEAR
        assert built_in.control == "agent" and (own / "Default" / "Cookies").exists()
        # A second time there is nothing left to end or to delete.
        assert await asyncio.to_thread(post, door) == (200, {"sessions_ended": 0, "profile_cleared": False})
    finally:
        await service.stop()
        await cloud.close()
        await built_in.close()


async def test_a_folder_that_is_not_a_profile_is_never_deleted(
    make_config: MakeConfig, tmp_path: Path
) -> None:
    """The configuration names the folder. A wrong name must not cost a person their files."""
    documents = tmp_path / "documents"
    documents.mkdir()
    (documents / "thesis.txt").write_text("years of work", encoding="utf-8")
    assert not looks_like_a_profile(documents) and not looks_like_a_profile(tmp_path / "nothing-there")
    config = make_config(tmp_path, browser={"user_data_dir": str(documents)})
    settings = SettingsStore(config)
    session = ServiceSession(config, FakeDriver(), settings=settings)
    await session.start()
    service = Service(config, {"default": session}, token=TOKEN, port=0, settings=settings)
    await service.start()
    try:
        answer = await asyncio.to_thread(post, f"{service.address}/api/browsing-data/clear")
        # The session ended, which is all a browser with nothing kept needs.
        assert answer == (200, {"sessions_ended": 1, "profile_cleared": False})
        assert (documents / "thesis.txt").read_text(encoding="utf-8") == "years of work"
    finally:
        await service.stop()
        await session.close()


async def test_a_profile_kept_by_staying_signed_in_is_deleted_with_no_session_open(
    make_config: MakeConfig, tmp_path: Path
) -> None:
    kept = a_profile(tmp_path / "home" / "browser-profile")
    config = make_config(tmp_path, browser={"kept_profile_dir": str(kept)})
    settings = SettingsStore(config)
    settings.change("web", {"stay_signed_in": True})
    service = Service(config, {}, token=TOKEN, port=0, settings=settings)
    await service.start()
    try:
        answer = await asyncio.to_thread(post, f"{service.address}/api/browsing-data/clear")
        assert answer == (200, {"sessions_ended": 0, "profile_cleared": True})
        assert not kept.exists()
    finally:
        await service.stop()


async def test_a_deployment_can_lock_it_and_a_service_without_settings_has_none(
    make_config: MakeConfig, tmp_path: Path
) -> None:
    profile = a_profile(tmp_path / "kept-profile")
    locked = make_config(
        tmp_path,
        browser={"user_data_dir": str(profile)},
        settings={"locked": ["clear_browsing_data"], "file": str(tmp_path / "settings.json")},
    )
    service = Service(locked, {}, token=TOKEN, port=0, settings=SettingsStore(locked))
    await service.start()
    try:
        answer = await asyncio.to_thread(post, f"{service.address}/api/browsing-data/clear")
        assert answer == (409, {"setting": "clear_browsing_data", "reason": "locked"})
        assert profile.exists()
    finally:
        await service.stop()
    bare = Service(locked, {}, token=TOKEN, port=0)
    await bare.start()
    try:
        assert (await asyncio.to_thread(post, f"{bare.address}/api/browsing-data/clear"))[0] == 404
        assert profile.exists()
    finally:
        await bare.stop()
