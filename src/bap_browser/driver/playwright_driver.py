"""Drives a browser that this process launched: the remote headless backend."""

from __future__ import annotations

import asyncio
import contextlib
import os
from collections.abc import Mapping, Sequence
from typing import Any

from playwright.async_api import Browser, Frame, Page, Request, async_playwright
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from bap_browser.config import Config
from bap_browser.driver.base import ActionOutcome, MouseButton, TabInfo
from bap_browser.driver.page_script import PageScript
from bap_browser.driver.snapshot import snapshot_arguments
from bap_browser.errors import BadInput, BrowserError, ConfigError, StaleRef

PROXY_USERNAME_ENV = "BAP_BROWSER_PROXY_USERNAME"
PROXY_PASSWORD_ENV = "BAP_BROWSER_PROXY_PASSWORD"
TAB_ID = "t1"
# After an action, two animation frames are enough for a navigation it started to show itself.
SETTLE_FRAMES = 2


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
    elif browser.channel != "chromium":
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


class PlaywrightDriver:
    def __init__(self, config: Config) -> None:
        self._config = config
        self._stack = contextlib.AsyncExitStack()
        self._browser: Browser | None = None
        self._page: Page | None = None
        self._script: PageScript | None = None
        self._navigations = 0
        self._commits = 0
        self._committed = asyncio.Event()
        self._next_ref = 1

    @property
    def page(self) -> Page:
        if self._page is None:
            raise BrowserError("The browser has not been started.")
        return self._page

    @property
    def page_script(self) -> PageScript:
        if self._script is None:
            raise BrowserError("The browser has not been started.")
        return self._script

    async def start(self) -> None:
        timeouts = self._config.browser.timeouts
        try:
            playwright = await async_playwright().start()
            self._stack.push_async_callback(playwright.stop)
            browser = await playwright.chromium.launch(**launch_options(self._config, os.environ))
            self._stack.push_async_callback(browser.close)
            context = await browser.new_context(**context_options(self._config))
            context.set_default_timeout(timeouts.action_ms)
            context.set_default_navigation_timeout(timeouts.navigation_ms)
            page = await context.new_page()
            cdp = await context.new_cdp_session(page)
        except PlaywrightError as exc:
            await self._stack.aclose()
            raise BrowserError(f"The browser could not be started: {first_line(exc)}") from exc
        page.on("request", self._on_request)
        page.on("framenavigated", self._on_frame_navigated)
        self._browser, self._page, self._script = browser, page, PageScript(cdp)

    async def close(self) -> None:
        await self._stack.aclose()
        self._browser = self._page = self._script = None

    def is_alive(self) -> bool:
        return self._browser is not None and self._browser.is_connected()

    def description(self) -> str:
        if self._browser is None:
            raise BrowserError("The browser has not been started.")
        return f"Chromium {self._browser.version}"

    async def tabs(self) -> list[TabInfo]:
        try:
            title = await self.page.title()
        except PlaywrightError:
            title = ""
        return [TabInfo(TAB_ID, self.page.url, title, True)]

    async def navigate(self, url: str) -> str:
        navigations, commits = self._navigations, self._commits
        try:
            await self.page.goto(url, wait_until="domcontentloaded")
        except PlaywrightError as exc:
            if self._navigations != navigations:
                # The browser shows its own error page for an address it could not load. A
                # navigation started before that page arrives would be interrupted by it.
                await self._wait_for_commit(commits, self._config.browser.timeouts.settle_ms)
            raise BrowserError(f"Could not open {url}: {first_line(exc)}") from exc
        finally:
            self.page_script.forget_document()
        await self._wait_for_load()
        return self.page.url

    async def snapshot(self, *, mode: str, ref: str | None, max_chars: int, include_bboxes: bool) -> str:
        arguments = snapshot_arguments(
            self._config.browser.snapshot,
            mode=mode,
            ref=ref,
            max_chars=max_chars,
            include_bboxes=include_bboxes,
            next_ref=self._next_ref,
        )
        data = await self.page_script.call("snapshot", arguments)
        if data.get("error") == "stale":
            raise StaleRef(ref or "")
        # Numbering continues across navigations, so an old ref can never point at a new element.
        self._next_ref = data["next"]
        return data["text"]

    async def click(
        self, ref: str, *, button: MouseButton = "left", click_count: int = 1, modifiers: Sequence[str] = ()
    ) -> ActionOutcome:
        browser = self._config.browser
        point = await self.page_script.call(
            "prepare",
            {
                "ref": ref,
                "timeoutMs": browser.timeouts.action_ms,
                "frameMs": browser.timeouts.frame_ms,
                "maxName": browser.snapshot.max_name_chars,
            },
        )
        self._raise_for(point, ref)
        navigations, commits = self._navigations, self._commits
        keyboard = self.page.keyboard
        try:
            for key in modifiers:
                await keyboard.down(key)
            try:
                await self.page.mouse.click(point["x"], point["y"], button=button, click_count=click_count)
            finally:
                for key in reversed(modifiers):
                    await keyboard.up(key)
        except PlaywrightError as exc:
            raise BrowserError(f"Could not click {ref}: {first_line(exc)}") from exc
        return ActionOutcome(point["describe"], await self._settle(navigations, commits))

    async def type_text(
        self, ref: str | None, text: str, *, clear: bool = True, submit: bool = False, slowly: bool = False
    ) -> ActionOutcome:
        browser = self._config.browser
        field = await self.page_script.call(
            "focus", {"ref": ref, "clear": clear, "maxName": browser.snapshot.max_name_chars}
        )
        self._raise_for(field, ref)
        navigations, commits = self._navigations, self._commits
        keyboard = self.page.keyboard
        delay = browser.input.slow_type_delay_ms if slowly else browser.input.type_delay_ms
        try:
            if text == "":
                if clear and field["hadText"]:
                    await keyboard.press("Delete")
            elif delay:
                await keyboard.type(text, delay=delay)
            else:
                await keyboard.insert_text(text)
            if submit:
                await keyboard.press("Enter")
        except PlaywrightError as exc:
            raise BrowserError(
                f"Could not type into {ref or 'the focused element'}: {first_line(exc)}"
            ) from exc
        navigated_to = await self._settle(navigations, commits) if submit else None
        return ActionOutcome(field["describe"], navigated_to)

    @staticmethod
    def _raise_for(result: dict[str, Any], ref: str | None) -> None:
        error = result.get("error")
        if error is None:
            return
        subject = ref or "The focused element"
        if error == "stale":
            raise StaleRef(ref or "")
        if error == "nothing_focused":
            raise BadInput("Nothing is focused. Give the ref of the field to type into.")
        if error == "not_editable":
            raise BadInput(
                f"{subject} ({result['describe']}) is not a text field. "
                "Use browser_click for buttons, checkboxes and links."
            )
        raise BrowserError(f"Could not act on {subject} ({result['describe']}): {result['reason']}.")

    async def _settle(self, navigations_before: int, commits_before: int) -> str | None:
        """Waits for a navigation the action started. Returns the new address, or None if there was none."""
        timeouts = self._config.browser.timeouts
        document_alive = await self.page_script.frames_passed(SETTLE_FRAMES, timeouts.frame_ms)
        if self._navigations != navigations_before or not document_alive:
            await self._wait_for_commit(commits_before, timeouts.settle_ms)
            with contextlib.suppress(PlaywrightTimeoutError):
                await self.page.wait_for_load_state("domcontentloaded", timeout=timeouts.settle_ms)
            await self._wait_for_load()
        return self.page.url if self._commits != commits_before else None

    async def _wait_for_commit(self, commits_before: int, timeout_ms: int) -> None:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout_ms / 1000
        while self._commits == commits_before:
            self._committed.clear()
            remaining = deadline - loop.time()
            if remaining <= 0:
                return
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._committed.wait(), remaining)

    async def _wait_for_load(self) -> None:
        # Some pages never fire the load event. The wait has a ceiling, and reaching it is not a failure.
        with contextlib.suppress(PlaywrightTimeoutError):
            await self.page.wait_for_load_state("load", timeout=self._config.browser.timeouts.load_wait_ms)

    def _on_request(self, request: Request) -> None:
        if request.is_navigation_request() and request.frame == self.page.main_frame:
            self._navigations += 1

    def _on_frame_navigated(self, frame: Frame) -> None:
        if frame == self.page.main_frame:
            self._commits += 1
            self._committed.set()
