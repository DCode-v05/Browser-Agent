"""The sentences a person reads in the viewer's timeline (spec 9.7).

A label says what the agent is doing, a summary what happened. Typed text appears as a character
count, never as the text.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import PurePosixPath
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
        case "browser_request_human":
            return _row("Asking for help: ", _reason(arguments), "")
        case "browser_screenshot":
            return "Taking a screenshot"
        case "browser_zoom":
            return "Looking closer at the screenshot"
        case "browser_drag":
            return _row("Dragging ", _dragged(arguments, target), "")
        case "browser_handle_dialog":
            return "Dismissing the dialog" if arguments.get("action") == "dismiss" else "Accepting the dialog"
        case "browser_tabs":
            return _fit(_TABS_DOING.get(_tab_action(arguments), "Looking at the tabs") + _tab(arguments))
        case "browser_console":
            return "Reading the console"
        case "browser_network":
            return "Reading the network log"
        case "browser_evaluate":
            return "Running a script in the page"
        case "browser_upload_file":
            return _row("Uploading ", _files(arguments), "")
        case "browser_downloads":
            return "Listing the downloads"
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
        case "browser_request_human":
            return _row("Asked for help: ", _reason(arguments), "")
        case "browser_screenshot":
            return "Took a screenshot"
        case "browser_zoom":
            return "Looked closer at the screenshot"
        case "browser_drag":
            return _row("Dragged ", _dragged(arguments, target), "")
        case "browser_handle_dialog":
            return "Dismissed the dialog" if arguments.get("action") == "dismiss" else "Accepted the dialog"
        case "browser_tabs":
            return _fit(_TABS_DONE.get(_tab_action(arguments), "Looked at the tabs") + _tab(arguments))
        case "browser_console":
            return "Read the console"
        case "browser_network":
            return "Read the network log"
        case "browser_evaluate":
            return "Ran a script in the page"
        case "browser_upload_file":
            return _row("Uploaded ", _files(arguments), "")
        case "browser_downloads":
            return "Listed the downloads"
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
        case "browser_request_human":
            return "get help"
        case "browser_screenshot":
            return "take a screenshot"
        case "browser_zoom":
            return "look closer at the screenshot"
        case "browser_drag":
            return f"drag {_dragged(arguments, target)}".rstrip()
        case "browser_handle_dialog":
            return "answer the dialog"
        case "browser_tabs":
            return _TABS_TO_DO.get(_tab_action(arguments), "look at the tabs") + _tab(arguments)
        case "browser_console":
            return "read the console"
        case "browser_network":
            return "read the network log"
        case "browser_evaluate":
            return "run a script in the page"
        case "browser_upload_file":
            return f"upload {_files(arguments)}"
        case "browser_downloads":
            return "list the downloads"
    return f"run {tool}"


_TABS_DOING = {
    "list": "Listing the tabs",
    "new": "Opening a tab",
    "switch": "Switching to",
    "close": "Closing",
}
_TABS_DONE = {"list": "Listed the tabs", "new": "Opened a tab", "switch": "Switched to", "close": "Closed"}
_TABS_TO_DO = {"list": "list the tabs", "new": "open a tab", "switch": "switch to", "close": "close"}


def _tab_action(arguments: Mapping[str, Any]) -> str:
    action = arguments.get("action")
    return action if isinstance(action, str) else ""


def _tab(arguments: Mapping[str, Any]) -> str:
    """The tab a switch or a close names, to follow the verb."""
    if arguments.get("action") not in ("switch", "close"):
        return ""
    tab = arguments.get("tab_id")
    return f" {tab}" if isinstance(tab, str) and re.fullmatch(r"t\d+", tab) else " the tab"


def _dragged(arguments: Mapping[str, Any], target: Located | None) -> str:
    """What a drag picks up: the element it starts on."""
    return _element({"ref": arguments.get("from_ref")}, target)


def _files(arguments: Mapping[str, Any]) -> str:
    """The files of an upload by name, without their folders."""
    paths = arguments.get("paths")
    if not isinstance(paths, list) or not paths or not all(isinstance(path, str) for path in paths):
        return "a file"
    first = PurePosixPath(paths[0].replace("\\", "/")).name or "a file"
    return first if len(paths) == 1 else f"{first} and {len(paths) - 1} more"


def _reason(arguments: Mapping[str, Any]) -> str:
    reason = arguments.get("reason")
    return f'"{" ".join(reason.split())}"' if isinstance(reason, str) and reason.strip() else "a person"


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
