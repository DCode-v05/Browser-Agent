"""`computer_use`: Hermes' tool for a real machine (spec 22.4), as this engine offers it.

It takes what Hermes' tool takes and returns what a tool here returns: short plain text, with a
picture only where a capture was asked for one.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import Field

from bap_browser.config_computer import Computer
from bap_browser.driver.hermes_driver import HermesDriver, as_shot
from bap_browser.driver.session import BrowserSession
from bap_browser.errors import BrowserError
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
# The roles of an app's menus, as the systems name them.
MENUS = frozenset({"menu", "menu item", "MenuItem", "Menu", "AXMenuItem", "AXMenu", "AXMenuBarItem"})
# What marks a line of the tool's text that names a file on the engine's machine. No model here
# can read one, and its path is nothing a result should hold.
OF_THIS_MACHINE = ("saved to", "read_file", "search_files")
REFUSALS = {"human_has_control": "a person has the screen"}


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


def of_a_capture(summary: str, elements: list[dict[str, Any]], shown: int, label: int) -> str:
    """What a capture says in text: what was captured, and its elements by number. Hermes' own text
    names the first forty as the window gives them, which in an app with large menus is menus alone.
    Here the page comes first and the menus after, and no file of the engine's machine is named."""
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


async def computer_use(session: BrowserSession, args: ComputerUseArgs) -> str | Shown:
    driver = await session.driver(may_restart=True)
    if not isinstance(driver, HermesDriver):
        raise BrowserError("This session drives no machine.", reason="this is not a machine")
    asked = args.model_dump(exclude_none=True)
    how = delivery_for(session.config.computer)
    if how and args.action in DELIVERED and "delivery_mode" not in asked:
        asked["delivery_mode"] = how
    result = await driver.use(asked)
    shown = session.config.computer.base.elements_shown
    label = session.config.computer.window_title_chars
    shot = as_shot(result)
    if shot is not None:
        elements = await asyncio.to_thread(every_element, result)
        summary = str(result.get("text_summary", ""))
        # Up to a hundred elements the tool's own text stands; past that, ours names the page first.
        text = of_a_capture(summary, elements, shown, label) if elements is not None else cleared(summary)
        return Shown(from_page(text), shot.picture)
    answer = json.loads(result) if isinstance(result, str) else result
    if not isinstance(answer, dict):
        return str(result)
    if "error" not in answer and isinstance(answer.get("summary"), str):
        elements = await asyncio.to_thread(every_element, answer)
        if elements is not None:
            return from_page(of_a_capture(answer["summary"], elements, shown, label))
    if "error" in answer:
        hint = f" {answer['hint']}" if answer.get("hint") else ""
        reason = REFUSALS.get(str(answer.get("code")), "the machine did not do it")
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
