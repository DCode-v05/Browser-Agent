"""The tools of computer use (spec 21.5): what an agent does on the contained desktop.

A desktop is seen as a picture and acted on by its pixels. No tool returns a picture that was not
asked for: an action says what it did in a sentence, and `computer_screenshot` shows the result.
"""

from __future__ import annotations

import asyncio
from typing import Literal

from pydantic import Field, model_validator

from bap_browser import keys
from bap_browser.driver.contained_desktop import APPS, allowed_apps
from bap_browser.driver.desktop_driver import DesktopDriver
from bap_browser.driver.session import BrowserSession
from bap_browser.errors import BadInput, BrowserError
from bap_browser.safeguards.reading import from_page
from bap_browser.tools.arguments import Modifier, NoArgs, RequestHumanArgs
from bap_browser.tools.browser_tools import request_human
from bap_browser.tools.registry import Args, Shown, ToolDefinition

LOOK = " Take a screenshot to see the result."


class PointArgs(Args):
    x: float = Field(ge=0)
    y: float = Field(ge=0)


class ClickArgs(PointArgs):
    button: Literal["left", "right", "middle"] = "left"
    click_count: int = Field(default=1, ge=1, le=3)
    # Pydantic copies the default for each call. A plain default, unlike a factory, appears in the schema.
    modifiers: list[Modifier] = Field(default=[])


class DragArgs(Args):
    from_xy: list[float] = Field(min_length=2, max_length=2)
    to_xy: list[float] = Field(min_length=2, max_length=2)


class TypeArgs(Args):
    text: str = Field(min_length=1)
    submit: bool = False


class PressKeyArgs(Args):
    keys: str
    repeat: int = Field(default=1, ge=1, le=50)


class ScrollArgs(Args):
    direction: Literal["up", "down", "left", "right"]
    amount: int = Field(default=1, ge=1, le=20)
    x: float | None = Field(default=None, ge=0)
    y: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _a_whole_point(self) -> ScrollArgs:
        if (self.x is None) != (self.y is None):
            raise ValueError("give both x and y, or neither")
        return self


class ZoomArgs(Args):
    region: list[float] = Field(min_length=4, max_length=4)


class WaitArgs(Args):
    seconds: float = Field(gt=0)


class OpenAppArgs(Args):
    app: str = Field(min_length=1, max_length=40)


async def _desktop(session: BrowserSession) -> DesktopDriver:
    driver = await session.driver(may_restart=True)
    if not isinstance(driver, DesktopDriver):
        raise BrowserError("This session has no desktop: it is a browser.", reason="this is not a desktop")
    return driver


async def _windows(driver: DesktopDriver) -> str:
    """The open windows, as a line of a result. Their titles are written by what is open in them."""
    titles = await driver.windows()
    if not titles:
        return "No window is open."
    return "Open windows: " + from_page("; ".join(titles)) + "."


async def screenshot(session: BrowserSession, args: NoArgs) -> Shown:
    driver = await _desktop(session)
    shot = await driver.screenshot(full_page=False, annotate=False)
    return Shown(
        f"Screenshot of the desktop, {shot.width} by {shot.height} pixels. x and y of every tool are "
        "pixels of this picture, from its top left.",
        shot.picture,
    )


async def zoom(session: BrowserSession, args: ZoomArgs) -> Shown:
    driver = await _desktop(session)
    x0, y0, x1, y1 = args.region
    shot = await driver.zoom((x0, y0, x1, y1))
    return Shown(
        f"The region ({x0:g}, {y0:g}) to ({x1:g}, {y1:g}) of the screen at twice its size, "
        f"{shot.width} by {shot.height} pixels. Give x and y in the pixels of a screenshot, not of this picture.",
        shot.picture,
    )


async def click(session: BrowserSession, args: ClickArgs) -> str:
    driver = await _desktop(session)
    done = await driver.click_at(
        args.x, args.y, button=args.button, click_count=args.click_count, modifiers=args.modifiers
    )
    how = {1: "Clicked", 2: "Double-clicked", 3: "Triple-clicked"}[args.click_count]
    button = "" if args.button == "left" else f" with the {args.button} button"
    return f"{how} {done.target}{button}.{LOOK}"


async def move(session: BrowserSession, args: PointArgs) -> str:
    driver = await _desktop(session)
    done = await driver.hover_at(args.x, args.y)
    return f"Moved the pointer to {done.target}.{LOOK}"


async def drag(session: BrowserSession, args: DragArgs) -> str:
    driver = await _desktop(session)
    start, end = (args.from_xy[0], args.from_xy[1]), (args.to_xy[0], args.to_xy[1])
    done = await driver.drag(start, end)
    return f"Dragged from {done.source} to {done.target}.{LOOK}"


async def type_text(session: BrowserSession, args: TypeArgs) -> str:
    driver = await _desktop(session)
    await driver.type_text(None, args.text, clear=False, submit=args.submit, slowly=False)
    then = " and pressed Enter" if args.submit else ""
    return f"Typed {len(args.text)} characters where the keyboard's focus is{then}.{LOOK}"


async def press_key(session: BrowserSession, args: PressKeyArgs) -> str:
    driver = await _desktop(session)
    named = keys.normalise(args.keys)
    await driver.press_key(named, repeat=args.repeat, ref=None)
    times = "" if args.repeat == 1 else f" {args.repeat} times"
    # A key that types a character is typed text: it is shown to nobody.
    shown = "a key" if keys.is_typed_text(args.keys) else named
    return f"Pressed {shown}{times}.{LOOK}"


async def scroll(session: BrowserSession, args: ScrollArgs) -> str:
    driver = await _desktop(session)
    at = (args.x, args.y) if args.x is not None and args.y is not None else None
    await driver.turn_wheel(args.direction, args.amount, at)
    where = f" at ({at[0]:g}, {at[1]:g})" if at else " where the pointer is"
    return f"Turned the wheel {args.direction} by {args.amount}{where}.{LOOK}"


async def wait(session: BrowserSession, args: WaitArgs) -> str:
    seconds = min(args.seconds, session.config.browser.timeouts.wait_max_s)
    await asyncio.sleep(seconds)
    return f"Waited {seconds:g} s."


async def list_apps(session: BrowserSession, args: NoArgs) -> str:
    driver = await _desktop(session)
    # What a person allows now: a change in the settings holds from the next call.
    allowed = allowed_apps(session.config.computer)
    names = ", ".join(app.name for app in allowed) or "none"
    shared = (
        " The folder Files in the home folder is shared with the person: what is saved there, they have."
        if driver.desktop.folder is not None
        else " No folder is shared with the person."
    )
    return f"Apps you may open: {names}.{shared}\n{await _windows(driver)}"


async def open_app(session: BrowserSession, args: OpenAppArgs) -> str:
    driver = await _desktop(session)
    wanted = args.app.strip().lower()
    known = next((app for app in APPS if wanted in (app.name.lower(), app.id, app.command)), None)
    allowed = allowed_apps(session.config.computer)
    if known is None or known not in allowed:
        names = ", ".join(app.name for app in allowed) or "none"
        if known is None:
            raise BadInput(f"There is no app of that name. Apps you may open: {names}.", reason="no such app")
        raise BrowserError(
            f"{known.name} is not allowed on this desktop: the person has turned it off. "
            f"Apps you may open: {names}. Do not look for another way to open it.",
            reason="the app is not allowed",
        )
    if not await driver.open_app(known):
        raise BrowserError(
            f"{known.name} was started, but no window of it came up in time. Take a screenshot to see "
            "the desktop as it is.",
            reason="no window came up",
        )
    return f"Opened {known.name}.{LOOK}\n{await _windows(driver)}"


COMPUTER_TOOLS: tuple[ToolDefinition, ...] = (
    ToolDefinition(
        "computer_screenshot",
        "Take a picture of the desktop's screen. It is how the desktop is seen: take one before the "
        "first action, and after an action whose result matters.",
        NoArgs,
        screenshot,
    ),
    ToolDefinition(
        "computer_zoom",
        "Look at a part of the screen at twice its size, to read small print. region is [x0, y0, x1, y1] "
        "in the pixels of a screenshot.",
        ZoomArgs,
        zoom,
    ),
    ToolDefinition(
        "computer_click",
        "Click at x and y of the screen. click_count 2 is a double click; button right opens a context menu.",
        ClickArgs,
        click,
    ),
    ToolDefinition("computer_move", "Move the pointer to x and y without clicking.", PointArgs, move),
    ToolDefinition(
        "computer_drag",
        "Press the left button at from_xy, move to to_xy and let go.",
        DragArgs,
        drag,
    ),
    ToolDefinition(
        "computer_type",
        "Type text where the keyboard's focus is. Click the field first. submit presses Enter after it.",
        TypeArgs,
        type_text,
    ),
    ToolDefinition(
        "computer_press_key",
        "Press a key or a chord, such as Enter, Escape, Tab, ArrowDown, Control+s or Alt+F4.",
        PressKeyArgs,
        press_key,
    ),
    ToolDefinition(
        "computer_scroll",
        "Turn the mouse wheel up, down, left or right, at x and y or where the pointer is.",
        ScrollArgs,
        scroll,
    ),
    ToolDefinition("computer_wait", "Wait some seconds, for an app that is busy.", WaitArgs, wait),
    ToolDefinition(
        "computer_list_apps",
        "The apps you may open, whether a folder is shared with the person, and the windows that are open.",
        NoArgs,
        list_apps,
    ),
    ToolDefinition(
        "computer_open_app",
        "Open one of the apps computer_list_apps names, by its name.",
        OpenAppArgs,
        open_app,
    ),
    ToolDefinition(
        "computer_request_human",
        "Ask the person to do a step on the desktop that you must not do: a password, a sign-in, a "
        "payment, or anything else that is theirs to do. Waits for them.",
        RequestHumanArgs,
        request_human,
    ),
)

# The tools that only look, or only wait.
COMPUTER_READS = frozenset(
    {"computer_screenshot", "computer_zoom", "computer_wait", "computer_list_apps", "computer_request_human"}
)
# The tools whose x and y are where the pointer goes.
COMPUTER_POINTED = frozenset({"computer_click", "computer_move"})
# The tools whose keys go where the focus is.
COMPUTER_KEYS = frozenset({"computer_type", "computer_press_key"})
COMPUTER_NAMES = frozenset(tool.name for tool in COMPUTER_TOOLS)
# The tools that are no step on the screen. They are not watched for going round in circles.
COMPUTER_NO_STEP = frozenset({"computer_wait", "computer_list_apps", "computer_request_human"})
