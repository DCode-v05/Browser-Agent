"""The tools an agent calls. Each handler returns the result text; failures are raised as BapError."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Sequence
from typing import Literal

from pydantic import Field, model_validator

from bap_browser import keys
from bap_browser.driver.base import ActionOutcome, Driver, LoadState, LogLevel, Place, TabInfo
from bap_browser.driver.session import BrowserSession
from bap_browser.errors import BadInput, BapError, BrowserError, PolicyBlocked
from bap_browser.policy.files import allowed_file
from bap_browser.tools.registry import REF_PATTERN, Args, Shown, ToolDefinition

Modifier = Literal["Alt", "Control", "Meta", "Shift"]
# What a person is shown in place of an address that could not be read.
UNREADABLE = "That address"
TAB_PATTERN = r"^t\d+$"
# From the least serious to the most.
LOG_LEVELS: tuple[LogLevel, ...] = ("debug", "info", "warning", "error")


class NavigateArgs(Args):
    url: str


class SnapshotArgs(Args):
    mode: Literal["interactive", "all"] | None = None
    ref: str | None = Field(default=None, pattern=REF_PATTERN)
    max_chars: int | None = Field(default=None, ge=1)
    include_bboxes: bool = False


class NoArgs(Args):
    pass


class PlaceArgs(Args):
    """An element by ref, or a point of the page in pixels from its top left."""

    ref: str | None = Field(default=None, pattern=REF_PATTERN)
    x: float | None = Field(default=None, ge=0)
    y: float | None = Field(default=None, ge=0)

    @property
    def point(self) -> tuple[float, float] | None:
        return (self.x, self.y) if self.x is not None and self.y is not None else None

    @property
    def place(self) -> str:
        """The place as a result names it: the ref, or the point."""
        return self.ref or f"({self.x:g}, {self.y:g})"


def _one_place(args: PlaceArgs, *, required: bool) -> None:
    half_a_point = (args.x is None) != (args.y is None)
    if half_a_point or (args.ref is not None and args.x is not None):
        raise ValueError("give either ref, or both x and y")
    if required and args.ref is None and args.x is None:
        raise ValueError("give ref, or both x and y")


class TargetArgs(PlaceArgs):
    @model_validator(mode="after")
    def _has_one_place(self) -> TargetArgs:
        _one_place(self, required=True)
        return self


class ClickArgs(TargetArgs):
    button: Literal["left", "right", "middle"] = "left"
    click_count: int = Field(default=1, ge=1, le=3)
    # Pydantic copies the default for each call. A plain default, unlike a factory, appears in the schema.
    modifiers: list[Modifier] = Field(default=[])


class TextArgs(Args):
    ref: str | None = Field(default=None, pattern=REF_PATTERN)
    max_chars: int | None = Field(default=None, ge=1)


class FindArgs(Args):
    query: str = Field(min_length=1)
    limit: int | None = Field(default=None, ge=1)


class ScrollArgs(PlaceArgs):
    direction: Literal["up", "down", "left", "right"]
    amount: int = Field(default=1, ge=1, le=20)

    @model_validator(mode="after")
    def _has_at_most_one_place(self) -> ScrollArgs:
        _one_place(self, required=False)
        return self


class RefArgs(Args):
    ref: str = Field(pattern=REF_PATTERN)


class PressKeyArgs(Args):
    keys: str
    repeat: int = Field(default=1, ge=1)
    ref: str | None = Field(default=None, pattern=REF_PATTERN)


class SelectArgs(Args):
    ref: str = Field(pattern=REF_PATTERN)
    values: list[str] = Field(min_length=1)


class CheckArgs(Args):
    ref: str = Field(pattern=REF_PATTERN)
    checked: bool


class FormField(Args):
    ref: str = Field(pattern=REF_PATTERN)
    value: str | bool


class FillFormArgs(Args):
    fields: list[FormField] = Field(min_length=1)


class WaitArgs(Args):
    text: str | None = Field(default=None, min_length=1)
    text_gone: str | None = Field(default=None, min_length=1)
    load_state: LoadState | None = None
    seconds: float | None = Field(default=None, ge=0)
    timeout_s: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def _waits_for_one_thing(self) -> WaitArgs:
        given = [self.text, self.text_gone, self.load_state, self.seconds]
        if sum(value is not None for value in given) != 1:
            raise ValueError("give exactly one of text, text_gone, load_state, seconds")
        return self


class TypeArgs(Args):
    text: str
    ref: str | None = Field(default=None, pattern=REF_PATTERN)
    clear: bool = True
    submit: bool = False
    slowly: bool = False


async def _page(session: BrowserSession, driver: Driver, args: SnapshotArgs | None = None) -> str:
    settings = session.config.browser.snapshot
    args = args or SnapshotArgs()
    return await driver.snapshot(
        mode=args.mode or settings.default_mode,
        ref=args.ref,
        # A call may ask for less than the cap, never for more.
        max_chars=min(args.max_chars or settings.max_chars, settings.max_chars),
        include_bboxes=args.include_bboxes or settings.include_bboxes,
    )


async def _allowed(session: BrowserSession, given: str) -> str:
    """The address to open, when the policy allows it. Only the address the policy judged is handed
    to the browser, never the text as it was given."""
    decision = await session.policy.check(given)
    url = decision.url
    if not decision.allowed:
        shown = session.shown_address(url) if url else ""
        raise PolicyBlocked(
            f"navigation to {shown} blocked: {decision.reason}"
            if shown
            else f"navigation blocked: {decision.reason}",
            url=shown or UNREADABLE,
            # The setting's name is for whoever runs the deployment, not for the person watching.
            reason=decision.reason.split(" (")[0],
        )
    return url


async def navigate(session: BrowserSession, args: NavigateArgs) -> str:
    url = await _allowed(session, args.url)
    driver = await session.driver(may_restart=True)
    text = f"Navigated to {session.shown_address(await driver.navigate(url))}"
    if session.config.browser.snapshot.after_navigation:
        text += "\n" + await _page(session, driver)
    return text


async def snapshot(session: BrowserSession, args: SnapshotArgs) -> str:
    return await _page(session, await session.driver(), args)


async def _after_action(session: BrowserSession, driver: Driver, text: str, outcome: ActionOutcome) -> str:
    if outcome.navigated_to:
        text += f"\nNavigated to {session.shown_address(outcome.navigated_to)}"
    if session.config.browser.snapshot.after_action:
        text += "\n" + await _page(session, driver)
    return text


def _named(place: str, target: str) -> str:
    return f"{place} ({target})" if target else place


async def _moved_to(session: BrowserSession, driver: Driver, address: str | None, nowhere: str) -> str:
    if address is None:
        return nowhere
    text = f"Navigated to {session.shown_address(address)}"
    if session.config.browser.snapshot.after_navigation:
        text += "\n" + await _page(session, driver)
    return text


async def go_back(session: BrowserSession, args: NoArgs) -> str:
    driver = await session.driver()
    return await _moved_to(session, driver, await driver.back(), "No previous page in history.")


async def go_forward(session: BrowserSession, args: NoArgs) -> str:
    driver = await session.driver()
    return await _moved_to(session, driver, await driver.forward(), "No next page in history.")


async def reload(session: BrowserSession, args: NoArgs) -> str:
    driver = await session.driver()
    address = await driver.reload()
    text = f"Reloaded {session.shown_address(address)}"
    if session.config.browser.snapshot.after_navigation:
        text += "\n" + await _page(session, driver)
    return text


async def get_text(session: BrowserSession, args: TextArgs) -> str:
    driver = await session.driver()
    cap = session.config.browser.text.max_chars
    text, more = await driver.text(args.ref, min(args.max_chars or cap, cap))
    if not text:
        return f"{args.ref or 'The page'} has no visible text."
    if more:
        text += f"\n\u2026 {more} more characters not shown. Give a ref to read one part of the page."
    return text


async def find(session: BrowserSession, args: FindArgs) -> str:
    driver = await session.driver()
    settings = session.config.browser.find
    found = await driver.find(args.query, min(args.limit or settings.default_limit, settings.max_limit))
    if not found.lines:
        return "No element matches. Try fewer or other words, or read the page with browser_snapshot."
    shown = len(found.lines)
    count = (
        f"{shown} of {found.total} matches"
        if found.total > shown
        else f"{shown} match{'' if shown == 1 else 'es'}"
    )
    return f"{count}, best first:\n" + "\n".join(found.lines)


async def click(session: BrowserSession, args: ClickArgs) -> str:
    driver = await session.driver()
    if args.ref is not None:
        outcome = await driver.click(
            args.ref, button=args.button, click_count=args.click_count, modifiers=args.modifiers
        )
    else:
        x, y = driver.page_point(*(args.point or (0, 0)))
        outcome = await driver.click_at(
            x, y, button=args.button, click_count=args.click_count, modifiers=args.modifiers
        )
    return await _after_action(session, driver, f"Clicked {_named(args.place, outcome.target)}", outcome)


async def type_text(session: BrowserSession, args: TypeArgs) -> str:
    driver = await session.driver()
    outcome = await driver.type_text(
        args.ref, args.text, clear=args.clear, submit=args.submit, slowly=args.slowly
    )
    text = (
        f"Typed {len(args.text)} characters into {_named(args.ref or 'the focused element', outcome.target)}"
    )
    return await _after_action(session, driver, text, outcome)


async def hover(session: BrowserSession, args: TargetArgs) -> str:
    driver = await session.driver()
    if args.ref is not None:
        outcome = await driver.hover(args.ref)
    else:
        x, y = driver.page_point(*(args.point or (0, 0)))
        outcome = await driver.hover_at(x, y)
    return await _after_action(
        session, driver, f"Hovering over {_named(args.place, outcome.target)}", outcome
    )


async def scroll(session: BrowserSession, args: ScrollArgs) -> str:
    driver = await session.driver()
    distance = args.amount * session.config.browser.input.scroll_step_px
    dx, dy = {"up": (0, -distance), "down": (0, distance), "left": (-distance, 0), "right": (distance, 0)}[
        args.direction
    ]
    at = driver.page_point(*args.point) if args.point else None
    position = await driver.scroll(dx, dy, ref=args.ref, at=at)
    sideways = args.direction in ("left", "right")
    at, of = (position.x, position.width) if sideways else (position.y, position.height)
    where = f" inside {args.ref}" if position.inside and args.ref else ""
    if not position.moved:
        return f"Nothing scrolled {args.direction}{where}. Position {at}px of {of}px."
    return f"Scrolled {args.direction} {args.amount}{where}. Position {at}px of {of}px."


async def scroll_to(session: BrowserSession, args: RefArgs) -> str:
    driver = await session.driver()
    outcome = await driver.scroll_to(args.ref)
    return await _after_action(
        session, driver, f"Scrolled {_named(args.ref, outcome.target)} into view.", outcome
    )


async def press_key(session: BrowserSession, args: PressKeyArgs) -> str:
    most = session.config.browser.input.key_repeat_max
    if args.repeat > most:
        raise BadInput(f"repeat is at most {most}.", reason="too many repeats")
    chord = keys.normalise(args.keys)
    driver = await session.driver()
    outcome = await driver.press_key(chord, repeat=args.repeat, ref=args.ref)
    # A key that types a character is typed text: the result does not repeat it.
    text = "Pressed a character key" if keys.is_typed_text(args.keys) else f"Pressed {chord}"
    if args.repeat > 1:
        text += f" {args.repeat} times"
    if args.ref:
        text += f" on {_named(args.ref, outcome.target)}"
    return await _after_action(session, driver, text, outcome)


async def select_option(session: BrowserSession, args: SelectArgs) -> str:
    driver = await session.driver()
    selected = await driver.select_option(args.ref, args.values)
    chosen = ", ".join(f'"{label}"' for label in selected.labels)
    text = f"Selected {chosen} in {_named(args.ref, selected.target)}"
    return await _after_action(session, driver, text, ActionOutcome(selected.target))


async def set_checked(session: BrowserSession, args: CheckArgs) -> str:
    driver = await session.driver()
    result = await driver.set_checked(args.ref, args.checked)
    state = "checked" if result.checked else "not checked"
    text = f"{args.ref} is now {state}." if result.changed else f"{args.ref} was already {state}."
    return await _after_action(session, driver, text, ActionOutcome(result.target))


async def _fill(driver: Driver, field: FormField) -> str:
    """Fills one field the way its kind is filled. Returns how the result names it."""
    kind = (await driver.locate(field.ref)).kind
    if kind == "check":
        if not isinstance(field.value, bool):
            raise BadInput(
                f"{field.ref} is a checkbox or a radio button: its value is true or false.",
                reason="a checkbox takes true or false",
            )
        await driver.set_checked(field.ref, field.value)
        return f"{field.ref}={'checked' if field.value else 'not checked'}"
    if isinstance(field.value, bool):
        raise BadInput(
            f"{field.ref} is not a checkbox: its value is text.", reason="only a checkbox takes true or false"
        )
    if kind == "select":
        selected = await driver.select_option(field.ref, [field.value])
        return f"{field.ref}={selected.labels[0]}"
    if kind == "text":
        await driver.type_text(field.ref, field.value, clear=True, submit=False, slowly=False)
        # What was typed is not repeated.
        return field.ref
    raise BadInput(
        f"{field.ref} is not a form field. Use browser_click for buttons and links.",
        reason="it is not a form field",
    )


async def fill_form(session: BrowserSession, args: FillFormArgs) -> str:
    driver = await session.driver()
    filled: list[str] = []
    for field in args.fields:
        try:
            filled.append(await _fill(driver, field))
        except BapError as exc:
            done = f"Filled: {', '.join(filled)}. " if filled else ""
            # The fields before this one stay filled, and the agent is told which they are.
            raise BrowserError(f"{done}Stopped at {field.ref}: {exc}", reason=exc.reason) from exc
    return await _after_action(session, driver, f"Filled: {', '.join(filled)}", ActionOutcome(""))


async def wait(session: BrowserSession, args: WaitArgs) -> str:
    most = session.config.browser.timeouts.wait_max_s
    limit = min(args.timeout_s or most, most)
    if args.seconds is not None:
        seconds = min(args.seconds, most)
        await asyncio.sleep(seconds)
        return f"Waited {seconds:g} s."
    driver = await session.driver()
    if args.load_state is not None:
        if await driver.wait_for_load(args.load_state, limit):
            return f"The page reached {args.load_state}."
        raise BrowserError(
            f"The page did not reach {args.load_state} within {limit:g} s. Read it as it is with "
            "browser_snapshot.",
            reason="the wait ran out",
        )
    gone = args.text is None
    wanted = "to go" if gone else "to appear"
    if await driver.wait_for_text(args.text_gone or args.text or "", gone=gone, timeout_s=limit):
        text = "The text is gone." if gone else "The text is on the page."
        return await _after_action(session, driver, text, ActionOutcome(""))
    raise BrowserError(
        f"Waited {limit:g} s for the text {wanted}, and it did not. Read the page with browser_snapshot.",
        reason="the wait ran out",
    )


class RequestHumanArgs(Args):
    reason: str = Field(min_length=1, max_length=300)
    kind: Literal["login", "verification", "payment", "other"] = "other"
    timeout_s: float | None = Field(default=None, gt=0)


async def request_human(session: BrowserSession, args: RequestHumanArgs) -> str:
    if session.ask_person is None:
        raise BrowserError(
            "No person can be asked in this session: it has no viewer. Say in your answer what is needed.",
            reason="nobody is watching",
        )
    most = session.config.control.handoff_timeout_s
    outcome, change = await session.ask_person(args.reason, args.kind, min(args.timeout_s or most, most))
    said = {
        "done": "done: the person did the step.",
        "could_not": "could_not: the person could not do the step. Do not ask again for the same thing; "
        "go on another way or say what is needed.",
        "timed_out": "timed_out: nobody answered in time.",
    }[outcome]
    return f"{said}\n{change}"


class ScreenshotArgs(Args):
    full_page: bool | None = None
    annotate: bool | None = None


async def screenshot(session: BrowserSession, args: ScreenshotArgs) -> Shown:
    settings = session.config.browser.screenshot
    full = settings.full_page if args.full_page is None else args.full_page
    annotate = settings.annotate_by_default if args.annotate is None else args.annotate
    driver = await session.driver()
    # The snapshot comes first: it is what gives each control the ref that is drawn on the picture.
    page = await _page(session, driver, SnapshotArgs(mode="interactive")) if annotate else ""
    shot = await driver.screenshot(full_page=full, annotate=annotate)
    if full:
        text = (
            f"Screenshot of the whole page, {shot.width} by {shot.height} pixels. To click by x and y, "
            "take a screenshot of what the browser shows first."
        )
    else:
        text = (
            f"Screenshot of what the browser shows, {shot.width} by {shot.height} pixels. "
            "x and y of a click are pixels of this picture."
        )
    if annotate:
        text += " Each ref is drawn at its element.\n" + page
    return Shown(text, shot.picture)


class ZoomArgs(Args):
    region: list[float] = Field(min_length=4, max_length=4)


async def zoom(session: BrowserSession, args: ZoomArgs) -> Shown:
    driver = await session.driver()
    x0, y0, x1, y1 = args.region
    shot = await driver.zoom((x0, y0, x1, y1))
    return Shown(
        f"The region ({x0:g}, {y0:g}) to ({x1:g}, {y1:g}) of the last screenshot, "
        f"{shot.width} by {shot.height} pixels.",
        shot.picture,
    )


class DragArgs(Args):
    from_ref: str | None = Field(default=None, pattern=REF_PATTERN)
    from_xy: list[float] | None = Field(default=None, min_length=2, max_length=2)
    to_ref: str | None = Field(default=None, pattern=REF_PATTERN)
    to_xy: list[float] | None = Field(default=None, min_length=2, max_length=2)

    @model_validator(mode="after")
    def _one_start_and_one_end(self) -> DragArgs:
        if (self.from_ref is None) == (self.from_xy is None):
            raise ValueError("give either from_ref or from_xy")
        if (self.to_ref is None) == (self.to_xy is None):
            raise ValueError("give either to_ref or to_xy")
        return self


def _end_of_drag(driver: Driver, ref: str | None, xy: Sequence[float] | None) -> tuple[Place, str]:
    """One end of a drag, for the driver and as the result names it."""
    if ref is not None:
        return ref, ref
    x, y = xy or (0, 0)
    return driver.page_point(x, y), f"({x:g}, {y:g})"


async def drag(session: BrowserSession, args: DragArgs) -> str:
    driver = await session.driver()
    start, start_said = _end_of_drag(driver, args.from_ref, args.from_xy)
    end, end_said = _end_of_drag(driver, args.to_ref, args.to_xy)
    done = await driver.drag(start, end)
    text = f"Dragged from {_named(start_said, done.source)} to {_named(end_said, done.target)}"
    return await _after_action(session, driver, text, ActionOutcome("", done.navigated_to))


class DialogArgs(Args):
    action: Literal["accept", "dismiss"]
    prompt_text: str | None = None


async def handle_dialog(session: BrowserSession, args: DialogArgs) -> str:
    driver = await session.driver()
    dialog = await driver.answer_dialog(args.action == "accept", args.prompt_text)
    done = "Accepted" if args.action == "accept" else "Dismissed"
    if dialog.kind == "beforeunload":
        return f"{done} the dialog that asked whether to leave the page."
    return f"{done} the dialog '{dialog.text}'."


class TabsArgs(Args):
    action: Literal["list", "new", "switch", "close"]
    tab_id: str | None = Field(default=None, pattern=TAB_PATTERN)
    url: str | None = None


def _tab_list(session: BrowserSession, tabs: Sequence[TabInfo]) -> str:
    if not tabs:
        return "No tab is open. browser_navigate opens one."
    limit = session.config.browser.snapshot.max_name_chars
    lines = [
        f"{tab.id}{'*' if tab.active else ''} {tab.title[:limit] or '(no title)'} | "
        f"{session.shown_address(tab.url)}"
        for tab in tabs
    ]
    count = f"{len(tabs)} tab{'' if len(tabs) == 1 else 's'}"
    return f"{count}, the active one marked *:\n" + "\n".join(lines)


async def _the_page_now(session: BrowserSession, driver: Driver) -> str:
    """The snapshot of the tab now active, to follow what was done. Not while a dialog is open: its
    page answers nothing."""
    if not session.config.browser.snapshot.after_navigation or session.pending_dialog() is not None:
        return ""
    return "\n" + await _page(session, driver)


async def tabs(session: BrowserSession, args: TabsArgs) -> str:
    if args.action == "new":
        url = None if args.url is None else await _allowed(session, args.url)
        driver = await session.driver(may_restart=True)
        text = f"Opened tab {await driver.new_tab()}."
        if url is None:
            return text + " It is empty: open a page in it with browser_navigate."
        text += f"\nNavigated to {session.shown_address(await driver.navigate(url))}"
        return text + await _the_page_now(session, driver)
    driver = await session.driver()
    if args.action == "list":
        return _tab_list(session, await driver.tabs())
    if args.action == "switch":
        if args.tab_id is None:
            raise BadInput("Give tab_id: the tab to switch to.", reason="no tab was named")
        await driver.switch_tab(args.tab_id)
        return f"Switched to {args.tab_id}." + await _the_page_now(session, driver)
    closed = await driver.close_tab(args.tab_id)
    active = next((tab.id for tab in await driver.tabs() if tab.active), None)
    if active is None:
        return f"Closed {closed}. No tab is open now: browser_navigate opens one."
    return f"Closed {closed}. {active} is the active tab." + await _the_page_now(session, driver)


class ConsoleArgs(Args):
    level: LogLevel | None = None
    clear: bool = False
    limit: int | None = Field(default=None, ge=1)


def _newest(session: BrowserSession, lines: Sequence[str], limit: int | None, what: str) -> str:
    """The newest lines of a log, oldest first, never more than the cap."""
    most = session.config.browser.capture.read_limit
    shown = lines[-min(limit or most, most) :]
    count = f"{len(shown)} {what}{'' if len(shown) == 1 else 's'}"
    if len(lines) > len(shown):
        count += f", the newest of {len(lines)}"
    return f"{count}, oldest first:\n" + "\n".join(shown)


async def console(session: BrowserSession, args: ConsoleArgs) -> str:
    driver = await session.driver()
    least = LOG_LEVELS.index(args.level or "debug")
    lines = [
        f"[{line.level}] {line.text}"
        for line in driver.console(clear=args.clear)
        if LOG_LEVELS.index(line.level) >= least
    ]
    if not lines:
        return "The console holds no message" + (f" of level {args.level} or above." if args.level else ".")
    return _newest(session, lines, args.limit, "console message")


class NetworkArgs(Args):
    filter: str | None = Field(default=None, min_length=1)
    failed_only: bool = False
    clear: bool = False
    limit: int | None = Field(default=None, ge=1)


async def network(session: BrowserSession, args: NetworkArgs) -> str:
    driver = await session.driver()
    lines: list[str] = []
    for request in driver.network(clear=args.clear):
        failed = request.status is None or request.status >= 400
        if (args.failed_only and not failed) or (args.filter and args.filter not in request.url):
            continue
        status = "failed" if request.status is None else str(request.status)
        why = f" ({request.failure})" if request.failure else ""
        lines.append(
            f"{request.method} {status} [{request.kind}] {session.shown_address(request.url)}{why}"
        )
    if not lines:
        return "No request matches." if args.filter or args.failed_only else "No request has been made."
    return _newest(session, lines, args.limit, "request")


class EvaluateArgs(Args):
    expression: str = Field(min_length=1)


async def evaluate(session: BrowserSession, args: EvaluateArgs) -> str:
    driver = await session.driver()
    value = await driver.evaluate(args.expression)
    if value is None:
        return "The script gave no value."
    try:
        text = json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError):
        text = json.dumps(str(value), ensure_ascii=False)
    cap = session.config.browser.javascript.max_result_chars
    # The first line says what was done. The value is what the page holds, and follows it.
    head = f"The script's value, as JSON ({len(text)} characters):"
    if len(text) > cap:
        return f"{head}\n{text[:cap]}\n\u2026 {len(text) - cap} more characters not shown."
    return f"{head}\n{text}"


class UploadArgs(Args):
    ref: str = Field(pattern=REF_PATTERN)
    paths: list[str] = Field(min_length=1)


async def upload_file(session: BrowserSession, args: UploadArgs) -> str:
    folders = session.config.browser.uploads.allowed_dirs
    files = [allowed_file(folders, path) for path in args.paths]
    driver = await session.driver()
    outcome = await driver.upload(args.ref, [str(file) for file in files])
    names = ", ".join(file.name for file in files)
    text = f"Uploaded {names} via {_named(args.ref, outcome.target)}."
    return await _after_action(session, driver, text, ActionOutcome(outcome.target))


def _size(count: int) -> str:
    """A file's size as a person says it."""
    if count < 1024:
        return f"{count} bytes"
    if count < 1024 * 1024:
        return f"{count / 1024:.0f} KB"
    return f"{count / (1024 * 1024):.1f} MB"


async def downloads(session: BrowserSession, args: NoArgs) -> str:
    driver = await session.driver()
    files = driver.downloads()
    if not files:
        return "No file has been downloaded in this session."
    lines: list[str] = []
    for file in files:
        if file.state == "saved":
            lines.append(f"{file.name} ({_size(file.size)}) saved at {file.path}")
        elif file.state == "downloading":
            lines.append(f"{file.name} is still downloading")
        else:
            lines.append(f"{file.name} failed: {file.reason}")
    return f"{len(files)} download{'' if len(files) == 1 else 's'}:\n" + "\n".join(lines)


TOOLS: tuple[ToolDefinition, ...] = (
    ToolDefinition(
        "browser_navigate",
        "Open a URL in the current tab and return the page snapshot. A URL with no scheme gets https://.",
        NavigateArgs,
        navigate,
    ),
    ToolDefinition("browser_go_back", "Go back one page in history.", NoArgs, go_back),
    ToolDefinition("browser_go_forward", "Go forward one page in history.", NoArgs, go_forward),
    ToolDefinition("browser_reload", "Reload the page.", NoArgs, reload),
    ToolDefinition(
        "browser_snapshot",
        "Read the page as text: one line per element, each with a ref such as e12. "
        "mode 'interactive' (default) lists controls and headings; 'all' adds text and structure. "
        "Give ref to read only that element's subtree.",
        SnapshotArgs,
        snapshot,
    ),
    ToolDefinition(
        "browser_get_text",
        "The visible text of the page, or of one element by ref. No refs: use it to read, not to act.",
        TextArgs,
        get_text,
    ),
    ToolDefinition(
        "browser_find",
        "Find elements by words in their name or text. Returns matching snapshot lines with refs, "
        "best first. Cheaper than a snapshot of a large page.",
        FindArgs,
        find,
    ),
    ToolDefinition(
        "browser_screenshot",
        "A picture of what the browser shows, or of the whole page with full_page. Use it only when "
        "the text of the page is not enough. annotate draws each element's ref on the picture.",
        ScreenshotArgs,
        screenshot,
    ),
    ToolDefinition(
        "browser_zoom",
        "A closer picture of a region [x0, y0, x1, y1] of the last screenshot, in its pixels.",
        ZoomArgs,
        zoom,
    ),
    ToolDefinition(
        "browser_click",
        "Click an element by its ref from the latest snapshot, or a point by x and y in page pixels.",
        ClickArgs,
        click,
    ),
    ToolDefinition(
        "browser_hover",
        "Move the pointer over an element by ref, or to x and y, to open a menu or a tooltip.",
        TargetArgs,
        hover,
    ),
    ToolDefinition(
        "browser_drag",
        "Drag from an element (from_ref) or a point (from_xy: [x, y]) to an element (to_ref) or a "
        "point (to_xy).",
        DragArgs,
        drag,
    ),
    ToolDefinition(
        "browser_type",
        "Type text into an element by ref, or into the focused element when no ref is given. "
        "clear replaces what is there; submit presses Enter afterwards.",
        TypeArgs,
        type_text,
    ),
    ToolDefinition(
        "browser_fill_form",
        "Fill several fields in one call. value is text for a text field, a label or value for a "
        "dropdown, true or false for a checkbox or radio button.",
        FillFormArgs,
        fill_form,
    ),
    ToolDefinition(
        "browser_select_option",
        "Choose options of a dropdown (select element) by label or value.",
        SelectArgs,
        select_option,
    ),
    ToolDefinition(
        "browser_set_checked",
        "Set a checkbox, radio button or switch to checked or not checked.",
        CheckArgs,
        set_checked,
    ),
    ToolDefinition(
        "browser_press_key",
        "Press a key or a chord such as Enter, Escape, ArrowDown or Control+a, on the focused element "
        "or on ref.",
        PressKeyArgs,
        press_key,
    ),
    ToolDefinition(
        "browser_scroll",
        "Scroll by steps. With ref, or x and y, scrolls the box under that place; otherwise the page.",
        ScrollArgs,
        scroll,
    ),
    ToolDefinition("browser_scroll_to", "Scroll an element into view.", RefArgs, scroll_to),
    ToolDefinition(
        "browser_wait",
        "Wait for one of: text to appear, text_gone to disappear, a load_state, or seconds.",
        WaitArgs,
        wait,
    ),
    ToolDefinition(
        "browser_handle_dialog",
        "Answer the alert, confirm or prompt dialog a page has opened: accept or dismiss. "
        "prompt_text is what to enter in a prompt.",
        DialogArgs,
        handle_dialog,
    ),
    ToolDefinition(
        "browser_tabs",
        "List the tabs, open a new one (empty, or on url), switch to one or close one by tab_id.",
        TabsArgs,
        tabs,
    ),
    ToolDefinition(
        "browser_console",
        "The page's console messages and errors, oldest first. level is the least serious to show.",
        ConsoleArgs,
        console,
    ),
    ToolDefinition(
        "browser_network",
        "The requests the page made: method, status, type, address. filter keeps the addresses that "
        "hold that text.",
        NetworkArgs,
        network,
    ),
    ToolDefinition(
        "browser_evaluate",
        "Run a JavaScript expression in the page and return its value as JSON. A person is asked first.",
        EvaluateArgs,
        evaluate,
    ),
    ToolDefinition(
        "browser_upload_file",
        "Give files to a file field, or to the button that opens a file chooser. paths are file names "
        "in the upload folder. A person is asked first.",
        UploadArgs,
        upload_file,
    ),
    ToolDefinition(
        "browser_downloads", "The files downloaded in this session, with size and path.", NoArgs, downloads
    ),
    ToolDefinition(
        "browser_request_human",
        "Ask the person watching to do a step you must not do: a sign-in, a CAPTCHA or other human "
        "check, a code, a payment. Waits until they answer. Never try to solve such a step yourself.",
        RequestHumanArgs,
        request_human,
    ),
)
