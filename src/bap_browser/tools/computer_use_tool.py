"""`computer_use`: Hermes' tool for a real machine (spec 22.4), as this engine offers it.

It takes what Hermes' tool takes and returns what a tool here returns: short plain text, with a
picture only where a capture was asked for one.
"""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import Field

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


def plain(answer: dict[str, Any]) -> str:
    """A result of Hermes' tool as plain text. What the screen wrote is marked as the screen's."""
    if isinstance(answer.get("summary"), str):
        return from_page(answer["summary"])
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
    result = await driver.use(args.model_dump(exclude_none=True))
    shot = as_shot(result)
    if shot is not None:
        return Shown(from_page(str(result.get("text_summary", ""))), shot.picture)
    answer = json.loads(result) if isinstance(result, str) else result
    if not isinstance(answer, dict):
        return str(result)
    if "error" in answer:
        hint = f" {answer['hint']}" if answer.get("hint") else ""
        reason = REFUSALS.get(str(answer.get("code")), "the machine did not do it")
        raise BrowserError(f"{answer['error']}{hint}", reason=reason)
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
