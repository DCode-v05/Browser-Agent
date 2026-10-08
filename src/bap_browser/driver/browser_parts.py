"""What the driver is made with: how a browser is launched, how a download is named, and what is
kept of each tab, each frame and each dialog."""

from __future__ import annotations

import asyncio
import re
from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from playwright.async_api import (
    CDPSession,
    Dialog,
    FileChooser,
    Frame,
    Page,
)

from bap_browser.config import Config
from bap_browser.driver.base import (
    ConsoleLine,
    DialogKind,
    Happened,
    LogLevel,
    NetworkLine,
    PageDialog,
)
from bap_browser.driver.page_script import PageScript
from bap_browser.errors import ConfigError

PROXY_USERNAME_ENV = "BAP_BROWSER_PROXY_USERNAME"
PROXY_PASSWORD_ENV = "BAP_BROWSER_PROXY_PASSWORD"
# A ref inside a frame: the frame's name, then the element's.
FRAME_REF = re.compile(r"(f\d+)e\d+")
# The operations that give a point of the page, and the one that gives a box.
GIVE_A_POINT = frozenset({"prepare", "wheelPoint"})
GIVE_A_BOX = frozenset({"locate"})
# Before these, a frame that is out of sight is brought into view: the pointer has to reach it.
NEED_THE_FRAME_IN_VIEW = frozenset({"prepare", "wheelPoint"})
NOT_STARTED = "The browser has not been started."
NO_TAB = "No tab is open. Open a page with browser_navigate."
DIALOG_KINDS: tuple[DialogKind, ...] = ("alert", "confirm", "prompt", "beforeunload")
# How the browser names what a page writes to its console, as the levels a call may ask for.
CONSOLE_LEVELS: dict[str, LogLevel] = {
    "error": "error",
    "assert": "error",
    "warning": "warning",
    "debug": "debug",
    "trace": "debug",
}
# What a file name may not hold, on any system a browser runs on.
NOT_IN_A_FILE_NAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
NAMELESS_DOWNLOAD = "download"


def launch_options(config: Config, env: Mapping[str, str]) -> dict[str, Any]:
    browser = config.browser
    options: dict[str, Any] = {
        "headless": browser.headless,
        "args": list(browser.args),
        "chromium_sandbox": browser.chromium_sandbox,
        "timeout": browser.timeouts.launch_ms,
    }
    if browser.ignore_default_args:
        options["ignore_default_args"] = list(browser.ignore_default_args)
    if browser.executable_path:
        options["executable_path"] = browser.executable_path
    elif browser.channel == "custom":
        raise ConfigError("browser.channel is 'custom' but browser.executable_path is not set")
    elif browser.channel != "chromium" or (browser.user_data_dir and browser.headless):
        # A kept profile may hold an extension, and the browser's small build for running without a
        # window cannot run one: the whole browser is named, so that it is the one started.
        options["channel"] = browser.channel
    if browser.proxy.server:
        proxy = {"server": browser.proxy.server}
        if browser.proxy.bypass:
            proxy["bypass"] = browser.proxy.bypass
        if env.get(PROXY_USERNAME_ENV):
            proxy["username"] = env[PROXY_USERNAME_ENV]
            proxy["password"] = env.get(PROXY_PASSWORD_ENV, "")
        options["proxy"] = proxy
    return options


def context_options(config: Config) -> dict[str, Any]:
    browser = config.browser
    options: dict[str, Any] = {
        "ignore_https_errors": browser.ignore_https_errors,
        "java_script_enabled": browser.javascript_enabled,
        "accept_downloads": browser.downloads.enabled,
    }
    if browser.viewport is None:
        options["no_viewport"] = True
    else:
        options["viewport"] = {"width": browser.viewport.width, "height": browser.viewport.height}
    optional = {
        "locale": browser.locale,
        "timezone_id": browser.timezone_id,
        "color_scheme": browser.color_scheme,
        "device_scale_factor": browser.device_scale_factor,
        "user_agent": browser.user_agent,
    }
    options.update({name: value for name, value in optional.items() if value is not None})
    if browser.geolocation is not None:
        options["geolocation"] = browser.geolocation.model_dump()
    if browser.permissions:
        options["permissions"] = list(browser.permissions)
    if browser.extra_http_headers:
        options["extra_http_headers"] = dict(browser.extra_http_headers)
    return options


def first_line(error: Exception) -> str:
    return str(error).splitlines()[0]


# Why a page did not open, for the person watching. The agent gets the browser's own words.
LOAD_FAILURES = {
    "ERR_NAME_NOT_RESOLVED": "the site was not found",
    "ERR_CONNECTION_REFUSED": "the site refused the connection",
    "ERR_INTERNET_DISCONNECTED": "there is no connection",
    "ERR_CERT_": "the site's certificate is not trusted",
    "Timeout": "the page took too long",
}


def load_failure(error: Exception) -> str:
    text = str(error)
    return next((words for sign, words in LOAD_FAILURES.items() if sign in text), "the page did not load")


def capped(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: max(limit - 1, 0)] + "…"


def file_name(suggested: str) -> str:
    """The name a download is saved under. The page suggests it, so it is never trusted as a path."""
    name = NOT_IN_A_FILE_NAME.sub("_", suggested.replace("\\", "/").rsplit("/", 1)[-1]).strip(" .")
    return name or NAMELESS_DOWNLOAD


def free_path(folder: str, name: str) -> Path:
    """Where a file of that name goes in the folder, which is made if it is not there. A name
    already taken is numbered: report (1).pdf."""
    kept = Path(folder).resolve()
    kept.mkdir(parents=True, exist_ok=True)
    path, count = kept / name, 0
    while path.exists():
        count += 1
        stem, dot, ending = name.rpartition(".")
        path = kept / (f"{stem} ({count}).{ending}" if dot and stem else f"{name} ({count})")
    return path


def retrieved(task: asyncio.Future[Any]) -> None:
    """The failure of work that was given up on is of no interest to anyone."""
    if not task.cancelled():
        task.exception()


@dataclass(frozen=True)
class Taken:
    """The last screenshot of a tab: where on the page it begins, how many of its pixels show one
    page pixel, and its size."""

    x: float
    y: float
    scale: float
    width: int
    height: int


@dataclass(eq=False)
class InnerFrame:
    """A frame inside a page (spec 5.3). Its elements' refs begin with its name: f2e7."""

    name: str
    script: PageScript
    cdp: CDPSession
    """The DevTools session that reaches it: the page's own, or one of its own when the browser
    keeps the frame in another process (a frame from another site)."""
    owner: str
    """The ref of the frame's element in the document around it."""
    parent: InnerFrame | None
    """The frame around it. None when it is in the page itself."""

    @property
    def depth(self) -> int:
        return 1 + (self.parent.depth if self.parent else 0)


@dataclass(eq=False)
class OpenTab:
    """One page of the browser, and what the driver keeps about it."""

    id: str
    page: Page
    cdp: CDPSession
    script: PageScript
    console: deque[ConsoleLine]
    network: deque[NetworkLine]
    committed: asyncio.Event = field(default_factory=asyncio.Event)
    navigations: int = 0
    commits: int = 0
    title: str = ""
    pixel: float = 1.0
    """Page pixels per pixel of the last screenshot of what the browser shows."""
    shot: Taken | None = None
    choosing: asyncio.Future[FileChooser] | None = None
    """Set while an upload waits for the file chooser its click opens."""
    opening: list[tuple[str, str]] | None = None
    """While the agent's own navigation is under way: the addresses the policy refused on its way."""
    main_frame_id: str = ""
    frames: dict[str, InnerFrame] = field(default_factory=dict[str, "InnerFrame"])
    """The frames read so far, by name."""
    frame_names: dict[str, str] = field(default_factory=dict[str, str])
    """The name each frame was given, by the browser's own id for it. A frame keeps its name."""
    apart: dict[Frame, tuple[str, CDPSession]] = field(default_factory=dict[Frame, tuple[str, CDPSession]])
    """The frames the browser keeps in a process of their own: its id for each, and the session that reaches it."""


@dataclass(eq=False)
class OpenDialog:
    info: PageDialog
    dialog: Dialog
    timer: asyncio.Task[Any] | None = None


def frame_ids(tree: dict[str, Any]) -> set[str]:
    """The browser's ids of a frame and of every frame inside it that the same session reaches."""
    ids = {tree["frame"]["id"]}
    for child in tree.get("childFrames", []):
        ids |= frame_ids(child)
    return ids


def told_refused(shown: str, reason: str, where: str) -> Happened:
    """A navigation the policy stopped. The setting's name is for the agent's result, not for the
    person watching."""
    return Happened(
        "blocked",
        f"navigation to {shown}{where} blocked: {reason}",
        {"url": shown, "reason": reason.split(" (")[0]},
    )
