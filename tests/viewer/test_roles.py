"""The admin and a user in a real browser (spec 4.11): a sign-in page for each, the admin's
configuration with what users are allowed, a user's own settings with the browser they prefer, and
the evaluations as each of them is shown them."""

import asyncio
import json
import urllib.error
import urllib.request
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from playwright.async_api import Browser, Locator, Page

from bap_browser import browser_extension
from bap_browser.agent.models import Reply, ScriptedModel, ToolCall
from bap_browser.agent.window import run_studio
from bap_browser.config import Config

ADMINS = "the admin's own words"
USERS = "what users sign in with"
VISIT = "sessionStorage.getItem('bap-browser.visit')"
IS_DARK = "document.documentElement.getAttribute('data-theme') === 'dark'"


def answers() -> ScriptedModel:
    look = ToolCall("a", "browser_snapshot", {})
    return ScriptedModel([lambda page: Reply("", (look,)), lambda page: Reply("The page is the start page.")])


@dataclass
class Running:
    service: str
    token: str
    """The service's own token: the link it printed when it started."""

    def _ask(self, method: str, path: str, body: Any, token: str | None) -> tuple[int, Any]:
        asked = urllib.request.Request(
            f"{self.service}{path}",
            data=None if body is None else json.dumps(body).encode(),
            headers={"Authorization": f"Bearer {token}"} if token else {},
            method=method,
        )
        try:
            with urllib.request.urlopen(asked, timeout=60) as answer:
                return answer.status, json.loads(answer.read())
        except urllib.error.HTTPError as refused:
            return refused.code, json.loads(refused.read() or b"null")

    async def ask(self, method: str, path: str, body: Any = None, *, token: str | None = None) -> Any:
        """Asks the service, from another thread: it answers on this one. Its own token unless another is given."""
        status, said = await asyncio.to_thread(self._ask, method, path, body, token or self.token)
        assert status == 200, (method, path, status, said)
        return said

    async def status(self, method: str, path: str, token: str | None) -> int:
        return (await asyncio.to_thread(self._ask, method, path, None, token))[0]

    async def room(self, name: str, state: str) -> None:
        async with asyncio.timeout(30):
            while True:
                rooms = (await self.ask("GET", "/api/sessions"))["rooms"]
                if next(room for room in rooms if room["id"] == name)["state"] == state:
                    return
                await asyncio.sleep(0.1)

    async def setting(self, system: str, setting: str, token: str) -> Any:
        groups = (await self.ask("GET", f"/api/settings?system={system}", token=token))["groups"]
        return next(one["value"] for group in groups for one in group["settings"] if one["id"] == setting)

    async def navigations(self, system: str) -> int:
        """How many times this browser opened its first page: once for each session it has had."""
        lines = (await self.ask("GET", f"/api/systems/{system}/log"))["lines"]
        return sum(line["tool"] == "browser_navigate" for line in lines)


@asynccontextmanager
async def studio(make_config: Callable[..., Config], tmp_path: Path) -> AsyncIterator[Running]:
    folder = browser_extension.install(tmp_path / "state" / "extension")
    config = make_config(tmp_path)
    running = asyncio.create_task(
        run_studio(config, lambda service: answers(), open_viewer=False, extension=folder)
    )
    state = Path(config.server.state_file)
    try:
        async with asyncio.timeout(30):
            while not state.exists():
                assert not running.done(), running.exception()
                await asyncio.sleep(0.05)
        service, token = json.loads(state.read_text(encoding="utf-8"))["viewer"].split("/#token=")
        one = Running(service, token)
        await one.room("cloud", "agent")
        await one.room("builtin", "agent")
        yield one
    finally:
        running.cancel()
        await asyncio.gather(running, return_exceptions=True)


async def turned(switch: Locator, on: bool) -> None:
    """Presses a switch, and waits until it shows what the service saved."""
    await switch.click()
    async with asyncio.timeout(10):
        while await switch.get_attribute("aria-checked") != ("true" if on else "false"):
            await asyncio.sleep(0.05)


async def tabs(page: Page, name: str) -> list[str]:
    return [
        " ".join(text.split())
        for text in await page.get_by_role("tablist", name=name).get_by_role("tab").all_inner_texts()
    ]


async def test_the_admin_sets_the_system_up_and_a_user_works_inside_what_the_admin_allows(
    make_config: Callable[..., Config], tmp_path: Path, browser: Browser, view_of: Callable[[Page], Any]
) -> None:
    async with studio(make_config, tmp_path) as running:
        admin = await browser.new_page(viewport={"width": 1360, "height": 850})
        user = await browser.new_page(viewport={"width": 1360, "height": 850})
        admin_view, user_view = view_of(admin), view_of(user)
        try:
            # The first time: the link the service printed makes the admin's password, on the admin's page.
            await admin.goto(f"{running.service}/admin#token={running.token}")
            await admin.get_by_role("heading", name="Create the admin password").wait_for()
            assert await admin_view.accessibility_violations() == []
            await admin_view.shot("sign-in-admin-first-time")
            await admin.get_by_label("New password", exact=True).fill(ADMINS)
            await admin.get_by_label("The same password again").fill(ADMINS)
            await admin.get_by_role("button", name="Create the password and sign in").click()
            await admin.get_by_role("tablist", name="Where the agent works").wait_for()
            await admin.get_by_text("Admin", exact=True).wait_for()
            # From here on the page holds the admin's own visit, not the link that made the password.
            assert "token" not in admin.url
            assert await admin.evaluate("sessionStorage.getItem('bap-browser.token')") is None
            admins_visit = await admin.evaluate(VISIT)
            assert admins_visit and admins_visit != running.token
            assert await tabs(admin, "What to show of Cloud browser") == [
                "Browser and chat",
                "Configuration",
                "Evaluations",
            ]
            # Every control of the page says what it does: the bar, the views, the session's controls.
            await admin.get_by_label("Your task").wait_for(timeout=20_000)
            assert await admin_view.silent_controls() == []

            # A user's page is the address itself. Until the admin sets a password, nobody signs in there.
            await user.goto(f"{running.service}/")
            await user.get_by_role("heading", name="Sign in").wait_for()
            # It says where the admin sets it, as the pages are now.
            await user.get_by_text("Ask them to set one: it is under Systems, Users.").wait_for()
            assert await user.get_by_label("Password").count() == 0

            # The Systems page is the admin's, for what is not one browser's: the password users sign
            # in with, and what users may change and see. Each line says what it is.
            await admin.get_by_role("button", name="Systems").click()
            systems = admin.get_by_role("region", name="Systems")
            assert await tabs(admin, "What to show of the systems") == ["Users", "All systems"]
            users = systems.get_by_role("article", name="Users")
            await users.get_by_label("The password users sign in with").fill(USERS)
            await users.get_by_role("button", name="Set it").click()
            await users.get_by_text("Set. A user who was signed in signs in again with it.").wait_for()
            await turned(users.get_by_role("switch", name="What users may see: What the tasks cost"), False)
            await turned(users.get_by_role("switch", name="What users may change: Picture quality"), False)
            await users.get_by_text(
                "The colours of this window: light, dark, or the same as your device."
            ).wait_for()
            assert await admin.evaluate("document.documentElement.scrollWidth <= innerWidth")
            assert await admin_view.accessibility_violations() == []
            assert await admin_view.silent_controls() == []
            await admin.evaluate("document.querySelector('.systems').scrollTop = 0")
            await admin_view.shot("admin-users")

            # Whether users may use a browser is set on that browser's own configuration, one press away.
            await users.get_by_role("button", name="Open its configuration: Cloud browser").click()
            await admin.get_by_role("heading", name="Configuration of Cloud browser").wait_for()
            cloud = admin.get_by_role("article", name="Cloud browser")
            await turned(cloud.get_by_role("switch", name="Let users use this browser: Cloud browser"), False)
            # A setting users are held to says so, where the admin sets it.
            await cloud.get_by_text(
                "Also on the user's page, held at your value: users cannot change it."
            ).wait_for()
            assert await admin.evaluate("document.documentElement.scrollWidth <= innerWidth")
            assert await admin_view.accessibility_violations() == []
            assert await admin_view.silent_controls() == []
            await admin_view.shot("admin-configuration")

            # A user signs in on their own page. A wrong password is said to be wrong, and opens nothing.
            await user.reload()
            await user.get_by_role("heading", name="Sign in").wait_for()
            assert await user_view.accessibility_violations() == []
            await user_view.shot("sign-in-user")
            password = user.get_by_label("Password")
            await password.fill("a guess at it")
            await password.press("Enter")
            await user.get_by_role("alert").get_by_text("That is not the password.").wait_for()
            assert await user.evaluate(VISIT) is None
            # The browser itself notes the refused request. Nothing else went wrong on the page.
            assert all("401" in error for error in user_view.errors), user_view.errors
            user_view.errors.clear()
            await password.fill(USERS)
            await user.get_by_role("button", name="Sign in").click()
            await user.get_by_role("tablist", name="Where the agent works").wait_for()
            await user.get_by_text("User", exact=True).wait_for()
            users_visit = await user.evaluate(VISIT)

            # The browser the admin keeps from users is not there for them at all, and neither is the Systems page.
            assert await tabs(user, "Where the agent works") == [
                "My Chrome Not connected",
                "Built-in browser Ready",
                "Computer Could not start",
            ]
            assert await user.get_by_role("button", name="Systems").count() == 0
            assert await running.status("GET", "/api/systems/cloud/evals", users_visit) == 404
            assert await running.status("GET", "/api/admin/policy", users_visit) == 403
            assert await tabs(user, "What to show of My Chrome") == [
                "Browser and chat",
                "Settings",
                "Evaluations",
            ]

            # Settings are the user's: the browser they prefer opens at once, and works.
            await user.get_by_role("tab", name="Settings").click()
            preferred = user.get_by_role("combobox", name="Preferred browser")
            await preferred.wait_for()
            assert await preferred.locator("option").all_text_contents() == [
                "My Chrome",
                "Built-in browser",
                "Computer",
            ]
            await preferred.select_option("builtin")
            task = user.get_by_label("Your task")
            await task.wait_for()
            assert (
                await user.get_by_role("tab", name="Built-in browser").get_attribute("aria-selected")
                == "true"
            )
            await task.fill("Say which page this is")
            await task.press("Enter")
            await user.get_by_text("The page is the start page.").wait_for()
            assert await user_view.silent_controls() == []

            # What is theirs to change is a working control, with a line saying what it does. What
            # the admin holds is said in words. The settings button on the chat goes there.
            await user.get_by_role("button", name="Open settings").click()
            await user.get_by_role("heading", name="Your settings for Built-in browser").wait_for()
            assert await user.get_by_role("dialog").count() == 0
            card = user.get_by_role("article", name="Built-in browser")
            await card.get_by_text("This is the one your window opens on.").wait_for()
            await turned(card.get_by_role("switch", name="Show where the agent is acting"), False)
            await card.get_by_role("radio", name="Every action").click()
            async with asyncio.timeout(10):
                while await running.setting("builtin", "ask_before", users_visit) != "every_action":
                    await asyncio.sleep(0.05)
            # It is the user's own, and tighter: the admin's configuration stays as the admin has it.
            assert await running.setting("builtin", "ask_before", admins_visit) == "risky"
            held = card.locator('.setting[data-locked="true"]').filter(has_text="Picture quality")
            await held.get_by_text("Set by your admin").wait_for()
            await held.get_by_text("Standard", exact=True).wait_for()
            assert await held.get_by_role("radio").count() == 0
            assert (
                await card.locator(".setting").count() == await card.locator(".setting-description").count()
            )
            # Managing the browser is the admin's.
            assert await card.get_by_role("button", name="Stop").count() == 0
            assert await card.get_by_role("switch", name="Let the agent download files").count() == 0
            assert await user.evaluate("document.documentElement.scrollWidth <= innerWidth")
            assert await user_view.accessibility_violations() == []
            assert await user_view.silent_controls() == []
            await user_view.shot("user-settings")

            # The colour mode is the user's own. It holds on every page of their window, and is not the admin's.
            await card.get_by_role("radio", name="Dark").click()
            await user.wait_for_function(IS_DARK)
            await user.get_by_role("tab", name="Browser and chat").click()
            await user.get_by_label("Your task").wait_for()
            assert await user.evaluate(IS_DARK)
            assert not await admin.evaluate(IS_DARK)

            # Evaluations, as the admin lets users see them: how the task went, and not what it cost.
            await user.get_by_role("tab", name="Evaluations").click()
            assert await user.evaluate(IS_DARK)
            card = user.get_by_role("article", name="Built-in browser")
            await card.get_by_text("1 task, 1 step").wait_for()
            await card.get_by_text("Say which page this is").wait_for()
            await card.get_by_role("button", name="Run the checklist").wait_for()
            assert await card.get_by_text("Cost", exact=True).count() == 0
            assert await user.get_by_role("article").count() == 1, "their browser's card, and not the whole"
            assert await user_view.silent_controls() == []
            await user_view.shot("user-evaluations")

            # The admin sees all of it: every system as one, and under a browser's tab what its tasks cost.
            await admin.get_by_role("button", name="Systems").click()
            await systems.get_by_role("tab", name="All systems").click()
            overall = systems.get_by_role("article", name="Evaluations of all systems")
            await overall.get_by_text("1 task, 1 step").wait_for()
            await overall.get_by_role("row", name="Built-in browser").wait_for()
            browsers = systems.get_by_role("article", name="The browsers")
            await browsers.get_by_role("row", name="Cloud browser").get_by_text("Kept from them").wait_for()
            assert await admin_view.accessibility_violations() == []
            assert await admin_view.silent_controls() == []
            await admin_view.shot("admin-all-systems")
            await browsers.get_by_role("button", name="Evaluations of Built-in browser").click()
            await admin.get_by_role("heading", name="Evaluations of Built-in browser").wait_for()
            built_in = admin.get_by_role("article", name="Built-in browser")
            await built_in.get_by_text("Cost", exact=True).wait_for()
            assert await admin_view.silent_controls() == []
            await admin.evaluate("document.querySelector('.systems').scrollTop = 0")
            await admin_view.shot("admin-evaluations")

            # The browser a user prefers is started for them when it has stopped.
            sessions = await running.navigations("builtin")
            await admin.get_by_role("tab", name="Configuration").click()
            await built_in.get_by_role("button", name="Stop").click()
            async with asyncio.timeout(30):
                while await running.navigations("builtin") == sessions:
                    await asyncio.sleep(0.1)
            await running.room("builtin", "agent")
            await user.get_by_role("tab", name="Browser and chat").click()
            await user.get_by_label("Your task").wait_for(timeout=20_000)

            # The admin keeps the evaluations from users: they leave the user's page by themselves.
            await admin.get_by_role("button", name="Systems").click()
            await turned(
                users.get_by_role("switch", name="What users may see: Evaluations of the browsers they use"),
                False,
            )
            await user.get_by_role("tab", name="Evaluations").wait_for(state="detached")
            assert await tabs(user, "What to show of Built-in browser") == ["Browser and chat", "Settings"]
            assert await running.status("GET", "/api/systems/builtin/evals", users_visit) == 403
            # A setting the admin now holds is shown to the user as held, with no reload either.
            await turned(users.get_by_role("switch", name="What users may change: Ask before"), False)
            await user.get_by_role("tab", name="Settings").click()
            held = user.locator('.setting[data-locked="true"]').filter(has_text="Ask before")
            await held.get_by_text("Risky actions").wait_for()
            assert await running.setting("builtin", "ask_before", users_visit) == "risky"
            # And the cloud browser, given back to users, is on the user's page again.
            await admin.get_by_role("tab", name="Cloud browser").click()
            await admin.get_by_role("tab", name="Configuration").click()
            await turned(cloud.get_by_role("switch", name="Let users use this browser: Cloud browser"), True)
            await user.get_by_role("tab", name="Cloud browser").wait_for()
            await admin.get_by_role("button", name="Systems").click()

            # The admin's page asks a user for the admin's password. Theirs does not open it.
            await user.goto(f"{running.service}/admin")
            await user.get_by_role("heading", name="Admin sign-in").wait_for()
            await user.get_by_role("link", name="Sign in as a user instead").click()
            await user.get_by_role("tablist", name="Where the agent works").wait_for()

            # A new password for users: the page of a user who signed in with the old one asks again.
            await users.get_by_label("The password users sign in with").fill("another one altogether")
            await users.get_by_role("button", name="Set it").click()
            await user.get_by_role("heading", name="Sign in").wait_for()
            assert await running.status("GET", "/api/sessions", users_visit) == 401
            user_view.errors.clear()  # The browser's own note of the request that was refused.
            await user.get_by_label("Password").fill("another one altogether")
            await user.get_by_role("button", name="Sign in").click()
            await user.get_by_role("tablist", name="Where the agent works").wait_for()
            users_visit = await user.evaluate(VISIT)

            # Signed out, the visit is over: the page asks again, and its token opens nothing.
            await user.get_by_role("button", name="Sign out").click()
            await user.get_by_role("heading", name="Sign in").wait_for()
            assert await user.evaluate(VISIT) is None
            assert await running.status("GET", "/api/sessions", users_visit) == 401
            await admin.get_by_role("button", name="Sign out").click()
            await admin.get_by_role("heading", name="Admin sign-in").wait_for()
            assert admin.url.endswith("/admin")
            await admin.get_by_label("Password").fill(ADMINS)
            await admin.get_by_role("button", name="Sign in").click()
            await admin.get_by_role("button", name="Systems").wait_for()
            assert admin_view.errors == [] and user_view.errors == []
        finally:
            await admin.close()
            await user.close()
