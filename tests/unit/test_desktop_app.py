"""The desktop app as the window of three browsers opens it (spec 9.16): a program of its own, started
once, with nothing from the editor's environment that would keep its window from opening."""

import json
import sys
import time
from pathlib import Path

import pytest

from bap_browser.desktop_app import DesktopApp
from bap_browser.errors import BapError

# Stands in for the app: it says what it was started with, and stays open until it is ended.
STAND_IN = """
import json, os, threading
from pathlib import Path

Path(__file__).parent.joinpath("started.json").write_text(
    json.dumps(
        {
            "as_node": os.environ.get("ELECTRON_RUN_AS_NODE"),
            "state_file": os.environ.get("BAP_BROWSER__SERVER__STATE_FILE"),
            "folder": os.getcwd(),
        }
    ),
    encoding="utf-8",
)
threading.Event().wait()
"""


def app_in(folder: Path, *, built: bool = True) -> DesktopApp:
    if built:
        (folder / "dist").mkdir(parents=True)
        (folder / "dist" / "index.html").write_text("<!doctype html>", encoding="utf-8")
    return DesktopApp(folder, folder / "state" / "desktop-service.json", close_wait_s=5)


def started(folder: Path) -> dict[str, str | None]:
    """What the stand-in was started with, once it has said so."""
    said = folder / "started.json"
    for _ in range(200):
        if said.is_file() and said.read_text(encoding="utf-8"):
            return json.loads(said.read_text(encoding="utf-8"))
        time.sleep(0.05)
    raise AssertionError("the app was not started")


def test_electron_is_found_where_the_apps_packages_put_it(tmp_path: Path) -> None:
    app = app_in(tmp_path)
    assert app.program() is None and not app.there

    electron = tmp_path / "node_modules" / "electron"
    (electron / "dist" / "Electron.app").mkdir(parents=True)
    (electron / "path.txt").write_text("Electron.app/Electron", encoding="utf-8")
    assert app.program() is None, "the packages name a program that was never downloaded"

    (electron / "dist" / "Electron.app" / "Electron").write_text("", encoding="utf-8")
    assert app.program() == electron / "dist" / "Electron.app" / "Electron"
    assert app.there


def test_an_app_whose_shell_is_not_built_is_not_there(tmp_path: Path) -> None:
    electron = tmp_path / "node_modules" / "electron"
    (electron / "dist").mkdir(parents=True)
    (electron / "dist" / "electron").write_text("", encoding="utf-8")
    (electron / "path.txt").write_text("electron", encoding="utf-8")
    assert not app_in(tmp_path, built=False).there


def test_an_app_that_is_not_installed_says_how_to_install_it(tmp_path: Path) -> None:
    with pytest.raises(BapError, match="npm --prefix desktop install"):
        app_in(tmp_path).start()


def test_it_is_opened_once_and_can_be_opened_again_after_it_was_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "__main__.py").write_text(STAND_IN, encoding="utf-8")
    # Python, given the folder, runs the stand-in there, as Electron runs the app in its folder.
    monkeypatch.setattr(DesktopApp, "program", lambda self: Path(sys.executable))
    # What an editor built on Electron sets for the programs it starts.
    monkeypatch.setenv("ELECTRON_RUN_AS_NODE", "1")
    app = app_in(tmp_path)
    try:
        assert app.start() is True
        told = started(tmp_path)
        assert told["as_node"] is None, "with it, Electron would run as Node and open no window"
        # Its core says where it is in a file of its own, not in the one of the service that opened it.
        assert told["state_file"] == str(tmp_path / "state" / "desktop-service.json")
        assert told["folder"] is not None and Path(told["folder"]).resolve() == tmp_path.resolve()

        assert app.open
        assert app.start() is False, "the one that is open is the one"

        app.close()
        assert not app.open
        (tmp_path / "started.json").unlink()
        assert app.start() is True
        started(tmp_path)
    finally:
        app.close()
    assert not app.open


def test_closing_an_app_that_was_never_opened_does_nothing(tmp_path: Path) -> None:
    app_in(tmp_path).close()


# Stands in for the side chat: it says what it was started with, and stays open until it is ended.
SIDE_STAND_IN = """
import json, os, sys, threading
from pathlib import Path

Path(__file__).parent.joinpath("side.json").write_text(
    json.dumps(
        {
            "chat": os.environ.get("BAP_SIDE_CHAT"),
            "width": os.environ.get("BAP_SIDE_CHAT_WIDTH"),
            "as_node": os.environ.get("ELECTRON_RUN_AS_NODE"),
        }
    ),
    encoding="utf-8",
)
threading.Event().wait()
"""
THE_CHAT = "http://127.0.0.1:8765/?session=computer&beside#token=a-visit"


def said_by_the_side(folder: Path) -> dict[str, str | None]:
    said = folder / "electron" / "side.json"
    for _ in range(200):
        if said.is_file() and said.read_text(encoding="utf-8"):
            return json.loads(said.read_text(encoding="utf-8"))
        time.sleep(0.05)
    raise AssertionError("the side chat was not started")


def test_the_chat_is_opened_in_a_window_of_its_own_above_the_other_apps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """While the agent works in Safari or any other app of this machine, the chat stays with the
    person (spec 22.3.1). It is one window: asked again, the one that is open is the one."""
    (tmp_path / "electron").mkdir()
    (tmp_path / "electron" / "side.cjs").write_text(SIDE_STAND_IN, encoding="utf-8")
    monkeypatch.setattr(DesktopApp, "program", lambda self: Path(sys.executable))
    monkeypatch.setenv("ELECTRON_RUN_AS_NODE", "1")
    app = app_in(tmp_path)
    try:
        assert app.chat_beside(THE_CHAT, 400) is True
        told = said_by_the_side(tmp_path)
        assert (told["chat"], told["width"], told["as_node"]) == (THE_CHAT, "400", None)
        assert app.chat_beside(THE_CHAT, 400) is False
    finally:
        app.close()


def test_a_side_chat_with_no_app_installed_says_how_to_install_it(tmp_path: Path) -> None:
    with pytest.raises(BapError, match="npm --prefix desktop install"):
        DesktopApp(tmp_path, tmp_path / "s.json", close_wait_s=1).chat_beside(THE_CHAT, 400)


# Stands in for the side chat when it is run to its end: it says what it was started with, and ends.
SIDE_THAT_ENDS = SIDE_STAND_IN.replace("threading.Event().wait()", "sys.exit(0)")


def test_a_person_opens_the_chat_of_a_service_elsewhere_from_their_own_machine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The engine in a micro VM cannot open a window on the person's Mac. The person opens the chat
    there themselves, by the service's address, and it stays above their apps (spec 22.6)."""
    (tmp_path / "electron").mkdir()
    (tmp_path / "electron" / "side.cjs").write_text(SIDE_THAT_ENDS, encoding="utf-8")
    monkeypatch.setattr(DesktopApp, "program", lambda self: Path(sys.executable))

    ended = app_in(tmp_path).chat_beside_until_closed("https://vm.tail1234.ts.net/", "computer", 400)

    assert ended == 0
    assert said_by_the_side(tmp_path)["chat"] == "https://vm.tail1234.ts.net/?session=computer&beside"


@pytest.mark.parametrize("service", ["vm.tail1234.ts.net", "file:///etc/passwd", "", "ftp://vm:8765"])
def test_what_is_no_address_of_a_service_is_refused_before_anything_is_opened(
    tmp_path: Path, service: str
) -> None:
    with pytest.raises(BapError, match="http:// or https://"):
        app_in(tmp_path).chat_beside_until_closed(service, "computer", 400)
