"""The demonstration: a scripted model signs up on the demo site that ships with bap-browser.

It runs the same loop, the same tools and the same browser as a real model would. Only the
replies are fixed, so it needs no key and always does the same thing.
"""

from __future__ import annotations

from typing import Any

from bap_browser.agent.models import Reply, ScriptedModel, Step, ToolCall, ref_of

TASK = (
    "Sign up on the Northfield demo site as Ada Lovelace (ada@example.com), enter the verification "
    "code, and say what the account page shows."
)
WELCOME = 'heading "Welcome, Ada"'


def demo_script(site: str, pause_s: float = 0) -> ScriptedModel:
    """`site` is where the demo site is served. `pause_s` is how long each step waits, for a person watching."""
    calls = 0

    def call(tool: str, arguments: dict[str, Any], say: str = "") -> Reply:
        nonlocal calls
        calls += 1
        return Reply(say, (ToolCall(f"demo-{calls}", tool, arguments),))

    def on(element: str, tool: str, **arguments: Any) -> Step:
        return lambda page: call(tool, {"ref": ref_of(page, element), **arguments})

    def report(page: str) -> Reply:
        if WELCOME in page:
            return Reply('The account was created. The page now shows "Welcome, Ada" with 3 open invoices.')
        return Reply("The sign-up did not reach the welcome page.")

    return ScriptedModel(
        [
            lambda page: call(
                "browser_navigate", {"url": f"{site}/signup.html"}, "I will open the sign-up page."
            ),
            on('textbox "Full name"', "browser_type", text="Ada Lovelace"),
            on('textbox "Email"', "browser_type", text="ada@example.com"),
            on('textbox "Password"', "browser_type", text="correct horse battery"),
            on('checkbox "I accept the terms"', "browser_click"),
            on('button "Create account"', "browser_click"),
            lambda page: call("browser_snapshot", {}, "The form was sent. I will read the next page."),
            on('textbox "Verification code"', "browser_type", text="424242"),
            on('button "Continue"', "browser_click"),
            lambda page: call("browser_snapshot", {}),
            report,
        ],
        pause_s,
    )
