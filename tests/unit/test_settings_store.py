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
        ("agent", "Agent"),
        ("approvals", "Approvals"),
        ("safety", "Safety"),
        ("sites", "Sites"),
        ("files", "Files"),
        ("limits", "Limits"),
        ("privacy", "Privacy"),
        ("live_view", "Live view"),
        ("appearance", "Appearance"),
        ("advanced", "Advanced"),
    ]
    settings = settings_in(answer)
    assert settings["ask_before"] == {
        "id": "ask_before",
        "title": "Ask before",
        "description": "When the agent must stop and wait for a person's approval before it acts.",
        "control": "choice",
        "choices": [
            {
                "value": "risky",
                "label": "Risky actions",
                "hint": "Uploads, page scripts and whatever the admin lists",
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
    # A person's preferred browser is one of the browsers the service has: it is asked for by
    # itself, and is no setting of this screen.
    assert "preferred_browser" not in settings
    assert answer["role"] == "admin"
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
    # A button asks first, in words that say what will be lost.
    assert settings["clear_browsing_data"] == {
        "id": "clear_browsing_data",
        "title": "Clear browsing data",
        "description": "Deletes cookies and site data in the cloud browser.",
        "control": "action",
        "action": "Clear data",
        "confirm": {
            "question": "Clear cookies and site data in the cloud browser?",
            "consequence": "You'll be signed out of sites there, and open sessions will end.",
            "button": "Clear data",
        },
        "value": None,
        "default": None,
        "locked": False,
        "applies": "now",
    }


def test_a_surface_shows_only_what_it_can_act_on(make_config: MakeConfig, tmp_path: Path) -> None:
    store = SettingsStore(make_config(tmp_path))
    web, mobile = settings_in(store.answer("web")), settings_in(store.answer("mobile"))
    assert set(mobile) < set(web)
    assert set(web) - set(mobile) == {"page_scripts", "code_tool", "about"}
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
        assert entry.control in ("choice", "select", "switch", "list", "about", "action")
        # What the deployment has is always a value a person may have. Two hold no value at all.
        if entry.control not in ("about", "action"):
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
        ("clear_browsing_data", True),
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


def test_a_user_asks_for_more_approvals_and_never_for_fewer_than_the_admin(
    make_config: MakeConfig, tmp_path: Path
) -> None:
    config = make_config(tmp_path)
    store = SettingsStore(config)
    # A user tightens what the admin has: more approvals, and an answer that is not remembered.
    store.change("web", {"ask_before": "every_action", "remember_site_approval": "none"}, role="user")
    made = store.apply_to(config)
    assert made.safety.ask_before == "every_action" and made.control.site_grant_lifetime == "none"
    # Back to what the admin has is no loosening.
    store.change("web", {"ask_before": "risky"}, role="user")
    assert store.apply_to(config).safety.ask_before == "risky"

    # The admin now requires more. The user is shown the looser choice, and cannot take it.
    store.change("web", {"ask_before": "every_action", "remember_site_approval": "none"})
    shown = settings_in(store.answer("web", role="user"))
    assert shown["ask_before"]["choices"][0] == {
        "value": "risky",
        "label": "Risky actions",
        "hint": "Uploads, page scripts and whatever the admin lists",
        "disabled": True,
    }
    assert shown["ask_before"]["locked"] is True and shown["ask_before"]["value"] == "every_action"
    assert shown["remember_site_approval"]["locked"] is True
    with pytest.raises(Refused) as no:
        store.change("web", {"ask_before": "risky"}, role="user")
    assert (no.value.setting, no.value.reason) == ("ask_before", "would_loosen")
    # The user's looser value, saved while the admin allowed it, no longer holds.
    assert store.apply_to(config).safety.ask_before == "every_action"
    # The admin is not held so: every choice is the admin's, the looser one too.
    admins = settings_in(store.answer("web"))["ask_before"]
    assert admins["locked"] is False and "disabled" not in admins["choices"][0]
    store.change("web", {"ask_before": "risky"})
    assert store.apply_to(config).safety.ask_before == "risky"


def test_the_admin_turns_on_what_the_agent_may_do_and_a_user_cannot(
    make_config: MakeConfig, tmp_path: Path
) -> None:
    config = make_config(tmp_path)
    store = SettingsStore(config)
    # As installed, scripts are off. The admin turns them on from the window, and off again.
    shown = settings_in(store.answer("web"))
    assert shown["page_scripts"]["value"] is False and shown["page_scripts"]["locked"] is False
    store.change("web", {"page_scripts": True, "code_tool": True, "allow_downloads": False})
    made = store.apply_to(config)
    assert made.browser.javascript.allow_evaluate is True and made.code.enabled is True
    assert made.browser.downloads.enabled is False
    store.change("web", {"page_scripts": False})
    assert store.apply_to(config).browser.javascript.allow_evaluate is False
    # What the agent may do is the admin's alone: a user is not shown it, and cannot change it.
    assert "page_scripts" not in settings_in(store.answer("web", role="user"))
    for setting in ("page_scripts", "code_tool", "allow_downloads", "system_enabled", "agent_model"):
        with pytest.raises(Refused) as no:
            store.change("web", {setting: True}, "cloud", role="user")
        assert no.value.reason == "not_on_this_surface", setting


def test_what_the_deployment_locked_not_even_the_admin_changes(
    make_config: MakeConfig, tmp_path: Path
) -> None:
    config = make_config(
        tmp_path, settings={"locked": ["page_scripts", "ask_before"], "file": str(tmp_path / "s.json")}
    )
    store = SettingsStore(config)
    assert settings_in(store.answer("web"))["page_scripts"]["locked"] is True
    for role in ("admin", "user"):
        assert settings_in(store.answer("web", role=role))["ask_before"]["locked"] is True
        with pytest.raises(Refused) as no:
            store.change("web", {"ask_before": "every_action"}, role=role)  # type: ignore[arg-type]
        assert no.value.reason == "locked"
    with pytest.raises(Refused) as no:
        store.change("web", {"page_scripts": True})
    assert (no.value.setting, no.value.reason) == ("page_scripts", "locked")


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


def test_a_user_narrows_the_allowed_sites_and_never_widens_them(
    make_config: MakeConfig, tmp_path: Path
) -> None:
    config = make_config(tmp_path)
    store = SettingsStore(config)
    # With no list above them, a user's list is theirs to make.
    store.change("web", {"allowed_sites": ["example.com"]}, role="user")
    assert store.apply_to(config).safety.allowed_domains == ["example.com"]

    # The admin makes a list. It takes the place of the deployment's, which had none.
    store.change("web", {"allowed_sites": ["example.com", "*.example.org"]})
    store.change("web", {"allowed_sites": []}, role="user")
    assert settings_in(store.answer("web", role="user"))["allowed_sites"]["value"] == [
        "example.com",
        "*.example.org",
    ]
    for outside in (["example.com", "elsewhere.test"], ["ample.com"]):
        with pytest.raises(Refused) as no:
            store.change("web", {"allowed_sites": outside}, role="user")
        assert (no.value.setting, no.value.reason) == ("allowed_sites", "would_loosen")
    store.change("web", {"allowed_sites": ["shop.example.com", "docs.example.org"]}, role="user")
    assert store.apply_to(config).safety.allowed_domains == ["shop.example.com", "docs.example.org"]
    # With no list of their own a user narrows nothing: the admin's list holds, and is shown.
    store.change("web", {"allowed_sites": []}, role="user")
    assert store.apply_to(config).safety.allowed_domains == ["example.com", "*.example.org"]
    # The admin widens the list: only the admin may.
    store.change("web", {"allowed_sites": ["elsewhere.test"]})
    assert store.apply_to(config).safety.allowed_domains == ["elsewhere.test"]


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


# Where a service has several browsers, each is a system with settings of its own (spec 9.17).


def test_a_system_has_settings_of_its_own(make_config: MakeConfig, tmp_path: Path) -> None:
    config = make_config(tmp_path)
    store = SettingsStore(config)
    assert store.change("web", {"ask_before": "every_action", "blocked_sites": ["ads.example"]}, "cloud") == {
        "ask_before": "every_action",
        "blocked_sites": ["ads.example"],
    }
    cloud, built_in = store.apply_to(config, system="cloud"), store.apply_to(config, system="builtin")
    assert cloud.safety.ask_before == "every_action" and cloud.safety.blocked_domains == ["ads.example"]
    assert built_in.safety.ask_before == "risky" and built_in.safety.blocked_domains == []
    # A service with one session, which is no system among several, is not touched by it either.
    assert store.apply_to(config) is config

    shown = store.answer("web", "cloud")
    assert shown["system"] == "cloud"
    assert settings_in(shown)["ask_before"]["value"] == "every_action"
    # The screen is told which settings are this browser's alone, and which are every browser's.
    assert settings_in(shown)["ask_before"]["scope"] == "system"
    assert settings_in(shown)["colour_mode"]["scope"] == "all"
    assert "scope" not in settings_in(store.answer("web"))["ask_before"]
    assert settings_in(store.answer("web", "builtin"))["ask_before"]["value"] == "risky"
    assert "system" not in store.answer("web")
    assert json.loads(Path(config.settings.file).read_text(encoding="utf-8")) == {
        "systems": {"cloud": {"ask_before": "every_action", "blocked_sites": ["ads.example"]}}
    }
    # And it is there again the next time the service starts.
    assert SettingsStore(config).apply_to(config, system="cloud").safety.ask_before == "every_action"


def test_a_system_without_a_value_of_its_own_has_the_one_for_every_browser(
    make_config: MakeConfig, tmp_path: Path
) -> None:
    config = make_config(tmp_path)
    store = SettingsStore(config)
    store.change("web", {"approval_wait": "60"})
    store.change("web", {"approval_wait": "600"}, "chrome")
    assert store.apply_to(config, system="cloud").control.approval_timeout_s == 60
    assert store.apply_to(config, system="chrome").control.approval_timeout_s == 600
    assert settings_in(store.answer("web", "cloud"))["approval_wait"]["value"] == "60"


def test_what_is_the_persons_and_not_a_browsers_is_kept_for_every_browser(
    make_config: MakeConfig, tmp_path: Path
) -> None:
    """The colour of the window is not one browser's. Changed on a system's screen, it changes everywhere."""
    config = make_config(tmp_path)
    store = SettingsStore(config)
    store.change("web", {"colour_mode": "dark", "picture_quality": "high"}, "cloud")
    assert json.loads(Path(config.settings.file).read_text(encoding="utf-8")) == {
        "colour_mode": "dark",
        "systems": {"cloud": {"picture_quality": "high"}},
    }
    assert settings_in(store.answer("web", "builtin"))["colour_mode"]["value"] == "dark"
    assert store.apply_to(config, system="builtin").viewer.quality == "standard"


def test_a_browser_of_the_window_is_turned_off_and_on(make_config: MakeConfig, tmp_path: Path) -> None:
    config = make_config(tmp_path)
    store = SettingsStore(config)
    assert all(store.enabled(system) for system in ("cloud", "chrome", "builtin"))
    shown = settings_in(store.answer("web", "chrome"))["system_enabled"]
    assert (shown["title"], shown["control"], shown["value"]) == ("Use this browser", "switch", True)
    store.change("web", {"system_enabled": False}, "chrome")
    assert not store.enabled("chrome") and store.enabled("cloud") and store.enabled("builtin")
    assert not SettingsStore(config).enabled("chrome"), "it stays off the next time"
    store.change("web", {"system_enabled": True}, "chrome")
    assert store.enabled("chrome")
    # A service with one session has no browser to turn off.
    assert "system_enabled" not in settings_in(store.answer("web"))
    assert refused(store, "web", system_enabled=False) == ("system_enabled", "not_on_this_surface")


def test_the_admin_sets_what_the_agent_may_do_for_each_system(
    make_config: MakeConfig, tmp_path: Path
) -> None:
    config = make_config(tmp_path)
    store = SettingsStore(config)
    store.change("web", {"code_tool": True, "page_scripts": True}, "builtin")
    assert store.apply_to(config, system="builtin").code.enabled is True
    assert store.apply_to(config, system="cloud").code.enabled is False
    assert store.apply_to(config, system="builtin").browser.javascript.allow_evaluate is True
    assert settings_in(store.answer("web", "builtin"))["code_tool"]["value"] is True
    assert settings_in(store.answer("web", "cloud"))["code_tool"]["value"] is False
    # A user's own value is held against the admin's for that system, not for another.
    store.change("web", {"ask_before": "every_action"}, "cloud")
    with pytest.raises(Refused):
        store.change("web", {"ask_before": "risky"}, "cloud", role="user")
    store.change("web", {"ask_before": "every_action"}, "builtin", role="user")
    assert store.apply_to(config, system="builtin").safety.ask_before == "every_action"
    assert store.apply_to(config, system="chrome").safety.ask_before == "risky"


def test_the_model_is_chosen_for_each_browser_among_those_offered(
    make_config: MakeConfig, tmp_path: Path
) -> None:
    config = make_config(tmp_path, agent={"model": "model-a", "offered_models": ["model-b", "model-a"]})
    store = SettingsStore(config)
    shown = settings_in(store.answer("web", "cloud"))["agent_model"]
    assert [choice["value"] for choice in shown["choices"]] == ["model-a", "model-b"]
    assert shown["value"] == "model-a" and shown["control"] == "select"
    store.change("web", {"agent_model": "model-b"}, "cloud")
    assert store.apply_to(config, system="cloud").agent.model == "model-b"
    assert store.apply_to(config, system="builtin").agent.model == "model-a"
    with pytest.raises(Refused) as no:
        store.change("web", {"agent_model": "model-z"}, "cloud")
    assert no.value.reason == "not_a_choice"


def test_each_browser_writes_a_log_of_its_own(make_config: MakeConfig, tmp_path: Path) -> None:
    config = make_config(tmp_path, logging={"event_log": None, "systems_dir": str(tmp_path / "logs")})
    store = SettingsStore(config)
    # The deployment keeps no log. A person who wants one for a browser gets that browser's own file.
    assert store.apply_to(config, system="cloud").logging.event_log is None
    store.change("web", {"activity_log": True}, "cloud")
    assert store.apply_to(config, system="cloud").logging.event_log == str(tmp_path / "logs" / "cloud.jsonl")
    assert store.apply_to(config, system="builtin").logging.event_log is None
    store.change("web", {"activity_log": False}, "cloud")
    assert store.apply_to(config, system="cloud").logging.event_log is None


def test_saved_settings_of_systems_are_read_with_care(make_config: MakeConfig, tmp_path: Path) -> None:
    config = make_config(tmp_path)
    Path(config.settings.file).write_text(
        json.dumps(
            {
                "colour_mode": "dark",
                "systems": {
                    "cloud": {
                        "ask_before": "every_action",
                        "a_later_setting": 1,
                        "picture_quality": "finest",
                    },
                    "Not A Name": {"ask_before": "every_action"},
                    "chrome": "not settings",
                },
            }
        ),
        encoding="utf-8",
    )
    store = SettingsStore(config)
    assert store.apply_to(config, system="cloud").safety.ask_before == "every_action"
    assert store.apply_to(config, system="cloud").viewer.quality == "standard"
    assert store.apply_to(config, system="chrome").safety.ask_before == "risky"
    with pytest.raises(Refused):
        store.change("web", {"ask_before": "risky"}, "Not A Name")
    # A file whose systems are no object is still a person's settings for every browser.
    Path(config.settings.file).write_text('{"colour_mode": "light", "systems": []}', encoding="utf-8")
    assert settings_in(SettingsStore(config).answer("web"))["colour_mode"]["value"] == "light"


# Two people save here (spec 4.11): the admin sets the system up, and a user sets a part of it for
# themselves, inside what the admin set and where the admin lets users change it.


def test_a_user_is_shown_only_the_settings_that_are_a_users(make_config: MakeConfig, tmp_path: Path) -> None:
    store = SettingsStore(make_config(tmp_path))
    answer = store.answer("web", "cloud", role="user")
    assert answer["role"] == "user" and answer["system"] == "cloud"
    assert list(settings_in(answer)) == [
        "ask_before",
        "approval_wait",
        "remember_site_approval",
        "scan_pages",
        "cross_site_text",
        "sensitive_sites",
        "blocked_sites",
        "allowed_sites",
        "task_limit",
        "picture_quality",
        "show_agent_pointer",
        "colour_mode",
    ]
    assert [group["id"] for group in answer["groups"]] == [
        "approvals",
        "safety",
        "sites",
        "limits",
        "live_view",
        "appearance",
    ]


def test_the_two_layers_are_kept_apart_in_the_file(make_config: MakeConfig, tmp_path: Path) -> None:
    config = make_config(tmp_path)
    store = SettingsStore(config)
    store.change("web", {"ask_before": "every_action"}, "cloud")
    store.change("web", {"colour_mode": "dark", "picture_quality": "data_saver"}, "cloud", role="user")
    assert json.loads(Path(config.settings.file).read_text(encoding="utf-8")) == {
        "systems": {"cloud": {"ask_before": "every_action"}},
        "user": {"colour_mode": "dark", "systems": {"cloud": {"picture_quality": "data_saver"}}},
    }
    again = SettingsStore(config)
    made = again.apply_to(config, system="cloud")
    assert (made.safety.ask_before, made.viewer.quality, made.viewer.theme) == (
        "every_action",
        "data_saver",
        "dark",
    )
    # What the user chose is theirs: the admin's screen shows the admin's own value.
    assert settings_in(again.answer("web", "cloud"))["picture_quality"]["value"] == "standard"
    assert settings_in(again.answer("web", "cloud", role="user"))["picture_quality"]["value"] == "data_saver"


def test_the_admin_says_which_settings_users_may_change(make_config: MakeConfig, tmp_path: Path) -> None:
    config = make_config(tmp_path)
    store = SettingsStore(config)
    store.systems = ("cloud", "chrome", "builtin")
    told = store.policy()
    assert [line["id"] for line in told["may_change"]] == [
        "ask_before",
        "approval_wait",
        "remember_site_approval",
        "scan_pages",
        "cross_site_text",
        "sensitive_sites",
        "task_limit",
        "blocked_sites",
        "allowed_sites",
        "picture_quality",
        "show_agent_pointer",
        "colour_mode",
    ]
    # Each line says what it is, so that the admin knows what they are deciding.
    assert told["may_change"][0] == {
        "id": "ask_before",
        "title": "Ask before",
        "description": "When the agent must stop and wait for a person's approval before it acts.",
        "allowed": True,
    }
    assert all(line["description"] for part in ("may_change", "sees") for line in told[part])
    store.change("web", {"approval_wait": "60"}, role="user")
    assert store.apply_to(config).control.approval_timeout_s == 60

    store.change_policy({"may_change": {"approval_wait": False}})
    assert not store.user_may_change("approval_wait") and store.user_may_change("ask_before")
    # What the user had chosen no longer holds, and they are shown the setting as fixed.
    assert store.apply_to(config).control.approval_timeout_s == 180
    shown = settings_in(store.answer("web", role="user"))["approval_wait"]
    assert shown["locked"] is True and shown["value"] == "180"
    with pytest.raises(Refused) as no:
        store.change("web", {"approval_wait": "300"}, role="user")
    assert (no.value.setting, no.value.reason) == ("approval_wait", "locked")
    # The admin is not held by their own policy, and it is still there the next time.
    store.change("web", {"approval_wait": "300"})
    assert SettingsStore(config).apply_to(config).control.approval_timeout_s == 300
    assert not SettingsStore(config).user_may_change("approval_wait")
    store.change_policy({"may_change": {"approval_wait": True}})
    assert store.apply_to(config).control.approval_timeout_s == 60, "the user's own value holds again"


def test_the_admin_says_which_browsers_users_may_use(make_config: MakeConfig, tmp_path: Path) -> None:
    config = make_config(tmp_path)
    store = SettingsStore(config)
    store.systems = ("cloud", "chrome", "builtin")
    assert store.allowed_systems("user") == ["cloud", "chrome", "builtin"]
    assert store.policy()["systems"] == [
        {"id": "cloud", "allowed": True},
        {"id": "chrome", "allowed": True},
        {"id": "builtin", "allowed": True},
    ]
    store.change_policy({"systems": {"chrome": False}})
    assert store.allowed_systems("user") == ["cloud", "builtin"]
    assert store.allowed_systems("admin") == ["cloud", "chrome", "builtin"]
    assert not store.users_may_use("chrome") and store.enabled("chrome"), "kept from users, and still running"
    # A browser the admin turned off is no user's either, whatever the policy says.
    store.change("web", {"system_enabled": False}, "builtin")
    assert store.allowed_systems("user") == ["cloud"]
    assert SettingsStore(config).users_may_use("chrome") is False


def test_a_person_prefers_a_browser_among_those_they_may_use(make_config: MakeConfig, tmp_path: Path) -> None:
    config = make_config(tmp_path)
    store = SettingsStore(config)
    store.systems = ("cloud", "chrome", "builtin")
    assert store.preferred() == "cloud", "the first they may use, until they choose"
    assert store.prefer("builtin") == "builtin"
    assert store.preferred() == "builtin"
    assert json.loads(Path(config.settings.file).read_text(encoding="utf-8")) == {
        "user": {"preferred_browser": "builtin"}
    }
    again = SettingsStore(config)
    again.systems = store.systems
    assert again.preferred() == "builtin"
    # The admin keeps that browser from users: the window opens on one they may still use.
    again.change_policy({"systems": {"builtin": False}})
    assert again.preferred() == "cloud"
    with pytest.raises(Refused) as no:
        again.prefer("builtin")
    assert (no.value.setting, no.value.reason) == ("preferred_browser", "not_a_choice")
    for not_a_browser in ("fridge", None, 7):
        with pytest.raises(Refused):
            again.prefer(not_a_browser)
    again.change_policy({"systems": {"cloud": False, "chrome": False}})
    assert again.preferred() is None, "a user who may use no browser has none to open"


def test_the_admin_says_what_of_the_evaluations_users_see(make_config: MakeConfig, tmp_path: Path) -> None:
    config = make_config(tmp_path)
    store = SettingsStore(config)
    assert {line["id"]: line["allowed"] for line in store.policy()["sees"]} == {
        "evaluations": True,
        "cost": True,
        "traces": True,
        "checklist": True,
        # The log holds every step: it is the admin's until the admin says otherwise.
        "log": False,
    }
    store.change_policy({"sees": {"cost": False, "log": True}})
    assert not store.user_sees("cost") and store.user_sees("log") and store.user_sees("traces")
    assert not store.user_sees("salaries")
    assert json.loads(Path(config.settings.file).read_text(encoding="utf-8")) == {
        "policy": {"sees": {"cost": False, "log": True}}
    }
    assert not SettingsStore(config).user_sees("cost")


@pytest.mark.parametrize(
    "changes",
    [
        {"sees": {"salaries": True}},
        {"sees": {"cost": "no"}},
        {"may_change": {"page_scripts": True}},
        {"systems": {"fridge": True}},
        {"colours": {"cost": True}},
        {"sees": ["cost"]},
    ],
)
def test_a_policy_that_is_not_one_changes_nothing(
    make_config: MakeConfig, tmp_path: Path, changes: Any
) -> None:
    config = make_config(tmp_path)
    store = SettingsStore(config)
    store.systems = ("cloud",)
    with pytest.raises(Refused) as no:
        store.change_policy({"sees": {"cost": False}, **changes})
    assert no.value.reason == "not_a_choice"
    assert store.user_sees("cost") and not Path(config.settings.file).exists()
