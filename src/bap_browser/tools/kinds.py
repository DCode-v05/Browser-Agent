"""The tools by kind: which only read, which go where the focus is, which touch no site, and so
on. The toolkit and the safety code decide by these what a call is."""

from __future__ import annotations

from bap_browser.tools.browser_tools import RUN_A_SCRIPT
from bap_browser.tools.computer_tools import (
    COMPUTER_KEYS,
    COMPUTER_NAMES,
    COMPUTER_NO_STEP,
    COMPUTER_POINTED,
    COMPUTER_READS,
)

# The tools whose x and y are where the pointer goes. For browser_scroll they are only where the wheel turns.
POINTED = frozenset({"browser_click", "browser_hover"}) | COMPUTER_POINTED
# The tools that only read, or only wait. With "ask before every action" these are still not asked about.
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
    | COMPUTER_READS
)
DECLARES_A_TASK = "browser_begin_task"
# The one use of the tabs tool that changes nothing: it tells which tabs are open.
LISTS_THE_TABS = ("browser_tabs", "list")
# The tools whose keys go to the element that has the focus when they name no element.
GO_WHERE_THE_FOCUS_IS = frozenset({"browser_type", "browser_press_key"}) | COMPUTER_KEYS
# The tools that touch no site: asking a person, waiting, and the list of saved files.
NO_SITE_IN_A_BROWSER = frozenset(
    {"browser_request_human", "browser_wait", "browser_downloads", DECLARES_A_TASK}
)
# A desktop has no site at all (spec 21.6).
NEED_NO_SITE = NO_SITE_IN_A_BROWSER | COMPUTER_NAMES
ANSWERS_A_DIALOG = "browser_handle_dialog"
# While a page has a dialog open it answers nothing. Only these tools need nothing from it (spec 5.7).
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
# The tools that are no step on a page. They are not watched for going round in circles.
NO_STEP_ON_A_PAGE = NO_SITE_IN_A_BROWSER | {"browser_tabs", ANSWERS_A_DIALOG, RUN_A_SCRIPT} | COMPUTER_NO_STEP
# What a hover brings up is often drawn by a style, which cannot be seen from here.
# The pointer itself is in no picture of a desktop.
CHANGES_UNSEEN = frozenset({"browser_hover", "computer_move"})
# A script in the page is mostly a way to read it. Whether it repeats itself is told by what it gives.
TOLD_BY_ITS_RESULT = READS | {"browser_evaluate"}
# The tools that press keys. A key that types a character is typed text.
PRESSES_KEYS = frozenset({"browser_press_key", "computer_press_key"})
