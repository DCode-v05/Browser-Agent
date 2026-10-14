"""`computer_use`: Hermes' tool for a real machine (spec 22.4), as this engine offers it.

It takes what Hermes' tool takes and returns what a tool here returns: short plain text, with a
picture only where a capture was asked for one.
"""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Literal

from pydantic import Field

from bap_browser.config_computer import Computer
from bap_browser.driver.hermes_driver import HermesDriver, as_shot
from bap_browser.driver.session import BrowserSession
from bap_browser.errors import BadInput, BrowserError
from bap_browser.safeguards.reading import from_page
from bap_browser.tools.registry import Args, Shown, ToolDefinition

NAME = "computer_use"
Action = Literal[
    "capture",
    "click",
    "double_click",
    "right_click",
    "middle_click",
    "drag",
    "scroll",
    "type",
    "key",
    "set_value",
    "wait",
    "list_apps",
    "list_windows",
    "focus_app",
]
Held = Literal["cmd", "shift", "option", "alt", "ctrl", "fn", "win", "windows", "super", "meta"]
# The actions that only look, or only wait.
LOOKS = frozenset({"capture", "wait", "list_apps", "list_windows"})
# The actions whose input is delivered to a window: in the background, or in front.
DELIVERED = frozenset(
    {"click", "double_click", "right_click", "middle_click", "drag", "scroll", "type", "key"}
)
# The actions that press one element.
PRESSES = frozenset({"click", "double_click", "right_click", "middle_click"})
NOT_ON_THE_SCREEN = (
    "Element {element} is not on the screen now: it is an item of a menu that is not open, or a hidden "
    "button. Click its menu to open it, capture again, and act on what the capture names."
)
LOOK_AGAIN = " Capture to see what it changed."
# Watch mode: what the agent is told when nobody came to watch an app a person must watch.
UNWATCHED = (
    "{app} is an app the agent works in only while a person watches its page (watch mode). Nobody "
    "had the page open and in front for {waited} s, so this step was not done. Stop here, and say in "
    "your answer that the person must have the page in front for you to go on in {app}."
)
NOT_A_WORD = re.compile(r"[^a-z0-9]+")
# What Hermes' backend says when the driver has stopped answering, or its session is gone. Seen
# under a model on Linux, where every call then failed the same way until the session ended; and
# over the tailnet, where the link's new process could not revive the session the old one had.
STOPPED_ANSWERING = ("timed out", "never reached ready", "has ended", "not available to this transport")
STARTED_AGAIN = (
    "The desktop stopped answering and was put right: a fresh session with its driver was begun. What "
    "you asked for may or may not have been done. Capture again to see the desktop as it is."
)
# The roles of an app's menus, as the systems name them.
MENUS = frozenset({"menu", "menu item", "MenuItem", "Menu", "AXMenuItem", "AXMenu", "AXMenuBarItem"})
# What marks a line of the tool's text that names a file on the engine's machine. No model here
# can read one, and its path is nothing a result should hold.
OF_THIS_MACHINE = ("saved to", "read_file", "search_files")
REFUSALS = {"human_has_control": "a person has the screen"}
# How Hermes' backend begins what it says of a desktop with no window. What follows it is about the
# engine's own system and a command for a person: nothing a model can use, and wrong for a desktop
# that is elsewhere.
NO_WINDOW = "window discovery returned no windows"
NOTHING_IS_OPEN = "No window is open on the desktop. Open an app with computer_open_app, then capture."


class ComputerUseArgs(Args):
    action: Action
    mode: Literal["som", "vision", "ax"] | None = None
    app: str | None = None
    pid: int | None = None
    window_id: int | None = None
    element: int | None = None
    coordinate: list[int] | None = Field(default=None, min_length=2, max_length=2)
    button: Literal["left", "right", "middle"] | None = None
    modifiers: list[Held] | None = None
    from_element: int | None = None
    to_element: int | None = None
    from_coordinate: list[int] | None = Field(default=None, min_length=2, max_length=2)
    to_coordinate: list[int] | None = Field(default=None, min_length=2, max_length=2)
    direction: Literal["up", "down", "left", "right"] | None = None
    amount: int | None = None
    value: str | None = None
    text: str | None = None
    keys: str | None = None
    seconds: float | None = None
    raise_window: bool | None = None
    delivery_mode: Literal["background", "foreground"] | None = None
    bring_to_front: bool | None = None
    capture_after: bool | None = None


def delivery_for(computer: Computer) -> str | None:
    """How the agent's input is delivered when a call does not say: in front, on a desktop nobody is
    at. None leaves it to the driver, which delivers in the background."""
    chosen = computer.base.delivery
    nobody_is_there = computer.runs in ("container", "here") or computer.base.virtual_screen
    in_front = chosen == "foreground" or (chosen == "auto" and nobody_is_there)
    return "foreground" if in_front else None


def cleared(summary: str) -> str:
    """A capture's text with no line that names a file of the engine's machine."""
    return "\n".join(
        line for line in summary.splitlines() if not any(word in line for word in OF_THIS_MACHINE)
    )


def sized(one: dict[str, Any]) -> bool:
    """Whether an element has a place on the screen. An item of a menu that is not open has none."""
    bounds = list(one.get("bounds") or ())
    return len(bounds) == 4 and bool(bounds[2]) and bool(bounds[3])


def of_a_capture(
    summary: str, elements: list[dict[str, Any]], shown: int, label: int, *, on_the_screen: bool = False
) -> str:
    """What a capture says in text: what was captured, and its elements by number. Hermes' own text
    names the first forty as the window gives them, which in an app with large menus is menus alone.
    Here the page comes first and the menus after, and no file of the engine's machine is named.
    With `on_the_screen`, only what has a place on the screen is named: the rest is counted."""
    away = [] if not on_the_screen else [one for one in elements if not sized(one)]
    elements = [one for one in elements if one not in away]
    kept = [
        line
        for line in summary.splitlines()
        if not line.lstrip().startswith(("#", "...")) and not any(word in line for word in OF_THIS_MACHINE)
    ]
    of_the_page = [one for one in elements if str(one.get("role", "")) not in MENUS]
    of_the_menus = [one for one in elements if str(one.get("role", "")) in MENUS]
    named = [*of_the_page, *of_the_menus][: max(shown, 0)]
    lines = [
        f"#{one.get('index')} {one.get('role')} {str(one.get('label', ''))[:label]!r}".rstrip()
        for one in named
    ]
    left = len(elements) - len(named)
    if left > 0:
        menus_left = len([one for one in of_the_menus if one not in named])
        lines.append(
            f"{left} more are not named here, {menus_left} menu items among them. Capture with mode=som to see "
            "them numbered in a picture."
        )
    if of_the_menus:
        lines.append(f"This window has {len(of_the_menus)} menu items.")
    if away:
        lines.append(
            f"{len(away)} more {'is' if len(away) == 1 else 'are'} not on the screen: items of menus that are "
            "not open, and hidden buttons. Click a menu to open it, then capture again."
        )
    return "\n".join([*kept, *lines])


def every_element(answer: dict[str, Any]) -> list[dict[str, Any]] | None:
    """Every element of a capture, as the tool gave them: in its answer, or, past a hundred, in the
    file it names. None when the answer holds no list of them."""
    file = answer.get("elements_file") or answer.get("meta", {}).get("elements_file")
    if file:
        try:
            return list(json.loads(Path(str(file)).read_text(encoding="utf-8"))["elements"])
        except (OSError, ValueError, KeyError):
            return None
    listed = answer.get("elements")
    return list(listed) if isinstance(listed, list) else None


def plain(answer: dict[str, Any]) -> str:
    """A result of Hermes' tool as plain text. What the screen wrote is marked as the screen's."""
    if isinstance(answer.get("summary"), str):
        return from_page(cleared(answer["summary"]))
    lines: list[str] = []
    if "action" in answer:
        lines.append(f"{answer['action']}: {'done' if answer.get('ok') else 'not done'}.")
    if answer.get("message"):
        lines.append(from_page(str(answer["message"])))
    verdict = answer.get("verdict")
    if isinstance(verdict, dict) and verdict.get("hint"):
        lines.append(str(verdict["hint"]))
    for kind in ("apps", "windows"):
        listed = answer.get(kind)
        if isinstance(listed, list):
            named = [
                str(item.get("name") or item.get("title") or item.get("app_name") or "") for item in listed
            ]
            lines.append(f"{len(listed)} {kind}: " + from_page("; ".join(name for name in named if name)))
    return "\n".join(lines) or json.dumps(answer)


def must_be_watched(app: str, listed: Sequence[str]) -> bool:
    """Whether an app is one of the apps a person must watch: a listed name is whole words of its name."""
    named = f" {NOT_A_WORD.sub(' ', app.lower())} "
    return any(f" {NOT_A_WORD.sub(' ', one.lower()).strip()} " in named for one in listed if one.strip())


async def watched_if_it_must_be(session: BrowserSession, app: str) -> None:
    """Watch mode (spec 22.7), as in OpenAI's Operator: in an app a person must watch, the agent
    acts only while a person has the page open. It waits for one, and stops when nobody comes."""
    settings = session.config.computer
    if not app or not must_be_watched(app, settings.watch_apps):
        return
    ends = asyncio.get_running_loop().time() + settings.watch_wait_s
    while not session.watched():
        if asyncio.get_running_loop().time() >= ends:
            raise BrowserError(
                UNWATCHED.format(app=app, waited=round(settings.watch_wait_s)), reason="nobody watches"
            )
        await asyncio.sleep(settings.app_poll_ms / 1000)


async def computer_use(session: BrowserSession, args: ComputerUseArgs) -> str | Shown:
    driver = await session.driver(may_restart=True)
    if not isinstance(driver, HermesDriver):
        raise BrowserError("This session drives no machine.", reason="this is not a machine")
    asked = args.model_dump(exclude_none=True)
    if args.action == "capture":
        asked.setdefault("mode", session.config.computer.base.capture_mode)
    if args.app:
        driver.working_in = args.app
    if args.action in DELIVERED:
        await watched_if_it_must_be(session, driver.working_in)
    if args.action in PRESSES:
        driver.pressed_on(args.element if args.coordinate is None else None)
    how = delivery_for(session.config.computer)
    in_front = how == "foreground"
    if how and args.action in DELIVERED and "delivery_mode" not in asked:
        asked["delivery_mode"] = how
    if in_front and args.action in PRESSES and args.element is not None and args.coordinate is None:
        # Pressed by its number, a button that opens a box leaves its app not answering until the
        # box is closed (seen on Linux). On a desktop nobody sits at, the pointer presses it.
        pressed = await driver.press(args.element, args.action)
        if pressed == "nowhere":
            raise BadInput(NOT_ON_THE_SCREEN.format(element=args.element), reason="not on the screen")
        if pressed == "pressed" and not args.capture_after:
            return f"{args.action}: done. The pointer pressed element {args.element}.{LOOK_AGAIN}"
        if pressed == "pressed":
            # What it changed is looked at the way the tool itself would after an action.
            await asyncio.sleep(session.config.computer.settle_ms / 1000)
            asked = {"action": "capture", "mode": "ax"}
    if in_front and args.action == "type" and args.text and await driver.typed(args.text):
        return f"type: done. The desktop's keyboard typed {len(args.text)} characters.{LOOK_AGAIN}"
    result = await driver.use(asked)
    shown = session.config.computer.base.elements_shown
    label = session.config.computer.window_title_chars

    def said(summary: str, elements: list[dict[str, Any]]) -> str:
        driver.saw(elements)
        return of_a_capture(summary, elements, shown, label, on_the_screen=in_front)

    shot = as_shot(result)
    if shot is not None:
        elements = await asyncio.to_thread(every_element, result)
        summary = str(result.get("text_summary", ""))
        # Up to a hundred elements the tool's own text stands; past that, ours names the page first.
        text = said(summary, elements) if elements is not None else cleared(summary)
        return Shown(from_page(text), shot.picture)
    answer = json.loads(result) if isinstance(result, str) else result
    if not isinstance(answer, dict):
        return str(result)
    if "error" not in answer and isinstance(answer.get("summary"), str):
        elements = await asyncio.to_thread(every_element, answer)
        if elements is not None:
            return from_page(said(answer["summary"], elements))
    if "error" in answer:
        hint = f" {answer['hint']}" if answer.get("hint") else ""
        reason = REFUSALS.get(str(answer.get("code")), "the machine did not do it")
        if NO_WINDOW in str(answer["error"]):
            raise BrowserError(NOTHING_IS_OPEN, reason="no window is open")
        if any(sign in str(answer["error"]) for sign in STOPPED_ANSWERING) and await driver.started_again():
            raise BrowserError(STARTED_AGAIN, reason="the driver stopped answering")
        raise BrowserError(f"{answer['error']}{hint}", reason=reason)
    if answer.get("ok") is False:
        # The driver answered, and did not do it. That is a failure, with what the driver said.
        raise BrowserError(plain(answer), reason="the machine did not do it")
    return plain(answer)


COMPUTER_USE = ToolDefinition(
    NAME,
    "Work on this machine's own screen: Windows, macOS or Linux. First action=capture: mode=som gives "
    "a picture with a number on every element that can be acted on, mode=ax the elements alone. Then "
    "act on an element by its number: action=click with element. Use coordinate only where an app "
    "shows no elements. action=type types where the focus is; action=key presses a key or a chord, "
    "such as return or ctrl+s. Input goes to the window in the background and leaves the person's "
    "pointer alone. Each result says whether the effect was confirmed and what to do next: follow "
    "it, never repeat input that was confirmed, and capture again before you retry one that was not.",
    ComputerUseArgs,
    computer_use,
)
