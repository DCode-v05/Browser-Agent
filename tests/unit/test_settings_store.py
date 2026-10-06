"""The settings a person can change (spec 10.2): what the screen is told, which changes are taken, and
the configuration a person's settings make. A person tightens what the deployment set, never loosens it."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from bap_browser.config import Config
from bap_browser.errors import ConfigError
from bap_browser.settings import Refused, SettingsStore
from bap_browser.settings.catalogue import CATALOGUE, SURFACES

MakeConfig = Callable[..., Config]


def settings_in(answer: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {setting["id"]: setting for group in answer["groups"] for setting in group["settings"]}


def refused(store: SettingsStore, surface: str, **changes: Any) -> tuple[str, str]:
    with pytest.raises(Refused) as no:
        store.change(surface, changes)
    return no.value.setting, no.value.reason


def test_the_screen_is_told_the_groups_and_their_settings(make_config: MakeConfig, tmp_path: Path) -> None:
    answer = SettingsStore(make_config(tmp_path)).answer("web")
    assert answer["surface"] == "web"
    assert [(group["id"], group["title"]) for group in answer["groups"]] == [
        ("browser", "Browser"),
        ("approvals", "Approvals"),
        ("sites", "Sites"),
        ("files", "Files"),
        ("privacy", "Privacy"),
        ("live_view", "Live view"),
        ("appearance", "Appearance"),
        ("advanced", "Advanced"),
    ]
    settings = settings_in(answer)
    assert settings["ask_before"] == {
        "id": "ask_before",
        "title": "Ask before",
        "description": "When the agent must wait for your approval.",
        "control": "choice",
        "choices": [
            {
                "value": "risky",
                "label": "Risky actions",
                "hint": "Uploads, page scripts and whatever your organisation lists",
            },
            {
                "value": "every_action",
                "label": "Every action",
                "hint": "Each click, key press and page change",
            },
        ],
        "value": "risky",
        "default": "risky",
        "locked": False,
        "applies": "now",
    }
    assert settings["approval_wait"]["control"] == "select"
    assert [(choice["value"], choice["label"]) for choice in settings["approval_wait"]["choices"]] == [
        ("60", "1 minute"),
        ("180", "3 minutes"),
        ("300", "5 minutes"),
        ("600", "10 minutes"),
    ]
    assert settings["approval_wait"]["value"] == "180"
    assert settings["stay_signed_in"]["applies"] == "next_session"
    assert settings["preferred_browser"]["choices"] == [
        {
            "value": "remote_headless",
            "label": "Cloud browser",
            "hint": "Runs beside the agent. You watch a live picture of it.",
        }
    ]
    assert settings["blocked_sites"] == {
        "id": "blocked_sites",
        "title": "Blocked sites",
        "description": "Sites the agent must never open.",
        "control": "list",
        "value": [],
        "default": [],
        "locked": False,
        "applies": "now",
    }
    assert settings["about"]["control"] == "about" and settings["about"]["value"] is None


def test_a_surface_shows_only_what_it_can_act_on(make_config: MakeConfig, tmp_path: Path) -> None:
    store = SettingsStore(make_config(tmp_path))
    web, mobile = settings_in(store.answer("web")), settings_in(store.answer("mobile"))
    assert set(mobile) < set(web)
    assert set(web) - set(mobile) == {"preferred_browser", "page_scripts", "about"}
    assert "advanced" not in [group["id"] for group in store.answer("mobile")["groups"]]
    assert settings_in(store.answer("desktop")).keys() == web.keys()
    # A setting of another surface is neither shown nor accepted.
    assert refused(store, "mobile", page_scripts=False) == ("page_scripts", "not_on_this_surface")
    assert refused(store, "web", no_such_setting=True) == ("no_such_setting", "not_on_this_surface")


def test_every_setting_names_a_surface_and_a_group(make_config: MakeConfig, tmp_path: Path) -> None:
    config = make_config(tmp_path)
    assert len({entry.id for entry in CATALOGUE}) == len(CATALOGUE)
    for entry in CATALOGUE:
        assert entry.surfaces and set(entry.surfaces) <= set(SURFACES)
        assert entry.control in ("choice", "select", "switch", "list", "about")
        # What the deployment has is always a value a person may have.
        if entry.control != "about":
            assert entry.problem(entry.deployed(config), config) is None, entry.id


def test_a_change_is_kept_for_the_next_start(make_config: MakeConfig, tmp_path: Path) -> None:
    config = make_config(tmp_path)
    store = SettingsStore(config)
    changed = store.change(
        "web", {"colour_mode": "dark", "approval_wait": "60", "blocked_sites": ["Ads.Example", ""]}
    )
    assert changed == {"colour_mode": "dark", "approval_wait": "60", "blocked_sites": ["ads.example"]}
    assert json.loads(Path(config.settings.file).read_text(encoding="utf-8")) == changed

    later = settings_in(SettingsStore(config).answer("web"))
    assert later["colour_mode"]["value"] == "dark" and later["colour_mode"]["default"] == "system"
    assert later["approval_wait"]["value"] == "60"
    assert later["blocked_sites"]["value"] == ["ads.example"]

    made = SettingsStore(config).apply_to(config)
    assert made.viewer.theme == "dark"
    assert made.control.approval_timeout_s == 60
    assert made.safety.blocked_domains == ["ads.example"]


def test_nothing_is_changed_when_one_change_is_refused(make_config: MakeConfig, tmp_path: Path) -> None:
    config = make_config(tmp_path)
    store = SettingsStore(config)
    assert refused(store, "web", colour_mode="dark", picture_quality="finest") == (
        "picture_quality",
        "not_a_choice",
    )
    assert settings_in(store.answer("web"))["colour_mode"]["value"] == "system"
    assert not Path(config.settings.file).exists()


@pytest.mark.parametrize(
    ("setting", "value"),
    [
        ("colour_mode", "purple"),
        ("colour_mode", True),
        ("show_agent_pointer", "yes"),
        ("approval_wait", "7"),
        ("approval_wait", 180),
        ("blocked_sites", "example.com"),
        ("blocked_sites", [1, 2]),
        ("about", "anything"),
    ],
)
def test_a_value_that_is_not_one_of_the_choices_is_refused(
    make_config: MakeConfig, tmp_path: Path, setting: str, value: Any
) -> None:
    assert refused(SettingsStore(make_config(tmp_path)), "web", **{setting: value}) == (
        setting,
        "not_a_choice",
    )


def test_a_site_list_takes_only_sites(make_config: MakeConfig, tmp_path: Path) -> None:
    store = SettingsStore(make_config(tmp_path))
    assert refused(store, "web", blocked_sites=["example.com", "not a site"]) == ("blocked_sites", "bad_site")
    assert refused(store, "web", allowed_sites=["https://example.com/page"]) == ("allowed_sites", "bad_site")
    assert store.change("web", {"allowed_sites": ["example.com", "*.example.org", "example.com"]}) == {
        "allowed_sites": ["example.com", "*.example.org"]
    }


def test_a_locked_setting_is_shown_and_cannot_be_changed(make_config: MakeConfig, tmp_path: Path) -> None:
    config = make_config(tmp_path, settings={"locked": ["activity_log"], "file": str(tmp_path / "s.json")})
    store = SettingsStore(config)
    shown = settings_in(store.answer("web"))["activity_log"]
    assert shown["locked"] is True and shown["value"] is True
    assert refused(store, "web", activity_log=False) == ("activity_log", "locked")
    # A value saved before the deployment locked the setting no longer holds.
    Path(config.settings.file).write_text('{"activity_log": false}', encoding="utf-8")
    again = SettingsStore(config)
    assert settings_in(again.answer("web"))["activity_log"]["value"] is True
    assert again.apply_to(config).logging.event_log == config.logging.event_log


def test_a_person_asks_for_more_approvals_and_never_for_fewer(
    make_config: MakeConfig, tmp_path: Path
) -> None:
    lenient = make_config(tmp_path)
    store = SettingsStore(lenient)
    store.change("web", {"ask_before": "every_action", "remember_site_approval": "none"})
    made = store.apply_to(lenient)
    assert made.safety.ask_before == "every_action" and made.control.site_grant_lifetime == "none"
    # Back to what the deployment has is no loosening.
    store.change("web", {"ask_before": "risky"})
    assert store.apply_to(lenient).safety.ask_before == "risky"

    strict = make_config(
        tmp_path, safety={"ask_before": "every_action"}, control={"site_grant_lifetime": "none"}
    )
    held = SettingsStore(strict)
    shown = settings_in(held.answer("web"))
    # The looser choice is shown, so a person sees why it is not possible, and cannot be taken.
    assert shown["ask_before"]["choices"][0] == {
        "value": "risky",
        "label": "Risky actions",
        "hint": "Uploads, page scripts and whatever your organisation lists",
        "disabled": True,
    }
    assert shown["ask_before"]["locked"] is True and shown["ask_before"]["value"] == "every_action"
    assert shown["remember_site_approval"]["locked"] is True
    assert refused(held, "web", ask_before="risky") == ("ask_before", "would_loosen")
    assert refused(held, "web", remember_site_approval="session") == (
        "remember_site_approval",
        "would_loosen",
    )
    # The person's looser value, saved under the lenient deployment, does not hold under the strict one.
    assert held.apply_to(strict).safety.ask_before == "every_action"


def test_what_the_deployment_turned_off_stays_off(make_config: MakeConfig, tmp_path: Path) -> None:
    config = make_config(tmp_path, browser={"downloads": {"enabled": False}})
    store = SettingsStore(config)
    shown = settings_in(store.answer("web"))
    assert shown["allow_downloads"]["locked"] is True and shown["allow_downloads"]["value"] is False
    assert refused(store, "web", allow_downloads=True) == ("allow_downloads", "would_loosen")
    # Page scripts are off unless the deployment turns them on, so a person cannot.
    assert shown["page_scripts"]["locked"] is True
    assert refused(store, "web", page_scripts=True) == ("page_scripts", "would_loosen")
    # What is on, a person may turn off.
    assert shown["allow_uploads"]["locked"] is False
    store.change("web", {"allow_uploads": False})
    assert store.apply_to(config).browser.uploads.enabled is False

    scripts_on = make_config(tmp_path, browser={"javascript": {"allow_evaluate": True}})
    allowed = SettingsStore(scripts_on)
    assert settings_in(allowed.answer("web"))["page_scripts"]["locked"] is False
    allowed.change("web", {"page_scripts": False})
    assert allowed.apply_to(scripts_on).browser.javascript.allow_evaluate is False


def test_a_persons_blocked_sites_are_added_to_the_deployments(
    make_config: MakeConfig, tmp_path: Path
) -> None:
    config = make_config(tmp_path, safety={"blocked_domains": ["*.internal.example"]})
    store = SettingsStore(config)
    shown = settings_in(store.answer("web"))["blocked_sites"]
    # The deployment's entries are shown apart, and are not the person's to remove.
    assert shown["fixed"] == ["*.internal.example"] and shown["value"] == []
    store.change("web", {"blocked_sites": ["ads.example", "*.internal.example"]})
    assert store.apply_to(config).safety.blocked_domains == ["*.internal.example", "ads.example"]
    store.change("web", {"blocked_sites": []})
    assert store.apply_to(config).safety.blocked_domains == ["*.internal.example"]


def test_a_person_narrows_the_allowed_sites_and_never_widens_them(
    make_config: MakeConfig, tmp_path: Path
) -> None:
    anywhere = make_config(tmp_path)
    free = SettingsStore(anywhere)
    free.change("web", {"allowed_sites": ["example.com"]})
    assert free.apply_to(anywhere).safety.allowed_domains == ["example.com"]

    config = make_config(tmp_path, safety={"allowed_domains": ["example.com", "*.example.org"]})
    Path(config.settings.file).unlink()
    store = SettingsStore(config)
    assert settings_in(store.answer("web"))["allowed_sites"]["value"] == ["example.com", "*.example.org"]
    assert refused(store, "web", allowed_sites=["example.com", "elsewhere.test"]) == (
        "allowed_sites",
        "would_loosen",
    )
    assert refused(store, "web", allowed_sites=["ample.com"]) == ("allowed_sites", "would_loosen")
    store.change("web", {"allowed_sites": ["shop.example.com", "docs.example.org"]})
    assert store.apply_to(config).safety.allowed_domains == ["shop.example.com", "docs.example.org"]
    # With no list of their own a person narrows nothing: the deployment's list holds, and is shown.
    store.change("web", {"allowed_sites": []})
    assert store.apply_to(config).safety.allowed_domains == ["example.com", "*.example.org"]
    assert settings_in(store.answer("web"))["allowed_sites"]["value"] == ["example.com", "*.example.org"]


def test_staying_signed_in_is_for_the_cloud_browser_alone(make_config: MakeConfig, tmp_path: Path) -> None:
    config = make_config(tmp_path)
    store = SettingsStore(config)
    assert settings_in(store.answer("web"))["stay_signed_in"]["value"] is False
    store.change("web", {"stay_signed_in": True})
    assert store.apply_to(config).browser.user_data_dir == config.browser.kept_profile_dir
    # The built-in browser keeps a profile of its own, which this setting does not touch.
    own = config.model_copy(
        update={"browser": config.browser.model_copy(update={"user_data_dir": str(tmp_path / "own")})}
    )
    store.change("web", {"stay_signed_in": False})
    assert store.apply_to(own, "bundled_chromium").browser.user_data_dir == str(tmp_path / "own")
    assert store.apply_to(own, "remote_headless").browser.user_data_dir is None


def test_the_log_can_be_turned_off_and_on_again(make_config: MakeConfig, tmp_path: Path) -> None:
    config = make_config(tmp_path)
    store = SettingsStore(config)
    store.change("web", {"activity_log": False})
    assert store.apply_to(config).logging.event_log is None
    store.change("web", {"activity_log": True})
    assert store.apply_to(config).logging.event_log == config.logging.event_log

    silent = make_config(tmp_path, logging={"event_log": None})
    assert settings_in(SettingsStore(silent).answer("web"))["activity_log"]["value"] is True
    assert SettingsStore(silent).apply_to(silent).logging.event_log == str(tmp_path / "events.jsonl")


def test_saved_settings_another_build_wrote_are_read_with_care(
    make_config: MakeConfig, tmp_path: Path
) -> None:
    config = make_config(tmp_path)
    saved = Path(config.settings.file)
    saved.write_text(
        json.dumps(
            {"colour_mode": "dark", "a_later_setting": 3, "picture_quality": "finest", "ask_before": 7}
        ),
        encoding="utf-8",
    )
    store = SettingsStore(config)
    shown = settings_in(store.answer("web"))
    assert shown["colour_mode"]["value"] == "dark"
    # A value that is no longer a choice does not hold: the deployment's does.
    assert shown["picture_quality"]["value"] == "standard" and shown["ask_before"]["value"] == "risky"
    assert store.apply_to(config).viewer.quality == "standard"


@pytest.mark.parametrize("text", ["{not json", "[]", '"settings"'])
def test_saved_settings_that_cannot_be_read_stop_the_start(
    make_config: MakeConfig, tmp_path: Path, text: str
) -> None:
    """Passing over the file in silence would drop a site a person blocked."""
    config = make_config(tmp_path)
    Path(config.settings.file).write_text(text, encoding="utf-8")
    with pytest.raises(ConfigError, match="saved settings"):
        SettingsStore(config)


def test_about_lists_what_differs_from_the_defaults_and_where_it_came_from(
    make_config: MakeConfig, tmp_path: Path
) -> None:
    config = make_config(tmp_path, safety={"blocked_domains": ["*.internal.example"]})
    about = SettingsStore(config, {"safety.blocked_domains": "config.json"}).about("Chromium 153")
    assert about["version"] and about["browser"] == "Chromium 153"
    changed = {item["key"]: item for item in about["changed"]}
    assert changed["safety.blocked_domains"] == {
        "key": "safety.blocked_domains",
        "value": '["*.internal.example"]',
        "source": "config.json",
    }
    assert changed["data_dir"]["source"] == "configuration"
    assert "viewer.theme" not in changed, "a value at its default is not listed"


def test_about_knows_where_a_loaded_configuration_got_its_values(
    make_config: MakeConfig, tmp_path: Path
) -> None:
    config = make_config(tmp_path, viewer={"theme": "dark"})
    changed = {item["key"]: item["source"] for item in SettingsStore(config).about("")["changed"]}
    assert changed["viewer.theme"] == "config.json"


def test_a_configuration_no_person_changed_is_handed_back_as_it_is(
    make_config: MakeConfig, tmp_path: Path
) -> None:
    config = make_config(tmp_path)
    assert SettingsStore(config).apply_to(config) is config
