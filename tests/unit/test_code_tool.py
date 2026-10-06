"""`browser_run` (spec 7): a script does several steps in one call, in a worker of its own, and every
step goes through the same checks as a single tool call."""

import asyncio
import json
import os
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any

import pytest
from fakes import FakeDriver

from bap_browser.config import Config
from bap_browser.driver.session import BrowserSession
from bap_browser.service.session import ServiceSession
from bap_browser.tools import Toolkit
from bap_browser.tools.toolkit import tools_for

MakeConfig = Callable[..., Config]
ON: dict[str, Any] = {"enabled": True}


class Scripts:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.driver = FakeDriver()
        self.session = BrowserSession(config, self.driver)
        self.tools = Toolkit(self.session)

    async def run(self, code: str, **more: Any) -> Any:
        return await asyncio.wait_for(self.tools.call("browser_run", {"code": code, **more}), 30)

    def did(self) -> list[str]:
        return [call[0] for call in self.driver.calls]

    def logged(self) -> list[dict[str, Any]]:
        log = Path(self.config.logging.event_log or "")
        return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]


Open = Callable[..., Scripts]


@pytest.fixture
async def scripts(make_config: MakeConfig, tmp_path: Path) -> AsyncIterator[Open]:
    opened: list[Scripts] = []

    def open_one(**sections: Any) -> Scripts:
        sections.setdefault("code", ON)
        opened.append(Scripts(make_config(tmp_path, **sections)))
        return opened[-1]

    yield open_one
    for one in opened:
        # Ending the session ends the worker with it.
        await one.session.close()


async def test_it_is_not_offered_until_a_deployment_turns_it_on(
    make_config: MakeConfig, tmp_path: Path
) -> None:
    off = make_config(tmp_path)
    assert "browser_run" not in {tool.name for tool in tools_for(off)}
    session = BrowserSession(off, FakeDriver())
    try:
        refused = await Toolkit(session).call("browser_run", {"code": "1"})
        assert refused.is_error and "Unknown tool 'browser_run'" in refused.text
    finally:
        await session.close()
    assert "browser_run" in {tool.name for tool in tools_for(make_config(tmp_path, code=ON))}


async def test_a_script_does_several_steps_in_one_call(scripts: Open) -> None:
    one = scripts()
    result = await one.run(
        "await browser.navigate('https://example.com/orders')\n"
        "snap = await browser.snapshot(mode='all')\n"
        "await browser.click(find='Go')\n"
        "print(len(snap) > 0)\n"
        "state['visited'] = 1\n"
        "[1, 'two']"
    )
    assert not result.is_error
    lines = result.text.splitlines()
    # What came of it is the first line. What the script printed can hold anything a page says.
    assert lines[0] == "Ran the script: 4 steps."
    assert "Printed:\nTrue" in result.text and 'Value: [1, "two"]' in result.text
    steps = lines[lines.index("Steps (4):") + 1 :][:4]
    assert [step.split(": ")[0] for step in steps] == ["1. ok", "2. ok", "3. ok", "4. ok"]
    assert steps[0] == "1. ok: Navigated to https://example.com/orders"
    # find="…" looks the words up first, and acts on the best match.
    # Opening a page reads it, as the single tool does.
    assert one.did() == ["navigate", "snapshot", "snapshot", "find", "click"]
    assert one.driver.calls[3][0] == "find" and one.driver.calls[3][1]["query"] == "Go"
    assert result.text.rstrip().splitlines()[-1].startswith("[tabs]")
    # What a script keeps is there for the next script of the session.
    assert "Value: 2" in (await one.run("state['visited'] + 1")).text


async def test_each_step_is_logged_as_the_call_it_is_and_the_script_is_never_kept(scripts: Open) -> None:
    one = scripts()
    await one.run(
        "await browser.navigate('https://example.com/')\nawait browser.type(ref='e1', text='hunter2-secret')"
    )
    logged = one.logged()
    assert [line["tool"] for line in logged] == ["browser_navigate", "browser_type", "browser_run"]
    # The script holds what it types. Only how much was typed is ever kept, as for a single call.
    assert logged[-1]["args"] == {"code": "<str>"}
    assert logged[-1]["result"] == "Ran the script: 2 steps."
    assert "hunter2-secret" not in json.dumps(logged)


async def test_a_step_that_fails_stops_the_script_and_says_what_was_done(scripts: Open) -> None:
    one = scripts()
    one.driver.fail_with = None
    result = await one.run(
        "await browser.navigate('https://example.com/')\nawait browser.click(find='no such thing')\nprint('never')"
    )
    assert result.is_error
    assert result.text.splitlines()[0] == (
        'Step 3 failed at line 2 of the script: Nothing on the page matches "no such thing". '
        "Earlier steps were carried out and are not undone."
    )
    assert "never" not in result.text
    # The words were looked up, which is a step of its own, and nothing was clicked.
    assert "1. ok: Navigated to " in result.text and "3. FAILED: Nothing on the page" in result.text
    assert "click" not in one.did()
    # A script that expects the failure goes on.
    caught = await one.run(
        "try:\n    await browser.click(find='no such thing')\nexcept StepError as failed:\n    print('went on')"
    )
    assert not caught.is_error and "went on" in caught.text and "2. FAILED: " in caught.text


async def test_a_script_acts_only_on_a_match_that_holds_every_word(scripts: Open) -> None:
    """`browser_find` also lists what matches in part, for an agent to choose from. A script must not
    act on a guess."""
    one = scripts()
    guess = await one.run("await browser.click(find='Go nowhere')")
    assert guess.is_error and 'Nothing on the page matches "Go nowhere".' in guess.text
    assert "click" not in one.did()
    exact = await one.run("await browser.click(find='go HOME')")
    assert not exact.is_error and one.driver.calls[-1][0] == "click"
    both = await one.run("await browser.click(find='Go', ref='e1')")
    assert both.is_error and "one of the two" in both.text


async def test_a_script_that_reaches_outside_is_not_run(scripts: Open) -> None:
    one = scripts()
    result = await one.run("import os\nawait browser.navigate('https://example.com/')")
    assert result.is_error
    assert result.text.startswith(
        "The script was not run: line 1: a script cannot import; re, json and math are there already."
    )
    assert one.did() == []
    stopped = await one.run("x = [1]\nx[3]")
    assert stopped.is_error and stopped.text.startswith("The script stopped at line 2: IndexError")
    long = await one.run("x = 1\n" * 30_000)
    assert long.is_error and "longer than 20000 characters" in long.text
    assert (await one.tools.call("browser_run", {})).is_error
    assert (await one.tools.call("browser_run", {"code": "1", "timeout_s": 0})).is_error


async def test_a_step_in_a_script_is_checked_like_a_single_call(scripts: Open) -> None:
    one = scripts(safety={"blocked_domains": ["ads.example"], "action_policies": {"browser_click": "deny"}})
    blocked = await one.run("await browser.navigate('https://ads.example/')")
    assert blocked.is_error and "blocked" in blocked.text.splitlines()[0]
    assert one.did() == []
    denied = await one.run("await browser.click(ref='e1')")
    assert denied.is_error and "not allowed on this deployment" in denied.text
    assert one.did() == []
    # A tool the deployment does not offer is no method of `browser`.
    absent = await one.run("await browser.evaluate('1')")
    assert absent.is_error and "has no attribute 'evaluate'" in absent.text
    # And a script cannot run a script.
    nested = await one.run("await browser.run('1')")
    assert nested.is_error and "has no attribute 'run'" in nested.text


async def test_a_script_does_no_more_steps_than_it_may(scripts: Open) -> None:
    one = scripts(code={**ON, "max_steps": 2})
    result = await one.run("for n in range(5):\n    await browser.snapshot()")
    assert result.is_error
    assert "This script has done 2 steps, the most one script may." in result.text
    assert one.did() == ["snapshot", "snapshot"]


async def test_a_script_that_computes_too_long_is_stopped_and_the_next_one_starts_afresh(
    scripts: Open,
) -> None:
    one = scripts()
    assert "Value: 1" in (await one.run("state['kept'] = 1\nstate['kept']")).text
    stopped = await one.run("await browser.snapshot()\nwhile True:\n    x = 1", timeout_s=1)
    assert stopped.is_error
    assert stopped.text.splitlines()[0] == (
        "The script stopped: it computed for longer than 1 s and was stopped. "
        "Earlier steps were carried out and are not undone."
    )
    # The worker was ended. A new one has nothing of what the scripts before it kept, and says so.
    again = await one.run("len(state)")
    assert not again.is_error and "Value: 0" in again.text
    assert "The worker was started again since the last script, so `state` was empty." in again.text
    assert "started again" not in (await one.run("1")).text


async def test_a_script_cannot_flood_the_core(scripts: Open) -> None:
    one = scripts(code={**ON, "max_message_chars": 20_000, "max_output_chars": 2000})
    result = await one.run("await browser.type(ref='e1', text='a' * 100000)")
    assert result.is_error and "handed over more at once than is taken" in result.text
    assert one.did() == []
    # What it prints, and its value, are cut.
    cut = await one.run("print('b' * 50000)\n'c' * 50000")
    assert not cut.is_error and len(cut.text) < 5000 and "[cut" in cut.text
    assert not (await one.run("1")).is_error


async def test_the_worker_is_handed_nothing_of_the_cores(
    scripts: Open, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "a-secret-key")
    monkeypatch.setenv("BAP_BROWSER_TOKEN", "a-secret-token")
    started: list[dict[str, Any]] = []
    start = asyncio.create_subprocess_exec

    async def watched(*command: Any, **how: Any) -> Any:
        started.append({"command": command, **how})
        return await start(*command, **how)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", watched)
    one = scripts()
    assert "Value: 2" in (await one.run("1 + 1")).text
    assert len(started) == 1
    # Isolated, and without the site packages: the worker is the standard library alone.
    assert started[0]["command"][1:3] == ("-I", "-S")
    assert set(started[0]["env"]) <= {"SYSTEMROOT"}
    assert "secret" not in json.dumps(started[0]["env"])
    # The worker is used again, not started for each script.
    await one.run("2")
    assert len(started) == 1
    assert {name for name in os.environ if "SECRET" in name.upper()} == set()


async def test_a_person_pauses_between_two_steps_of_a_script(make_config: MakeConfig, tmp_path: Path) -> None:
    """The script's call holds neither the turn nor the browser: its steps are calls of their own."""
    driver = FakeDriver()
    session = ServiceSession(make_config(tmp_path, code=ON), driver)
    await session.start()
    try:
        script = asyncio.create_task(
            session.toolkit.call(
                "browser_run",
                {
                    "code": "await browser.navigate('https://example.com/')\n"
                    "for n in range(3000000):\n    x = n\n"
                    "await browser.find(query='Go')\n'done'"
                },
            )
        )
        async with asyncio.timeout(10):
            while ("navigate", "https://example.com/") not in driver.calls:
                await asyncio.sleep(0.01)
        # The script is computing. A person's Pause takes hold at once, not when the script ends.
        await asyncio.wait_for(session.handle({"type": "pause"}), 2)
        assert session.control == "paused"
        await asyncio.sleep(0.5)
        assert "find" not in [call[0] for call in driver.calls], "the next step waits for the person"
        await session.handle({"type": "resume"})
        result = await asyncio.wait_for(script, 20)
        assert not result.is_error and 'Value: "done"' in result.text
        # A person watching sees the script, and each step of it, as steps.
        told = [item for item in session.hub.subscribe()[0] if isinstance(item, dict)]
        started = [(event["tool"], event["label"]) for event in told if event["type"] == "step_started"]
        assert started[0] == ("browser_run", "Running a script")
        assert [tool for tool, _ in started[1:]] == ["browser_navigate", "browser_find"]
        assert [event["summary"] for event in told if event["type"] == "step_finished"][
            -1
        ] == "Ran a script: 2 steps"
    finally:
        await session.close()
