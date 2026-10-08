"""What an agent does on a page: reading it, finding an element by its ref, clicking, typing,
scrolling, choosing, dragging, and waiting for what it did to show.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Callable, Coroutine, Sequence
from typing import Any

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import (
    FileChooser,
)
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from bap_browser.driver.base import (
    ActionOutcome,
    Box,
    Checked,
    Dragged,
    Found,
    LoadState,
    Located,
    MouseButton,
    Place,
    ScrollPosition,
    Selected,
)
from bap_browser.driver.browser_parts import (
    InnerFrame,
    OpenTab,
    first_line,
    load_failure,
)
from bap_browser.driver.snapshot import NOTICE, WHOLE_PAGE, matching_lines, snapshot_arguments
from bap_browser.driver.watching import Watching
from bap_browser.errors import BadInput, BrowserError, StaleRef


class Acting(Watching):
    """The actions of the tools (spec 5), each on the tab that is active."""

    async def locate(self, ref: str) -> Located:
        return await self._locate(self._current(), ref)

    async def _locate(self, tab: OpenTab, ref: str) -> Located:
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
        tab: OpenTab,
        frame: InnerFrame | None,
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

    async def click(
        self, ref: str, *, button: MouseButton = "left", click_count: int = 1, modifiers: Sequence[str] = ()
    ) -> ActionOutcome:
        return await self._click_ref(self._current(), ref, button, click_count, modifiers)

    async def _click_ref(
        self, tab: OpenTab, ref: str, button: MouseButton, click_count: int, modifiers: Sequence[str]
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

    async def _point_under_pointer(self, tab: OpenTab, ref: str) -> dict[str, Any]:
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

    async def _prepare(self, tab: OpenTab, ref: str) -> dict[str, Any]:
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
        tab: OpenTab,
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

    async def _describe_at(self, tab: OpenTab, x: float, y: float) -> str:
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
        self, tab: OpenTab, move: Callable[..., Coroutine[Any, Any, Any]], what: str
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
        await tab.script.frames_passed(
            self._config.browser.timeouts.settle_frames, self._config.browser.timeouts.frame_ms
        )
        return ActionOutcome(point["describe"])

    async def hover_at(self, x: float, y: float) -> ActionOutcome:
        tab = self._current()
        described = await self._describe_at(tab, x, y)
        await self._move_to(tab, x, y)
        await tab.script.frames_passed(
            self._config.browser.timeouts.settle_frames, self._config.browser.timeouts.frame_ms
        )
        return ActionOutcome(described)

    async def _move_to(self, tab: OpenTab, x: float, y: float) -> None:
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

    async def _scrolled(self, tab: OpenTab, ref: str | None, *, wait: bool) -> dict[str, Any]:
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

    async def _checkable(self, tab: OpenTab, ref: str) -> dict[str, Any]:
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

    async def upload(self, ref: str, paths: Sequence[str]) -> ActionOutcome:
        tab = self._current()
        point = await self._point_under_pointer(tab, ref)
        described = point["describe"]
        waiting: asyncio.Future[FileChooser] = asyncio.get_running_loop().create_future()
        tab.choosing = waiting
        try:
            # The element is clicked as a person would click it, and the file chooser that opens is
            # given the files. No chooser is ever shown on a screen.
            await self._click(tab, point["x"], point["y"], ref, "left", 1, ())
            chooser = await asyncio.wait_for(waiting, self._config.browser.timeouts.settle_ms / 1000)
        except TimeoutError:
            raise BadInput(
                f"Clicked {ref} ({described}) and no file chooser opened. Give the ref of a file field, "
                "or of the button that opens the file chooser.",
                reason="no file chooser opened",
            ) from None
        finally:
            tab.choosing = None
        if len(paths) > 1 and not chooser.is_multiple():
            # The chooser is closed with nothing chosen: one left open would keep the next from opening.
            with contextlib.suppress(PlaywrightError):
                await chooser.set_files([])
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
