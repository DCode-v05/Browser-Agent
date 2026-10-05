"""Drives a browser that this process launched: the remote headless backend."""

from __future__ import annotations

import asyncio
import base64
import contextlib
import os
from collections.abc import Callable, Coroutine, Mapping, Sequence
from typing import Any

from playwright.async_api import Browser, BrowserContext, CDPSession, Frame, Page, Request, async_playwright
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from bap_browser.config import Config, QualityLevel
from bap_browser.driver.base import (
    ActionOutcome,
    Box,
    Checked,
    Found,
    KeyAction,
    LoadState,
    Located,
    MouseButton,
    PointerAction,
    ScrollPosition,
    Selected,
    TabInfo,
)
from bap_browser.driver.page_script import PageScript
from bap_browser.driver.snapshot import snapshot_arguments
from bap_browser.errors import BadInput, BrowserError, ConfigError, StaleRef
from bap_browser.policy.address import without_credentials

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


class PlaywrightDriver:
    def __init__(self, config: Config) -> None:
        self._config = config
        self._stack = contextlib.AsyncExitStack()
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._version = ""
        self._page: Page | None = None
        self._script: PageScript | None = None
        self._navigations = 0
        self._commits = 0
        self._committed = asyncio.Event()
        self._next_ref = 1
        self._cdp: CDPSession | None = None
        self._frames: tuple[Callable[[bytes], None], QualityLevel] | None = None
        self._next_acknowledgement = 0.0
        self._acknowledging: set[asyncio.Task[None]] = set()

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
            launch = launch_options(self._config, os.environ)
            profile = self._config.browser.user_data_dir
            browser: Browser | None = None
            attach = self._config.browser.cdp_url
            if attach:
                # A browser that is already running, started by someone else. It is driven, and on
                # close it is let go of, not ended: the page stays where the agent left it.
                browser = await playwright.chromium.connect_over_cdp(attach, timeout=timeouts.launch_ms)
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
            cdp = await context.new_cdp_session(page)
            # A browser with a kept profile is not handed over as an object of its own, so its version is asked for.
            product = browser.version if browser else (await cdp.send("Browser.getVersion"))["product"]
        except PlaywrightError as exc:
            await self._stack.aclose()
            raise BrowserError(f"The browser could not be started: {first_line(exc)}") from exc
        page.on("request", self._on_request)
        page.on("framenavigated", self._on_frame_navigated)
        cdp.on("Page.screencastFrame", self._on_picture)
        context.on("close", self._on_context_closed)
        self._browser, self._context, self._page, self._cdp = browser, context, page, cdp
        self._version = product.rpartition("/")[2]
        self._script = PageScript(cdp, timeouts.page_reply_ms)
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
        for task in self._acknowledging:
            task.cancel()
        await self._stack.aclose()
        self._browser = self._context = self._page = self._script = self._cdp = None

    def _on_context_closed(self, context: BrowserContext) -> None:
        if context is self._context:
            self._context = None

    def is_alive(self) -> bool:
        if self._browser is not None:
            return self._browser.is_connected()
        # A browser with a kept profile is gone when its one context has closed.
        return self._context is not None

    def description(self) -> str:
        if self._page is None:
            raise BrowserError("The browser has not been started.")
        return f"Chromium {self._version}"

    async def tabs(self) -> list[TabInfo]:
        try:
            async with asyncio.timeout(self._config.browser.timeouts.page_reply_ms / 1000):
                title = await self.page.title()
        except (PlaywrightError, TimeoutError):
            title = ""
        return [TabInfo(TAB_ID, self.page.url, title, True)]

    async def viewport(self) -> tuple[int, int]:
        size = self.page.viewport_size
        if size is None:
            # No fixed size was asked for: the page is as large as its window.
            size = await self.page.evaluate("({ width: innerWidth, height: innerHeight })")
        return size["width"], size["height"]

    async def navigate(self, url: str) -> str:
        navigations, commits = self._navigations, self._commits
        try:
            await self.page.goto(url, wait_until="domcontentloaded")
        except PlaywrightError as exc:
            if self._navigations != navigations:
                # The browser shows its own error page for an address it could not load. A
                # navigation started before that page arrives would be interrupted by it.
                await self._wait_for_commit(commits, self._config.browser.timeouts.settle_ms)
            # The browser's own words repeat the address, which may hold a name and password.
            shown = without_credentials(url)
            raise BrowserError(
                f"Could not open {shown}: {first_line(exc).replace(url, shown)}", reason=load_failure(exc)
            ) from exc
        finally:
            self.page_script.forget_document()
        await self._wait_for_load()
        return self.page.url

    async def locate(self, ref: str) -> Located:
        found = await self.page_script.call(
            "locate", {"ref": ref, "maxName": self._config.browser.snapshot.max_name_chars}
        )
        if found.get("error") == "stale":
            raise StaleRef(ref)
        box = Box(*found["box"]) if found["box"] else None
        return Located(found["role"], found["name"], box, found["secret"], found["kind"])

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
        point = await self._point_under_pointer(ref)
        navigated_to = await self._click(point["x"], point["y"], ref, button, click_count, modifiers)
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
        described = await self._describe_at(x, y)
        navigated_to = await self._click(x, y, f"at ({x:g}, {y:g})", button, click_count, modifiers)
        return ActionOutcome(described, navigated_to)

    async def _point_under_pointer(self, ref: str) -> dict[str, Any]:
        """Waits until an element can be pressed, and moves the pointer onto it."""
        point = await self._prepare(ref)
        await self._move_to(point["x"], point["y"])
        frame_ms = self._config.browser.timeouts.frame_ms
        still_there = await self.page_script.call(
            "holds", {"ref": ref, "x": point["x"], "y": point["y"], "frameMs": frame_ms}, wait_ms=frame_ms
        )
        if not still_there:
            # Moving the pointer changed the page: a menu it was over has closed, say. The element
            # is found again where it is now.
            point = await self._prepare(ref)
            await self._move_to(point["x"], point["y"])
        return point

    async def _prepare(self, ref: str) -> dict[str, Any]:
        browser = self._config.browser
        point = await self.page_script.call(
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
        self, x: float, y: float, where: str, button: MouseButton, click_count: int, modifiers: Sequence[str]
    ) -> str | None:
        """Presses the mouse at a point. Returns the address the page went to, if it went anywhere."""
        navigations, commits = self._navigations, self._commits
        keyboard = self.page.keyboard

        async def press() -> None:
            for key in modifiers:
                await keyboard.down(key)
            await self.page.mouse.click(x, y, button=button, click_count=click_count)

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
        return await self._settle(navigations, commits)

    async def _describe_at(self, x: float, y: float) -> str:
        """What is at a point, as the snapshot names it. A point outside the page is refused."""
        width, height = await self.viewport()
        if not (0 <= x < width and 0 <= y < height):
            raise BadInput(
                f"({x:g}, {y:g}) is outside the page, which is {width} by {height} pixels.",
                reason="the point is outside the page",
            )
        found = await self.page_script.call(
            "at", {"x": x, "y": y, "maxName": self._config.browser.snapshot.max_name_chars}
        )
        return found["describe"]

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
        navigated_to = await self._settle(navigations, commits) if submit else None
        return ActionOutcome(field["describe"], navigated_to)

    async def back(self) -> str | None:
        return await self._through_history(self.page.go_back, "go back")

    async def forward(self) -> str | None:
        return await self._through_history(self.page.go_forward, "go forward")

    async def reload(self) -> str:
        address = await self._through_history(self.page.reload, "reload the page")
        return address or self.page.url

    async def _through_history(self, move: Callable[..., Coroutine[Any, Any, Any]], what: str) -> str | None:
        commits = self._commits
        try:
            await move(wait_until="domcontentloaded")
        except PlaywrightError as exc:
            raise BrowserError(f"Could not {what}: {first_line(exc)}", reason=load_failure(exc)) from exc
        finally:
            self.page_script.forget_document()
        if self._commits == commits:
            # Nothing was loaded: there is no page that way.
            return None
        await self._wait_for_load()
        return self.page.url

    async def text(self, ref: str | None, max_chars: int) -> tuple[str, int]:
        data = await self.page_script.call("text", {"ref": ref, "maxChars": max_chars})
        if data.get("error") == "stale":
            raise StaleRef(ref or "")
        return data["text"], data["more"]

    async def find(self, query: str, limit: int) -> Found:
        settings = self._config.browser.snapshot
        arguments = snapshot_arguments(
            settings,
            mode="all",
            ref=None,
            max_chars=settings.max_chars,
            include_bboxes=False,
            next_ref=self._next_ref,
        )
        data = await self.page_script.call("find", {"query": query, "limit": limit, "snapshot": arguments})
        self._next_ref = data["next"]
        return Found(data["lines"], data["total"])

    async def hover(self, ref: str) -> ActionOutcome:
        point = await self._point_under_pointer(ref)
        await self.page_script.frames_passed(SETTLE_FRAMES, self._config.browser.timeouts.frame_ms)
        return ActionOutcome(point["describe"])

    async def hover_at(self, x: float, y: float) -> ActionOutcome:
        described = await self._describe_at(x, y)
        await self._move_to(x, y)
        await self.page_script.frames_passed(SETTLE_FRAMES, self._config.browser.timeouts.frame_ms)
        return ActionOutcome(described)

    async def _move_to(self, x: float, y: float) -> None:
        try:
            await self._input(self.page.mouse.move(x, y), "the pointer moved")
        except PlaywrightError as exc:
            raise BrowserError(
                f"The pointer could not be moved: {first_line(exc)}", reason="the browser did not respond"
            ) from exc

    async def scroll(
        self, dx: float, dy: float, *, ref: str | None = None, at: tuple[float, float] | None = None
    ) -> ScrollPosition:
        if ref is not None:
            point = await self.page_script.call(
                "wheelPoint", {"ref": ref, "maxName": self._config.browser.snapshot.max_name_chars}
            )
            self._raise_for(point, ref)
            x, y = point["x"], point["y"]
        elif at is not None:
            x, y = at
            await self._describe_at(x, y)
        else:
            width, height = await self.viewport()
            x, y = width / 2, height / 2
        before = await self._scrolled(ref, wait=False)
        await self.wheel(x, y, dx, dy)
        after = await self._scrolled(ref, wait=True)
        moved = (after["x"], after["y"]) != (before["x"], before["y"])
        return ScrollPosition(after["x"], after["y"], after["width"], after["height"], moved, after["inside"])

    async def _scrolled(self, ref: str | None, *, wait: bool) -> dict[str, Any]:
        timeouts = self._config.browser.timeouts
        wait_ms = timeouts.settle_ms if wait else 0
        position = await self.page_script.call(
            "scrolled", {"ref": ref, "timeoutMs": wait_ms, "frameMs": timeouts.frame_ms}, wait_ms=wait_ms
        )
        self._raise_for(position, ref)
        return position

    async def scroll_to(self, ref: str) -> ActionOutcome:
        found = await self.page_script.call(
            "reveal", {"ref": ref, "maxName": self._config.browser.snapshot.max_name_chars}
        )
        self._raise_for(found, ref)
        await self._scrolled(None, wait=True)
        return ActionOutcome(found["describe"])

    async def press_key(self, keys: str, *, repeat: int = 1, ref: str | None = None) -> ActionOutcome:
        described = ""
        if ref is not None:
            found = await self.page_script.call(
                "focusOn", {"ref": ref, "maxName": self._config.browser.snapshot.max_name_chars}
            )
            self._raise_for(found, ref)
            described = found["describe"]
        navigations, commits = self._navigations, self._commits
        keyboard = self.page.keyboard

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
        return ActionOutcome(described, await self._settle(navigations, commits))

    async def select_option(self, ref: str, values: Sequence[str]) -> Selected:
        settings = self._config.browser.snapshot
        navigations, commits = self._navigations, self._commits
        chosen = await self.page_script.call(
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
        await self._settle(navigations, commits)
        return Selected(chosen["describe"], chosen["selected"])

    async def set_checked(self, ref: str, checked: bool) -> Checked:
        before = await self._checkable(ref)
        if before["checked"] == checked:
            return Checked(before["describe"], checked, changed=False)
        if before["radio"] and not checked:
            raise BadInput(
                f"{ref} ({before['describe']}) is a radio button. It is cleared by choosing another one "
                "of its group.",
                reason="a radio button cannot be cleared",
            )
        await self.click(ref)
        after = await self._checkable(ref)
        if after["checked"] != checked:
            raise BrowserError(
                f"Clicked {ref} ({before['describe']}), but it is still "
                f"{'checked' if after['checked'] else 'not checked'}. The page may have refused the change.",
                reason="the page did not accept the change",
            )
        return Checked(before["describe"], checked, changed=True)

    async def _checkable(self, ref: str) -> dict[str, Any]:
        state = await self.page_script.call(
            "checkable", {"ref": ref, "maxName": self._config.browser.snapshot.max_name_chars}
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
                found = await self.page_script.call(
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
            await self.page.wait_for_load_state(state, timeout=timeout_s * 1000)
        except PlaywrightTimeoutError:
            return False
        except PlaywrightError as exc:
            raise BrowserError(
                f"Could not wait for the page: {first_line(exc)}", reason="the browser did not respond"
            ) from exc
        return True

    async def start_frames(self, on_frame: Callable[[bytes], None], level: QualityLevel) -> None:
        self._frames = (on_frame, level)
        await self._begin_pictures(level)

    async def stop_frames(self) -> None:
        self._frames = None
        if self._cdp is not None:
            with contextlib.suppress(PlaywrightError):
                await self._cdp.send("Page.stopScreencast")

    async def _begin_pictures(self, level: QualityLevel) -> None:
        if self._cdp is None:
            raise BrowserError("The browser has not been started.")
        width, height = await self.viewport()
        try:
            await self._cdp.send(
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

    def _on_picture(self, frame: dict[str, Any]) -> None:
        if self._frames is None:
            return
        on_frame, level = self._frames
        on_frame(base64.b64decode(frame["data"]))
        task = asyncio.create_task(self._acknowledge(frame["sessionId"], level.max_fps))
        self._acknowledging.add(task)
        task.add_done_callback(self._acknowledging.discard)

    async def _acknowledge(self, picture: int, max_fps: int) -> None:
        """The browser sends its next picture only once this one is acknowledged. Waiting here is what
        limits the rate, and the picture that follows is always the newest one."""
        now = asyncio.get_running_loop().time()
        wait = self._next_acknowledgement - now
        self._next_acknowledgement = max(now, self._next_acknowledgement) + 1 / max_fps
        if wait > 0:
            await asyncio.sleep(wait)
        if self._cdp is not None:
            with contextlib.suppress(PlaywrightError):
                await self._cdp.send("Page.screencastFrameAck", {"sessionId": picture})

    async def pointer(self, action: PointerAction, x: float, y: float, button: MouseButton = "left") -> None:
        mouse = self.page.mouse

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
        keyboard = self.page.keyboard

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
        async def act() -> None:
            await self.page.mouse.move(x, y)
            await self.page.mouse.wheel(dx, dy)

        try:
            await self._input(act(), "the wheel turned")
        except PlaywrightError as exc:
            raise BrowserError(f"The page could not be scrolled: {first_line(exc)}") from exc

    async def _input(self, work: Coroutine[Any, Any, None], what: str, *, extra_ms: float = 0) -> None:
        """Sends mouse or keyboard input. The browser answers only once the page has handled it, and a
        page can take as long as it likes: past the action limit, the call fails instead of waiting."""
        limit = self._config.browser.timeouts.action_ms / 1000
        try:
            async with asyncio.timeout(limit + extra_ms / 1000):
                await work
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
