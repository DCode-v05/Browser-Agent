"""Shared fixtures: the local test site, and configurations that keep their files in a temporary folder."""

from __future__ import annotations

import functools
import json
import os
import threading
from collections.abc import Callable, Iterator
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

from bap_browser.config import ENV_PREFIX, Config, load_config

SITE = Path(__file__).parent / "site"


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        """The test site writes nothing to the test output."""


@pytest.fixture(autouse=True)
def the_environment_is_left_as_it_was() -> Iterator[None]:
    """The command adds a .env file's settings to the process's environment. No test may leave any behind."""
    before = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(before)


@pytest.fixture(scope="session")
def site() -> Iterator[str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(QuietHandler, directory=str(SITE)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()
    thread.join()


def write_config(folder: Path, **sections: Any) -> Path:
    """A config.json in `folder` that keeps every file the engine writes inside that folder."""
    data: dict[str, Any] = {"data_dir": str(folder), "logging": {"event_log": str(folder / "events.jsonl")}}
    data.update(sections)
    # The file that says where a service is, too: the developer may have a service of their own running.
    data["server"] = {"state_file": str(folder / "service.json"), **data.get("server", {})}
    # And what a person saved in the settings screen: the developer's own must not reach a test.
    data["settings"] = {"file": str(folder / "settings.json"), **data.get("settings", {})}
    # And the records of what each browser of the window did, and their logs.
    data["evals"] = {"dir": str(folder / "evals"), **data.get("evals", {})}
    # And who may sign in: a test never reads or changes the developer's own passwords.
    data["auth"] = {"file": str(folder / "accounts.json"), **data.get("auth", {})}
    data["logging"] = {"systems_dir": str(folder / "logs"), **data.get("logging", {})}
    # Most tests say exactly what a result holds. The marks around what a page wrote (spec 18.5) are
    # left out of those, and tested where they are what the test is about.
    guards = dict(data.get("safeguards", {}))
    guards["incoming"] = {"mark_page_text": False, **guards.get("incoming", {})}
    data["safeguards"] = guards
    path = folder / "config.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def passed_through_env() -> dict[str, str]:
    """Settings given to the test run itself, such as turning the browser sandbox off in CI."""
    return {name: value for name, value in os.environ.items() if name.startswith(ENV_PREFIX)}


@pytest.fixture(scope="session")
def make_config() -> Callable[..., Config]:
    def make(folder: Path, **sections: Any) -> Config:
        return load_config(write_config(folder, **sections), env=passed_through_env())

    return make
