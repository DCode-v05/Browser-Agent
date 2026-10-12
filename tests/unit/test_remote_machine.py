"""An engine that drives a machine elsewhere (spec 22.6.2): it starts the link in the driver's place,
and the pairing code goes to the link in a file of its own and to nothing else."""

from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path

import pytest

from bap_browser import computer
from bap_browser.computer.seams.driver_package import installed_package
from bap_browser.config import Config
from bap_browser.errors import BrowserError


def elsewhere(tmp_path: Path) -> Config:
    settings = {
        "runs": "remote",
        "helper_url": "https://desk.tail1234.ts.net:8796",
        "base": {"home": str(tmp_path)},
    }
    return Config.model_validate({"computer": settings})


def test_the_engine_starts_the_link_in_the_drivers_place(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("BAP_BROWSER_HELPER_TOKEN", "the-pairing-code")

    with computer.base(elsewhere(tmp_path)):
        driver = installed_package("cua-driver")
        told = json.loads((tmp_path / "link.json").read_text(encoding="utf-8"))

    assert driver is not None and driver.binary.name.startswith("bap-browser-driver-link")
    assert told == {"url": "https://desk.tail1234.ts.net:8796", "code": "the-pairing-code"}


def test_the_code_is_in_a_file_for_the_engines_user_alone_and_gone_when_the_work_ends(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("BAP_BROWSER_HELPER_TOKEN", "the-pairing-code")

    with computer.base(elsewhere(tmp_path)):
        file = tmp_path / "link.json"
        mode = stat.S_IMODE(file.stat().st_mode)
        environment = computer.driver_environment()

    if sys.platform != "win32":
        assert mode == 0o600
    assert environment["BAP_BROWSER_LINK_FILE"] == str(file)
    assert "the-pairing-code" not in json.dumps(environment)
    assert not file.exists()
    assert "BAP_BROWSER_LINK_FILE" not in os.environ


def test_without_the_code_the_engine_says_where_it_is_to_be_put(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("BAP_BROWSER_HELPER_TOKEN", raising=False)

    with pytest.raises(BrowserError, match="BAP_BROWSER_HELPER_TOKEN"), computer.base(elsewhere(tmp_path)):
        pass
