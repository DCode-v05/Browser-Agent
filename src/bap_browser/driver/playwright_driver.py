"""Drives a browser through Playwright: one this process launched, or one that is already running."""

from __future__ import annotations

import contextlib
import os
from collections import deque

from playwright.async_api import (
    Browser,
    Page,
    async_playwright,
)
from playwright.async_api import Error as PlaywrightError

from bap_browser.address import without_credentials
from bap_browser.driver.base import (
    Happened,
)
from bap_browser.driver.browser_parts import (
    NOT_STARTED,
    OpenTab,
    capped,
    context_options,
    first_line,
    launch_options,
    load_failure,
)
from bap_browser.driver.for_the_check import ForTheCheck
from bap_browser.driver.page_script import PageScript
from bap_browser.errors import BadInput, BrowserError, PolicyBlocked


class PlaywrightDriver(ForTheCheck):
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

    async def _add_tab(self, page: Page) -> OpenTab:
        """Takes a page in as a tab, and listens to what happens in it."""
        browser = self._config.browser
        if self._context is None:
            raise BrowserError(NOT_STARTED)
        self._tab_count += 1
        tab_id = f"t{self._tab_count}"
        # First of all: a dialog that nobody listens for is dismissed by the browser's driver at once.
        page.on("dialog", lambda dialog: self._on_dialog(tab_id, dialog))
        cdp = await self._context.new_cdp_session(page)
        tab = OpenTab(
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
        page.on("crash", lambda _: self._crashed(tab))
        page.on("download", lambda download: self._spawn(self._save(download)))
        # Listened for from the start, so that the browser hands every file chooser to this driver.
        # One that is asked for only at the moment of an upload can open before the browser has
        # heard that it is wanted, and is then never seen (and no later one opens).
        page.on("filechooser", lambda chooser: self._on_file_chooser(tab, chooser))
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
        cdp.on("Page.screencastFrame", lambda frame: self._on_picture(tab, frame))
        cdp.on("Page.windowOpen", lambda _: self._window_opening())
        cdp.on("Page.frameRequestedNavigation", lambda asked: self._on_leaving(tab, asked))
        # The page says when it opens a window, or sets out for another page, only to one who has
        # asked to hear about the page.
        await cdp.send("Page.enable")
        tab.main_frame_id = (await cdp.send("Page.getFrameTree"))["frameTree"]["frame"]["id"]
        self._tabs[tab_id] = tab
        return tab

    async def new_tab(self) -> str:
        tab = await self._open_tab()
        return tab.id

    async def _open_tab(self) -> OpenTab:
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

    async def _show(self, tab: OpenTab) -> None:
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

    def _crashed(self, tab: OpenTab) -> None:
        """A tab's page has crashed. Nothing more can be done in it, so it is told and closed like
        any tab that goes away (spec 18.8)."""
        if tab.id not in self._tabs:
            return
        self._forget(tab, "crashed")
        self._spawn(self._close_quietly(tab.page))

    @staticmethod
    async def _close_quietly(page: Page) -> None:
        with contextlib.suppress(PlaywrightError):
            await page.close()

    def _forget(self, tab: OpenTab, how: str = "closed") -> None:
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
        self._tell(Happened("tab_closed", f"tab {tab.id} {how}{now}"))
        if was_active and self._active is not None:
            self._spawn(self._show(self._active))

    def _on_page(self, page: Page) -> None:
        if not self._own_pages:
            self._spawn(self._adopt(page))

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
