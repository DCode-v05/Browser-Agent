"""What is timed for each line of the budget (spec 11.3): one tool call, through the tool layer, against
small pages that ship with the bench.

A line with no scenario here is reported as not run. It is never left out and never counted as passing.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from bap_browser.agent.models import ref_of
from bap_browser.results import ToolResult
from bap_browser.tools import Toolkit


class ScenarioFailed(Exception):
    """A call the scenario needs did not work, so its time means nothing."""


@dataclass
class Stage:
    """Where a scenario plays: the tools, the address of the bench's pages, and what it remembers."""

    tools: Toolkit
    site: str
    kept: dict[str, Any]

    async def call(self, name: str, arguments: dict[str, Any] | None = None) -> ToolResult:
        result = await self.tools.call(name, arguments or {})
        if result.is_error:
            raise ScenarioFailed(f"{name}: {result.text.splitlines()[0]}")
        return result

    async def open(self, page: str) -> str:
        return (await self.call("browser_navigate", {"url": f"{self.site}/{page}"})).text

    def ref(self, page: str, element: str) -> str:
        found = ref_of(page, element)
        if not found:
            raise ScenarioFailed(f"{element} is not on the page")
        return found


Step = Callable[[Stage], Awaitable[Any]]


async def _nothing(stage: Stage) -> None:
    return None


@dataclass(frozen=True)
class Scenario:
    timed: Step
    """The one call whose time is the line's."""
    once: Step = _nothing
    """Before the first run."""
    before: Step = _nothing
    """Before each run, not timed."""
    after: Step = _nothing
    """After each run, not timed."""
    share: int = 1
    """The timed call does this many of the thing the line is about: its time is divided by it."""


def _on(page: str, element: str, key: str = "ref") -> Step:
    """Opens a page and keeps the ref of one of its elements."""

    async def once(stage: Stage) -> None:
        stage.kept[key] = stage.ref(await stage.open(page), element)

    return once


def _call(name: str, arguments: Callable[[Stage], dict[str, Any]] | dict[str, Any] | None = None) -> Step:
    async def timed(stage: Stage) -> None:
        await stage.call(name, arguments(stage) if callable(arguments) else arguments)

    return timed


def _open(page: str) -> Step:
    async def once(stage: Stage) -> None:
        await stage.open(page)

    return once


async def _two_pages(stage: Stage) -> None:
    await stage.open("form.html")
    await stage.open("other.html")


async def _two_pages_and_back(stage: Stage) -> None:
    await _two_pages(stage)
    await stage.call("browser_go_back")


async def _screenshot(stage: Stage) -> None:
    await stage.open("form.html")
    await stage.call("browser_screenshot")


async def _four_fields(stage: Stage) -> None:
    page = await stage.open("form.html")
    stage.kept["fields"] = [
        {"ref": stage.ref(page, f'textbox "{label}"'), "value": value}
        for label, value in (
            ("Full name", "Ada Lovelace"),
            ("Email", "ada@example.com"),
            ("City", "London"),
            ("Phone", "020 7946 0000"),
        )
    ]


async def _flip(stage: Stage) -> None:
    stage.kept["checked"] = not stage.kept.get("checked", False)


async def _turn(stage: Stage) -> None:
    stage.kept["direction"] = "up" if stage.kept.get("direction") == "down" else "down"


async def _a_second_tab(stage: Stage) -> None:
    await stage.open("form.html")
    await stage.call("browser_tabs", {"action": "new"})
    stage.kept["other"] = "t1"


async def _other_tab(stage: Stage) -> None:
    listed = (await stage.call("browser_tabs", {"action": "list"})).text.splitlines()
    waiting = [line.split()[0] for line in listed[1:] if line.startswith("t") and "*" not in line.split()[0]]
    if not waiting:
        raise ScenarioFailed("there is no second tab")
    stage.kept["other"] = waiting[0]


async def _open_a_tab(stage: Stage) -> None:
    await stage.call("browser_tabs", {"action": "new"})


async def _close_the_tab(stage: Stage) -> None:
    await stage.call("browser_tabs", {"action": "close"})


SCENARIOS: dict[str, Scenario] = {
    "navigate.small": Scenario(_call("browser_navigate", lambda stage: {"url": f"{stage.site}/form.html"})),
    "go_back": Scenario(_call("browser_go_back"), before=_two_pages),
    "go_forward": Scenario(_call("browser_go_forward"), before=_two_pages_and_back),
    "reload": Scenario(_call("browser_reload"), once=_open("form.html")),
    "snapshot.small": Scenario(_call("browser_snapshot"), once=_open("form.html")),
    "get_text.small": Scenario(_call("browser_get_text"), once=_open("form.html")),
    "find.small": Scenario(_call("browser_find", {"query": "email"}), once=_open("form.html")),
    "screenshot.visible": Scenario(_call("browser_screenshot"), once=_open("form.html")),
    "screenshot.full": Scenario(_call("browser_screenshot", {"full_page": True}), once=_open("tall.html")),
    "screenshot.labels": Scenario(_call("browser_screenshot", {"annotate": True}), once=_open("form.html")),
    "zoom.region": Scenario(_call("browser_zoom", {"region": [0, 0, 400, 200]}), once=_screenshot),
    "click.ref.small": Scenario(
        _call("browser_click", lambda stage: {"ref": stage.kept["ref"]}),
        once=_on("form.html", 'button "Save"'),
    ),
    "click.ref.big": Scenario(
        _call("browser_click", lambda stage: {"ref": stage.kept["ref"]}),
        once=_on("big.html", 'button "Item 3"'),
    ),
    "click.point": Scenario(_call("browser_click", {"x": 600, "y": 20}), once=_open("form.html")),
    "hover.ref": Scenario(
        _call("browser_hover", lambda stage: {"ref": stage.kept["ref"]}),
        once=_on("form.html", 'button "Save"'),
    ),
    "type.small": Scenario(
        _call("browser_type", lambda stage: {"ref": stage.kept["ref"], "text": "Ada Lovelace"}),
        once=_on("form.html", 'textbox "Full name"'),
    ),
    "type.big": Scenario(
        _call("browser_type", lambda stage: {"ref": stage.kept["ref"], "text": "Ada Lovelace"}),
        once=_on("big.html", 'textbox "Note"'),
    ),
    "fill_form.per_field": Scenario(
        _call("browser_fill_form", lambda stage: {"fields": stage.kept["fields"]}), once=_four_fields, share=4
    ),
    "select_option": Scenario(
        _call("browser_select_option", lambda stage: {"ref": stage.kept["ref"], "values": ["India"]}),
        once=_on("form.html", 'combobox "Country"'),
    ),
    "set_checked": Scenario(
        _call(
            "browser_set_checked", lambda stage: {"ref": stage.kept["ref"], "checked": stage.kept["checked"]}
        ),
        once=_on("form.html", 'checkbox "I accept the terms"'),
        before=_flip,
    ),
    "press_key.small": Scenario(_call("browser_press_key", {"keys": "ArrowDown"}), once=_open("form.html")),
    "press_key.big": Scenario(_call("browser_press_key", {"keys": "ArrowDown"}), once=_open("big.html")),
    "scroll.step": Scenario(
        _call("browser_scroll", lambda stage: {"direction": stage.kept["direction"]}),
        once=_open("tall.html"),
        before=_turn,
    ),
    "scroll_to.far": Scenario(
        _call("browser_scroll_to", lambda stage: {"ref": stage.kept["ref"]}),
        before=_on("tall.html", 'button "Far below"'),
    ),
    "wait.true": Scenario(_call("browser_wait", {"text": "The form is ready."}), once=_open("form.html")),
    "tabs.list": Scenario(_call("browser_tabs", {"action": "list"}), once=_open("form.html")),
    "tabs.new": Scenario(
        _call("browser_tabs", {"action": "new"}), once=_open("form.html"), after=_close_the_tab
    ),
    "tabs.switch": Scenario(
        _call("browser_tabs", lambda stage: {"action": "switch", "tab_id": stage.kept["other"]}),
        once=_a_second_tab,
        before=_other_tab,
    ),
    "tabs.close": Scenario(
        _call("browser_tabs", {"action": "close"}), once=_open("form.html"), before=_open_a_tab
    ),
    "console.read": Scenario(_call("browser_console"), once=_open("form.html")),
    "network.read": Scenario(_call("browser_network"), once=_open("form.html")),
    "downloads.list": Scenario(_call("browser_downloads"), once=_open("form.html")),
}
