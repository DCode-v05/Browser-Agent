"""What the copied code is working for at the moment: a configuration, a folder, and who to ask."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from bap_browser.config_computer import Computer

# Asked before an action that changes something: the action's name and a sentence about it.
Asker = Callable[[str, str], bool]


@dataclass
class Working:
    computer: Computer = field(default_factory=Computer)
    home: Path = field(default_factory=lambda: Path.home() / ".bap-browser" / "computer")
    # A backend to use in place of the driver: a stand-in, in tests.
    backend: Callable[[], Any] | None = None
    ask: Asker | None = None


class Holder:
    now = Working()


def current() -> Working:
    return Holder.now


def work_for(working: Working) -> Working:
    """Sets what the copied code works for. Returns what it worked for before."""
    before, Holder.now = Holder.now, working
    return before
