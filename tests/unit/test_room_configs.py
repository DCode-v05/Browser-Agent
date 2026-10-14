"""How each page of the window has its browser set up, before a person's settings (spec 9.16)."""

from bap_browser.agent.room_configs import built_in_config
from bap_browser.config import Config


def test_the_built_in_browser_starts_its_own_with_no_cdp_url() -> None:
    config = Config.model_validate({"browser": {"cdp_url": "http://127.0.0.1:19200"}})

    given = built_in_config(config)

    assert given.browser.cdp_url is None
    assert given.browser.headless is True


def test_the_desktop_apps_shell_keeps_the_cdp_url_it_was_given() -> None:
    """The desktop app's own browser is a real window it shows itself; the room attaches to it
    instead of starting one of its own (spec 14.3)."""
    config = Config.model_validate({"browser": {"cdp_url": "http://127.0.0.1:19200"}})

    given = built_in_config(config, keep_cdp=True)

    assert given.browser.cdp_url == "http://127.0.0.1:19200"
    assert given.browser.headless is True
