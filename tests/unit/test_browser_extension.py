"""The extension that ships with bap-browser: its files, its id, and how a session is made known to it."""

import base64
import hashlib
import json
from collections.abc import Callable
from pathlib import Path

from bap_browser import browser_extension
from bap_browser.config import Config


def test_the_extension_is_copied_to_where_a_browser_loads_it(tmp_path: Path) -> None:
    folder = browser_extension.install(tmp_path / "extension")
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["manifest_version"] == 3
    assert manifest["side_panel"] == {"default_path": "panel.html"}
    # The side panel for the chat; the debugger, the tabs and their groups for take-over Chrome,
    # where the extension attaches to the one tab it opened for the agent. No site is named:
    # it reads no page by itself.
    # Storage keeps the sites the person allowed, on their own machine; the alarm lets the background
    # look for a session while no panel is open.
    assert manifest["permissions"] == ["sidePanel", "debugger", "tabs", "tabGroups", "storage", "alarms"]
    assert "host_permissions" not in manifest
    named = [
        manifest["background"]["service_worker"],
        manifest["side_panel"]["default_path"],
        *manifest["content_scripts"][0]["js"],
        *manifest["icons"].values(),
    ]
    for name in ["panel.js", *named]:
        assert (folder / name).is_file(), name
    assert not (folder / "session.json").exists()


def test_the_id_follows_from_the_key_in_the_manifest(tmp_path: Path) -> None:
    manifest = json.loads(
        (browser_extension.install(tmp_path / "x") / "manifest.json").read_text(encoding="utf-8")
    )
    digest = hashlib.sha256(base64.b64decode(manifest["key"])).hexdigest()[:32]
    assert "".join(chr(ord("a") + int(digit, 16)) for digit in digest) == browser_extension.EXTENSION_ID


def test_a_configuration_with_the_extension_loads_it_and_lets_it_show_the_viewer(
    make_config: Callable[..., Config], tmp_path: Path
) -> None:
    folder = tmp_path / "state" / "extension"
    given = make_config(
        tmp_path, browser={"args": ["--lang=en"]}, viewer={"embed_origins": ["https://app.example.com"]}
    )
    config = browser_extension.with_extension(given, folder)
    assert config.browser.args == [
        "--lang=en",
        f"--disable-extensions-except={folder}",
        f"--load-extension={folder}",
    ]
    # Not under the project folder: on Windows the browser gives up on a profile whose files have
    # paths longer than 260 characters, and a project folder can be deep.
    assert config.browser.user_data_dir == str(Path.home() / ".bap-browser" / "browser-profile")
    elsewhere = make_config(tmp_path, browser={"kept_profile_dir": str(tmp_path / "kept")})
    assert browser_extension.with_extension(elsewhere, folder).browser.user_data_dir == str(tmp_path / "kept")
    assert config.viewer.embed_origins == [
        "https://app.example.com",
        "chrome-extension://" + browser_extension.EXTENSION_ID,
    ]
    assert given.browser.args == ["--lang=en"] and given.browser.user_data_dir is None

    kept = browser_extension.with_extension(
        make_config(tmp_path, browser={"user_data_dir": "my-profile"}), folder
    )
    assert kept.browser.user_data_dir == "my-profile", "a profile the person chose is the one used"


def test_a_session_is_made_known_to_the_extension_and_forgotten_again(tmp_path: Path) -> None:
    folder = browser_extension.install(tmp_path / "extension")
    browser_extension.announce(folder, "http://127.0.0.1:8123/#token=abc")
    assert json.loads((folder / "session.json").read_text(encoding="utf-8")) == {
        "viewer": "http://127.0.0.1:8123/?embed=1#token=abc"
    }
    browser_extension.forget(folder)
    assert not (folder / "session.json").exists()
    browser_extension.forget(folder)

    # For take-over Chrome it is also told where to dial in, and with which token.
    browser_extension.announce(folder, bridge="ws://127.0.0.1:8123/bridge", token="abc")
    assert json.loads((folder / "session.json").read_text(encoding="utf-8")) == {
        "bridge": "ws://127.0.0.1:8123/bridge",
        "token": "abc",
    }

    # Installing again never leaves an old session's address behind.
    browser_extension.announce(folder, "http://127.0.0.1:8123/#token=abc")
    browser_extension.install(folder)
    assert not (folder / "session.json").exists()


def test_the_folder_a_person_loads_the_extension_from_is_one_a_file_chooser_shows(tmp_path: Path) -> None:
    """A folder whose name begins with a dot is hidden from the browser's file chooser on a Mac and
    on Linux: a person could not choose it."""
    from bap_browser.cli import _extension_folder  # pyright: ignore[reportPrivateUsage]
    from bap_browser.config import Config, Server

    default = _extension_folder(Config())
    assert default.is_absolute()
    assert not default.name.startswith("."), default
    assert not any(part.startswith(".") for part in Path(Config().server.extension_dir).parts)
    chosen = _extension_folder(Config(server=Server(extension_dir=str(tmp_path / "ext"))))
    assert chosen == (tmp_path / "ext").resolve()
