"""The tools by kind: which only read, which go where the focus is, which touch no site, and so
on. The toolkit and the safety code decide by these what a call is."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, get_args

from bap_browser.tools.browser_tools import RUN_A_SCRIPT
from bap_browser.tools.computer_tools import COMPUTER_NAMES, OURS_LOOK
from bap_browser.tools.computer_use_tool import COMPUTER_USE, LOOKS, Action

BY_ITS_ACTION = COMPUTER_USE.name
ITS_KINDS = frozenset(f"{BY_ITS_ACTION}.{action}" for action in get_args(Action)) | {BY_ITS_ACTION}
IT_LOOKS = frozenset(f"{BY_ITS_ACTION}.{action}" for action in LOOKS)


def of(name: str, arguments: Mapping[str, Any]) -> str:
    """The kind a call is judged by: the tool's name, or for a tool that does many things the tool
    and the action."""
    action = arguments.get("action") if name == BY_ITS_ACTION else None
    return f"{name}.{action}" if isinstance(action, str) else name


POINTED = frozenset({"browser_click", "browser_hover"})
READS = frozenset(
    {
        "browser_snapshot",
        "browser_get_text",
        "browser_find",
        "browser_screenshot",
        "browser_zoom",
        "browser_console",
        "browser_network",
        "browser_downloads",
        "browser_wait",
        "browser_request_human",
        "browser_begin_task",
    }
    | OURS_LOOK
    | IT_LOOKS
)
DECLARES_A_TASK = "browser_begin_task"
LISTS_THE_TABS = ("browser_tabs", "list")
TYPES_ON_A_MACHINE = f"{BY_ITS_ACTION}.type"
PRESSES_ON_A_MACHINE = f"{BY_ITS_ACTION}.key"
SETS_ON_A_MACHINE = f"{BY_ITS_ACTION}.set_value"
GO_WHERE_THE_FOCUS_IS = frozenset(
    {"browser_type", "browser_press_key", TYPES_ON_A_MACHINE, PRESSES_ON_A_MACHINE}
)
NO_SITE_IN_A_BROWSER = frozenset(
    {"browser_request_human", "browser_wait", "browser_downloads", DECLARES_A_TASK}
)
NEED_NO_SITE = NO_SITE_IN_A_BROWSER | COMPUTER_NAMES | ITS_KINDS
ANSWERS_A_DIALOG = "browser_handle_dialog"
RUN_BESIDE_A_DIALOG = frozenset(
    {
        ANSWERS_A_DIALOG,
        "browser_tabs",
        "browser_console",
        "browser_network",
        "browser_downloads",
        DECLARES_A_TASK,
    }
)
NO_STEP_ON_A_PAGE = (
    NO_SITE_IN_A_BROWSER
    | {"browser_tabs", ANSWERS_A_DIALOG, RUN_A_SCRIPT}
    | OURS_LOOK
    | (IT_LOOKS - {f"{BY_ITS_ACTION}.capture"})
)
CHANGES_UNSEEN = frozenset({"browser_hover"})
TOLD_BY_ITS_RESULT = READS | {"browser_evaluate"}
PRESSES_KEYS = frozenset({"browser_press_key", PRESSES_ON_A_MACHINE})
