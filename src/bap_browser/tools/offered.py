"""The tools an agent is offered (spec 6): each with its name, what it says of itself, what it
is given, and what does it. A tool that is not in this list does not exist for an agent.
"""

from __future__ import annotations

from bap_browser.tools.arguments import (
    CheckArgs,
    ClickArgs,
    ConsoleArgs,
    DialogArgs,
    DragArgs,
    EvaluateArgs,
    FillFormArgs,
    FindArgs,
    NavigateArgs,
    NetworkArgs,
    NoArgs,
    PressKeyArgs,
    RefArgs,
    RequestHumanArgs,
    RunArgs,
    ScreenshotArgs,
    ScrollArgs,
    SelectArgs,
    SnapshotArgs,
    TabsArgs,
    TargetArgs,
    TextArgs,
    TypeArgs,
    UploadArgs,
    WaitArgs,
    ZoomArgs,
)
from bap_browser.tools.browser_tools import (
    RUN_A_SCRIPT,
    click,
    console,
    downloads,
    drag,
    evaluate,
    fill_form,
    find,
    get_text,
    go_back,
    go_forward,
    handle_dialog,
    hover,
    navigate,
    network,
    press_key,
    reload,
    request_human,
    run,
    screenshot,
    scroll,
    scroll_to,
    select_option,
    set_checked,
    snapshot,
    tabs,
    type_text,
    upload_file,
    wait,
    zoom,
)
from bap_browser.tools.registry import ToolDefinition

TOOLS: tuple[ToolDefinition, ...] = (
    ToolDefinition(
        "browser_navigate",
        "Open a URL in the current tab and return the page snapshot. A URL with no scheme gets https://.",
        NavigateArgs,
        navigate,
    ),
    ToolDefinition("browser_go_back", "Go back one page in history.", NoArgs, go_back),
    ToolDefinition("browser_go_forward", "Go forward one page in history.", NoArgs, go_forward),
    ToolDefinition("browser_reload", "Reload the page.", NoArgs, reload),
    ToolDefinition(
        "browser_snapshot",
        "Read the page as text: one line per element, each with a ref such as e12. "
        "mode 'interactive' (default) lists controls and headings; 'all' adds text and structure. "
        "Give ref to read only that element's subtree.",
        SnapshotArgs,
        snapshot,
    ),
    ToolDefinition(
        "browser_get_text",
        "The visible text of the page, or of one element by ref. No refs: use it to read, not to act.",
        TextArgs,
        get_text,
    ),
    ToolDefinition(
        "browser_find",
        "Find elements by words in their name or text. Returns matching snapshot lines with refs, "
        "best first. Cheaper than a snapshot of a large page.",
        FindArgs,
        find,
    ),
    ToolDefinition(
        "browser_screenshot",
        "A picture of what the browser shows, or of the whole page with full_page. Use it only when "
        "the text of the page is not enough. annotate draws each element's ref on the picture.",
        ScreenshotArgs,
        screenshot,
    ),
    ToolDefinition(
        "browser_zoom",
        "A closer picture of a region [x0, y0, x1, y1] of the last screenshot, in its pixels.",
        ZoomArgs,
        zoom,
    ),
    ToolDefinition(
        "browser_click",
        "Click an element by its ref from the latest snapshot, or a point by x and y in page pixels.",
        ClickArgs,
        click,
    ),
    ToolDefinition(
        "browser_hover",
        "Move the pointer over an element by ref, or to x and y, to open a menu or a tooltip.",
        TargetArgs,
        hover,
    ),
    ToolDefinition(
        "browser_drag",
        "Drag from an element (from_ref) or a point (from_xy: [x, y]) to an element (to_ref) or a "
        "point (to_xy).",
        DragArgs,
        drag,
    ),
    ToolDefinition(
        "browser_type",
        "Type text into an element by ref, or into the focused element when no ref is given. "
        "clear replaces what is there; submit presses Enter afterwards.",
        TypeArgs,
        type_text,
    ),
    ToolDefinition(
        "browser_fill_form",
        "Fill several fields in one call. value is text for a text field, a label or value for a "
        "dropdown, true or false for a checkbox or radio button.",
        FillFormArgs,
        fill_form,
    ),
    ToolDefinition(
        "browser_select_option",
        "Choose options of a dropdown (select element) by label or value.",
        SelectArgs,
        select_option,
    ),
    ToolDefinition(
        "browser_set_checked",
        "Set a checkbox, radio button or switch to checked or not checked.",
        CheckArgs,
        set_checked,
    ),
    ToolDefinition(
        "browser_press_key",
        "Press a key or a chord such as Enter, Escape, ArrowDown or Control+a, on the focused element "
        "or on ref.",
        PressKeyArgs,
        press_key,
    ),
    ToolDefinition(
        "browser_scroll",
        "Scroll by steps. With ref, or x and y, scrolls the box under that place; otherwise the page.",
        ScrollArgs,
        scroll,
    ),
    ToolDefinition("browser_scroll_to", "Scroll an element into view.", RefArgs, scroll_to),
    ToolDefinition(
        "browser_wait",
        "Wait for one of: text to appear, text_gone to disappear, a load_state, or seconds.",
        WaitArgs,
        wait,
    ),
    ToolDefinition(
        "browser_handle_dialog",
        "Answer the alert, confirm or prompt dialog a page has opened: accept or dismiss. "
        "prompt_text is what to enter in a prompt.",
        DialogArgs,
        handle_dialog,
    ),
    ToolDefinition(
        "browser_tabs",
        "List the tabs, open a new one (empty, or on url), switch to one or close one by tab_id.",
        TabsArgs,
        tabs,
    ),
    ToolDefinition(
        "browser_console",
        "The page's console messages and errors, oldest first. level is the least serious to show.",
        ConsoleArgs,
        console,
    ),
    ToolDefinition(
        "browser_network",
        "The requests the page made: method, status, type, address. filter keeps the addresses that "
        "hold that text.",
        NetworkArgs,
        network,
    ),
    ToolDefinition(
        "browser_evaluate",
        "Run a JavaScript expression in the page and return its value as JSON. A person is asked first.",
        EvaluateArgs,
        evaluate,
    ),
    ToolDefinition(
        "browser_upload_file",
        "Give files to a file field, or to the button that opens a file chooser. paths are file names "
        "in the upload folder. A person is asked first.",
        UploadArgs,
        upload_file,
    ),
    ToolDefinition(
        "browser_downloads", "The files downloaded in this session, with size and path.", NoArgs, downloads
    ),
    ToolDefinition(
        "browser_request_human",
        "Ask the person watching to do a step you must not do: a sign-in, a CAPTCHA or other human "
        "check, a code, a payment. Waits until they answer. Never try to solve such a step yourself.",
        RequestHumanArgs,
        request_human,
    ),
    ToolDefinition(
        RUN_A_SCRIPT,
        "Do several steps in one call with a short Python script. `browser` has the tools as async "
        'methods (`await browser.click(find="Next")`); print() and the last expression come back; '
        "`state` is kept between scripts. No imports. Each step is checked like a single call.",
        RunArgs,
        run,
    ),
)
