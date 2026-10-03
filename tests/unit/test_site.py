import urllib.request
from collections.abc import Callable
from pathlib import Path

from bap_browser.config import Config


def test_the_site_serves_the_form(site: str) -> None:
    with urllib.request.urlopen(f"{site}/form.html") as response:
        assert response.status == 200
        assert b"<title>Sign up</title>" in response.read()


def test_make_config_keeps_files_in_its_folder(make_config: Callable[..., Config], tmp_path: Path) -> None:
    config = make_config(tmp_path, browser={"timeouts": {"action_ms": 600}})
    assert config.data_dir == str(tmp_path)
    assert config.logging.event_log == str(tmp_path / "events.jsonl")
    assert config.browser.timeouts.action_ms == 600
    assert config.browser.timeouts.navigation_ms == 30000
