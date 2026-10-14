"""The safeguards of computer use that look at what has the focus and at which app is being worked
in (spec 22.7): Enter in a message box sends, a password field is a person's, and in the apps a
person must watch the agent acts only while the page is open."""

from pathlib import Path
from typing import Any

from desktop_stand_in import Desk

from bap_browser.computer.hermes.computer_use.backend import ActionResult, CaptureResult, UIElement
from bap_browser.driver.hermes_driver import HermesDriver
from bap_browser.service.session import ServiceSession
from bap_browser.tools.computer_tools import computer_tools_for


class AChatApp(Desk):
    """A window of a chat app: a box a message is written in, a search field and a password field."""

    def capture(
        self, mode: str = "som", app: str | None = None, pid: int | None = None, window_id: int | None = None
    ) -> CaptureResult:
        elements = [
            UIElement(index=1, role="AXTextArea", label="Message to Ada", bounds=(10, 10, 300, 120)),
            UIElement(index=2, role="AXTextField", label="Search", bounds=(10, 140, 200, 24)),
            UIElement(index=3, role="AXSecureTextField", label="Password", bounds=(10, 180, 200, 24)),
        ]
        return CaptureResult(mode=mode, width=800, height=600, elements=elements, app=app or "Chat")

    def type_text(self, text: str, **how: Any) -> ActionResult:
        self.done.append(("type", {"length": len(text)}))
        return ActionResult(ok=True, action="type")

    def key(self, keys: str, **how: Any) -> ActionResult:
        self.done.append(("key", {"keys": keys}))
        return ActionResult(ok=True, action="key")


def did(desk: Desk, name: str) -> list[dict[str, Any]]:
    return [how for done, how in desk.done if done == name]


async def working(
    make_config,
    tmp_path: Path,
    steps: list[dict[str, Any]],
    *,
    answer: str = "denied",
    watched: bool = True,
    **computer: Any,
) -> tuple[AChatApp, list[Any], list[Any]]:
    """The steps, done in a chat app on a person's machine. What the app was given, who was asked,
    and each step's result."""
    settings = {"runs": "machine", "base": {"home": str(tmp_path / "home")}, **computer}
    config = make_config(tmp_path, computer=settings)
    desk = AChatApp()
    session = ServiceSession(
        config,
        HermesDriver(config, backend=lambda: desk),
        name="computer",
        backend="contained_desktop",
        tools=computer_tools_for,
    )
    asked: list[Any] = []

    async def a_person(question: Any) -> Any:
        asked.append(question)
        return answer

    await session.start()
    session.browser.ask_approval = a_person
    session.browser.watched = lambda: watched
    try:
        done = [await session.toolkit.call("computer_use", step) for step in steps]
    finally:
        await session.close()
    return desk, asked, done


async def test_enter_in_a_box_a_message_is_written_in_waits_for_a_person(make_config, tmp_path: Path) -> None:
    """As in a browser (spec 18.4): Enter there sends the message."""
    steps = [
        {"action": "capture", "mode": "ax", "app": "Chat"},
        {"action": "click", "element": 1},
        {"action": "key", "keys": "return"},
    ]
    desk, asked, done = await working(make_config, tmp_path, steps)

    assert len(asked) == 1 and done[2].is_error
    assert did(desk, "key") == []


async def test_enter_in_a_search_field_asks_nobody(make_config, tmp_path: Path) -> None:
    steps = [
        {"action": "capture", "mode": "ax", "app": "Chat"},
        {"action": "click", "element": 2},
        {"action": "key", "keys": "return"},
    ]
    desk, asked, done = await working(make_config, tmp_path, steps)

    assert asked == [] and not done[2].is_error
    assert did(desk, "key") == [{"keys": "return"}]


async def test_typing_into_a_password_field_is_for_a_person(make_config, tmp_path: Path) -> None:
    steps = [
        {"action": "capture", "mode": "ax", "app": "Chat"},
        {"action": "click", "element": 3},
        {"action": "type", "text": "hunter2"},
    ]
    desk, asked, done = await working(make_config, tmp_path, steps)

    assert len(asked) == 1 and done[2].is_error
    assert did(desk, "type") == []
    assert "hunter2" not in done[2].text


async def test_in_an_app_a_person_must_watch_the_agent_does_not_act_while_nobody_watches(
    make_config, tmp_path: Path
) -> None:
    """Watch mode, as in OpenAI's Operator: in mail and the like, the agent goes on only while the
    page is open. It may still look."""
    steps = [
        {"action": "capture", "mode": "ax", "app": "Mail"},
        {"action": "click", "element": 2},
    ]
    desk, _, done = await working(make_config, tmp_path, steps, watched=False, watch_wait_s=0.2)

    assert not done[0].is_error
    assert done[1].is_error and "watch" in done[1].text and "Mail" in done[1].text
    assert did(desk, "click") == []


async def test_in_an_app_a_person_must_watch_the_agent_acts_while_the_page_is_open(
    make_config, tmp_path: Path
) -> None:
    steps = [
        {"action": "capture", "mode": "ax", "app": "Mail"},
        {"action": "click", "element": 2},
    ]
    desk, _, done = await working(make_config, tmp_path, steps, watched=True, watch_wait_s=0.2)

    assert not done[1].is_error
    assert len(did(desk, "click")) == 1


async def test_an_app_nobody_listed_is_worked_in_unwatched(make_config, tmp_path: Path) -> None:
    steps = [
        {"action": "capture", "mode": "ax", "app": "Calculator"},
        {"action": "click", "element": 2},
    ]
    _, _, done = await working(make_config, tmp_path, steps, watched=False, watch_wait_s=0.2)

    assert not done[1].is_error
