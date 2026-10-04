"""The tools an agent calls. Each handler returns the result text; failures are raised as BapError."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from bap_browser.driver.base import Driver
from bap_browser.driver.session import BrowserSession
from bap_browser.errors import PolicyBlocked
from bap_browser.tools.registry import REF_PATTERN, Args, ToolDefinition

Modifier = Literal["Alt", "Control", "Meta", "Shift"]


class NavigateArgs(Args):
    url: str


class SnapshotArgs(Args):
    mode: Literal["interactive", "all"] | None = None
    ref: str | None = Field(default=None, pattern=REF_PATTERN)
    max_chars: int | None = Field(default=None, ge=1)
    include_bboxes: bool = False


class ClickArgs(Args):
    ref: str = Field(pattern=REF_PATTERN)
    button: Literal["left", "right", "middle"] = "left"
    click_count: int = Field(default=1, ge=1, le=3)
    # Pydantic copies the default for each call. A plain default, unlike a factory, appears in the schema.
    modifiers: list[Modifier] = Field(default=[])


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


async def navigate(session: BrowserSession, args: NavigateArgs) -> str:
    decision = await session.policy.check(args.url)
    # Only the address the policy judged is handed to the browser, never the text as it was given.
    url = decision.url
    if not decision.allowed:
        shown = session.shown_address(url)
        raise PolicyBlocked(
            f"navigation to {shown} blocked: {decision.reason}",
            url=shown,
            # The setting's name is for whoever runs the deployment, not for the person watching.
            reason=decision.reason.split(" (")[0],
        )
    driver = await session.driver(may_restart=True)
    text = f"Navigated to {session.shown_address(await driver.navigate(url))}"
    if session.config.browser.snapshot.after_navigation:
        text += "\n" + await _page(session, driver)
    return text


async def snapshot(session: BrowserSession, args: SnapshotArgs) -> str:
    return await _page(session, await session.driver(), args)


async def click(session: BrowserSession, args: ClickArgs) -> str:
    driver = await session.driver()
    outcome = await driver.click(
        args.ref, button=args.button, click_count=args.click_count, modifiers=args.modifiers
    )
    text = f"Clicked {args.ref} ({outcome.target})"
    if outcome.navigated_to:
        text += f"\nNavigated to {session.shown_address(outcome.navigated_to)}"
    if session.config.browser.snapshot.after_action:
        text += "\n" + await _page(session, driver)
    return text


async def type_text(session: BrowserSession, args: TypeArgs) -> str:
    driver = await session.driver()
    outcome = await driver.type_text(
        args.ref, args.text, clear=args.clear, submit=args.submit, slowly=args.slowly
    )
    text = f"Typed {len(args.text)} characters into {args.ref or 'the focused element'} ({outcome.target})"
    if outcome.navigated_to:
        text += f"\nNavigated to {session.shown_address(outcome.navigated_to)}"
    if session.config.browser.snapshot.after_action:
        text += "\n" + await _page(session, driver)
    return text


TOOLS: tuple[ToolDefinition, ...] = (
    ToolDefinition(
        "browser_navigate",
        "Open a URL in the current tab and return the page snapshot. A URL with no scheme gets https://.",
        NavigateArgs,
        navigate,
    ),
    ToolDefinition(
        "browser_snapshot",
        "Read the page as text: one line per element, each with a ref such as e12. "
        "mode 'interactive' (default) lists controls and headings; 'all' adds text and structure. "
        "Give ref to read only that element's subtree.",
        SnapshotArgs,
        snapshot,
    ),
    ToolDefinition(
        "browser_click",
        "Click an element by its ref from the latest snapshot.",
        ClickArgs,
        click,
    ),
    ToolDefinition(
        "browser_type",
        "Type text into an element by ref, or into the focused element when no ref is given. "
        "clear replaces what is there; submit presses Enter afterwards.",
        TypeArgs,
        type_text,
    ),
)
