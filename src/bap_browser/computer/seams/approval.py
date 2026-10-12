"""Hermes' approval gate, answered by this engine: a person is asked through whoever was named to
ask (the viewer, in the service), and with nobody to ask the action is refused."""

from __future__ import annotations

from typing import Any

from bap_browser.computer.seams.state import current


def run_approval_gate(
    *, pattern_key: str, description: str, no_human_block_message: str = "", **more: Any
) -> dict[str, Any]:
    """Whether the person allows an action. `pattern_key` is `cua:<action>:<background or foreground>`.
    The sentence put to the person is the action's kind alone: what is typed is never in it."""
    action = pattern_key.split(":")[1] if pattern_key.count(":") >= 1 else pattern_key
    theirs = more.get("approval_callback")
    if callable(theirs):
        # Hermes' own way of naming who answers (`set_approval_callback`), which its tests use.
        answer = theirs(more.get("display_target", ""), description)
        if answer in ("once", "session", "always"):
            return {"approved": True}
        return {"approved": False, "message": f"BLOCKED: User denied `{action}`."}
    ask = current().ask
    if ask is None:
        return {"approved": False, "message": no_human_block_message or "Nobody is there to allow it."}
    if ask(action, description):
        return {"approved": True}
    return {"approved": False, "message": f"BLOCKED: User denied `{action}`."}


def is_approval_bypass_active_for_session(session: str) -> bool:
    """Hermes can be told to ask nobody. This engine cannot."""
    return False


def get_current_session_key(default: str = "") -> str:
    return default
