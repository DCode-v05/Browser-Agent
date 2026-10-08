"""The driver's core: the browser and its tabs as they are held, the frames of a page, and waiting
for a page to settle after something was done to it.
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import logging
from collections.abc import Awaitable, Callable, Coroutine, Mapping
from pathlib import Path
from typing import Any

from playwright.async_api import (
    Browser,
    BrowserContext,
    CDPSession,
    Frame,
    Page,
    Request,
)
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from bap_browser.address import without_credentials
from bap_browser.config import Config, QualityLevel
from bap_browser.driver.base import (
    Box,
    FileGuard,
    Guard,
    Happened,
    Located,
    SavedFile,
    TabInfo,
)
from bap_browser.driver.browser_parts import (
    FRAME_REF,
    GIVE_A_BOX,
    GIVE_A_POINT,
    NEED_THE_FRAME_IN_VIEW,
    NO_TAB,
    NOT_STARTED,
    InnerFrame,
    OpenDialog,
    OpenTab,
    capped,
    frame_ids,
    retrieved,
    told_refused,
)
from bap_browser.driver.page_script import PageScript
from bap_browser.driver.screenshots import size_of
from bap_browser.errors import BadInput, BrowserError, StaleRef
from bap_browser.results import Picture

logger = logging.getLogger(__name__)


class DriverCore:
    """What every other part of the driver builds on. It starts nothing and acts on nothing by itself."""

    def __init__(self, config: Config, *, cdp_headers: Mapping[str, str] | None = None) -> None:
        """`cdp_headers` go with the request that attaches to a running browser (`browser.cdp_url`),
        for one that asks who is attaching."""
        self._config = config
        self._cdp_headers = dict(cdp_headers or {})
        self._stack = contextlib.AsyncExitStack()
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._version = ""
        self._tabs: dict[str, OpenTab] = {}
        self._active: OpenTab | None = None
        # Tab ids are never used twice in a session, and neither are refs, in any tab.
        self._tab_count = 0
        self._next_ref = 1
        self._next_frame = 1
        self._frames: tuple[Callable[[bytes], None], QualityLevel] | None = None
        self._next_acknowledgement = 0.0
        self._tasks: set[asyncio.Task[Any]] = set()
        self._on_event: Callable[[Happened], None] | None = None
        self._guard: Guard | None = None
        self._judge_file: FileGuard | None = None
        # The dialogs that wait for an answer, oldest first.
        self._dialogs: list[OpenDialog] = []
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
        self._pictured: OpenTab | None = None

    def guard(self, judge: Guard) -> None:
        self._guard = judge

    def guard_files(self, judge: FileGuard) -> None:
        self._judge_file = judge

    def _what_to_locate(self, *, press: bool) -> dict[str, Any]:
        return {
            "press": press,
            "maxName": self._config.browser.snapshot.max_name_chars,
            "maxAround": self._config.safeguards.money.around_chars,
        }

    @staticmethod
    def _located(found: dict[str, Any]) -> Located:
        box = Box(*found["box"]) if found["box"] else None
        return Located(
            found["role"],
            found["name"],
            box,
            found["secret"],
            found["kind"],
            document=found.get("document", ""),
            input_type=found.get("inputType", ""),
            autocomplete=found.get("autocomplete", ""),
            attributes=tuple(found.get("attributes", ())),
            dots=bool(found.get("dots", False)),
            multiline=bool(found.get("multiline", False)),
            search=bool(found.get("search", False)),
            sends_form=tuple(
                (str(role), str(name), bool(multiline), bool(search))
                for role, name, multiline, search in found.get("sendsForm", ())
            ),
            around=tuple(found.get("around", ())),
        )

    def _unseen_limits(self) -> dict[str, Any] | None:
        """What the page script is told about text nobody can see, or None when it is not looked for."""
        incoming = self._config.safeguards.incoming
        if not incoming.unseen_text:
            return None
        return {
            "minOpacity": incoming.min_opacity,
            "minFontPx": incoming.min_font_px,
            "minContrast": incoming.min_contrast,
            "contrast": incoming.contrast,
            "screenReaderChars": incoming.screen_reader_max_chars,
        }

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

    def _current(self) -> OpenTab:
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
        # A file nobody said yes to does not outlive the session.
        for place, file in enumerate(self._downloads):
            if file.state == "held":
                try:
                    await asyncio.to_thread(Path(file.path).unlink, True)
                except OSError:
                    logger.warning("A downloaded file that was not kept could not be deleted.")
                self._downloads[place] = SavedFile(file.name, "failed", reason="the session ended")
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

    def _tab_of(self, page: Page) -> OpenTab | None:
        return next((tab for tab in self._tabs.values() if tab.page is page), None)

    def _tab(self, tab_id: str) -> OpenTab:
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

    async def _read_title(self, tab: OpenTab) -> None:
        """A page with a dialog open answers nothing, so it is not asked: its last title stands."""
        try:
            async with asyncio.timeout(self._config.browser.timeouts.page_reply_ms / 1000):
                tab.title = await tab.page.title()
        except (PlaywrightError, TimeoutError):
            tab.title = ""

    def _window_opening(self) -> None:
        if self._early:
            self._early -= 1
        else:
            self._opening += 1

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

    async def _viewport(self, tab: OpenTab) -> tuple[int, int]:
        size = tab.page.viewport_size
        if size is None:
            # No fixed size was asked for: the page is as large as its window.
            size = await tab.page.evaluate("({ width: innerWidth, height: innerHeight })")
        return size["width"], size["height"]

    async def _judge_request(self, tab: OpenTab, paused: dict[str, Any]) -> None:
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
        self._tell(told_refused(shown, reason, " in a frame" if in_frame else ""))

    async def _closed_as_refused(self, tab: OpenTab) -> bool:
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

    def _frame_of(self, tab: OpenTab, ref: str | None) -> InnerFrame | None:
        """The frame a ref is in. None for an element of the page itself."""
        named = FRAME_REF.fullmatch(ref) if ref else None
        if named is None:
            return None
        frame = tab.frames.get(named.group(1))
        if frame is None:
            raise StaleRef(ref or "")
        return frame

    async def _ask(self, tab: OpenTab, operation: str, arguments: dict[str, Any], *, wait_ms: int = 0) -> Any:
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

    async def _where(self, tab: OpenTab, frame: InnerFrame, ref: str, *, bring: bool) -> tuple[float, float]:
        """How far the page inside a frame is from the top left of what the browser shows."""
        chain: list[InnerFrame] = []
        at: InnerFrame | None = frame
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

    async def _frame_under(self, tab: OpenTab, parent: InnerFrame | None, owner: str) -> InnerFrame | None:
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
        frame = tab.frames[name] = InnerFrame(name, script, reached, owner, parent)
        return frame

    async def _session_for(self, tab: OpenTab, session: CDPSession, frame_id: str) -> CDPSession | None:
        """The DevTools session that reaches a frame: the one of the document around it, or the
        frame's own when the browser keeps it in another process."""
        try:
            tree = await session.send("Page.getFrameTree")
        except PlaywrightError:
            return None
        if frame_id in frame_ids(tree["frameTree"]):
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

    async def _fitted(self, tab: OpenTab, picture: Picture) -> tuple[Picture, tuple[int, int]]:
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
                "piece": settings.shrink_piece_bytes,
            },
            wait_ms=self._config.browser.timeouts.action_ms,
        )
        return Picture(base64.b64decode(smaller["data"]), picture.mime), (width, height)

    def page_point(self, x: float, y: float) -> tuple[float, float]:
        pixel = self._active.pixel if self._active else 1.0
        return x * pixel, y * pixel

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
                task.add_done_callback(retrieved)

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

    async def _settle(self, tab: OpenTab, navigations_before: int, commits_before: int) -> str | None:
        """Waits for a navigation the action started, and for a window it opened. Returns the new
        address of the tab, or None if it went nowhere."""
        timeouts = self._config.browser.timeouts
        # The page is given its turn to do what the action set going. It says at once when it sets
        # out for another page or opens a window, and what it says arrives here before the answer
        # to this question does: so nothing has to be waited for that is not happening (spec 11.3).
        document_alive = await tab.script.turn_passed()
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

    async def _wait_for_commit(self, tab: OpenTab, commits_before: int, timeout_ms: int) -> None:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout_ms / 1000
        while tab.commits == commits_before:
            tab.committed.clear()
            remaining = deadline - loop.time()
            if remaining <= 0:
                return
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(tab.committed.wait(), remaining)

    async def _wait_for_load(self, tab: OpenTab) -> None:
        # Some pages never fire the load event. The wait has a ceiling, and reaching it is not a failure.
        with contextlib.suppress(PlaywrightTimeoutError):
            await tab.page.wait_for_load_state("load", timeout=self._config.browser.timeouts.load_wait_ms)

    @staticmethod
    def _on_leaving(tab: OpenTab, asked: dict[str, Any]) -> None:
        """The page has set out for another page in this tab: a link, a form, a script."""
        if (
            asked.get("frameId") == tab.main_frame_id
            and asked.get("disposition", "currentTab") == "currentTab"
        ):
            tab.navigations += 1

    @staticmethod
    def _on_request(tab: OpenTab, request: Request) -> None:
        if request.is_navigation_request() and request.frame == tab.page.main_frame:
            tab.navigations += 1

    @staticmethod
    def _on_frame_navigated(tab: OpenTab, frame: Frame) -> None:
        if frame == tab.page.main_frame:
            tab.commits += 1
            tab.committed.set()
            # Another document: its frames are other frames.
            tab.frames.clear()
        # A frame that went to another site may have moved to another process, or back.
        tab.apart.pop(frame, None)
