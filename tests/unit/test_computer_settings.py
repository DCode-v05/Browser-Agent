"""The settings of computer use on the admin's Configuration (spec 21.7), each as the vendors offer it:
the screen's size, the zoom tool, a picture after each action, a person's yes before an app opens, and
which of them a user may change."""

from pathlib import Path
from typing import Any

from desktop_stand_in import StandIn

from bap_browser.driver.desktop_driver import DesktopDriver
from bap_browser.driver.session import Question
from bap_browser.service.session import ServiceSession
from bap_browser.settings.store import SettingsStore
from bap_browser.tools.computer_tools import computer_tools_for

SYSTEMS = {"cloud": "remote_headless", "computer": "contained_desktop"}


def a_store(make_config, tmp_path: Path, **sections: Any) -> SettingsStore:
    store = SettingsStore(make_config(tmp_path, **sections))
    store.systems, store.backends = tuple(SYSTEMS), dict(SYSTEMS)
    return store


def drawn(store: SettingsStore, role: str = "admin") -> dict[str, dict[str, Any]]:
    groups = store.answer("web", "computer", role)["groups"]  # pyright: ignore[reportArgumentType]
    return {setting["id"]: setting for group in groups for setting in group["settings"]}


def a_session(make_config, tmp_path: Path, store: SettingsStore) -> tuple[ServiceSession, StandIn]:
    config = make_config(tmp_path, computer={"app_poll_ms": 1})
    driver = DesktopDriver(config)
    stand_in = StandIn()
    driver.desktop = stand_in
    session = ServiceSession(
        config,
        driver,
        name="computer",
        backend="contained_desktop",
        tools=computer_tools_for,
        settings=store,
    )
    return session, stand_in


def test_the_admin_has_the_vendors_settings_for_the_desktop(make_config, tmp_path: Path) -> None:
    settings = drawn(a_store(make_config, tmp_path))
    assert [option["value"] for option in settings["computer_screen"]["choices"]] == [
        "1024x768",
        "1280x800",
        "1366x768",
    ]
    assert settings["computer_screen"]["value"] == "1280x800"
    assert settings["computer_zoom"]["value"] is True
    assert settings["computer_picture_after_action"]["value"] is False
    assert settings["computer_ask_before_apps"]["value"] is False


def test_the_screen_a_person_chooses_is_the_desktops_size(make_config, tmp_path: Path) -> None:
    store = a_store(make_config, tmp_path)
    store.change("web", {"computer_screen": "1024x768"}, "computer")
    computer = store.apply_to(make_config(tmp_path), "contained_desktop", "computer").computer
    assert (computer.screen_width, computer.screen_height) == (1024, 768)


async def test_zoom_turned_off_is_not_offered_to_the_agent(make_config, tmp_path: Path) -> None:
    store = a_store(make_config, tmp_path)
    session, _ = a_session(make_config, tmp_path, store)
    await session.start()
    try:
        assert "computer_zoom" in {tool.name for tool in session.toolkit.definitions()}
        store.change("web", {"computer_zoom": False}, "computer")
        await session.settings_changed({"computer_zoom": False})
        assert "computer_zoom" not in {tool.name for tool in session.toolkit.definitions()}
    finally:
        await session.close()


async def test_a_picture_comes_with_each_action_when_a_person_asks_for_it(
    make_config, tmp_path: Path
) -> None:
    store = a_store(make_config, tmp_path)
    session, _ = a_session(make_config, tmp_path, store)
    await session.start()
    try:
        assert (await session.toolkit.call("computer_click", {"x": 10, "y": 10})).picture is None
        store.change("web", {"computer_picture_after_action": True}, "computer")
        await session.settings_changed({"computer_picture_after_action": True})
        clicked = await session.toolkit.call("computer_click", {"x": 10, "y": 10})
        assert clicked.picture is not None and "picture of the screen after it" in clicked.text
    finally:
        await session.close()


async def test_an_app_opens_only_after_a_persons_yes_when_the_admin_asks_for_it(
    make_config, tmp_path: Path
) -> None:
    store = a_store(make_config, tmp_path)
    store.change("web", {"computer_ask_before_apps": True}, "computer")
    session, desktop = a_session(make_config, tmp_path, store)
    asked: list[Question] = []

    async def no(question: Question) -> Any:
        asked.append(question)
        return "denied"

    await session.start()
    session.browser.ask_approval = no
    try:
        refused = await session.toolkit.call("computer_open_app", {"app": "Text editor"})
        assert refused.is_error and desktop.started == []
        assert [question.tool for question in asked] == ["computer_open_app"]
        # A desktop has no site: the yes cannot be given for one, only for this step.
        assert asked[0].every_time is True
    finally:
        await session.close()


def test_a_user_may_ask_for_more_but_not_for_less_than_the_admin(make_config, tmp_path: Path) -> None:
    store = a_store(make_config, tmp_path)
    store.change_policy(
        {"may_change": {"computer_ask_before_apps": True, "computer_picture_after_action": True}}
    )
    users = drawn(store, "user")
    assert {"computer_ask_before_apps", "computer_picture_after_action"} <= set(users)
    assert not {"computer_screen", "computer_zoom", "computer_terminal", "computer_network"} & set(users)
    store.change("web", {"computer_ask_before_apps": True}, "computer")
    assert drawn(store, "user")["computer_ask_before_apps"]["locked"] is True
