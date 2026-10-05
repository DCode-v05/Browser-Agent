"""The sentences a person reads in the viewer's timeline (spec 9.7).

A label says what the agent is doing, a summary what happened. Typed text appears as a character
count, never as the text.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit

from bap_browser import keys
from bap_browser.driver.base import POINT, Located
from bap_browser.policy.address import presentable_address
from bap_browser.tools.registry import REF_PATTERN

# A row is under 60 characters.
ROW_CHARS = 59
CUT = "…"
# What is left of an element's name when a row has to be shortened.
SHORTEST_NAME = 12


DIRECTIONS = ("up", "down", "left", "right")


def label_for(tool: str, arguments: Mapping[str, Any], target: Located | None) -> str:
    """What the agent is doing: 'Clicking "Create account"'."""
    match tool:
        case "browser_navigate":
            return _row("Opening ", _address(arguments), "")
        case "browser_go_back":
            return "Going back"
        case "browser_go_forward":
            return "Going forward"
        case "browser_reload":
            return "Reloading the page"
        case "browser_snapshot" | "browser_get_text":
            return "Reading the page"
        case "browser_find":
            return _row("Looking for ", _query(arguments), "")
        case "browser_click":
            return _row("Clicking ", _element(arguments, target), "")
        case "browser_hover":
            return _row("Pointing at ", _element(arguments, target), "")
        case "browser_type":
            return _row(f"Typing {_count(arguments, target)}", _into(arguments, target), "")
        case "browser_fill_form":
            return f"Filling {_fields(arguments)}"
        case "browser_select_option":
            return _row("Choosing an option", _in(arguments, target), "")
        case "browser_set_checked":
            verb = "Clearing " if arguments.get("checked") is False else "Checking "
            return _row(verb, _element(arguments, target), "")
        case "browser_press_key":
            return _fit(f"Pressing {_key(arguments)}")
        case "browser_scroll":
            return f"Scrolling{_direction(arguments)}"
        case "browser_scroll_to":
            return _row("Scrolling to ", _element(arguments, target), "")
        case "browser_wait":
            return f"Waiting{_awaited(arguments)}"
    return _fit(tool)


def summary_for(tool: str, arguments: Mapping[str, Any], target: Located | None, failure: str | None) -> str:
    """What happened: 'Clicked "Create account" (button)', or 'Could not click "Pay": it is covered'."""
    if failure is not None:
        return _fit(_row("Could not ", _attempt(tool, arguments, target), "") + f": {failure}")
    match tool:
        case "browser_navigate":
            return _row("Opened ", _address(arguments), "")
        case "browser_go_back":
            return "Went back"
        case "browser_go_forward":
            return "Went forward"
        case "browser_reload":
            return "Reloaded the page"
        case "browser_snapshot" | "browser_get_text":
            return "Read the page"
        case "browser_find":
            return _row("Looked for ", _query(arguments), "")
        case "browser_click":
            kind = f" ({target.role})" if target is not None and target.name else ""
            return _row("Clicked ", _element(arguments, target), kind)
        case "browser_hover":
            return _row("Pointed at ", _element(arguments, target), "")
        case "browser_type":
            return _row(f"Typed {_count(arguments, target)}", _into(arguments, target), "")
        case "browser_fill_form":
            return f"Filled {_fields(arguments)}"
        case "browser_select_option":
            return _row("Chose an option", _in(arguments, target), "")
        case "browser_set_checked":
            verb = "Cleared " if arguments.get("checked") is False else "Checked "
            return _row(verb, _element(arguments, target), "")
        case "browser_press_key":
            return _fit(f"Pressed {_key(arguments)}")
        case "browser_scroll":
            return f"Scrolled{_direction(arguments)}"
        case "browser_scroll_to":
            return _row("Scrolled to ", _element(arguments, target), "")
        case "browser_wait":
            return f"Waited{_awaited(arguments)}"
    return _fit(tool)


def _attempt(tool: str, arguments: Mapping[str, Any], target: Located | None) -> str:
    element = _element(arguments, target)
    match tool:
        case "browser_navigate":
            return f"open {_address(arguments)}"
        case "browser_go_back":
            return "go back"
        case "browser_go_forward":
            return "go forward"
        case "browser_reload":
            return "reload the page"
        case "browser_snapshot" | "browser_get_text":
            return "read the page"
        case "browser_find":
            return "search the page"
        case "browser_click":
            return f"click {element}".rstrip()
        case "browser_hover":
            return f"point at {element}".rstrip() if element else "move the pointer"
        case "browser_type":
            return f"type{_into(arguments, target)}"
        case "browser_fill_form":
            return "fill the form"
        case "browser_select_option":
            return f"choose an option{_in(arguments, target)}"
        case "browser_set_checked":
            verb = "clear" if arguments.get("checked") is False else "check"
            return f"{verb} {element}".rstrip() if element else f"{verb} the box"
        case "browser_press_key":
            return f"press {_key(arguments)}"
        case "browser_scroll":
            return f"scroll{_direction(arguments)}"
        case "browser_scroll_to":
            return f"scroll to {element}" if element else "scroll"
        case "browser_wait":
            return f"wait{_awaited(arguments)}" if _awaited(arguments) else "finish waiting"
    return f"run {tool}"


def _query(arguments: Mapping[str, Any]) -> str:
    query = arguments.get("query")
    return f'"{" ".join(query.split())}"' if isinstance(query, str) and query.strip() else "elements"


def _fields(arguments: Mapping[str, Any]) -> str:
    fields = arguments.get("fields")
    if not isinstance(fields, list) or not fields:
        return "a form"
    return f"{len(fields)} field{'' if len(fields) == 1 else 's'}"


def _key(arguments: Mapping[str, Any]) -> str:
    """The key by name. A key that types a character is typed text, and is not named."""
    pressed = arguments.get("keys")
    if not isinstance(pressed, str) or keys.is_typed_text(pressed):
        return "a key"
    return keys.normalise(pressed)


def _direction(arguments: Mapping[str, Any]) -> str:
    direction = arguments.get("direction")
    return f" {direction}" if direction in DIRECTIONS else ""


def _awaited(arguments: Mapping[str, Any]) -> str:
    # The text waited for may be something the agent typed: the row says only that it waits for text.
    if isinstance(arguments.get("text"), str):
        return " for text to appear"
    if isinstance(arguments.get("text_gone"), str):
        return " for text to go"
    if isinstance(arguments.get("load_state"), str):
        return " for the page to load"
    return ""


def _address(arguments: Mapping[str, Any]) -> str:
    """The site and the path, the way a person says an address. A name and password before the site,
    and the query, can hold secrets and are left out."""
    url = arguments.get("url")
    shown = presentable_address(url) if isinstance(url, str) else None
    if shown is None:
        return "a page"
    parts = urlsplit(shown)
    return parts.netloc + parts.path.rstrip("/") if parts.netloc else shown


def _element(arguments: Mapping[str, Any], target: Located | None) -> str:
    if target is not None and target.role == POINT and target.box is not None:
        return f"the page at {target.box.x:g}, {target.box.y:g}"
    if target is not None:
        return f'"{target.name}"' if target.name else f"a {target.role}"
    ref = arguments.get("ref")
    # Anything else an agent put there is not a ref, and is not repeated to the person watching.
    return ref if isinstance(ref, str) and re.fullmatch(REF_PATTERN, ref) else ""


def _into(arguments: Mapping[str, Any], target: Located | None) -> str:
    element = _element(arguments, target)
    return f" into {element}" if element else ""


def _in(arguments: Mapping[str, Any], target: Located | None) -> str:
    element = _element(arguments, target)
    return f" in {element}" if element else ""


def _count(arguments: Mapping[str, Any], target: Located | None) -> str:
    if target is not None and target.secret:
        return "a password"
    text = arguments.get("text")
    if not isinstance(text, str):
        return ""
    return f"{len(text)} character{'' if len(text) == 1 else 's'}"


def _row(before: str, subject: str, after: str) -> str:
    """Joins the parts, shortening a quoted name first so that the words around it stay whole."""
    row = (before + subject + after).rstrip()
    over = len(row) - ROW_CHARS
    if over > 0 and subject.startswith('"') and subject.endswith('"'):
        name = subject[1:-1]
        keep = max(len(name) - over - len(CUT), SHORTEST_NAME)
        if keep < len(name):
            row = f'{before}"{name[:keep].rstrip()}{CUT}"{after}'
    return _fit(row)


def _fit(row: str) -> str:
    return row if len(row) <= ROW_CHARS else row[: ROW_CHARS - len(CUT)].rstrip() + CUT
