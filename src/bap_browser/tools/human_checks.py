"""Pages that need a person (spec 8.4): a human check such as a CAPTCHA, or a sign-in.

The agent is never left to notice by itself. When what it reads shows one of these, the result says
so and says what to do: ask the person, and wait. The engine itself never tries such a step.
"""

from __future__ import annotations

import re

HUMAN_CHECK = re.compile(
    r"captcha|not a robot|human check|are you (a )?human|verify (that )?you(\s+are|.re) (a )?human",
    re.IGNORECASE,
)
SIGN_IN = re.compile(r"\b(sign in|sign-in|log in|log-in|login|signin)\b", re.IGNORECASE)
# The lines of a page that say what the page is for: its title, its headings and its buttons.
SAYS_WHAT_IT_IS = ("Page:", "- heading", "- button")
PASSWORD_FIELD = "type=password"

HUMAN_CHECK_NOTICE = (
    "[notice] This page has a human check (CAPTCHA). Do not try to pass it yourself: call "
    'browser_request_human with kind "verification", and go on when the person has done it.'
)
SIGN_IN_NOTICE = (
    "[notice] This page asks for a sign-in. Do not guess or make up a password: when the task needs "
    'the sign-in, call browser_request_human with kind "login", and go on when the person has done it.'
)


def notice_for(page: str) -> str:
    """What the agent is told about a page that needs a person, or nothing."""
    lines = page.split("\n")
    signs_in = any(PASSWORD_FIELD in line for line in lines) and any(
        SIGN_IN.search(line) for line in lines if line.lstrip().startswith(SAYS_WHAT_IT_IS)
    )
    if signs_in:
        # A sign-in page with a human check on it is one step for the person: signing in.
        return SIGN_IN_NOTICE
    return HUMAN_CHECK_NOTICE if HUMAN_CHECK.search(page) else ""
