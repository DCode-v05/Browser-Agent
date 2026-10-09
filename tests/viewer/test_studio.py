"""The window of three pages in a real browser (spec 9.16): the cloud browser, the person's own Chrome
and the built-in browser, each with its own session; the pop-up that asks a person to do a step; and
a new session on a page whose session was stopped."""

import asyncio
import json
import urllib.error
import urllib.request
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from playwright.async_api import Browser, Locator, Page, async_playwright

from bap_browser import browser_extension
from bap_browser.agent.models import Reply, ScriptedModel, ToolCall
from bap_browser.agent.studio import run_studio
from bap_browser.config import Config

ASK = ToolCall("a", "browser_request_human", {"reason": "Sign in to Northfield for me", "kind": "login"})


def asks_then_answers() -> ScriptedModel:
    """An agent that asks the person to sign in, and says so when they have."""
    return ScriptedModel([lambda page: Reply("", (ASK,)), lambda page: Reply("You are signed in.")])


@dataclass
class Window:
    viewer: str
    token: str
    folder: Path
    page: Page
    running: asyncio.Task[None]

    @property
    def service(self) -> str:
        return self.viewer.split("/#")[0]

    def rooms(self) -> list[dict[str, Any]]:
        asked = urllib.request.Request(
            f"{self.service}/api/sessions", headers={"Authorization": f"Bearer {self.token}"}
        )
        with urllib.request.urlopen(asked, timeout=10) as answer:
            return json.loads(answer.read())["rooms"]

    def _ask(self, method: str, path: str, body: Any) -> tuple[int, Any]:
        data = None if body is None else json.dumps(body).encode()
        asked = urllib.request.Request(
            f"{self.service}{path}",
            data=data,
            headers={"Authorization": f"Bearer {self.token}"},
            method=method,
        )
        try:
            with urllib.request.urlopen(asked, timeout=60) as answer:
                return answer.status, json.loads(answer.read())
        except urllib.error.HTTPError as refused:
            return refused.code, json.loads(refused.read() or b"null")

    async def ask(self, method: str, path: str, body: Any = None) -> tuple[int, Any]:
        """Asks the service, from another thread: it answers on this one."""
        return await asyncio.to_thread(self._ask, method, path, body)

    async def room(self, name: str, state: str) -> dict[str, Any]:
        """Waits until a page of the window is in a state, and gives what the service says of it."""
        async with asyncio.timeout(30):
            while True:
                # A window whose service has stopped says why, instead of being asked for ever.
                assert not self.running.done(), self.running.exception()
                found = next(room for room in await asyncio.to_thread(self.rooms) if room["id"] == name)
                if found["state"] == state:
                    return found
                await asyncio.sleep(0.1)

    async def open(self, tab: str) -> None:
        await self.page.get_by_role("tab", name=tab).click()

    async def tab(self, tab: str) -> str:
        return " ".join((await self.page.get_by_role("tab", name=tab).inner_text()).split())


@asynccontextmanager
async def window(
    make_config: Callable[..., Config], tmp_path: Path, browser: Browser, model: Callable[[], Any]
) -> AsyncIterator[Window]:
    folder = browser_extension.install(tmp_path / "state" / "extension")
    # The file that says where the service is stays in the test's own folder, apart from a service
    # the developer may have running.
    config = make_config(tmp_path, server={"state_file": str(tmp_path / "service.json")})
    running = asyncio.create_task(
        run_studio(config, lambda service: model(), open_viewer=False, extension=folder)
    )
    state = Path(config.server.state_file)
    try:
        async with asyncio.timeout(30):
            while not state.exists():
                assert not running.done(), running.exception()
                await asyncio.sleep(0.05)
        viewer = json.loads(state.read_text(encoding="utf-8"))["viewer"]
        page = await browser.new_page(viewport={"width": 1360, "height": 850})
        opened = Window(viewer, viewer.split("#token=")[1], folder, page, running)
        await opened.room("cloud", "agent")
        await opened.room("builtin", "agent")
        await page.goto(viewer)
        await page.get_by_role("tablist", name="Where the agent works").wait_for()
        yield opened
        await page.close()
    finally:
        running.cancel()
        await asyncio.gather(running, return_exceptions=True)


async def test_the_window_has_a_page_for_each_browser(
    make_config: Callable[..., Config], tmp_path: Path, browser: Browser
) -> None:
    async with window(make_config, tmp_path, browser, lambda: ScriptedModel([])) as opened:
        # Asked from another thread: the service answers on this one.
        rooms = await asyncio.to_thread(opened.rooms)
        assert [(room["id"], room["backend"]) for room in rooms] == [
            ("cloud", "remote_headless"),
            ("chrome", "takeover_chrome"),
            ("builtin", "bundled_chromium"),
            ("computer", "contained_desktop"),
        ]
        # The person's own Chrome is not there until its extension dials in.
        assert rooms[1]["state"] == "waiting" and rooms[1]["extension"] == str(opened.folder)
        page = opened.page
        assert [
            " ".join((await tab.inner_text()).split()) for tab in await page.locator(".studio-tab").all()
        ] == [
            "Cloud browser Ready",
            "My Chrome Not connected",
            "Built-in browser Ready",
            "Computer Could not start",
        ]
        # The cloud browser's page: its picture, and its own chat.
        await page.get_by_label("Your task").wait_for()
        await page.get_by_role("img", name="Live browser view: BAP Browser,").wait_for()
        assert await page.get_by_title("Session", exact=True).inner_text() == "Session\ncloud"

        await opened.open("My Chrome")
        await page.get_by_role("heading", name="Connect your Chrome").wait_for()
        assert await page.locator(".studio-folder code").inner_text() == str(opened.folder)
        assert await page.get_by_label("Your task").count() == 0

        # The built-in browser is another browser with another session, and keeps its sign-ins.
        await opened.open("Built-in browser")
        await page.get_by_label("Your task").wait_for()
        assert await page.get_by_title("Session", exact=True).inner_text() == "Session\nbuiltin"
        assert (tmp_path / "built-in-browser").is_dir(), "the built-in browser keeps a profile of its own"

        # Computer use: a desktop and no browser. Here there is no program to run it, and it says what to do.
        await opened.open("Computer")
        await page.get_by_role("heading", name="The desktop could not be started").wait_for()
        assert "Install Docker" in await page.locator(".studio-wait-lead").inner_text()
        assert await page.evaluate("document.documentElement.scrollWidth <= innerWidth")


async def test_a_page_that_needs_a_person_pops_up_and_says_so_on_its_tab(
    make_config: Callable[..., Config], tmp_path: Path, browser: Browser
) -> None:
    async with window(make_config, tmp_path, browser, asks_then_answers) as opened:
        page = opened.page
        await opened.open("Built-in browser")
        task = page.get_by_label("Your task")
        await task.fill("Open my account")
        await task.press("Enter")

        popup = page.get_by_role("dialog", name="The agent needs you to sign in")
        await popup.wait_for()
        assert "Sign in to Northfield for me" in await popup.inner_text()
        # The pop-up holds the answers: they are not offered a second time behind it.
        assert await page.get_by_role("button", name="Take over").count() == 1
        # Seen from any other page of the window.
        await popup.get_by_role("button", name="Look first").click()
        await popup.wait_for(state="hidden")
        await opened.open("Cloud browser")
        async with asyncio.timeout(10):
            while await opened.tab("Built-in browser") != "Built-in browser Needs you":
                await asyncio.sleep(0.1)

        # Back on its page the pop-up asks again, and the person does the step.
        await opened.open("Built-in browser")
        await popup.wait_for()
        await popup.get_by_role("button", name="Take over").click()
        await popup.wait_for(state="hidden")
        await page.get_by_role("button", name="Done").first.click()
        await page.get_by_text("You are signed in.").wait_for()
        async with asyncio.timeout(10):
            while await opened.tab("Built-in browser") != "Built-in browser Ready":
                await asyncio.sleep(0.1)


async def test_a_stopped_session_is_started_again_from_its_page(
    make_config: Callable[..., Config], tmp_path: Path, browser: Browser
) -> None:
    async with window(
        make_config, tmp_path, browser, lambda: ScriptedModel([lambda page: Reply("Done.")])
    ) as opened:
        page = opened.page
        task = page.get_by_label("Your task")
        await task.fill("Say done")
        await task.press("Enter")
        await page.get_by_text("Done.", exact=True).wait_for()

        await page.get_by_role("button", name="Stop session").click()
        await page.get_by_role("alertdialog").get_by_role("button", name="Stop session").click()
        await opened.room("cloud", "ended")
        assert await opened.tab("Cloud browser") in ("Cloud browser Stopped", "Cloud browser Ready")
        await page.get_by_role("button", name="Start a new session").click()

        # A new browser and a new conversation on the same page of the window.
        await opened.room("cloud", "agent")
        await page.get_by_text("Tell the agent what to do in the browser.").wait_for()
        assert await page.get_by_text("Done.", exact=True).count() == 0
        await task.fill("Say done again")
        await task.press("Enter")
        await page.get_by_text("Done.", exact=True).wait_for()
        # The other pages were not touched.
        assert (await opened.room("builtin", "agent"))["state"] == "agent"


async def test_the_persons_own_chrome_becomes_a_page_once_its_extension_dials_in(
    make_config: Callable[..., Config], tmp_path: Path, browser: Browser
) -> None:
    async with window(make_config, tmp_path, browser, lambda: ScriptedModel([])) as opened:
        page = opened.page
        await opened.open("My Chrome")
        await page.get_by_role("heading", name="Connect your Chrome").wait_for()
        async with async_playwright() as playwright:
            chrome = await playwright.chromium.launch_persistent_context(
                str(tmp_path / "their-profile"),
                channel="chromium",
                headless=True,
                args=[f"--disable-extensions-except={opened.folder}", f"--load-extension={opened.folder}"],
            )
            try:
                # The extension's own page, as the person would open its side panel.
                panel = await chrome.new_page()
                await panel.goto(f"chrome-extension://{browser_extension.EXTENSION_ID}/panel.html")
                room = await opened.room("chrome", "agent")
                assert room["backend"] == "takeover_chrome"
                # The window's page turns from "connect" into the chat for that Chrome.
                await page.get_by_label("Your task").wait_for(timeout=20_000)
                assert await opened.tab("My Chrome") == "My Chrome Ready"
                # The agent's tab in that Chrome is on the start page, and its side panel shows the same chat.
                async with asyncio.timeout(20):
                    while not any(tab.url.endswith("/demo-site/start.html") for tab in chrome.pages):
                        await asyncio.sleep(0.1)
                await panel.frame_locator("#viewer").get_by_label("Your task").wait_for(timeout=20_000)
            finally:
                await chrome.close()


# Each browser of the window is a system of its own (spec 9.17), and is evaluated by itself (spec 12.6).


async def test_each_system_has_its_own_log_and_its_own_record_of_a_task(
    make_config: Callable[..., Config], tmp_path: Path, browser: Browser
) -> None:
    def answers() -> ScriptedModel:
        go = ToolCall("a", "browser_snapshot", {})
        return ScriptedModel(
            [lambda page: Reply("", (go,)), lambda page: Reply("The page is the start page.")]
        )

    async with window(make_config, tmp_path, browser, answers) as opened:
        page = opened.page
        task = page.get_by_label("Your task")
        await task.fill("Say which page this is")
        await task.press("Enter")
        await page.get_by_text("The page is the start page.").wait_for()

        status, told = await opened.ask("GET", "/api/systems")
        systems = {system["id"]: system for system in told["systems"]}
        assert status == 200 and list(systems) == ["cloud", "chrome", "builtin", "computer"]
        assert all(system["enabled"] for system in systems.values())
        # A log for each browser, in the folder for them, and not one for all.
        assert systems["cloud"]["log"] == str((tmp_path / "logs" / "cloud.jsonl").resolve())
        assert systems["builtin"]["log"] == str((tmp_path / "logs" / "builtin.jsonl").resolve())
        cloud_log = (await opened.ask("GET", "/api/systems/cloud/log"))[1]
        assert [line["tool"] for line in cloud_log["lines"]] == ["browser_navigate", "browser_snapshot"]
        built_in_log = (await opened.ask("GET", "/api/systems/builtin/log"))[1]
        assert [line["tool"] for line in built_in_log["lines"]] == ["browser_navigate"]
        assert not (tmp_path / "events.jsonl").exists(), "nothing goes to the one log of a single session"

        # The task is on the record of the browser that did it, and of no other.
        evals = (await opened.ask("GET", "/api/systems/cloud/evals"))[1]
        assert evals["backend"] == "remote_headless" and evals["checking"] is False
        assert (evals["tasks"]["count"], evals["tasks"]["answered"], evals["tasks"]["success_rate"]) == (
            1,
            1,
            1.0,
        )
        assert evals["latency"]["tool"]["count"] == 1 and evals["latency"]["model"]["count"] == 2
        assert evals["latency"]["by_tool"][0]["tool"] == "browser_snapshot"
        done = evals["recent"][0]
        assert done["task"] == "Say which page this is" and done["answer"] == "The page is the start page."
        assert (done["steps"], done["model_calls"], done["tokens_known"]) == (1, 2, False)
        assert (await opened.ask("GET", "/api/systems/builtin/evals"))[1]["tasks"]["count"] == 0
        # Its trace: every reply of the model and every step, in order.
        trace = (await opened.ask("GET", f"/api/systems/cloud/evals/{done['id']}"))[1]
        assert [(span["kind"], span["name"]) for span in trace["spans"]] == [
            ("model", trace["model"]),
            ("tool", "browser_snapshot"),
            ("model", trace["model"]),
        ]
        # A person says the answer was good, and it counts.
        assert (
            await opened.ask("POST", f"/api/systems/cloud/evals/{done['id']}/rating", {"rating": "good"})
        )[0] == 200
        assert (await opened.ask("GET", "/api/systems/cloud/evals"))[1]["tasks"]["rated_good"] == 1


async def test_the_checklist_runs_real_steps_on_a_system(
    make_config: Callable[..., Config], tmp_path: Path, browser: Browser
) -> None:
    async with window(make_config, tmp_path, browser, lambda: ScriptedModel([])) as opened:
        await opened.open("Built-in browser")
        await opened.page.get_by_label("Your task").wait_for()
        status, result = await opened.ask("POST", "/api/systems/builtin/checks")
        assert status == 200, result
        checks = {check["id"]: check for check in result["checks"]}
        assert list(checks) == [
            "answers",
            "opens",
            "reads",
            "finds",
            "acts",
            "types",
            "picture",
            "refuses",
            "fast",
            "logged",
            "person",
        ]
        assert {name: check["state"] for name, check in checks.items()} == dict.fromkeys(checks, "ok"), result
        assert (result["passed"], result["failed"], result["skipped"]) == (11, 0, 0)
        assert all(
            check["ms"] is not None for name, check in checks.items() if name not in ("logged", "person")
        )
        # The browser is back where it was, for whatever the agent does next.
        async with asyncio.timeout(10):
            while not (await opened.room("builtin", "agent")):
                await asyncio.sleep(0.1)
        log = (await opened.ask("GET", "/api/systems/builtin/log"))[1]
        assert log["lines"][-1]["tool"] == "browser_navigate" and "start.html" in log["lines"][-1]["result"]
        # What was typed in the check reached the page, and no log.
        assert "Ada Lovelace" not in json.dumps(log["lines"])
        # The result is kept, and shown with the rest of what is known of that browser.
        kept = (await opened.ask("GET", "/api/systems/builtin/evals"))[1]["checklist"]
        assert kept["passed"] == 11 and kept["ran"] == result["ran"]
        assert (await opened.ask("GET", "/api/systems/cloud/evals"))[1]["checklist"] is None
        # A browser that is not there has nothing to check.
        status, why = await opened.ask("POST", "/api/systems/chrome/checks")
        assert status == 409 and why == {"error": "This browser has no session. Start it first."}


async def test_a_task_set_is_run_from_the_evaluations_view_and_its_result_is_kept(
    make_config: Callable[..., Config], tmp_path: Path, browser: Browser, view_of: Callable[[Page], Any]
) -> None:
    """The task sets (spec 12.7) in the real window: a person runs one with the reference solutions
    and reads the result; the same set run by an agent that does nothing fails every task; and the
    admin's overview puts the browsers side by side."""
    async with window(make_config, tmp_path, browser, lambda: ScriptedModel([])) as opened:
        page, view = opened.page, view_of(opened.page)
        await opened.open("Built-in browser")
        await page.get_by_role("tab", name="Evaluations").click()
        long_tasks = page.get_by_role("listitem", name="Long tasks")
        await long_tasks.get_by_text("This set has not been run yet.").wait_for()
        assert await page.get_by_role("listitem", name="Short tasks").get_by_text("20 tasks").count() == 1
        assert await view.silent_controls() == []

        await page.get_by_label("Times each task is tried").select_option("1")
        await long_tasks.get_by_role("button", name="Run the reference solutions").click()
        # While it runs the page says where it is, and offers to stop it and nothing else.
        await long_tasks.get_by_role("button", name="Stop the run").wait_for()
        await long_tasks.get_by_text("Passed 4 of 4 tries (100%).").wait_for(timeout=60_000)
        await long_tasks.get_by_text("Done by the reference solutions").wait_for()
        await long_tasks.get_by_role("button", name="Show the tasks").click()
        rows = long_tasks.get_by_role("row")
        assert await rows.count() == 5
        assert "Buy three things, then write the total to someone" in await rows.nth(1).inner_text()
        assert await view.accessibility_violations() == [] and await view.silent_controls() == []
        assert await view.sideways_overflow() == 0 and view.errors == []
        await view.shot("task-sets-run")

        # The browser is back where it was, and what the run did is in its log like any step.
        await opened.room("builtin", "agent")
        log = (await opened.ask("GET", "/api/systems/builtin/log"))[1]
        assert "start.html" in log["lines"][-1]["result"]
        assert any("lab/reset.html" in line["result"] for line in log["lines"])

        # The same set done by the agent. This one's model answers at once and does nothing.
        status, told = await opened.ask(
            "POST", "/api/systems/builtin/suite", {"set": "long", "trials": 10, "mode": "agent"}
        )
        assert status == 202 and told["running"]["mode"] == "agent"
        # One run at a time on a browser, and no checklist under it. Ten tries of each task, so that
        # the run is still under way when these are asked.
        again = await opened.ask(
            "POST", "/api/systems/builtin/suite", {"set": "short", "trials": 1, "mode": "reference"}
        )
        assert again == (409, {"error": "This browser is busy. Run the task set when its task is finished."})
        assert (await opened.ask("POST", "/api/systems/builtin/checks"))[0] == 409
        async with asyncio.timeout(60):
            while (told := (await opened.ask("GET", "/api/systems/builtin/suite"))[1])["running"] is not None:
                await asyncio.sleep(0.2)
        last = next(one for one in told["sets"] if one["id"] == "long")
        assert (last["last"]["mode"], last["last"]["trials"], last["last"]["stopped"]) == ("agent", 10, False)
        assert last["last"]["totals"]["passed"] == 0 and last["last"]["totals"]["every_time"] == 0
        assert [run["pass_rate"] for run in last["earlier"]] == [1.0]
        # Each try of the agent has a record of its own, apart from the records of a person's tasks.
        records = (tmp_path / "evals" / "builtin" / "suite" / "tasks.jsonl").read_text("utf-8").splitlines()
        assert len(records) == 40 and json.loads(records[0])["task"].startswith("Buy the Blue running shoes")
        assert (await opened.ask("GET", "/api/systems/builtin/evals"))[1]["tasks"]["count"] == 0
        # The chat shows each task as it was given.
        await page.get_by_role("tab", name="Browser and chat").click()
        await page.get_by_text("Go through the inbox: delete the message from Shop Daily").first.wait_for()

        # A run that is stopped keeps what it did.
        await opened.ask(
            "POST", "/api/systems/cloud/suite", {"set": "short", "trials": 10, "mode": "reference"}
        )
        assert (await opened.ask("POST", "/api/systems/cloud/suite/stop"))[0] == 200
        async with asyncio.timeout(60):
            while (cloud := (await opened.ask("GET", "/api/systems/cloud/suite"))[1])["running"] is not None:
                await asyncio.sleep(0.2)
        stopped = next(one for one in cloud["sets"] if one["id"] == "short")["last"]
        assert stopped["stopped"] and stopped["totals"]["tasks"] < 20
        assert (
            await opened.ask(
                "POST", "/api/systems/chrome/suite", {"set": "short", "trials": 1, "mode": "reference"}
            )
        ) == (
            409,
            {"error": "This browser has no session. Start it first."},
        )
        for wrong in ({"set": "none", "trials": 1}, {"set": "short", "trials": 99}):
            assert (await opened.ask("POST", "/api/systems/cloud/suite", {**wrong, "mode": "reference"}))[
                0
            ] == 409

        # The admin's overview: the newest run of each set, browser by browser.
        await page.get_by_role("button", name="Systems").click()
        await page.get_by_role("tab", name="All systems").click()
        parity = page.get_by_role("article", name="Task sets, browser by browser")
        row = parity.get_by_role("row", name="Long tasks")
        await row.get_by_text("0% passed").wait_for()
        await row.get_by_text("Done by the agent").wait_for()
        side_by_side = (await opened.ask("GET", "/api/suite"))[1]["systems"]
        built_in = next(one for one in side_by_side if one["system"] == "builtin")["runs"]["long"]
        assert (built_in["mode"], built_in["trials"], built_in["tasks"], built_in["pass_rate"]) == (
            "agent",
            10,
            4,
            0.0,
        )
        assert "Not run" in await row.inner_text()
        assert await view.accessibility_violations() == [] and view.errors == []


async def test_a_system_is_turned_off_and_on_and_stopped_and_started(
    make_config: Callable[..., Config], tmp_path: Path, browser: Browser
) -> None:
    async with window(make_config, tmp_path, browser, lambda: ScriptedModel([])) as opened:
        turn = {"surface": "web", "system": "builtin", "changes": {"system_enabled": False}}
        status, shown = await opened.ask("PATCH", "/api/settings", turn)
        assert status == 200 and shown["system"] == "builtin"
        # Turned off: it has no session, its tab says so, and the other browsers go on.
        off = await opened.room("builtin", "off")
        assert off["working"] is False
        assert (await opened.room("cloud", "agent"))["state"] == "agent"
        async with asyncio.timeout(10):
            while await opened.tab("Built-in browser") != "Built-in browser Turned off":
                await asyncio.sleep(0.1)
        assert await opened.ask("POST", "/api/systems/builtin/start") == (
            409,
            {"error": "This browser is turned off. Turn it on first."},
        )
        turn["changes"] = {"system_enabled": True}
        assert (await opened.ask("PATCH", "/api/settings", turn))[0] == 200
        await opened.room("builtin", "agent")

        # Stopped by hand, and started again: a new browser and a new conversation.
        assert (await opened.ask("POST", "/api/systems/cloud/stop"))[0] == 200
        await opened.room("cloud", "ended")
        assert await opened.ask("POST", "/api/systems/cloud/stop") == (
            409,
            {"error": "This browser has no session to stop."},
        )
        assert (await opened.ask("POST", "/api/systems/cloud/start"))[0] == 200
        await opened.room("cloud", "agent")
        assert (await opened.ask("POST", "/api/systems/cloud/restart"))[0] == 200
        await opened.room("cloud", "agent")
        assert (await opened.ask("POST", "/api/systems/cloud/sing"))[0] == 409


async def test_a_systems_settings_reach_that_browser_alone(
    make_config: Callable[..., Config], tmp_path: Path, browser: Browser
) -> None:
    async with window(make_config, tmp_path, browser, lambda: ScriptedModel([])) as opened:
        block = {"surface": "web", "system": "cloud", "changes": {"activity_log": False}}
        assert (await opened.ask("PATCH", "/api/settings", block))[0] == 200
        systems = {system["id"]: system for system in (await opened.ask("GET", "/api/systems"))[1]["systems"]}
        # The cloud browser's log is off, and the built-in browser's is still written.
        assert systems["cloud"]["log"] is None
        assert systems["builtin"]["log"] == str((tmp_path / "logs" / "builtin.jsonl").resolve())
        assert (await opened.ask("GET", "/api/systems/cloud/log"))[1] == {
            "path": None,
            "lines": [],
            "size": 0,
        }


SHOTS = Path(__file__).parents[2] / ".bap-browser" / "viewer-shots"


async def turned(switch: Locator, on: bool) -> None:
    """Presses a switch, and waits until it shows what the service saved."""
    await switch.click()
    async with asyncio.timeout(10):
        while await switch.get_attribute("aria-checked") != ("true" if on else "false"):
            await asyncio.sleep(0.05)


async def saved(opened: Window, system: str, setting: str, value: Any) -> None:
    """Waits until the service has a setting of one browser at a value."""
    async with asyncio.timeout(10):
        while True:
            groups = (await opened.ask("GET", f"/api/settings?system={system}"))[1]["groups"]
            if next(s["value"] for g in groups for s in g["settings"] if s["id"] == setting) == value:
                return
            await asyncio.sleep(0.05)


async def test_each_browser_is_set_up_managed_and_evaluated_under_its_own_tab(
    make_config: Callable[..., Config], tmp_path: Path, browser: Browser
) -> None:
    def answers() -> ScriptedModel:
        go = ToolCall("a", "browser_snapshot", {})
        return ScriptedModel(
            [lambda page: Reply("", (go,)), lambda page: Reply("The page is the start page.")]
        )

    async with window(make_config, tmp_path, browser, answers) as opened:
        page = opened.page
        task = page.get_by_label("Your task")
        await task.fill("Say which page this is")
        await task.press("Enter")
        await page.get_by_text("The page is the start page.").wait_for()

        # The settings button on a browser's page goes to that browser's own configuration: a
        # setting is in one place, and no second screen opens over the page.
        await page.get_by_role("button", name="Open settings").click()
        await page.get_by_role("heading", name="Configuration of Cloud browser").wait_for()
        assert await page.get_by_role("dialog").count() == 0
        assert await page.get_by_role("tab", name="Configuration").get_attribute("aria-selected") == "true"
        cloud = page.get_by_role("article", name="Cloud browser")
        assert await page.get_by_role("article").count() == 1, "that browser's card, and no other's"

        # What the agent may do in one browser is that browser's alone, and says what it does.
        downloads = cloud.get_by_role("switch", name="Let the agent download files")
        await downloads.wait_for()
        assert await downloads.get_attribute("aria-checked") == "true"
        await cloud.get_by_text("On: the agent may download files, saved where you can find them").wait_for()
        await turned(downloads, False)
        await cloud.get_by_text("Saved", exact=True).wait_for()
        own = {
            s["id"]: s
            for g in (await opened.ask("GET", "/api/settings?system=cloud"))[1]["groups"]
            for s in g["settings"]
        }
        others = {
            s["id"]: s
            for g in (await opened.ask("GET", "/api/settings?system=builtin"))[1]["groups"]
            for s in g["settings"]
        }
        assert own["allow_downloads"]["value"] is False and others["allow_downloads"]["value"] is True
        # A choice, a list of sites: every kind of setting is changed on the page itself.
        await cloud.get_by_role("radio", name="Every action").click()
        await saved(opened, "cloud", "ask_before", "every_action")
        await cloud.get_by_role("radio", name="Risky actions").click()
        await saved(opened, "cloud", "ask_before", "risky")
        blocked = cloud.get_by_role("textbox", name="Blocked sites")
        await blocked.fill("ads.example")
        await blocked.blur()
        await saved(opened, "cloud", "blocked_sites", ["ads.example"])
        # What the deployment left off is the admin's to turn on: the switch is a working one.
        scripts = cloud.get_by_role("switch", name="Let the agent run scripts of several steps")
        assert await scripts.get_attribute("aria-checked") == "false"
        assert await scripts.is_enabled()
        # Every row says what its control does.
        assert await cloud.locator(".setting").count() == await cloud.locator(".setting-description").count()
        assert await cloud.locator(".setting-description:empty").count() == 0
        # And the admin says, on the same page, whether users may use this browser at all.
        for_users = cloud.get_by_role("switch", name="Let users use this browser: Cloud browser")
        assert await for_users.get_attribute("aria-checked") == "true"
        await cloud.get_by_text("Also on the user's page. Users may set their own").first.wait_for()

        # Its log is a file of its own, and its newest lines are read from here.
        await cloud.get_by_text(str((tmp_path / "logs" / "cloud.jsonl").resolve())).wait_for()
        await cloud.get_by_role("button", name="Show the log").click()
        await cloud.get_by_text("The newest 2 lines, newest first").wait_for()
        assert await cloud.locator(".system-log-tool").all_inner_texts() == ["snapshot", "navigate"]
        assert await page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        SHOTS.mkdir(parents=True, exist_ok=True)
        await page.evaluate("document.querySelector('.systems').scrollTop = 0")
        await page.screenshot(path=str(SHOTS / "system-configuration-under-its-tab.png"))

        # The browser is stopped and started from here.
        await cloud.get_by_role("button", name="Stop").click()
        await opened.room("cloud", "ended")
        await cloud.get_by_role("button", name="Start").click()
        await opened.room("cloud", "agent")
        await cloud.get_by_role("button", name="Restart").wait_for()

        # The view stays from one browser to the next. The built-in browser is turned off from its
        # own configuration, and the page stays where it is.
        await opened.open("Built-in browser")
        await page.get_by_role("heading", name="Configuration of Built-in browser").wait_for()
        built_in = page.get_by_role("article", name="Built-in browser")
        await built_in.get_by_text(str((tmp_path / "logs" / "builtin.jsonl").resolve())).wait_for()
        use = built_in.get_by_role("switch", name="Use this browser: Built-in browser", exact=True)
        await turned(use, False)
        await opened.room("builtin", "off")
        await built_in.get_by_text("Turned off").first.wait_for()
        assert await built_in.get_by_role("button", name="Start").is_disabled()
        assert await opened.tab("Built-in browser") == "Built-in browser Turned off"

        # Evaluations of the cloud browser: what the task took, the checklist, and the trace.
        await opened.open("Cloud browser")
        await page.get_by_role("tab", name="Evaluations").click()
        await page.get_by_role("heading", name="Evaluations of Cloud browser").wait_for()
        cloud = page.get_by_role("article", name="Cloud browser")
        await cloud.get_by_text("1 task, 1 step").wait_for()
        await cloud.get_by_text("100% answered (1 of 1)").wait_for()
        await cloud.get_by_text("The model did not say how many tokens it used.").wait_for()
        await cloud.get_by_text("Not run yet.").wait_for()
        await cloud.get_by_role("button", name="Run the checklist").click()
        # Nobody is watching that browser's own page now, so whether a person can be asked is skipped.
        await cloud.get_by_text("10 of 11 passed").wait_for(timeout=60_000)
        assert await cloud.locator('.system-check[data-state="ok"]').count() == 10
        await cloud.get_by_text("Say which page this is").wait_for()
        await cloud.get_by_role("button", name="Show the trace").click()
        trace = cloud.get_by_role("list", name="Trace")
        await trace.wait_for()
        assert await trace.locator(".system-span-name").all_inner_texts() == [
            "The model",
            "snapshot",
            "The model",
        ]
        await cloud.get_by_role("button", name="Good").click()
        await cloud.get_by_text("You rated 1 good and 0 bad").wait_for()
        assert await page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        await page.evaluate("document.querySelector('.systems').scrollTop = 0")
        await page.screenshot(path=str(SHOTS / "system-evaluations-under-its-tab.png"))
        assert await page.get_by_role("article").count() == 1

        # Back on a browser's own page: the one turned off says so, and is turned on from there.
        await opened.open("Built-in browser")
        await page.get_by_role("tab", name="Browser and chat").click()
        await page.get_by_role("heading", name="This browser is turned off").wait_for()
        await page.get_by_role("button", name="Turn it on").click()
        await opened.room("builtin", "agent")
        await page.get_by_label("Your task").wait_for(timeout=20_000)
        assert await page.get_by_title("Session", exact=True).inner_text() == "Session\nbuiltin"


async def test_the_systems_page_has_what_is_not_one_browsers_and_repeats_none_of_it(
    make_config: Callable[..., Config], tmp_path: Path, browser: Browser
) -> None:
    def answers() -> ScriptedModel:
        go = ToolCall("a", "browser_snapshot", {})
        return ScriptedModel(
            [lambda page: Reply("", (go,)), lambda page: Reply("The page is the start page.")]
        )

    async with window(make_config, tmp_path, browser, answers) as opened:
        page = opened.page
        task = page.get_by_label("Your task")
        await task.fill("Say which page this is")
        await task.press("Enter")
        await page.get_by_text("The page is the start page.").wait_for()

        await page.get_by_role("button", name="Systems").click()
        systems = page.get_by_role("region", name="Systems")
        await systems.get_by_role("article").first.wait_for()
        views = systems.get_by_role("tablist", name="What to show of the systems")
        assert await views.get_by_role("tab").all_inner_texts() == ["Users", "All systems"]

        # Users: what a user is allowed. No browser's own settings are repeated here.
        assert [
            await card.get_attribute("aria-label") for card in await systems.get_by_role("article").all()
        ] == ["Users"]
        users = systems.get_by_role("article", name="Users")
        assert await systems.get_by_role("switch", name="Let the agent download files").count() == 0
        assert await systems.get_by_role("switch", name="Use this browser").count() == 0
        # Every switch says what it lets a user do, and works.
        switches = await users.get_by_role("switch").all()
        assert len(switches) == 17
        assert await users.locator(".system-row-hint:empty").count() == 0
        cost = users.get_by_role("switch", name="What users may see: What the tasks cost")
        await turned(cost, False)
        assert (await opened.ask("GET", "/api/admin/policy"))[1]["sees"][1]["allowed"] is False
        await turned(cost, True)
        colour = users.get_by_role("switch", name="What users may change: Colour mode")
        await turned(colour, False)
        policy = (await opened.ask("GET", "/api/admin/policy"))[1]
        assert {"id": "colour_mode", "allowed": False}.items() <= policy["may_change"][-1].items()
        await turned(colour, True)
        assert await page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        SHOTS.mkdir(parents=True, exist_ok=True)
        await page.evaluate("document.querySelector('.systems').scrollTop = 0")
        await page.screenshot(path=str(SHOTS / "systems-users.png"))

        # All systems: where each browser stands, and the tasks of all three as one.
        await views.get_by_role("tab", name="All systems").click()
        browsers = systems.get_by_role("article", name="The browsers")
        await browsers.wait_for()
        assert [
            await card.get_attribute("aria-label") for card in await systems.get_by_role("article").all()
        ] == ["The browsers", "Evaluations of all systems", "Task sets, browser by browser"]
        rows = browsers.get_by_role("row")
        model = (await opened.ask("GET", "/api/systems"))[1]["systems"][0]["model"]
        assert [" ".join(text.split()) for text in await rows.all_inner_texts()][1:] == [
            f"Cloud browser Ready On May use it {model} Configuration Evaluations",
            f"My Chrome Not connected On May use it {model} Configuration Evaluations",
            f"Built-in browser Ready On May use it {model} Configuration Evaluations",
            # The desktop of computer use: no container program in a test, so it could not start.
            f"Computer Could not start On May use it {model} Configuration Evaluations",
        ]
        assert await browsers.get_by_role("switch").count() == 0, "nothing is changed here"
        overall = systems.get_by_role("article", name="Evaluations of all systems")
        await overall.get_by_text("1 task, 1 step").wait_for()
        await overall.get_by_text("100% answered (1 of 1)").wait_for()
        assert await page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        await page.screenshot(path=str(SHOTS / "systems-all.png"))

        # From here to a browser's own evaluations, and to its configuration.
        await browsers.get_by_role("button", name="Evaluations of Cloud browser").click()
        await page.get_by_role("heading", name="Evaluations of Cloud browser").wait_for()
        await page.get_by_role("article", name="Cloud browser").get_by_text("1 task, 1 step").wait_for()
        assert (
            await opened.page.get_by_role("tab", name="Cloud browser").get_attribute("aria-selected")
            == "true"
        )
        await page.get_by_role("button", name="Systems").click()
        await views.get_by_role("tab", name="All systems").click()
        await browsers.get_by_role("button", name="Configuration of Built-in browser").click()
        await page.get_by_role("heading", name="Configuration of Built-in browser").wait_for()
        await (
            page.get_by_role("article", name="Built-in browser")
            .get_by_role("switch", name="Use this browser: Built-in browser", exact=True)
            .wait_for()
        )
