import pytest

from bap_browser.config import Browser, Config, Proxy
from bap_browser.driver.playwright_driver import context_options, launch_options
from bap_browser.errors import ConfigError


def test_default_launch_uses_playwrights_chromium() -> None:
    assert launch_options(Config(), {}) == {
        "headless": True,
        "args": [],
        "chromium_sandbox": True,
        "timeout": 30000,
    }


def test_a_channel_other_than_chromium_is_passed_on() -> None:
    assert launch_options(Config(browser=Browser(channel="msedge")), {})["channel"] == "msedge"


def test_an_executable_path_replaces_the_channel() -> None:
    options = launch_options(Config(browser=Browser(channel="chrome", executable_path="C:/b/brave.exe")), {})
    assert options["executable_path"] == "C:/b/brave.exe"
    assert "channel" not in options


def test_custom_without_a_path_is_a_configuration_error() -> None:
    with pytest.raises(ConfigError, match=r"browser.executable_path is not set"):
        launch_options(Config(browser=Browser(channel="custom")), {})


def test_proxy_credentials_come_from_the_environment() -> None:
    config = Config(browser=Browser(proxy=Proxy(server="http://proxy:3128", bypass="*.local")))
    env = {"BAP_BROWSER_PROXY_USERNAME": "user", "BAP_BROWSER_PROXY_PASSWORD": "pass"}
    assert launch_options(config, env)["proxy"] == {
        "server": "http://proxy:3128",
        "bypass": "*.local",
        "username": "user",
        "password": "pass",
    }
    assert launch_options(config, {})["proxy"] == {"server": "http://proxy:3128", "bypass": "*.local"}


def test_default_context() -> None:
    assert context_options(Config()) == {
        "viewport": {"width": 1280, "height": 800},
        "ignore_https_errors": False,
        "java_script_enabled": True,
        "accept_downloads": True,
    }


def test_context_passes_the_emulation_settings_through() -> None:
    browser = Browser(
        viewport=None,
        locale="en-IN",
        timezone_id="Asia/Kolkata",
        color_scheme="dark",
        device_scale_factor=2,
        user_agent="agent/1",
        permissions=["clipboard-read"],
        extra_http_headers={"X-Test": "1"},
    )
    assert context_options(Config(browser=browser)) == {
        "no_viewport": True,
        "ignore_https_errors": False,
        "java_script_enabled": True,
        "accept_downloads": True,
        "locale": "en-IN",
        "timezone_id": "Asia/Kolkata",
        "color_scheme": "dark",
        "device_scale_factor": 2,
        "user_agent": "agent/1",
        "permissions": ["clipboard-read"],
        "extra_http_headers": {"X-Test": "1"},
    }
