"""The tools of computer use (spec 22.4): Hermes' one tool, `computer_use`, and three of ours that it
has none of: the apps a person allows, opening one, and asking the person.
"""

from __future__ import annotations

from pydantic import Field

from bap_browser.config import Config
from bap_browser.driver.contained_desktop import APPS, allowed_apps
from bap_browser.driver.desktop_driver import DesktopDriver
from bap_browser.driver.session import BrowserSession
from bap_browser.errors import BadInput, BrowserError
from bap_browser.safeguards.reading import from_page
from bap_browser.tools.arguments import NoArgs, RequestHumanArgs
from bap_browser.tools.browser_tools import request_human
from bap_browser.tools.computer_use_tool import COMPUTER_USE
from bap_browser.tools.registry import Args, ToolDefinition

LOOK = " Capture to see the result."


class OpenAppArgs(Args):
    app: str = Field(min_length=1, max_length=40)


def any_app(config: Config) -> bool:
    """Whether the agent may open any app by its name: on a person's own machine, where they allow it."""
    return config.computer.runs not in ("container", "here") and config.computer.any_app


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


async def list_apps(session: BrowserSession, args: NoArgs) -> str:
    driver = await _desktop(session)
    # What a person allows now: a change in the settings holds from the next call.
    allowed = allowed_apps(session.config.computer)
    names = ", ".join(app.name for app in allowed) or "none"
    if any_app(session.config):
        names += "; and any app on this machine, by its name: each opening asks the person first"
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
    if known is None and any_app(session.config):
        # On the person's own machine, where they allow any app: it is opened by its name, after their yes.
        name = args.app.strip()
        if not await driver.open_named_app(name):
            raise BrowserError(
                f"{name} was asked to open, but it did not come to the front in time. Take a screenshot.",
                reason="no window came up",
            )
        return f"Opened {name}.{LOOK}\n{await _windows(driver)}"
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
    COMPUTER_USE,
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

# Ours of the tools, beside Hermes' one: they only look, or only wait, and are no step on the screen.
OURS_LOOK = frozenset({"computer_list_apps", "computer_request_human"})
COMPUTER_NAMES = frozenset(tool.name for tool in COMPUTER_TOOLS)


def computer_tools_for(config: Config) -> tuple[ToolDefinition, ...]:
    """The tools of computer use (spec 22.4): Hermes' one tool, and three of ours it has none of."""
    return COMPUTER_TOOLS
