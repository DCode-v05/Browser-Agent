"""Computer use (spec 21, 22.4) without a desktop: its sentences, its settings, and what its tools
refuse. The desktop itself is driven in tests/e2e/test_computer.py."""

from pathlib import Path
from typing import Any

from desktop_stand_in import Desk

from bap_browser.driver.contained_desktop import APPS, allowed_apps
from bap_browser.driver.desktop_driver import NO_PAGE
from bap_browser.driver.hermes_driver import HermesDriver
from bap_browser.service.session import ServiceSession
from bap_browser.settings.store import SettingsStore
from bap_browser.tools.computer_tools import COMPUTER_TOOLS
from bap_browser.tools.event_log import masked
from bap_browser.tools.sentences import label_for, summary_for


def a_desktop_session(make_config, tmp_path: Path, **computer: Any) -> tuple[ServiceSession, Desk]:
    settings = {"runs": "machine", "base": {"home": str(tmp_path / "home")}, **computer}
    config = make_config(tmp_path, computer=settings)
    desk = Desk()
    driver = HermesDriver(config, backend=lambda: desk)
    session = ServiceSession(
        config, driver, name="computer", backend="contained_desktop", tools=COMPUTER_TOOLS
    )
    return session, desk


def test_the_terminal_is_off_until_a_person_turns_it_on(make_config, tmp_path: Path) -> None:
    config = make_config(tmp_path)
    assert [app.id for app in allowed_apps(config.computer)] == ["text_editor", "files", "calculator"]
    on = make_config(tmp_path, computer={"apps": {"terminal": True}})
    assert [app.id for app in allowed_apps(on.computer)] == [app.id for app in APPS]


def test_the_timeline_says_what_happened_on_the_desktop_and_never_what_was_typed() -> None:
    assert label_for("computer_open_app", {"app": "Text editor"}, None) == "Opening Text editor"
    assert summary_for("computer_open_app", {"app": "Text editor"}, None, None) == "Opened Text editor"
    assert summary_for("computer_open_app", {"app": "rm -rf /"}, None, None) == "Opened an app"
    assert summary_for("computer_open_app", {"app": "Terminal"}, None, "the app is not allowed") == (
        "Could not open Terminal: the app is not allowed"
    )
    # The log keeps the length of typed text, never the text.
    assert masked({"text": "my secret"}, lambda text: text) == {"text": "<9 characters>"}


async def test_an_app_that_is_not_allowed_is_not_opened(make_config, tmp_path: Path) -> None:
    session, desk = a_desktop_session(make_config, tmp_path)
    await session.start()
    try:
        refused = await session.toolkit.call("computer_open_app", {"app": "Terminal"})
        assert refused.is_error and "not allowed" in refused.text and desk.opened == []
        unknown = await session.toolkit.call("computer_open_app", {"app": "Chess"})
        assert unknown.is_error and "no app of that name" in unknown.text and desk.opened == []
        opened = await session.toolkit.call("computer_open_app", {"app": "Text editor"})
        assert not opened.is_error, opened.text
        assert len(desk.opened) == 1
        # The title of a window is written by what is open in it: it is marked as such.
        assert f"Untitled 1 - {desk.opened[0]}" in opened.text and "[tabs]" not in opened.text
    finally:
        await session.close()


async def test_the_apps_a_person_allows_are_named_with_the_windows_that_are_open(
    make_config, tmp_path: Path
) -> None:
    session, _ = a_desktop_session(make_config, tmp_path)
    await session.start()
    try:
        before = await session.toolkit.call("computer_list_apps", {})
        await session.toolkit.call("computer_open_app", {"app": "Calculator"})
        after = await session.toolkit.call("computer_list_apps", {})
    finally:
        await session.close()

    assert "Apps you may open: Text editor, Files, Calculator." in before.text
    assert "Terminal" not in before.text and "No window is open." in before.text
    assert "Open windows:" in after.text


async def test_a_browser_tool_is_refused_on_a_desktop(make_config, tmp_path: Path) -> None:
    session, _ = a_desktop_session(make_config, tmp_path)
    await session.start()
    try:
        browser = await session.toolkit.call("browser_navigate", {"url": "https://example.com"})
        assert browser.is_error and "Unknown tool 'browser_navigate'" in browser.text
        assert NO_PAGE.startswith("A desktop has no web page")
    finally:
        await session.close()


def test_the_desktop_has_its_own_settings_and_none_that_are_a_browsers_alone(
    make_config, tmp_path: Path
) -> None:
    store = SettingsStore(make_config(tmp_path))
    store.systems = ("cloud", "computer")
    store.backends = {"cloud": "remote_headless", "computer": "contained_desktop"}

    def ids(system: str) -> set[str]:
        groups = store.answer("web", system)["groups"]
        return {setting["id"] for group in groups for setting in group["settings"]}

    desktop, browser = ids("computer"), ids("cloud")
    assert {
        "computer_text_editor",
        "computer_terminal",
        "computer_share_folder",
        "computer_network",
    } <= desktop
    assert not {"allowed_sites", "page_scripts", "allow_downloads", "scan_pages"} & desktop
    assert not any(name.startswith("computer_") for name in browser)
    assert {"agent_model", "ask_before", "task_limit", "system_enabled"} <= desktop & browser


def test_a_person_turns_an_app_on_for_the_desktop_alone(make_config, tmp_path: Path) -> None:
    store = SettingsStore(make_config(tmp_path))
    store.systems = ("cloud", "computer")
    store.backends = {"cloud": "remote_headless", "computer": "contained_desktop"}
    store.change("web", {"computer_terminal": True}, "computer")
    config = store.apply_to(make_config(tmp_path), "contained_desktop", "computer")
    assert config.computer.apps.terminal


async def test_where_a_person_allows_any_app_one_outside_the_list_is_opened_by_its_name_after_their_yes(
    make_config, tmp_path: Path
) -> None:
    """On Windows, macOS or Linux alike: with the switch on, the agent is not held to the four apps."""
    session, desk = a_desktop_session(make_config, tmp_path, any_app=True)
    asked: list[str] = []

    async def yes(question: Any) -> Any:
        asked.append(question.tool)
        return "allowed"

    await session.start()
    session.browser.ask_approval = yes
    try:
        listed = await session.toolkit.call("computer_list_apps", {})
        opened = await session.toolkit.call("computer_open_app", {"app": "File Explorer"})
    finally:
        await session.close()

    assert "any app on this machine, by its name" in listed.text
    assert not opened.is_error and desk.opened == ["File Explorer"]
    assert asked == ["computer_open_app"]


def test_the_switch_for_any_app_is_named_for_every_system(make_config, tmp_path: Path) -> None:
    store = SettingsStore(make_config(tmp_path))
    store.systems = ("cloud", "computer")
    store.backends = {"cloud": "remote_headless", "computer": "contained_desktop"}
    groups = store.answer("web", "computer")["groups"]
    one = next(s for g in groups for s in g["settings"] if s["id"] == "computer_any_app")

    assert one["title"] == "Let the agent work in any app on the machine"
    assert "Mac" not in one["title"] + one["description"]


async def test_the_drivers_own_windows_are_not_among_the_open_windows(make_config, tmp_path: Path) -> None:
    """On Windows the driver draws the agent's pointer in windows of its own. They are nothing to work in."""

    class WithTheDriversOwn(Desk):
        def list_windows(self) -> list[dict[str, Any]]:
            return [
                {"title": "Cua.AgentCursorOverlay.default", "app_name": "cua-driver.exe", "pid": 3},
                {"title": "Cua Driver", "app_name": "Cua Driver", "pid": 4},
                {"title": "Untitled - Notepad", "app_name": "notepad.exe", "pid": 7},
            ]

    config = make_config(tmp_path, computer={"runs": "machine", "base": {"home": str(tmp_path / "home")}})
    session = ServiceSession(
        config,
        HermesDriver(config, backend=WithTheDriversOwn),
        name="computer",
        backend="contained_desktop",
        tools=COMPUTER_TOOLS,
    )
    await session.start()
    try:
        listed = await session.toolkit.call("computer_list_apps", {})
    finally:
        await session.close()

    assert "Untitled - Notepad" in listed.text and "Cua" not in listed.text
