"""A name and password written into an address reach no log, no viewer and no result, whatever
shape the address has; and no address, however malformed, can make a watched call fail to answer."""

import json
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import pytest
from fakes import FakeDriver

from bap_browser.config import Config
from bap_browser.driver import BrowserSession
from bap_browser.driver.base import Box, TabInfo
from bap_browser.policy.address import presentable_address
from bap_browser.tools import Toolkit
from bap_browser.tools.sentences import label_for, summary_for


class Seen:
    def __init__(self) -> None:
        self.told: list[Any] = []

    def step_started(self, step: int, tool: str, label: str, target: Box | None) -> None:
        self.told.append(label)

    def step_finished(
        self, step: int, ok: bool, ms: float, chars: int, summary: str, tabs: Sequence[TabInfo]
    ) -> None:
        self.told += [summary, *(tab.url for tab in tabs)]

    def navigation_blocked(self, url: str, reason: str) -> None:
        self.told += [url, reason]


def watched(make_config: Callable[..., Config], folder: Path, **sections: Any) -> tuple[Toolkit, Seen]:
    seen = Seen()
    return Toolkit(BrowserSession(make_config(folder, **sections), FakeDriver()), observer=seen), seen


SECRET = "hunter2"
# Each of these is opened by a browser as a page with the name "admin" and the password "hunter2",
# or is close enough to one that a person might paste it.
ADDRESSES = [
    f"https://admin:{SECRET}@93.184.216.34/login",
    f"admin:{SECRET}@93.184.216.34/login",
    f"   https://admin:{SECRET}@93.184.216.34/  ",
    f"http:/\\admin:{SECRET}@93.184.216.34/x",
    f"HTTPS://admin:{SECRET}@93.184.216.34",
    f"admin:{SECRET}@exa mple.org",
    f"https://admin:{SECRET}@[::1",
    f"https://admin:{SECRET}@exa%2Fmple.org/",
]


@pytest.mark.parametrize("address", ADDRESSES)
async def test_a_password_in_an_address_reaches_nothing_that_is_kept_or_shown(
    make_config, tmp_path: Path, address: str
) -> None:
    tools, seen = watched(make_config, tmp_path, safety={"block_private_networks": True})
    result = await tools.call("browser_navigate", {"url": address})
    log = (tmp_path / "events.jsonl").read_text(encoding="utf-8")
    assert SECRET not in result.text, "the result"
    assert SECRET not in log, "the event log"
    assert SECRET not in json.dumps(seen.told), "what a viewer is told"


@pytest.mark.parametrize("address", ADDRESSES)
def test_a_password_in_an_address_is_in_no_sentence(address: str) -> None:
    arguments = {"url": address}
    for sentence in (
        label_for("browser_navigate", arguments, None),
        summary_for("browser_navigate", arguments, None, None),
        summary_for("browser_navigate", arguments, None, "the site was not found"),
    ):
        assert SECRET not in sentence and "admin" not in sentence, sentence


@pytest.mark.parametrize(
    ("text", "shown"),
    [
        (f"https://admin:{SECRET}@Example.com/a?b=1", "https://example.com/a?b=1"),
        (f"admin:{SECRET}@example.com/login", "https://example.com/login"),
        (f"http:/\\admin:{SECRET}@example.com/x", "http://example.com/x"),
        ("about:blank", "about:blank"),
        (f"admin:{SECRET}@exa mple.org", None),
        ("http://[::1", None),
        ("", None),
    ],
)
def test_an_address_as_it_may_be_shown(text: str, shown: str | None) -> None:
    assert presentable_address(text) == shown


@pytest.mark.parametrize(
    "address",
    ["http://[::1", "http://[", "https://exa mple.org]", "\x00", "http://a:b:c:d/", "[", "http://%zz/"],
)
async def test_a_malformed_address_is_answered_and_reported_like_any_other_call(
    make_config, tmp_path: Path, address: str
) -> None:
    tools, seen = watched(make_config, tmp_path)
    result = await tools.call("browser_navigate", {"url": address})
    assert result.is_error
    assert result.text == "navigation blocked: not a valid address"
    assert seen.told[0] == "Opening a page"
    assert seen.told[-1] == "Could not open a page: not a valid address"
    line = json.loads((tmp_path / "events.jsonl").read_text(encoding="utf-8"))
    assert line["args"] == {"url": "<not a valid address>"}


async def test_a_ref_that_is_not_a_ref_is_never_sent_to_the_page(make_config, tmp_path: Path) -> None:
    driver = FakeDriver()
    located: list[str] = []
    original = driver.locate

    async def locate(ref: str) -> Any:
        located.append(ref)
        return await original(ref)

    driver.locate = locate  # type: ignore[method-assign]
    tools = Toolkit(BrowserSession(make_config(tmp_path), driver), observer=Seen())
    await tools.call("browser_snapshot", {})
    await tools.call("browser_click", {"ref": "x" * 100_000})
    await tools.call("browser_fly", {"ref": "e1"})
    await tools.call("browser_click", {"ref": "e1"})
    assert located == ["e1"]
