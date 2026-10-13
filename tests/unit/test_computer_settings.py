"""The settings of computer use on the admin's Configuration (spec 21.7), each as the vendors offer it:
the screen's size, the tool's manual, where input goes, a person's yes before an app opens, and which
of them a user may change."""

from pathlib import Path
from typing import Any

import pytest
from desktop_stand_in import Desk

from bap_browser.driver.hermes_driver import HermesDriver
from bap_browser.driver.session import Question
from bap_browser.service.session import ServiceSession
from bap_browser.settings.store import Refused, SettingsStore
from bap_browser.tools.computer_tools import computer_tools_for

SYSTEMS = {"cloud": "remote_headless", "computer": "contained_desktop"}


def a_store(make_config, tmp_path: Path, **sections: Any) -> SettingsStore:
    store = SettingsStore(make_config(tmp_path, **sections))
    store.systems, store.backends = tuple(SYSTEMS), dict(SYSTEMS)
    return store


def drawn(store: SettingsStore, role: str = "admin") -> dict[str, dict[str, Any]]:
    groups = store.answer("web", "computer", role)["groups"]  # pyright: ignore[reportArgumentType]
    return {setting["id"]: setting for group in groups for setting in group["settings"]}


def a_session(make_config, tmp_path: Path, store: SettingsStore) -> tuple[ServiceSession, Desk]:
    config = make_config(tmp_path, computer={"runs": "machine", "base": {"home": str(tmp_path / "home")}})
    desk = Desk()
    session = ServiceSession(
        config,
        HermesDriver(config, backend=lambda: desk),
        name="computer",
        backend="contained_desktop",
        tools=computer_tools_for,
        settings=store,
    )
    return session, desk


def test_the_admin_has_the_vendors_settings_for_the_desktop(make_config, tmp_path: Path) -> None:
    settings = drawn(a_store(make_config, tmp_path))
    assert [option["value"] for option in settings["computer_screen"]["choices"]] == [
        "1024x768",
        "1280x800",
        "1366x768",
    ]
    assert settings["computer_screen"]["value"] == "1280x800"
    assert settings["computer_manual"]["value"] is True
    assert [option["value"] for option in settings["computer_delivery"]["choices"]] == [
        "auto",
        "background",
        "foreground",
    ]
    assert settings["computer_ask_before_apps"]["value"] is False


def test_the_screen_a_person_chooses_is_the_desktops_size(make_config, tmp_path: Path) -> None:
    store = a_store(make_config, tmp_path)
    store.change("web", {"computer_screen": "1024x768"}, "computer")
    computer = store.apply_to(make_config(tmp_path), "contained_desktop", "computer").computer
    assert (computer.screen_width, computer.screen_height) == (1024, 768)


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
        assert refused.is_error and desktop.opened == []
        assert [question.tool for question in asked] == ["computer_open_app"]
        # A desktop has no site: the yes cannot be given for one, only for this step.
        assert asked[0].every_time is True
    finally:
        await session.close()


def test_a_user_may_ask_for_more_but_not_for_less_than_the_admin(make_config, tmp_path: Path) -> None:
    store = a_store(make_config, tmp_path)
    store.change_policy({"may_change": {"computer_ask_before_apps": True}})
    users = drawn(store, "user")
    assert "computer_ask_before_apps" in users
    assert not {"computer_screen", "computer_manual", "computer_terminal", "computer_network"} & set(users)
    store.change("web", {"computer_ask_before_apps": True}, "computer")
    assert drawn(store, "user")["computer_ask_before_apps"]["locked"] is True


def test_the_admin_says_where_the_helper_of_a_machine_elsewhere_answers(make_config, tmp_path: Path) -> None:
    store = a_store(make_config, tmp_path)

    assert drawn(store)["computer_helper_url"]["control"] == "address"
    store.change("web", {"computer_helper_url": " https://desk.tail1234.ts.net:8796/ "}, "computer")
    computer = store.apply_to(make_config(tmp_path), "contained_desktop", "computer").computer

    assert computer.helper_url == "https://desk.tail1234.ts.net:8796"
    assert "computer_helper_url" not in drawn(store, "user")


@pytest.mark.parametrize("address", ["desk.tail1234.ts.net", "ftp://desk:8796", "http://", "", 7])
def test_an_address_that_is_no_web_address_is_refused(make_config, tmp_path: Path, address: Any) -> None:
    store = a_store(make_config, tmp_path)

    with pytest.raises(Refused) as no:
        store.change("web", {"computer_helper_url": address}, "computer")

    assert no.value.reason in ("bad_address", "not_a_choice")


def test_the_admin_says_what_a_capture_holds_and_whether_the_drivers_pointer_shows(
    make_config, tmp_path: Path
) -> None:
    store = a_store(make_config, tmp_path)
    settings = drawn(store)

    assert [option["value"] for option in settings["computer_capture_mode"]["choices"]] == [
        "som",
        "vision",
        "ax",
    ]
    assert settings["computer_capture_mode"]["value"] == "som"
    assert [option["value"] for option in settings["computer_no_overlay"]["choices"]] == ["auto", "off", "on"]
    assert settings["computer_no_overlay"]["value"] == "auto"

    store.change("web", {"computer_capture_mode": "ax", "computer_no_overlay": "on"}, "computer")
    base = store.apply_to(make_config(tmp_path), "contained_desktop", "computer").computer.base

    assert (base.capture_mode, base.no_overlay) == ("ax", "on")
    assert not {"computer_capture_mode", "computer_no_overlay"} & set(drawn(store, "user"))


def test_a_setting_both_have_is_described_for_the_desktop_on_its_page_and_as_it_was_for_a_browser(
    make_config, tmp_path: Path
) -> None:
    store = a_store(make_config, tmp_path)
    of_a_browser = {
        setting["id"]: setting["description"]
        for group in store.answer("web", "cloud")["groups"]
        for setting in group["settings"]
    }
    of_the_desktop = {name: setting["description"] for name, setting in drawn(store).items()}
    shared = of_a_browser.keys() & of_the_desktop.keys()
    assert "browser" not in " ".join(of_the_desktop[name] for name in shared).replace(
        "every browser and the desktop", ""
    )
    assert "How sharp the live picture of the browser is." in " ".join(of_a_browser.values())
    assert "How sharp the live picture of the desktop is." in " ".join(of_the_desktop.values())
