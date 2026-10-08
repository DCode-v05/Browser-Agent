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
