"""Drives a browser through Playwright: one this process launched, or one that is already running."""

from __future__ import annotations

import asyncio
import base64
import contextlib
import os
import re
from collections import deque
from collections.abc import Awaitable, Callable, Coroutine, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from playwright.async_api import (
    Browser,
    BrowserContext,
    CDPSession,
    ConsoleMessage,
    Dialog,
    Download,
    Frame,
    Page,
    Request,
    Response,
    async_playwright,
)
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from bap_browser.config import Config, QualityLevel
from bap_browser.driver.base import (
    ActionOutcome,
    Box,
    Checked,
    ConsoleLine,
    DialogKind,
    Dragged,
    Found,
    Guard,
    Happened,
    KeyAction,
    LoadState,
    Located,
    LogLevel,
    MouseButton,
    NetworkLine,
    PageDialog,
    Place,
    PointerAction,
    SavedFile,
    ScrollPosition,
    Selected,
    Shot,
    TabInfo,
)
from bap_browser.driver.page_script import PageScript
from bap_browser.driver.screenshots import size_of
from bap_browser.driver.snapshot import NOTICE, WHOLE_PAGE, matching_lines, snapshot_arguments
from bap_browser.errors import BadInput, BrowserError, ConfigError, PolicyBlocked, StaleRef
from bap_browser.policy.address import without_credentials
from bap_browser.results import Picture

PROXY_USERNAME_ENV = "BAP_BROWSER_PROXY_USERNAME"
PROXY_PASSWORD_ENV = "BAP_BROWSER_PROXY_PASSWORD"
# How many bytes of a picture the page script turns into text at a time.
SHRINK_PIECE = 32768
# A ref inside a frame: the frame's name, then the element's.
FRAME_REF = re.compile(r"(f\d+)e\d+")
# The operations that give a point of the page, and the one that gives a box.
GIVE_A_POINT = frozenset({"prepare", "wheelPoint"})
GIVE_A_BOX = frozenset({"locate"})
# Before these, a frame that is out of sight is brought into view: the pointer has to reach it.
NEED_THE_FRAME_IN_VIEW = frozenset({"prepare", "wheelPoint"})
# After an action, two animation frames are enough for a navigation it started to show itself.
SETTLE_FRAMES = 2
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


def _retrieved(task: asyncio.Future[Any]) -> None:
    """The failure of work that was given up on is of no interest to anyone."""
    if not task.cancelled():
        task.exception()


@dataclass(frozen=True)
class _Taken:
    """The last screenshot of a tab: where on the page it begins, how many of its pixels show one
    page pixel, and its size."""

    x: float
    y: float
    scale: float
    width: int
    height: int


@dataclass(eq=False)
class _InnerFrame:
    """A frame inside a page (spec 5.3). Its elements' refs begin with its name: f2e7."""

    name: str
    script: PageScript
    cdp: CDPSession
    """The DevTools session that reaches it: the page's own, or one of its own when the browser
    keeps the frame in another process (a frame from another site)."""
    owner: str
    """The ref of the frame's element in the document around it."""
    parent: _InnerFrame | None
    """The frame around it. None when it is in the page itself."""

    @property
    def depth(self) -> int:
        return 1 + (self.parent.depth if self.parent else 0)


@dataclass(eq=False)
class _Tab:
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
    shot: _Taken | None = None
    opening: list[tuple[str, str]] | None = None
    """While the agent's own navigation is under way: the addresses the policy refused on its way."""
    main_frame_id: str = ""
    frames: dict[str, _InnerFrame] = field(default_factory=dict[str, "_InnerFrame"])
    """The frames read so far, by name."""
    frame_names: dict[str, str] = field(default_factory=dict[str, str])
    """The name each frame was given, by the browser's own id for it. A frame keeps its name."""
    apart: dict[Frame, tuple[str, CDPSession]] = field(default_factory=dict[Frame, tuple[str, CDPSession]])
    """The frames the browser keeps in a process of their own: its id for each, and the session that reaches it."""


@dataclass(eq=False)
class _OpenDialog:
    info: PageDialog
    dialog: Dialog
    timer: asyncio.Task[Any] | None = None


def _frame_ids(tree: dict[str, Any]) -> set[str]:
    """The browser's ids of a frame and of every frame inside it that the same session reaches."""
    ids = {tree["frame"]["id"]}
    for child in tree.get("childFrames", []):
        ids |= _frame_ids(child)
    return ids


def _refused(shown: str, reason: str, where: str) -> Happened:
    """A navigation the policy stopped. The setting's name is for the agent's result, not for the
    person watching."""
    return Happened(
        "blocked",
        f"navigation to {shown}{where} blocked: {reason}",
        {"url": shown, "reason": reason.split(" (")[0]},
    )


class PlaywrightDriver:
    def __init__(self, config: Config, *, cdp_headers: Mapping[str, str] | None = None) -> None:
        """`cdp_headers` go with the request that attaches to a running browser (`browser.cdp_url`),
        for one that asks who is attaching."""
        self._config = config
        self._cdp_headers = dict(cdp_headers or {})
        self._stack = contextlib.AsyncExitStack()
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._version = ""
        self._tabs: dict[str, _Tab] = {}
        self._active: _Tab | None = None
        # Tab ids are never used twice in a session, and neither are refs, in any tab.
        self._tab_count = 0
        self._next_ref = 1
        self._next_frame = 1
        self._frames: tuple[Callable[[bytes], None], QualityLevel] | None = None
        self._next_acknowledgement = 0.0
        self._tasks: set[asyncio.Task[Any]] = set()
        self._on_event: Callable[[Happened], None] | None = None
        self._guard: Guard | None = None
        # The dialogs that wait for an answer, oldest first.
        self._dialogs: list[_OpenDialog] = []
        self._dialog_count = 0
        self._dialog_open = asyncio.Event()
        self._no_dialog = asyncio.Event()
        self._no_dialog.set()
        self._downloads: list[SavedFile] = []
        # Windows that a page has opened and that have not been handed over yet, and windows that
        # were handed over before their page said it was opening them.
        self._opening = 0
        self._early = 0
        self._arrived = asyncio.Event()
        # Pages this driver is opening itself. They are not windows that a page opened.
        self._own_pages = 0
        # Tabs this driver is closing itself: whoever asked is told by the answer, not as news.
        self._closing: set[str] = set()
        # The tab the live picture is of.
        self._pictured: _Tab | None = None

    def guard(self, judge: Guard) -> None:
        self._guard = judge

    def listen(self, on_event: Callable[[Happened], None]) -> None:
        self._on_event = on_event

    def _tell(self, event: Happened) -> None:
        if self._on_event is not None:
            self._on_event(event)

    def _spawn(self, work: Coroutine[Any, Any, Any]) -> asyncio.Task[Any]:
        """Runs work that nothing waits for. It ends with the browser."""
        task = asyncio.create_task(work)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    def _current(self) -> _Tab:
        if self._active is None:
            raise BrowserError(NOT_STARTED if self._context is None else NO_TAB)
        return self._active

    @property
    def page(self) -> Page:
        """The page of the active tab."""
        return self._current().page

    @property
    def page_script(self) -> PageScript:
        return self._current().script

    async def start(self) -> None:
        timeouts = self._config.browser.timeouts
        try:
            playwright = await async_playwright().start()
            self._stack.push_async_callback(playwright.stop)
            launch = launch_options(self._config, os.environ)
            profile = self._config.browser.user_data_dir
            browser: Browser | None = None
            attach = self._config.browser.cdp_url
            if attach:
                # A browser that is already running, started by someone else. It is driven, and on
                # close it is let go of, not ended: the page stays where the agent left it.
                browser = await playwright.chromium.connect_over_cdp(
                    attach, timeout=timeouts.launch_ms, headers=self._cdp_headers or None
                )
                self._stack.push_async_callback(browser.close)
                context, page = self._page_to_drive(browser)
            elif profile:
                # A profile that is kept: its sign-ins, and an extension loaded into it, are there next time.
                context = await playwright.chromium.launch_persistent_context(
                    profile, **launch, **context_options(self._config)
                )
                self._stack.push_async_callback(context.close)
                page = context.pages[0] if context.pages else await context.new_page()
            else:
                browser = await playwright.chromium.launch(**launch)
                self._stack.push_async_callback(browser.close)
                context = await browser.new_context(**context_options(self._config))
                page = await context.new_page()
            context.set_default_timeout(timeouts.action_ms)
            context.set_default_navigation_timeout(timeouts.navigation_ms)
            self._browser, self._context = browser, context
            tab = await self._add_tab(page)
            # A browser with a kept profile is not handed over as an object of its own, so its version is asked for.
            product = browser.version if browser else (await tab.cdp.send("Browser.getVersion"))["product"]
        except PlaywrightError as exc:
            await self._stack.aclose()
            self._browser = self._context = None
            self._tabs.clear()
            raise BrowserError(f"The browser could not be started: {first_line(exc)}") from exc
        context.on("page", self._on_page)
        context.on("close", self._on_context_closed)
        self._active = tab
        self._version = product.rpartition("/")[2]
        if self._frames is not None:
            # A browser that was started again goes on sending pictures to whoever was watching.
            await self._begin_pictures(self._frames[1])

    def _page_to_drive(self, browser: Browser) -> tuple[BrowserContext, Page]:
        """The page of a running browser that the agent is to drive."""
        mark = self._config.browser.cdp_target
        pages = [page for context in browser.contexts for page in context.pages]
        chosen = next((page for page in pages if mark is None or mark in page.url), None)
        if chosen is None:
            wanted = f"has {mark} in its address" if mark else "is there"
            raise PlaywrightError(f"no open page {wanted}")
        return chosen.context, chosen

    async def close(self) -> None:
        tasks = list(self._tasks)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await self._stack.aclose()
        self._browser = self._context = self._active = self._pictured = None
        self._tabs.clear()
        self._dialogs.clear()
        self._dialog_open.clear()
        self._no_dialog.set()
        self._opening = self._early = 0

    def _on_context_closed(self, context: BrowserContext) -> None:
        if context is self._context:
            self._context = None

    def is_alive(self) -> bool:
        if self._browser is not None:
            return self._browser.is_connected()
        # A browser with a kept profile is gone when its one context has closed.
        return self._context is not None

    def description(self) -> str:
        if self._context is None and self._browser is None:
            raise BrowserError(NOT_STARTED)
        return f"Chromium {self._version}"

    # Tabs (spec 5.3).

    async def _add_tab(self, page: Page) -> _Tab:
        """Takes a page in as a tab, and listens to what happens in it."""
        browser = self._config.browser
        if self._context is None:
            raise BrowserError(NOT_STARTED)
        self._tab_count += 1
        tab_id = f"t{self._tab_count}"
        # First of all: a dialog that nobody listens for is dismissed by the browser's driver at once.
        page.on("dialog", lambda dialog: self._on_dialog(tab_id, dialog))
        cdp = await self._context.new_cdp_session(page)
        tab = _Tab(
            tab_id,
            page,
            cdp,
            PageScript(cdp, browser.timeouts.page_reply_ms, self._within),
            deque(maxlen=browser.capture.max_console_entries),
            deque(maxlen=browser.capture.max_network_entries),
        )
        page.on("request", lambda request: self._on_request(tab, request))
        page.on("framenavigated", lambda frame: self._on_frame_navigated(tab, frame))
        page.on("close", lambda _: self._forget(tab))
        page.on("download", lambda download: self._spawn(self._save(download)))
        if browser.capture.console:
            page.on("console", lambda message: self._on_console(tab, message))
            page.on("pageerror", lambda error: self._on_page_error(tab, error))
        if browser.capture.network:
            page.on("response", lambda response: self._on_response(tab, response))
            page.on("requestfailed", lambda request: self._on_request_failed(tab, request))
        if self._guard is not None:
            # Every document this tab sets out to load is judged first, whoever started it: a link, a
            # redirect, a frame, a script. Only documents are held up, unless the deployment asks for
            # everything: holding up every request makes a page load much slower (spec 8.1).
            everything = self._config.safety.enforce_on_subresources
            wanted = {"urlPattern": "*"} if everything else {"urlPattern": "*", "resourceType": "Document"}
            cdp.on("Fetch.requestPaused", lambda paused: self._spawn(self._judge_request(tab, paused)))
            await cdp.send("Fetch.enable", {"patterns": [wanted]})
            tab.main_frame_id = (await cdp.send("Page.getFrameTree"))["frameTree"]["frame"]["id"]
        cdp.on("Page.screencastFrame", lambda frame: self._on_picture(tab, frame))
        cdp.on("Page.windowOpen", lambda _: self._window_opening())
        # The page says when it opens a window only to one who has asked to hear about the page.
        await cdp.send("Page.enable")
        self._tabs[tab_id] = tab
        return tab

    def _tab_of(self, page: Page) -> _Tab | None:
        return next((tab for tab in self._tabs.values() if tab.page is page), None)

    def _tab(self, tab_id: str) -> _Tab:
        tab = self._tabs.get(tab_id)
        if tab is None:
            open_tabs = ", ".join(self._tabs) or "none"
            raise BadInput(
                f"There is no tab {tab_id}. Open tabs: {open_tabs}.", reason="there is no such tab"
            )
        return tab

    async def tabs(self) -> list[TabInfo]:
        tabs = list(self._tabs.values())
        asking = {entry.info.tab for entry in self._dialogs}
        await asyncio.gather(*(self._read_title(tab) for tab in tabs if tab.id not in asking))
        return [
            TabInfo(tab.id, tab.page.url, tab.title, tab is self._active, tab.id in asking) for tab in tabs
        ]

    async def _read_title(self, tab: _Tab) -> None:
        """A page with a dialog open answers nothing, so it is not asked: its last title stands."""
        try:
            async with asyncio.timeout(self._config.browser.timeouts.page_reply_ms / 1000):
                tab.title = await tab.page.title()
        except (PlaywrightError, TimeoutError):
            tab.title = ""

    async def new_tab(self) -> str:
        tab = await self._open_tab()
        return tab.id

    async def _open_tab(self) -> _Tab:
        most = self._config.browser.tabs.max_tabs
        if self._context is None:
            raise BrowserError(NOT_STARTED)
        if len(self._tabs) >= most:
            raise BadInput(
                f"{most} tabs are open, which is the most allowed. Close one first.",
                reason="too many tabs are open",
            )
        self._own_pages += 1
        try:
            page = await self._context.new_page()
            tab = await self._add_tab(page)
        except PlaywrightError as exc:
            raise BrowserError(
                f"A tab could not be opened: {first_line(exc)}", reason="the browser did not respond"
            ) from exc
        finally:
            self._own_pages -= 1
        await self._show(tab)
        return tab

    async def switch_tab(self, tab_id: str) -> None:
        await self._show(self._tab(tab_id))

    async def close_tab(self, tab_id: str | None) -> str:
        tab = self._current() if tab_id is None else self._tab(tab_id)
        self._closing.add(tab.id)
        with contextlib.suppress(PlaywrightError):
            await tab.page.close()
        self._forget(tab)
        if self._active is not None:
            await self._show(self._active)
        return tab.id

    async def _show(self, tab: _Tab) -> None:
        """Makes a tab the active one: it comes to the front, and the live picture is of it."""
        self._active = tab
        with contextlib.suppress(PlaywrightError):
            await tab.page.bring_to_front()
        if self._frames is None or self._pictured is tab:
            return
        if self._pictured is not None:
            with contextlib.suppress(PlaywrightError):
                await self._pictured.cdp.send("Page.stopScreencast")
        with contextlib.suppress(BrowserError):
            await self._begin_pictures(self._frames[1])

    def _forget(self, tab: _Tab) -> None:
        """A tab has closed. The one opened last becomes the active one."""
        if self._tabs.pop(tab.id, None) is None:
            return
        for entry in [entry for entry in self._dialogs if entry.info.tab == tab.id]:
            self._close_dialog(entry, "dismissed", "")
        was_active = tab is self._active
        if was_active:
            self._active = next(reversed(self._tabs.values()), None)
        if tab.id in self._closing:
            return
        now = f"; {self._active.id} is now the active tab" if was_active and self._active else ""
        self._tell(Happened("tab_closed", f"tab {tab.id} closed{now}"))
        if was_active and self._active is not None:
            self._spawn(self._show(self._active))

    def _on_page(self, page: Page) -> None:
        if not self._own_pages:
            self._spawn(self._adopt(page))

    def _window_opening(self) -> None:
        if self._early:
            self._early -= 1
        else:
            self._opening += 1

    async def _adopt(self, page: Page) -> None:
        """A window that one of the agent's tabs opened becomes a tab. A window that someone else
        opened in the same browser is theirs, and is left alone."""
        browser = self._config.browser
        try:
            opener = await page.opener()
        except PlaywrightError:
            return
        if opener is None or self._tab_of(opener) is None:
            return
        try:
            if len(self._tabs) >= browser.tabs.max_tabs:
                await page.close()
                self._tell(
                    Happened(
                        "tab_out_of_reach",
                        f"a new tab was closed at once: {browser.tabs.max_tabs} tabs are open, "
                        "which is the most allowed",
                    )
                )
                return
            tab = await self._add_tab(page)
            with contextlib.suppress(PlaywrightError):
                await page.wait_for_load_state("domcontentloaded", timeout=browser.timeouts.popup_adopt_ms)
            if await self._closed_as_refused(tab):
                return
            focus = browser.tabs.focus_new_tabs and tab.id in self._tabs
            if focus:
                await self._show(tab)
            now = " and is now the active tab" if focus else ""
            # A page can make its own address as long as it likes.
            address = capped(without_credentials(page.url), browser.snapshot.max_text_chars)
            self._tell(Happened("tab_opened", f"tab {tab.id} opened{now}: {address}"))
        except (PlaywrightError, BrowserError):
            # It closed again before it could be taken in.
            return
        finally:
            if self._opening:
                self._opening -= 1
            else:
                self._early += 1
            self._arrived.set()

    async def _let_new_tabs_in(self) -> None:
        """A window that the page opened is handed over a moment later. The action waits for it, so
        that its own result already shows the new tab."""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self._config.browser.timeouts.popup_adopt_ms / 1000
        while self._opening:
            remaining = deadline - loop.time()
            if remaining <= 0:
                self._opening = 0
                self._tell(
                    Happened(
                        "tab_out_of_reach",
                        "the page opened a new window, and these tools cannot reach it",
                    )
                )
                return
            self._arrived.clear()
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._arrived.wait(), remaining)

    async def viewport(self) -> tuple[int, int]:
        return await self._viewport(self._current())

    async def _viewport(self, tab: _Tab) -> tuple[int, int]:
        size = tab.page.viewport_size
        if size is None:
            # No fixed size was asked for: the page is as large as its window.
            size = await tab.page.evaluate("({ width: innerWidth, height: innerHeight })")
        return size["width"], size["height"]

    async def _judge_request(self, tab: _Tab, paused: dict[str, Any]) -> None:
        """Lets a request the browser is about to make go on, or stops it (spec 8.1)."""
        request, url = paused["requestId"], str(paused.get("request", {}).get("url", ""))
        try:
            allowed, reason = await self._guard(url) if self._guard else (True, "")
        except Exception:
            # What cannot be judged is not loaded.
            allowed, reason = False, "the address could not be checked"
        try:
            if allowed:
                await tab.cdp.send("Fetch.continueRequest", {"requestId": request})
                return
            await tab.cdp.send("Fetch.failRequest", {"requestId": request, "errorReason": "BlockedByClient"})
        except PlaywrightError:
            # The tab closed, or went elsewhere, while the address was being judged.
            return
        if paused.get("resourceType") != "Document":
            return
        shown = capped(without_credentials(url), self._config.browser.snapshot.max_text_chars)
        in_frame = paused.get("frameId") != tab.main_frame_id
        if tab.opening is not None and not in_frame:
            # The agent's own navigation ran into it: that call says so itself.
            tab.opening.append((shown, reason))
            return
        self._tell(_refused(shown, reason, " in a frame" if in_frame else ""))

    async def _closed_as_refused(self, tab: _Tab) -> bool:
        """A window a page opened may have begun to load before anyone could judge where it goes.
        One that is at an address the policy refuses is closed, and the agent is told."""
        if self._guard is None:
            return False
        url = tab.page.url
        allowed, reason = await self._guard(url)
        if allowed:
            return False
        self._closing.add(tab.id)
        with contextlib.suppress(PlaywrightError):
            await tab.page.close()
        shown = capped(without_credentials(url), self._config.browser.snapshot.max_text_chars)
        self._tell(
            Happened(
                "blocked",
                f"a new tab at {shown} was closed: {reason}",
                {"url": shown, "reason": reason.split(" (")[0]},
            )
        )
        return True

    async def navigate(self, url: str) -> str:
        tab = self._active or await self._open_tab()
        navigations, commits = tab.navigations, tab.commits
        tab.opening = refused = []
        try:
            await tab.page.goto(url, wait_until="domcontentloaded")
        except PlaywrightError as exc:
            if tab.navigations != navigations:
                # The browser shows its own error page for an address it could not load. A
                # navigation started before that page arrives would be interrupted by it.
                await self._wait_for_commit(tab, commits, self._config.browser.timeouts.settle_ms)
            if refused:
                # The address led, by a redirect, to one the policy refuses.
                led_to, reason = refused[-1]
                raise PolicyBlocked(
                    f"navigation to {led_to} blocked: {reason}", url=led_to, reason=reason.split(" (")[0]
                ) from exc
            # The browser's own words repeat the address, which may hold a name and password.
            shown = without_credentials(url)
            raise BrowserError(
                f"Could not open {shown}: {first_line(exc).replace(url, shown)}", reason=load_failure(exc)
            ) from exc
        finally:
            tab.opening = None
            tab.script.forget_document()
        await self._wait_for_load(tab)
        return tab.page.url

    async def locate(self, ref: str) -> Located:
        return await self._locate(self._current(), ref)

    async def _locate(self, tab: _Tab, ref: str) -> Located:
        found = await self._ask(
            tab, "locate", {"ref": ref, "maxName": self._config.browser.snapshot.max_name_chars}
        )
        if found.get("error") == "stale":
            raise StaleRef(ref)
        box = Box(*found["box"]) if found["box"] else None
        return Located(found["role"], found["name"], box, found["secret"], found["kind"])

    async def snapshot(self, *, mode: str, ref: str | None, max_chars: int, include_bboxes: bool) -> str:
        tab = self._current()
        frame = self._frame_of(tab, ref)
        return await self._read(tab, frame, mode, ref, max_chars, include_bboxes, embedded=False, indent=0)

    async def _read(
        self,
        tab: _Tab,
        frame: _InnerFrame | None,
        mode: str,
        ref: str | None,
        max_chars: int,
        include_bboxes: bool,
        *,
        embedded: bool,
        indent: int,
    ) -> str:
        """The page, a frame or a subtree as text, with what is inside each of its frames under that
        frame's line (spec 5.3). Everything together stays within `max_chars`."""
        settings = self._config.browser.snapshot
        arguments = snapshot_arguments(
            settings,
            mode=mode,
            ref=ref,
            max_chars=max_chars,
            include_bboxes=include_bboxes,
            next_ref=self._next_ref,
        )
        arguments |= {"prefix": frame.name if frame else "", "embedded": embedded, "indent": indent}
        data = await (frame.script if frame else tab.script).call("snapshot", arguments)
        if data.get("error") == "stale":
            raise StaleRef(ref or "")
        # Numbering continues across navigations, tabs and frames, so an old ref can never point at a
        # new element.
        self._next_ref = data["next"]
        text: str = data["text"]
        depth = frame.depth if frame else 0
        if not settings.include_iframes or depth >= settings.max_frame_depth or data["truncated"]:
            return text
        lines, used = text.split("\n"), len(text)
        inside: list[tuple[int, str]] = []
        for met in data["frames"]:
            left = max_chars - used
            if left < 2 * len(NOTICE):
                break
            try:
                inner = await self._frame_under(tab, frame, met["ref"])
                if inner is None:
                    continue
                read = await self._read(
                    tab, inner, mode, None, left, include_bboxes, embedded=True, indent=met["indent"] + 1
                )
            except BrowserError:
                # A frame that cannot be read (it is loading, or gone) is listed and left empty.
                continue
            # The notice that something was left out is said once, at the end of the whole.
            cut_short = read.endswith(NOTICE)
            read = read.removesuffix(NOTICE).rstrip("\n")
            if read:
                inside.append((met["line"], read))
                used += len(read) + 1
            if cut_short:
                lines.append(NOTICE)
                break
        for line, read in reversed(inside):
            lines[line + 1 : line + 1] = read.split("\n")
        return "\n".join(lines)

    # Frames (spec 5.3).

    def _frame_of(self, tab: _Tab, ref: str | None) -> _InnerFrame | None:
        """The frame a ref is in. None for an element of the page itself."""
        named = FRAME_REF.fullmatch(ref) if ref else None
        if named is None:
            return None
        frame = tab.frames.get(named.group(1))
        if frame is None:
            raise StaleRef(ref or "")
        return frame

    async def _ask(self, tab: _Tab, operation: str, arguments: dict[str, Any], *, wait_ms: int = 0) -> Any:
        """Runs an operation where its element is: in the page, or in a frame. A point or a box that
        comes back from a frame is given as a point or a box of the page."""
        ref = arguments.get("ref")
        frame = self._frame_of(tab, ref)
        if frame is None:
            return await tab.script.call(operation, arguments, wait_ms=wait_ms)
        dx, dy = await self._where(tab, frame, str(ref), bring=operation in NEED_THE_FRAME_IN_VIEW)
        if "x" in arguments and "y" in arguments:
            arguments = {**arguments, "x": arguments["x"] - dx, "y": arguments["y"] - dy}
        result = await frame.script.call(operation, arguments, wait_ms=wait_ms)
        if not isinstance(result, dict) or result.get("error"):
            return result
        if operation in GIVE_A_POINT:
            return {**result, "x": result["x"] + dx, "y": result["y"] + dy}
        if operation in GIVE_A_BOX and result.get("box"):
            x, y, width, height = result["box"]
            return {**result, "box": [x + dx, y + dy, width, height]}
        return result

    async def _where(self, tab: _Tab, frame: _InnerFrame, ref: str, *, bring: bool) -> tuple[float, float]:
        """How far the page inside a frame is from the top left of what the browser shows."""
        chain: list[_InnerFrame] = []
        at: _InnerFrame | None = frame
        while at is not None:
            chain.append(at)
            at = at.parent
        dx = dy = 0.0
        for inner in reversed(chain):
            around = inner.parent.script if inner.parent else tab.script
            if bring:
                await around.call("intoView", {"ref": inner.owner})
            box = await around.call("frameBox", {"ref": inner.owner})
            if box.get("error"):
                # The frame's own element is gone, and everything inside it with it.
                raise StaleRef(ref)
            dx, dy = dx + box["x"], dy + box["y"]
        return dx, dy

    async def _frame_under(self, tab: _Tab, parent: _InnerFrame | None, owner: str) -> _InnerFrame | None:
        """The frame a frame element holds, ready to be read. None when it cannot be reached."""
        around, session = (parent.script, parent.cdp) if parent else (tab.script, tab.cdp)
        element = await around.object_of(owner)
        if element is None:
            return None
        try:
            described = await session.send("DOM.describeNode", {"objectId": element})
        except PlaywrightError:
            return None
        frame_id = described.get("node", {}).get("frameId")
        if not frame_id:
            return None
        reached = await self._session_for(tab, session, frame_id)
        if reached is None:
            return None
        name = tab.frame_names.get(frame_id)
        if name is None:
            name = tab.frame_names[frame_id] = f"f{self._next_frame}"
            self._next_frame += 1
        known = tab.frames.get(name)
        if known and known.cdp is reached and known.owner == owner and known.parent is parent:
            return known
        script = PageScript(
            reached, self._config.browser.timeouts.page_reply_ms, self._within, frame_id=frame_id
        )
        frame = tab.frames[name] = _InnerFrame(name, script, reached, owner, parent)
        return frame

    async def _session_for(self, tab: _Tab, session: CDPSession, frame_id: str) -> CDPSession | None:
        """The DevTools session that reaches a frame: the one of the document around it, or the
        frame's own when the browser keeps it in another process."""
        try:
            tree = await session.send("Page.getFrameTree")
        except PlaywrightError:
            return None
        if frame_id in _frame_ids(tree["frameTree"]):
            return session
        for frame, (known_id, own) in tab.apart.items():
            if known_id == frame_id and not frame.is_detached():
                return own
        for frame in tab.page.frames[1:]:
            if frame in tab.apart or frame.is_detached():
                continue
            try:
                own = await tab.page.context.new_cdp_session(frame)
                root = (await own.send("Page.getFrameTree"))["frameTree"]["frame"]["id"]
            except PlaywrightError:
                # A frame in the page's own process has no session of its own.
                continue
            tab.apart[frame] = (root, own)
            if root == frame_id:
                return own
        return None

    async def click(
        self, ref: str, *, button: MouseButton = "left", click_count: int = 1, modifiers: Sequence[str] = ()
    ) -> ActionOutcome:
        return await self._click_ref(self._current(), ref, button, click_count, modifiers)

    async def _click_ref(
        self, tab: _Tab, ref: str, button: MouseButton, click_count: int, modifiers: Sequence[str]
    ) -> ActionOutcome:
        point = await self._point_under_pointer(tab, ref)
        navigated_to = await self._click(tab, point["x"], point["y"], ref, button, click_count, modifiers)
        return ActionOutcome(point["describe"], navigated_to)

    async def click_at(
        self,
        x: float,
        y: float,
        *,
        button: MouseButton = "left",
        click_count: int = 1,
        modifiers: Sequence[str] = (),
    ) -> ActionOutcome:
        tab = self._current()
        described = await self._describe_at(tab, x, y)
        navigated_to = await self._click(tab, x, y, f"at ({x:g}, {y:g})", button, click_count, modifiers)
        return ActionOutcome(described, navigated_to)

    async def _point_under_pointer(self, tab: _Tab, ref: str) -> dict[str, Any]:
        """Waits until an element can be pressed, and moves the pointer onto it."""
        point = await self._prepare(tab, ref)
        await self._move_to(tab, point["x"], point["y"])
        frame_ms = self._config.browser.timeouts.frame_ms
        still_there = await self._ask(
            tab,
            "holds",
            {"ref": ref, "x": point["x"], "y": point["y"], "frameMs": frame_ms},
            wait_ms=frame_ms,
        )
        if not still_there:
            # Moving the pointer changed the page: a menu it was over has closed, say. The element
            # is found again where it is now.
            point = await self._prepare(tab, ref)
            await self._move_to(tab, point["x"], point["y"])
        return point

    async def _prepare(self, tab: _Tab, ref: str) -> dict[str, Any]:
        browser = self._config.browser
        point = await self._ask(
            tab,
            "prepare",
            {
                "ref": ref,
                "timeoutMs": browser.timeouts.action_ms,
                "frameMs": browser.timeouts.frame_ms,
                "maxName": browser.snapshot.max_name_chars,
            },
            wait_ms=browser.timeouts.action_ms,
        )
        self._raise_for(point, ref)
        return point

    async def _click(
        self,
        tab: _Tab,
        x: float,
        y: float,
        where: str,
        button: MouseButton,
        click_count: int,
        modifiers: Sequence[str],
    ) -> str | None:
        """Presses the mouse at a point. Returns the address the page went to, if it went anywhere."""
        navigations, commits = tab.navigations, tab.commits
        keyboard = tab.page.keyboard

        async def press() -> None:
            for key in modifiers:
                await keyboard.down(key)
            await tab.page.mouse.click(x, y, button=button, click_count=click_count)

        async def release() -> None:
            for key in reversed(modifiers):
                await keyboard.up(key)

        try:
            await self._input(press(), "the click")
        except PlaywrightError as exc:
            raise BrowserError(
                f"Could not click {where}: {first_line(exc)}", reason="the browser did not respond"
            ) from exc
        finally:
            if modifiers:
                with contextlib.suppress(BrowserError, PlaywrightError):
                    await self._input(release(), "the click")
        return await self._settle(tab, navigations, commits)

    async def _describe_at(self, tab: _Tab, x: float, y: float) -> str:
        """What is at a point, as the snapshot names it. A point outside the page is refused."""
        width, height = await self._viewport(tab)
        if not (0 <= x < width and 0 <= y < height):
            raise BadInput(
                f"({x:g}, {y:g}) is outside the page, which is {width} by {height} pixels.",
                reason="the point is outside the page",
            )
        found = await tab.script.call(
            "at", {"x": x, "y": y, "maxName": self._config.browser.snapshot.max_name_chars}
        )
        return found["describe"]

    async def type_text(
        self, ref: str | None, text: str, *, clear: bool = True, submit: bool = False, slowly: bool = False
    ) -> ActionOutcome:
        tab = self._current()
        browser = self._config.browser
        field = await self._ask(
            tab, "focus", {"ref": ref, "clear": clear, "maxName": browser.snapshot.max_name_chars}
        )
        self._raise_for(field, ref)
        navigations, commits = tab.navigations, tab.commits
        keyboard = tab.page.keyboard
        delay = browser.input.slow_type_delay_ms if slowly else browser.input.type_delay_ms

        async def enter() -> None:
            if text == "":
                if clear and field["hadText"]:
                    await keyboard.press("Delete")
            elif delay:
                await keyboard.type(text, delay=delay)
            else:
                await keyboard.insert_text(text)
            if submit:
                await keyboard.press("Enter")

        try:
            # Typing with a pause between keys takes that long on top of the time the page may take.
            await self._input(enter(), "the typing", extra_ms=delay * len(text))
        except PlaywrightError as exc:
            raise BrowserError(
                f"Could not type into {ref or 'the focused element'}: {first_line(exc)}",
                reason="the browser did not respond",
            ) from exc
        navigated_to = await self._settle(tab, navigations, commits) if submit else None
        return ActionOutcome(field["describe"], navigated_to)

    async def back(self) -> str | None:
        tab = self._current()
        return await self._through_history(tab, tab.page.go_back, "go back")

    async def forward(self) -> str | None:
        tab = self._current()
        return await self._through_history(tab, tab.page.go_forward, "go forward")

    async def reload(self) -> str:
        tab = self._current()
        address = await self._through_history(tab, tab.page.reload, "reload the page")
        return address or tab.page.url

    async def _through_history(
        self, tab: _Tab, move: Callable[..., Coroutine[Any, Any, Any]], what: str
    ) -> str | None:
        commits = tab.commits
        try:
            await move(wait_until="domcontentloaded")
        except PlaywrightError as exc:
            raise BrowserError(f"Could not {what}: {first_line(exc)}", reason=load_failure(exc)) from exc
        finally:
            tab.script.forget_document()
        if tab.commits == commits:
            # Nothing was loaded: there is no page that way.
            return None
        await self._wait_for_load(tab)
        return tab.page.url

    async def text(self, ref: str | None, max_chars: int) -> tuple[str, int]:
        data = await self._ask(self._current(), "text", {"ref": ref, "maxChars": max_chars})
        if data.get("error") == "stale":
            raise StaleRef(ref or "")
        return data["text"], data["more"]

    async def find(self, query: str, limit: int) -> Found:
        # The whole page with its frames, read in the browser and searched here.
        page = await self._read(
            self._current(), None, "all", None, WHOLE_PAGE, False, embedded=False, indent=0
        )
        return Found(*matching_lines(page, query, limit))

    async def hover(self, ref: str) -> ActionOutcome:
        tab = self._current()
        point = await self._point_under_pointer(tab, ref)
        await tab.script.frames_passed(SETTLE_FRAMES, self._config.browser.timeouts.frame_ms)
        return ActionOutcome(point["describe"])

    async def hover_at(self, x: float, y: float) -> ActionOutcome:
        tab = self._current()
        described = await self._describe_at(tab, x, y)
        await self._move_to(tab, x, y)
        await tab.script.frames_passed(SETTLE_FRAMES, self._config.browser.timeouts.frame_ms)
        return ActionOutcome(described)

    async def _move_to(self, tab: _Tab, x: float, y: float) -> None:
        try:
            await self._input(tab.page.mouse.move(x, y), "the pointer moved")
        except PlaywrightError as exc:
            raise BrowserError(
                f"The pointer could not be moved: {first_line(exc)}", reason="the browser did not respond"
            ) from exc

    async def drag(self, start: Place, end: Place) -> Dragged:
        tab = self._current()
        if isinstance(start, str):
            point = await self._prepare(tab, start)
            sx, sy, source = point["x"], point["y"], point["describe"]
        else:
            sx, sy = start
            source = await self._describe_at(tab, sx, sy)
        if isinstance(end, str):
            # Bringing the source into view may have moved the page: the target is looked for where it is now.
            found = await self._locate(tab, end)
            target = f'{found.role} "{found.name}"' if found.name else found.role
            if found.box is None:
                raise BrowserError(
                    f"{end} ({target}) is outside what the browser shows while the start of the drag "
                    "is in view. Scroll until both are visible, or drag to a point.",
                    reason="the two are not on the screen together",
                )
            tx, ty = found.box.x + found.box.w / 2, found.box.y + found.box.h / 2
        else:
            tx, ty = end
            target = await self._describe_at(tab, tx, ty)
        navigations, commits = tab.navigations, tab.commits
        mouse = tab.page.mouse

        async def pull() -> None:
            await mouse.move(sx, sy)
            await mouse.down()
            await mouse.move(tx, ty, steps=self._config.browser.input.drag_steps)
            await mouse.up()

        try:
            await self._input(pull(), "the drag")
        except (PlaywrightError, BrowserError) as exc:
            # A drag that failed part-way leaves the button held, and every move after it would drag.
            with contextlib.suppress(BrowserError, PlaywrightError):
                await self._input(mouse.up(), "the drag")
            if isinstance(exc, BrowserError):
                raise
            raise BrowserError(
                f"Could not drag: {first_line(exc)}", reason="the browser did not respond"
            ) from exc
        return Dragged(source, target, await self._settle(tab, navigations, commits))

    async def scroll(
        self, dx: float, dy: float, *, ref: str | None = None, at: tuple[float, float] | None = None
    ) -> ScrollPosition:
        tab = self._current()
        if ref is not None:
            point = await self._ask(
                tab, "wheelPoint", {"ref": ref, "maxName": self._config.browser.snapshot.max_name_chars}
            )
            self._raise_for(point, ref)
            x, y = point["x"], point["y"]
        elif at is not None:
            x, y = at
            await self._describe_at(tab, x, y)
        else:
            width, height = await self._viewport(tab)
            x, y = width / 2, height / 2
        before = await self._scrolled(tab, ref, wait=False)
        await self._wheel(tab, x, y, dx, dy)
        after = await self._scrolled(tab, ref, wait=True)
        moved = (after["x"], after["y"]) != (before["x"], before["y"])
        return ScrollPosition(after["x"], after["y"], after["width"], after["height"], moved, after["inside"])

    async def _scrolled(self, tab: _Tab, ref: str | None, *, wait: bool) -> dict[str, Any]:
        timeouts = self._config.browser.timeouts
        wait_ms = timeouts.settle_ms if wait else 0
        position = await self._ask(
            tab, "scrolled", {"ref": ref, "timeoutMs": wait_ms, "frameMs": timeouts.frame_ms}, wait_ms=wait_ms
        )
        self._raise_for(position, ref)
        return position

    async def scroll_to(self, ref: str) -> ActionOutcome:
        tab = self._current()
        found = await self._ask(
            tab, "reveal", {"ref": ref, "maxName": self._config.browser.snapshot.max_name_chars}
        )
        self._raise_for(found, ref)
        await self._scrolled(tab, None, wait=True)
        return ActionOutcome(found["describe"])

    async def press_key(self, keys: str, *, repeat: int = 1, ref: str | None = None) -> ActionOutcome:
        tab = self._current()
        described = ""
        if ref is not None:
            found = await self._ask(
                tab, "focusOn", {"ref": ref, "maxName": self._config.browser.snapshot.max_name_chars}
            )
            self._raise_for(found, ref)
            described = found["describe"]
        navigations, commits = tab.navigations, tab.commits
        keyboard = tab.page.keyboard

        async def press() -> None:
            for _ in range(repeat):
                try:
                    await keyboard.press(keys)
                except PlaywrightError as exc:
                    if "Unknown key" not in str(exc) or len(keys) != 1:
                        raise
                    # A character that is on no key of the keyboard Playwright knows is put in as text.
                    await keyboard.insert_text(keys)

        async def release() -> None:
            for modifier in reversed(keys.split("+")[:-1]):
                await keyboard.up(modifier)

        try:
            await self._input(press(), "the key press")
        except (PlaywrightError, BrowserError) as exc:
            # A press that failed part-way leaves its modifiers held down, and every click after it
            # would be a click with Control held.
            with contextlib.suppress(BrowserError, PlaywrightError):
                await self._input(release(), "the key press")
            if isinstance(exc, BrowserError):
                raise
            if "Unknown key" in str(exc):
                raise BadInput(
                    "The browser has no key of that name. Use a name such as Enter, Escape, Tab or "
                    "ArrowDown, or one character.",
                    reason="the key name is not known",
                ) from exc
            raise BrowserError(
                f"The key could not be pressed: {first_line(exc)}", reason="the browser did not respond"
            ) from exc
        return ActionOutcome(described, await self._settle(tab, navigations, commits))

    async def select_option(self, ref: str, values: Sequence[str]) -> Selected:
        tab = self._current()
        settings = self._config.browser.snapshot
        navigations, commits = tab.navigations, tab.commits
        chosen = await self._ask(
            tab,
            "select",
            {
                "ref": ref,
                "values": list(values),
                "maxName": settings.max_name_chars,
                "maxOptions": settings.max_options,
            },
        )
        error = chosen.get("error")
        if error == "not_select":
            raise BadInput(
                f"{ref} ({chosen['describe']}) is not a dropdown. browser_select_option works on a "
                "select element. For any other list, click it open and click the option.",
                reason="it is not a dropdown",
            )
        if error == "one_only":
            raise BadInput(
                f"{ref} ({chosen['describe']}) takes one option, and {len(values)} were given.",
                reason="it takes one option",
            )
        if error == "no_option":
            options = ", ".join(f'"{option}"' for option in chosen["options"])
            raise BadInput(
                f'{ref} ({chosen["describe"]}) has no option "{chosen["want"]}". Its options: {options}.',
                reason="there is no such option",
            )
        self._raise_for(chosen, ref)
        # A page may load another one as soon as an option is chosen.
        await self._settle(tab, navigations, commits)
        return Selected(chosen["describe"], chosen["selected"])

    async def set_checked(self, ref: str, checked: bool) -> Checked:
        tab = self._current()
        before = await self._checkable(tab, ref)
        if before["checked"] == checked:
            return Checked(before["describe"], checked, changed=False)
        if before["radio"] and not checked:
            raise BadInput(
                f"{ref} ({before['describe']}) is a radio button. It is cleared by choosing another one "
                "of its group.",
                reason="a radio button cannot be cleared",
            )
        await self._click_ref(tab, ref, "left", 1, ())
        after = await self._checkable(tab, ref)
        if after["checked"] != checked:
            raise BrowserError(
                f"Clicked {ref} ({before['describe']}), but it is still "
                f"{'checked' if after['checked'] else 'not checked'}. The page may have refused the change.",
                reason="the page did not accept the change",
            )
        return Checked(before["describe"], checked, changed=True)

    async def _checkable(self, tab: _Tab, ref: str) -> dict[str, Any]:
        state = await self._ask(
            tab, "checkable", {"ref": ref, "maxName": self._config.browser.snapshot.max_name_chars}
        )
        if state.get("error") == "not_checkable":
            raise BadInput(
                f"{ref} ({state['describe']}) is not a checkbox, a radio button or a switch.",
                reason="it cannot be checked",
            )
        self._raise_for(state, ref)
        return state

    async def wait_for_text(self, text: str, *, gone: bool, timeout_s: float) -> bool:
        timeouts = self._config.browser.timeouts
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout_s
        while True:
            remaining_ms = max(0, round((deadline - loop.time()) * 1000))
            try:
                found = await self._current().script.call(
                    "waitText",
                    {"text": text, "gone": gone, "timeoutMs": remaining_ms, "pollMs": timeouts.frame_ms},
                    wait_ms=remaining_ms,
                )
            except BrowserError:
                # The page was replaced, or was too busy to answer. The wait goes on in what is there
                # now, for as long as there is time.
                if loop.time() >= deadline:
                    return False
                await asyncio.sleep(timeouts.frame_ms / 1000)
                continue
            return found["reached"]

    async def wait_for_load(self, state: LoadState, timeout_s: float) -> bool:
        try:
            await self._current().page.wait_for_load_state(state, timeout=timeout_s * 1000)
        except PlaywrightTimeoutError:
            return False
        except PlaywrightError as exc:
            raise BrowserError(
                f"Could not wait for the page: {first_line(exc)}", reason="the browser did not respond"
            ) from exc
        return True

    # Pictures (spec 5.5).

    async def screenshot(self, *, full_page: bool, annotate: bool) -> Shot:
        tab = self._current()
        frame_ms = self._config.browser.timeouts.frame_ms
        area = await tab.script.call("area", {})
        if full_page:
            x, y, width = 0, 0, area["fullWidth"]
        else:
            x, y, width = area["x"], area["y"], area["width"]
        if annotate:
            await tab.script.call(
                "label", {"on": True, "fullPage": full_page, "frameMs": frame_ms}, wait_ms=2 * frame_ms
            )
        try:
            # One pixel of the picture is one pixel of the page, on a screen of any density.
            picture = await self._capture(tab, None, full_page=full_page, every_pixel=False)
        finally:
            if annotate:
                with contextlib.suppress(BrowserError):
                    await tab.script.call("label", {"on": False})
        picture, (shown_width, shown_height) = await self._fitted(tab, picture)
        scale = shown_width / width
        taken = _Taken(x, y, scale, shown_width, shown_height)
        tab.shot = taken
        if not full_page:
            # From now on a point the agent gives is a point of this picture.
            tab.pixel = 1 / scale
        return Shot(picture, taken.width, taken.height, scaled=scale < 1)

    async def zoom(self, region: tuple[float, float, float, float]) -> Shot:
        tab = self._current()
        taken = tab.shot
        if taken is None:
            raise BadInput(
                "Take a screenshot first: the region is given in its pixels.", reason="there is no screenshot"
            )
        x0, y0, x1, y1 = region
        if not (0 <= x0 < x1 <= taken.width and 0 <= y0 < y1 <= taken.height):
            raise BadInput(
                f"The region must lie inside the last screenshot, which is {taken.width} by "
                f"{taken.height} pixels, with x0 less than x1 and y0 less than y1.",
                reason="the region is outside the screenshot",
            )
        clip = {
            "x": taken.x + x0 / taken.scale,
            "y": taken.y + y0 / taken.scale,
            "width": (x1 - x0) / taken.scale,
            "height": (y1 - y0) / taken.scale,
        }
        # Every pixel the browser draws for the region, unless that picture would be too large.
        whole = await self._capture(tab, clip, full_page=True, every_pixel=True)
        picture, (width, height) = await self._fitted(tab, whole)
        return Shot(picture, width, height, scaled=size_of(whole) != (width, height))

    async def _capture(
        self, tab: _Tab, clip: dict[str, float] | None, *, full_page: bool, every_pixel: bool
    ) -> Picture:
        """A picture of the page, or of a rectangle of it given in page pixels. It is taken the way the
        browser's own driver takes one: a capture asked for on this driver's own DevTools session
        resets the screen the browser emulates (spec 5.5)."""
        settings = self._config.browser.screenshot
        limit = self._config.browser.timeouts.action_ms / 1000
        wanted: dict[str, Any] = {
            "type": settings.format,
            "full_page": full_page,
            # "css": one picture pixel to a page pixel. "device": every pixel a dense screen has.
            "scale": "device" if every_pixel else "css",
            "timeout": limit * 1000,
        }
        if clip is not None:
            wanted["clip"] = clip
        if settings.format == "jpeg":
            wanted["quality"] = settings.jpeg_quality
        try:
            data = await self._within(limit, tab.page.screenshot(**wanted))
        except (TimeoutError, PlaywrightTimeoutError):
            raise BrowserError(
                f"The browser did not give the picture within {limit:g} s.",
                reason="the page is not answering",
            ) from None
        except PlaywrightError as exc:
            raise BrowserError(
                f"The picture could not be taken: {first_line(exc)}", reason="the browser did not respond"
            ) from exc
        return Picture(data, f"image/{settings.format}")

    async def _fitted(self, tab: _Tab, picture: Picture) -> tuple[Picture, tuple[int, int]]:
        """The picture, made smaller when its longest side is over the limit, and its size. The
        browser makes it smaller itself, in the page script."""
        settings = self._config.browser.screenshot
        width, height = size_of(picture)
        longest = max(width, height)
        if longest <= settings.max_dimension:
            return picture, (width, height)
        fit = settings.max_dimension / longest
        width, height = max(1, round(width * fit)), max(1, round(height * fit))
        smaller = await tab.script.call(
            "shrink",
            {
                "data": base64.b64encode(picture.data).decode("ascii"),
                "mime": picture.mime,
                "width": width,
                "height": height,
                "quality": settings.jpeg_quality / 100,
                "piece": SHRINK_PIECE,
            },
            wait_ms=self._config.browser.timeouts.action_ms,
        )
        return Picture(base64.b64decode(smaller["data"]), picture.mime), (width, height)

    def page_point(self, x: float, y: float) -> tuple[float, float]:
        pixel = self._active.pixel if self._active else 1.0
        return x * pixel, y * pixel

    # Dialogs (spec 5.7).

    def _on_dialog(self, tab_id: str, dialog: Dialog) -> None:
        settings = self._config.browser.dialogs
        self._dialog_count += 1
        kind: DialogKind = "alert"
        for known in DIALOG_KINDS:
            if dialog.type == known:
                kind = known
        text = capped(dialog.message, self._config.browser.snapshot.max_text_chars)
        info = PageDialog(f"d{self._dialog_count}", kind, text, tab_id)
        if settings.policy != "agent":
            accept = settings.policy == "auto_accept"
            self._spawn(self._answer(dialog, accept, settings.default_prompt_text))
            done = "accepted" if accept else "dismissed"
            self._tell(Happened("dialog_closed", f"{info.named} opened and was {done} automatically"))
            return
        entry = _OpenDialog(info, dialog)
        entry.timer = self._spawn(self._expire(entry))
        self._dialogs.append(entry)
        self._dialog_open.set()
        self._no_dialog.clear()
        # The agent is told by the call the dialog interrupts, or by the next one, which is refused.
        shown = {"id": info.id, "kind": kind, "text": text, "expires_in_s": settings.timeout_s}
        self._tell(Happened("dialog_opened", "", shown))

    @staticmethod
    async def _answer(dialog: Dialog, accept: bool, text: str | None) -> None:
        with contextlib.suppress(PlaywrightError):
            if accept:
                await dialog.accept(text)
            else:
                await dialog.dismiss()

    async def _expire(self, entry: _OpenDialog) -> None:
        """A dialog nobody answers is dismissed, so that a page is not held for ever."""
        wait = self._config.browser.dialogs.timeout_s
        await asyncio.sleep(wait)
        if entry in self._dialogs:
            await self._answer(entry.dialog, False, None)
            self._close_dialog(
                entry, "timed_out", f"{entry.info.named} was dismissed: nobody answered it within {wait} s"
            )

    def _close_dialog(self, entry: _OpenDialog, outcome: str, told: str) -> None:
        if entry not in self._dialogs:
            return
        self._dialogs.remove(entry)
        if entry.timer is not None and entry.timer is not asyncio.current_task():
            entry.timer.cancel()
        if not self._dialogs:
            self._dialog_open.clear()
            self._no_dialog.set()
        self._tell(Happened("dialog_closed", told, {"id": entry.info.id, "outcome": outcome}))

    def pending_dialog(self) -> PageDialog | None:
        return self._dialogs[0].info if self._dialogs else None

    async def dialog_opened(self) -> None:
        await self._dialog_open.wait()

    async def answer_dialog(self, accept: bool, text: str | None) -> PageDialog:
        if not self._dialogs:
            raise BadInput("No dialog is open.", reason="no dialog is open")
        entry = self._dialogs[0]
        try:
            if accept:
                # A prompt that is accepted with no text keeps the text the page put there.
                await entry.dialog.accept(entry.dialog.default_value if text is None else text)
            else:
                await entry.dialog.dismiss()
        except PlaywrightError as exc:
            self._close_dialog(entry, "dismissed", "")
            raise BrowserError(
                f"The dialog could not be answered: {first_line(exc)}", reason="the dialog has gone"
            ) from exc
        self._close_dialog(entry, "accepted" if accept else "dismissed", "")
        return entry.info

    async def _within(self, seconds: float, work: Awaitable[Any]) -> Any:
        """Waits for the browser for at most `seconds`, not counting the time a dialog is open: while
        one is, its page answers nothing. Raises TimeoutError when no answer came."""
        task = asyncio.ensure_future(work)
        try:
            while True:
                done, _ = await asyncio.wait({task}, timeout=seconds)
                if done:
                    return task.result()
                if not self._dialogs:
                    raise TimeoutError
                await self._no_dialog.wait()
        finally:
            if not task.done():
                task.cancel()
                task.add_done_callback(_retrieved)

    # Diagnostics (spec 5.9).

    def _on_console(self, tab: _Tab, message: ConsoleMessage) -> None:
        limit = self._config.browser.capture.max_entry_chars
        tab.console.append(ConsoleLine(CONSOLE_LEVELS.get(message.type, "info"), capped(message.text, limit)))

    def _on_page_error(self, tab: _Tab, error: Exception) -> None:
        limit = self._config.browser.capture.max_entry_chars
        tab.console.append(ConsoleLine("error", capped(f"Uncaught {first_line(error)}", limit)))

    @staticmethod
    def _on_response(tab: _Tab, response: Response) -> None:
        request = response.request
        tab.network.append(NetworkLine(request.method, response.status, request.resource_type, request.url))

    @staticmethod
    def _on_request_failed(tab: _Tab, request: Request) -> None:
        tab.network.append(
            NetworkLine(request.method, None, request.resource_type, request.url, request.failure or "failed")
        )

    def console(self, *, clear: bool) -> list[ConsoleLine]:
        tab = self._current()
        lines = list(tab.console)
        if clear:
            tab.console.clear()
        return lines

    def network(self, *, clear: bool) -> list[NetworkLine]:
        tab = self._current()
        lines = list(tab.network)
        if clear:
            tab.network.clear()
        return lines

    async def evaluate(self, expression: str) -> Any:
        tab = self._current()
        limit = self._config.browser.timeouts.action_ms / 1000
        try:
            return await self._within(limit, tab.page.evaluate(expression))
        except TimeoutError:
            raise BrowserError(
                f"The script did not finish within {limit:g} s.", reason="the script took too long"
            ) from None
        except PlaywrightError as exc:
            said = first_line(exc).removeprefix("Page.evaluate: ")
            raise BrowserError(f"The script failed: {said}", reason="the script failed") from exc

    # Files (spec 5.8).

    async def upload(self, ref: str, paths: Sequence[str]) -> ActionOutcome:
        tab = self._current()
        point = await self._point_under_pointer(tab, ref)
        described = point["describe"]
        try:
            # The element is clicked as a person would click it, and the file chooser that opens is
            # given the files. No chooser is ever shown on a screen.
            async with tab.page.expect_file_chooser(
                timeout=self._config.browser.timeouts.settle_ms
            ) as opening:
                await self._click(tab, point["x"], point["y"], ref, "left", 1, ())
            chooser = await opening.value
        except PlaywrightTimeoutError:
            raise BadInput(
                f"Clicked {ref} ({described}) and no file chooser opened. Give the ref of a file field, "
                "or of the button that opens the file chooser.",
                reason="no file chooser opened",
            ) from None
        if len(paths) > 1 and not chooser.is_multiple():
            raise BadInput(
                f"{ref} ({described}) takes one file, and {len(paths)} were given.",
                reason="it takes one file",
            )
        try:
            await chooser.set_files(list(paths))
        except PlaywrightError as exc:
            raise BrowserError(
                f"The files could not be given to {ref} ({described}): {first_line(exc)}",
                reason="the browser did not take the files",
            ) from exc
        return ActionOutcome(described)

    def downloads(self) -> list[SavedFile]:
        return list(self._downloads)

    async def _save(self, download: Download) -> None:
        """Keeps a file the browser downloaded: in the downloads folder, under a name of its own."""
        settings = self._config.browser.downloads
        name = file_name(download.suggested_filename)
        place = len(self._downloads)
        self._downloads.append(SavedFile(name, "downloading"))

        def failed(reason: str) -> None:
            self._downloads[place] = SavedFile(name, "failed", reason=reason)
            self._tell(Happened("download", f"the download of {name} failed: {reason}"))

        if not settings.enabled:
            with contextlib.suppress(PlaywrightError):
                await download.cancel()
            failed("downloads are turned off")
            return
        try:
            arrived = await download.path()
        except PlaywrightError:
            failed("the browser could not finish it")
            return
        size = await asyncio.to_thread(os.path.getsize, arrived)
        if size > settings.max_size_mb * 1024 * 1024:
            with contextlib.suppress(PlaywrightError):
                await download.delete()
            failed(f"it is larger than {settings.max_size_mb} MB, the most allowed")
            return
        try:
            target = await asyncio.to_thread(free_path, settings.dir, name)
            await download.save_as(target)
        except (PlaywrightError, OSError):
            failed("it could not be saved in the downloads folder")
            return
        self._downloads[place] = SavedFile(target.name, "saved", str(target), size)
        self._tell(
            Happened("download", f"download saved: {target.name}", {"name": target.name, "size": size})
        )

    # The live picture.

    async def start_frames(self, on_frame: Callable[[bytes], None], level: QualityLevel) -> None:
        self._frames = (on_frame, level)
        await self._begin_pictures(level)

    async def stop_frames(self) -> None:
        self._frames = None
        pictured, self._pictured = self._pictured, None
        if pictured is not None:
            with contextlib.suppress(PlaywrightError):
                await pictured.cdp.send("Page.stopScreencast")

    async def _begin_pictures(self, level: QualityLevel) -> None:
        tab = self._current()
        width, height = await self._viewport(tab)
        try:
            await tab.cdp.send(
                "Page.startScreencast",
                {
                    "format": "jpeg",
                    "quality": level.jpeg_quality,
                    "maxWidth": level.max_width,
                    "maxHeight": max(1, round(level.max_width * height / width)),
                },
            )
        except PlaywrightError as exc:
            raise BrowserError(f"The live picture could not be started: {first_line(exc)}") from exc
        self._pictured = tab

    def _on_picture(self, tab: _Tab, frame: dict[str, Any]) -> None:
        if self._frames is None or tab is not self._active:
            return
        on_frame, level = self._frames
        on_frame(base64.b64decode(frame["data"]))
        self._spawn(self._acknowledge(tab, frame["sessionId"], level.max_fps))

    async def _acknowledge(self, tab: _Tab, picture: int, max_fps: int) -> None:
        """The browser sends its next picture only once this one is acknowledged. Waiting here is what
        limits the rate, and the picture that follows is always the newest one."""
        now = asyncio.get_running_loop().time()
        wait = self._next_acknowledgement - now
        self._next_acknowledgement = max(now, self._next_acknowledgement) + 1 / max_fps
        if wait > 0:
            await asyncio.sleep(wait)
        with contextlib.suppress(PlaywrightError):
            await tab.cdp.send("Page.screencastFrameAck", {"sessionId": picture})

    # What a person does with the mouse and the keyboard while they are in control.

    async def pointer(self, action: PointerAction, x: float, y: float, button: MouseButton = "left") -> None:
        mouse = self._current().page.mouse

        async def act() -> None:
            await mouse.move(x, y)
            if action == "down":
                await mouse.down(button=button)
            elif action == "up":
                await mouse.up(button=button)

        try:
            await self._input(act(), "the pointer moved")
        except PlaywrightError as exc:
            raise BrowserError(f"The pointer could not be moved: {first_line(exc)}") from exc

    async def key(self, action: KeyAction, key: str) -> None:
        keyboard = self._current().page.keyboard

        async def act() -> None:
            try:
                if action == "down":
                    await keyboard.down(key)
                else:
                    await keyboard.up(key)
            except PlaywrightError as exc:
                if "Unknown key" not in str(exc):
                    raise
                # A character that is on no key of the keyboard Playwright knows, such as é, is put in
                # as text. A name that is no key and no character, such as "Dead", is left out.
                if action == "down" and len(key) == 1:
                    await keyboard.insert_text(key)

        try:
            await self._input(act(), "the key")
        except PlaywrightError as exc:
            raise BrowserError(f"The key could not be pressed: {first_line(exc)}") from exc

    async def wheel(self, x: float, y: float, dx: float, dy: float) -> None:
        await self._wheel(self._current(), x, y, dx, dy)

    async def _wheel(self, tab: _Tab, x: float, y: float, dx: float, dy: float) -> None:
        async def act() -> None:
            await tab.page.mouse.move(x, y)
            await tab.page.mouse.wheel(dx, dy)

        try:
            await self._input(act(), "the wheel turned")
        except PlaywrightError as exc:
            raise BrowserError(f"The page could not be scrolled: {first_line(exc)}") from exc

    async def _input(self, work: Coroutine[Any, Any, None], what: str, *, extra_ms: float = 0) -> None:
        """Sends mouse or keyboard input. The browser answers only once the page has handled it, and a
        page can take as long as it likes: past the action limit, the call fails instead of waiting."""
        limit = self._config.browser.timeouts.action_ms / 1000
        try:
            await self._within(limit + extra_ms / 1000, work)
        except TimeoutError:
            raise BrowserError(
                f"The page did not answer within {limit:g} s after {what}. It may still be working on it. "
                "Take a new snapshot before you act again.",
                reason="the page is not answering",
            ) from None

    @staticmethod
    def _raise_for(result: dict[str, Any], ref: str | None) -> None:
        error = result.get("error")
        if error is None:
            return
        subject = ref or "The focused element"
        if error == "stale":
            raise StaleRef(ref or "")
        if error == "nothing_focused":
            raise BadInput(
                "Nothing is focused. Give the ref of the field to type into.", reason="nothing is focused"
            )
        if error == "not_editable":
            raise BadInput(
                f"{subject} ({result['describe']}) is not a text field. "
                "Use browser_click for buttons, checkboxes and links.",
                reason="it is not a text field",
            )
        raise BrowserError(
            f"Could not act on {subject} ({result['describe']}): {result['reason']}.", reason=result["reason"]
        )

    async def _settle(self, tab: _Tab, navigations_before: int, commits_before: int) -> str | None:
        """Waits for a navigation the action started, and for a window it opened. Returns the new
        address of the tab, or None if it went nowhere."""
        timeouts = self._config.browser.timeouts
        document_alive = await tab.script.frames_passed(SETTLE_FRAMES, timeouts.frame_ms)
        if tab.id not in self._tabs:
            # The action closed its own tab.
            return None
        if tab.navigations != navigations_before or not document_alive:
            await self._wait_for_commit(tab, commits_before, timeouts.settle_ms)
            with contextlib.suppress(PlaywrightTimeoutError):
                await tab.page.wait_for_load_state("domcontentloaded", timeout=timeouts.settle_ms)
            await self._wait_for_load(tab)
        await self._let_new_tabs_in()
        return tab.page.url if tab.commits != commits_before else None

    async def _wait_for_commit(self, tab: _Tab, commits_before: int, timeout_ms: int) -> None:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout_ms / 1000
        while tab.commits == commits_before:
            tab.committed.clear()
            remaining = deadline - loop.time()
            if remaining <= 0:
                return
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(tab.committed.wait(), remaining)

    async def _wait_for_load(self, tab: _Tab) -> None:
        # Some pages never fire the load event. The wait has a ceiling, and reaching it is not a failure.
        with contextlib.suppress(PlaywrightTimeoutError):
            await tab.page.wait_for_load_state("load", timeout=self._config.browser.timeouts.load_wait_ms)

    @staticmethod
    def _on_request(tab: _Tab, request: Request) -> None:
        if request.is_navigation_request() and request.frame == tab.page.main_frame:
            tab.navigations += 1

    @staticmethod
    def _on_frame_navigated(tab: _Tab, frame: Frame) -> None:
        if frame == tab.page.main_frame:
            tab.commits += 1
            tab.committed.set()
            # Another document: its frames are other frames.
            tab.frames.clear()
        # A frame that went to another site may have moved to another process, or back.
        tab.apart.pop(frame, None)
