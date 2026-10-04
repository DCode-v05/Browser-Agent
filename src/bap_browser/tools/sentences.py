"""The sentences a person reads in the viewer's timeline (spec 9.7).

A label says what the agent is doing, a summary what happened. Typed text appears as a character
count, never as the text.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit

from bap_browser.driver.base import Located
from bap_browser.tools.registry import REF_PATTERN

# A row is under 60 characters.
ROW_CHARS = 59
CUT = "…"
# What is left of an element's name when a row has to be shortened.
SHORTEST_NAME = 12


def label_for(tool: str, arguments: Mapping[str, Any], target: Located | None) -> str:
    """What the agent is doing: 'Clicking "Create account"'."""
    match tool:
        case "browser_navigate":
            return _row("Opening ", _address(arguments), "")
        case "browser_snapshot":
            return "Reading the page"
        case "browser_click":
            return _row("Clicking ", _element(arguments, target), "")
        case "browser_type":
            return _row(f"Typing {_count(arguments, target)}", _into(arguments, target), "")
    return _fit(tool)


def summary_for(tool: str, arguments: Mapping[str, Any], target: Located | None, failure: str | None) -> str:
    """What happened: 'Clicked "Create account" (button)', or 'Could not click "Pay": it is covered'."""
    if failure is not None:
        return _fit(_row("Could not ", _attempt(tool, arguments, target), "") + f": {failure}")
    match tool:
        case "browser_navigate":
            return _row("Opened ", _address(arguments), "")
        case "browser_snapshot":
            return "Read the page"
        case "browser_click":
            kind = f" ({target.role})" if target is not None and target.name else ""
            return _row("Clicked ", _element(arguments, target), kind)
        case "browser_type":
            return _row(f"Typed {_count(arguments, target)}", _into(arguments, target), "")
    return _fit(tool)


def _attempt(tool: str, arguments: Mapping[str, Any], target: Located | None) -> str:
    match tool:
        case "browser_navigate":
            return f"open {_address(arguments)}"
        case "browser_snapshot":
            return "read the page"
        case "browser_click":
            return f"click {_element(arguments, target)}".rstrip()
        case "browser_type":
            return f"type{_into(arguments, target)}"
    return f"run {tool}"


def _address(arguments: Mapping[str, Any]) -> str:
    """The site and the path, the way a person says an address. A name and password before the site,
    and the query, can hold secrets and are left out."""
    url = arguments.get("url")
    if not isinstance(url, str) or not url:
        return "a page"
    parts = urlsplit(url if "://" in url or url.startswith(("about:", "data:", "blob:")) else f"//{url}")
    if not parts.netloc:
        return f"{parts.scheme}:{parts.path}" if parts.scheme else url
    return parts.netloc.rpartition("@")[2] + parts.path.rstrip("/")


def _element(arguments: Mapping[str, Any], target: Located | None) -> str:
    if target is not None:
        return f'"{target.name}"' if target.name else f"a {target.role}"
    ref = arguments.get("ref")
    # Anything else an agent put there is not a ref, and is not repeated to the person watching.
    return ref if isinstance(ref, str) and re.fullmatch(REF_PATTERN, ref) else ""


def _into(arguments: Mapping[str, Any], target: Located | None) -> str:
    element = _element(arguments, target)
    return f" into {element}" if element else ""


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
