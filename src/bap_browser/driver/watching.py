"""What happens in a browser by itself, and what a person does in it: dialogs, the console and the
network, files, pictures, and the mouse and the keyboard of a person who has taken over.
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import os
from collections.abc import Callable, Coroutine
from typing import Any

from playwright.async_api import (
    ConsoleMessage,
    Dialog,
    Download,
    FileChooser,
    Request,
    Response,
)
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from bap_browser.config import QualityLevel
from bap_browser.driver.base import (
    ConsoleLine,
    DialogKind,
    Happened,
    KeyAction,
    MouseButton,
    NetworkLine,
    PageDialog,
    PointerAction,
    SavedFile,
    Shot,
)
from bap_browser.driver.browser_parts import (
    CONSOLE_LEVELS,
    DIALOG_KINDS,
    OpenDialog,
    OpenTab,
    Taken,
    capped,
    file_name,
    first_line,
    free_path,
)
from bap_browser.driver.core import DriverCore
from bap_browser.driver.screenshots import size_of
from bap_browser.errors import BadInput, BrowserError
from bap_browser.results import Picture


class Watching(DriverCore):
    """Hears what the browser says, keeps what a tool will ask for, and passes a person's own input on."""

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
        taken = Taken(x, y, scale, shown_width, shown_height)
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
        self, tab: OpenTab, clip: dict[str, float] | None, *, full_page: bool, every_pixel: bool
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
        entry = OpenDialog(info, dialog)
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

    async def _expire(self, entry: OpenDialog) -> None:
        """A dialog nobody answers is dismissed, so that a page is not held for ever."""
        wait = self._config.browser.dialogs.timeout_s
        await asyncio.sleep(wait)
        if entry in self._dialogs:
            await self._answer(entry.dialog, False, None)
            self._close_dialog(
                entry, "timed_out", f"{entry.info.named} was dismissed: nobody answered it within {wait} s"
            )

    def _close_dialog(self, entry: OpenDialog, outcome: str, told: str) -> None:
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

    def _on_console(self, tab: OpenTab, message: ConsoleMessage) -> None:
        limit = self._config.browser.capture.max_entry_chars
        tab.console.append(ConsoleLine(CONSOLE_LEVELS.get(message.type, "info"), capped(message.text, limit)))

    def _on_page_error(self, tab: OpenTab, error: Exception) -> None:
        limit = self._config.browser.capture.max_entry_chars
        tab.console.append(ConsoleLine("error", capped(f"Uncaught {first_line(error)}", limit)))

    @staticmethod
    def _on_response(tab: OpenTab, response: Response) -> None:
        request = response.request
        tab.network.append(NetworkLine(request.method, response.status, request.resource_type, request.url))

    @staticmethod
    def _on_request_failed(tab: OpenTab, request: Request) -> None:
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

    def _on_file_chooser(self, tab: OpenTab, chooser: FileChooser) -> None:
        if tab.choosing is not None and not tab.choosing.done():
            tab.choosing.set_result(chooser)
            return
        # Nobody asked for it: a click opened it. It is closed with nothing chosen, and the agent
        # is told how a file is given.
        self._spawn(self._close_chooser(chooser))
        self._tell(
            Happened(
                "file_chooser",
                "a file chooser opened and was closed: give files with browser_upload_file",
            )
        )

    @staticmethod
    async def _close_chooser(chooser: FileChooser) -> None:
        with contextlib.suppress(PlaywrightError):
            await chooser.set_files([])

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

    def _on_picture(self, tab: OpenTab, frame: dict[str, Any]) -> None:
        if self._frames is None or tab is not self._active:
            return
        on_frame, level = self._frames
        on_frame(base64.b64decode(frame["data"]))
        self._spawn(self._acknowledge(tab, frame["sessionId"], level.max_fps))

    async def _acknowledge(self, tab: OpenTab, picture: int, max_fps: int) -> None:
        """The browser sends its next picture only once this one is acknowledged. Waiting here is what
        limits the rate, and the picture that follows is always the newest one."""
        now = asyncio.get_running_loop().time()
        wait = self._next_acknowledgement - now
        self._next_acknowledgement = max(now, self._next_acknowledgement) + 1 / max_fps
        if wait > 0:
            await asyncio.sleep(wait)
        with contextlib.suppress(PlaywrightError):
            await tab.cdp.send("Page.screencastFrameAck", {"sessionId": picture})

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

    async def _wheel(self, tab: OpenTab, x: float, y: float, dx: float, dy: float) -> None:
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
