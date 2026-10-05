import json
from pathlib import Path
from typing import Any

import pytest

from bap_browser.config import Config, defaults, load_config, load_config_with_sources
from bap_browser.errors import ConfigError

SPEC_DEFAULTS: dict[str, Any] = {
    "data_dir": ".bap-browser",
    "backend.kind": "remote_headless",
    "backend.offered": ["remote_headless"],
    "browser.channel": "chromium",
    "browser.executable_path": None,
    "browser.headless": True,
    "browser.chromium_sandbox": True,
    "browser.cdp_url": None,
    "browser.cdp_target": None,
    "browser.user_data_dir": None,
    "browser.kept_profile_dir": "~/.bap-browser/browser-profile",
    "browser.args": [],
    "browser.viewport": {"width": 1280, "height": 800},
    "browser.permissions": [],
    "browser.ignore_https_errors": False,
    "browser.javascript_enabled": True,
    "browser.proxy.server": None,
    "browser.timeouts.launch_ms": 30000,
    "browser.timeouts.navigation_ms": 30000,
    "browser.timeouts.action_ms": 10000,
    "browser.timeouts.load_wait_ms": 5000,
    "browser.timeouts.settle_ms": 3000,
    "browser.timeouts.frame_ms": 100,
    "browser.timeouts.page_reply_ms": 5000,
    "browser.timeouts.popup_adopt_ms": 3000,
    "browser.timeouts.wait_max_s": 30,
    "browser.timeouts.idle_session_s": 900,
    "browser.snapshot.default_mode": "interactive",
    "browser.snapshot.max_chars": 20000,
    "browser.snapshot.max_depth": 60,
    "browser.snapshot.max_name_chars": 120,
    "browser.snapshot.max_value_chars": 200,
    "browser.snapshot.max_text_chars": 300,
    "browser.snapshot.max_options": 25,
    "browser.snapshot.max_frame_depth": 4,
    "browser.snapshot.include_iframes": True,
    "browser.snapshot.include_shadow_dom": True,
    "browser.snapshot.include_bboxes": False,
    "browser.snapshot.after_navigation": True,
    "browser.snapshot.after_action": False,
    "browser.screenshot.format": "png",
    "browser.screenshot.jpeg_quality": 80,
    "browser.screenshot.max_dimension": 1568,
    "browser.screenshot.full_page": False,
    "browser.screenshot.annotate_by_default": False,
    "browser.text.max_chars": 20000,
    "browser.find.default_limit": 10,
    "browser.find.max_limit": 50,
    "browser.capture.console": True,
    "browser.capture.network": True,
    "browser.capture.max_console_entries": 500,
    "browser.capture.max_network_entries": 500,
    "browser.capture.max_entry_chars": 2000,
    "browser.tabs.max_tabs": 20,
    "browser.tabs.focus_new_tabs": True,
    "browser.dialogs.policy": "agent",
    "browser.dialogs.timeout_s": 120,
    "browser.dialogs.default_prompt_text": "",
    "browser.downloads.enabled": True,
    "browser.downloads.dir": ".bap-browser/downloads",
    "browser.downloads.max_size_mb": 500,
    "browser.uploads.enabled": True,
    "browser.uploads.allowed_dirs": [".bap-browser/uploads"],
    "browser.javascript.allow_evaluate": False,
    "browser.javascript.max_result_chars": 20000,
    "browser.input.scroll_step_px": 400,
    "browser.input.type_delay_ms": 0,
    "browser.input.slow_type_delay_ms": 40,
    "browser.input.drag_steps": 15,
    "browser.input.key_repeat_max": 100,
    "safety.allowed_domains": [],
    "safety.blocked_domains": [],
    "safety.allowed_schemes": ["http", "https", "about", "data", "blob"],
    "safety.allow_file_urls": False,
    "safety.block_private_networks": False,
    "safety.block_cloud_metadata": True,
    "safety.enforce_on_subresources": False,
    "safety.policy_cache_s": 5,
    "safety.default_action_policy": "allow",
    "safety.action_policies": {"browser_evaluate": "confirm", "browser_upload_file": "confirm"},
    "safety.ask_before": "risky",
    "safety.redact_patterns": [],
    "control.hold_timeout_s": 300,
    "control.approval_timeout_s": 180,
    "permissions.consequential_words": [
        "pay",
        "buy",
        "order",
        "purchase",
        "checkout",
        "subscribe",
        "send",
        "delete",
        "remove",
        "transfer",
        "confirm",
        "publish",
        "authorize",
        "authorise",
        "grant",
    ],
    "control.approval_timeout_choices_s": [60, 180, 300, 600],
    "control.handoff_timeout_s": 900,
    "control.approval_without_viewer": "deny",
    "control.site_grant_lifetime": "session",
    "sessions.max_concurrent": 4,
    "server.host": "127.0.0.1",
    "server.public_url": None,
    "server.port": 8765,
    "server.token_env": "BAP_BROWSER_TOKEN",
    "server.state_file": ".bap-browser/service.json",
    "server.auth_wait_s": 10,
    "server.shutdown_wait_s": 3,
    "server.command_backlog": 256,
    "mcp.server_name": "bap-browser",
    "mcp.http_path": "/mcp",
    "viewer.quality": "standard",
    "viewer.quality_levels.standard": {"max_fps": 24, "jpeg_quality": 70, "max_width": 1280},
    "viewer.quality_levels.data_saver": {"max_fps": 8, "jpeg_quality": 50, "max_width": 800},
    "viewer.quality_levels.high": {"max_fps": 30, "jpeg_quality": 85, "max_width": 1600},
    "viewer.history_events": 500,
    "viewer.stale_after_s": 5,
    "viewer.idle_divider_s": 10,
    "viewer.picture_heartbeat_s": 2,
    "viewer.takeover.release_chord": "Ctrl+Alt+Enter",
    "viewer.theme": "system",
    "viewer.embed_origins": [],
    "viewer.pointer_hold_ms": 600,
    "viewer.show_agent_pointer": True,
    "agent.provider": "openai",
    "agent.model": "gpt-5.6-luna",
    "agent.api_key_env": "OPENAI_API_KEY",
    "agent.base_url": "https://api.openai.com/v1",
    "agent.request_timeout_s": 120,
    "agent.max_steps": 40,
    "agent.max_tokens": 4096,
    "agent.max_task_chars": 4000,
    "settings.file": ".bap-browser/settings.json",
    "settings.locked": [],
    "logging.level": "INFO",
    "logging.event_log": ".bap-browser/events.jsonl",
    "logging.log_tool_args": True,
    "logging.max_result_chars": 2000,
    "bench.runs": 30,
    "bench.warmup": 5,
    "bench.budget_file": "perf/budget.json",
    "bench.results_dir": ".bap-browser/bench",
}


def lookup(config: Config, dotted: str) -> Any:
    node: Any = config.model_dump()
    for part in dotted.split("."):
        node = node[part]
    return node


def write(path: Path, data: object) -> Path:
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


@pytest.mark.parametrize("key", sorted(SPEC_DEFAULTS))
def test_default_matches_the_spec(key: str) -> None:
    assert lookup(defaults(), key) == SPEC_DEFAULTS[key]


def test_no_file_means_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert load_config(env={}) == defaults()


def test_file_in_the_working_folder_is_found(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    write(tmp_path / "config.json", {"browser": {"headless": False}})
    assert load_config(env={}).browser.headless is False


def test_file_named_by_the_environment_is_used(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    file = write(tmp_path / "elsewhere.json", {"browser": {"channel": "chrome"}})
    assert load_config(env={"BAP_BROWSER_CONFIG": str(file)}).browser.channel == "chrome"


def test_nested_sections_merge_and_lists_are_replaced(tmp_path: Path) -> None:
    file = write(
        tmp_path / "config.json",
        {
            "browser": {"args": ["--a"], "timeouts": {"action_ms": 500}},
            "safety": {"action_policies": {"browser_evaluate": "deny"}},
            "viewer": {"quality_levels": {"standard": {"max_fps": 12}}},
        },
    )
    config = load_config(file, env={})
    assert config.browser.args == ["--a"]
    assert config.browser.timeouts.action_ms == 500
    assert config.browser.timeouts.navigation_ms == 30000
    assert config.safety.action_policies == {"browser_evaluate": "deny", "browser_upload_file": "confirm"}
    assert config.viewer.quality_levels.standard.max_fps == 12
    assert config.viewer.quality_levels.standard.max_width == 1280


def test_a_null_viewport_means_sized_to_the_window(tmp_path: Path) -> None:
    file = write(tmp_path / "config.json", {"browser": {"viewport": None}})
    assert load_config(file, env={}).browser.viewport is None


def test_environment_wins_over_the_file(tmp_path: Path) -> None:
    file = write(tmp_path / "config.json", {"browser": {"headless": True, "channel": "chrome"}})
    env = {"BAP_BROWSER__BROWSER__HEADLESS": "false", "BAP_BROWSER__BROWSER__CHANNEL": "msedge"}
    config = load_config(file, env=env)
    assert config.browser.headless is False
    assert config.browser.channel == "msedge"


def test_session_options_win_over_the_environment(tmp_path: Path) -> None:
    file = write(tmp_path / "config.json", {})
    config = load_config(
        file, env={"BAP_BROWSER__BROWSER__HEADLESS": "false"}, session={"browser.headless": True}
    )
    assert config.browser.headless is True


def test_a_setting_outside_the_session_list_is_refused(tmp_path: Path) -> None:
    file = write(tmp_path / "config.json", {})
    with pytest.raises(ConfigError, match=r"'safety.block_private_networks' cannot be set per session"):
        load_config(file, env={}, session={"safety.block_private_networks": False})


def test_unknown_key_names_the_key_and_where_it_came_from(tmp_path: Path) -> None:
    file = write(tmp_path / "config.json", {"browser": {"headles": True}})
    with pytest.raises(ConfigError, match=r"unknown setting 'browser.headles' \(from config.json\)"):
        load_config(file, env={})


def test_unknown_key_from_the_environment_is_named(tmp_path: Path) -> None:
    file = write(tmp_path / "config.json", {})
    with pytest.raises(ConfigError, match=r"unknown setting 'browser.nope' \(from environment\)"):
        load_config(file, env={"BAP_BROWSER__BROWSER__NOPE": "1"})


def test_bad_value_names_the_key(tmp_path: Path) -> None:
    file = write(tmp_path / "config.json", {"browser": {"viewport": {"width": "wide"}}})
    with pytest.raises(ConfigError, match=r"bad value for 'browser.viewport.width' \(from config.json\)"):
        load_config(file, env={})


def test_invalid_json_reports_the_file_and_the_line(tmp_path: Path) -> None:
    file = tmp_path / "config.json"
    file.write_text('{\n  "browser": {,\n}', encoding="utf-8")
    with pytest.raises(ConfigError, match=r"config.json: not valid JSON \(line 2"):
        load_config(file, env={})


def test_top_level_must_be_an_object(tmp_path: Path) -> None:
    file = tmp_path / "config.json"
    file.write_text("[1, 2]", encoding="utf-8")
    with pytest.raises(ConfigError, match="the top level must be an object"):
        load_config(file, env={})


def test_a_byte_order_mark_is_accepted(tmp_path: Path) -> None:
    file = tmp_path / "config.json"
    file.write_bytes(b"\xef\xbb\xbf" + b'{"browser": {"headless": false}}')
    assert load_config(file, env={}).browser.headless is False


def test_a_path_with_spaces_works(tmp_path: Path) -> None:
    folder = tmp_path / "my folder"
    folder.mkdir()
    file = write(folder / "config.json", {"browser": {"headless": False}})
    assert load_config(str(file), env={}).browser.headless is False


def test_a_missing_named_file_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="config file not found"):
        load_config(tmp_path / "missing.json", env={})


def test_sources_say_where_each_overridden_value_came_from(tmp_path: Path) -> None:
    file = write(tmp_path / "config.json", {"browser": {"headless": False}})
    _, sources = load_config_with_sources(
        file, env={"BAP_BROWSER__BROWSER__CHANNEL": "chrome"}, session={"browser.headless": True}
    )
    assert sources == {"browser.headless": "session", "browser.channel": "environment"}


def test_the_configuration_holds_no_secret() -> None:
    dumped = json.dumps(defaults().model_dump())
    assert '"token"' not in dumped
    assert "password" not in dumped


@pytest.mark.parametrize(
    "entry", ["https://evil.example/", "evil.example/", "*", "evil.example:8443", "", "a b"]
)
@pytest.mark.parametrize("key", ["blocked_domains", "allowed_domains"])
def test_a_site_list_entry_that_could_never_match_is_refused(tmp_path: Path, key: str, entry: str) -> None:
    with pytest.raises(
        ConfigError,
        match=rf"bad value for 'safety\.{key}' \(from config.json\): .*entry 1 .*write a site as a host name",
    ):
        load_config(write(tmp_path / "config.json", {"safety": {key: [entry]}}), env={})


def test_site_list_entries_are_kept_as_written(tmp_path: Path) -> None:
    sites = ["example.com", "*.Example.org", "127.0.0.1", "::1", "bücher.example"]
    config = load_config(write(tmp_path / "config.json", {"safety": {"blocked_domains": sites}}), env={})
    assert config.safety.blocked_domains == sites


def test_the_scripted_model_can_be_chosen(tmp_path: Path) -> None:
    config = load_config(write(tmp_path / "config.json", {"agent": {"provider": "scripted"}}), env={})
    assert config.agent.provider == "scripted"


def test_a_model_provider_that_does_not_exist_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match=r"bad value for 'agent.provider' \(from config.json\)"):
        load_config(write(tmp_path / "config.json", {"agent": {"provider": "somebody"}}), env={})


@pytest.mark.parametrize("address", ["file:///etc/passwd", "ftp://example.com/v1", "api.openai.com/v1", ""])
def test_the_models_address_must_be_a_web_address(tmp_path: Path, address: str) -> None:
    with pytest.raises(ConfigError, match=r"bad value for 'agent.base_url' .*https://"):
        load_config(write(tmp_path / "config.json", {"agent": {"base_url": address}}), env={})
