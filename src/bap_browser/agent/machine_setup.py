"""Making a real machine ready for computer use, from the window (spec 22.10.1): what the page's two
buttons do, and the wait until the machine lacks nothing."""

from __future__ import annotations

import asyncio
import contextlib
import sys
from typing import Literal

from bap_browser import computer
from bap_browser.computer import commands, driver
from bap_browser.computer.hermes.computer_use import permissions
from bap_browser.config import Config

Step = Literal["install", "allow"]
NOT_THIS_MACHINE = 'Choose "This machine" under Where the agent works first.'
ONLY_MACOS = "Only macOS asks for this. On Windows and Linux there is nothing to allow."
NOT_ASKED = "macOS did not show its question. Run: bap-browser computer permissions grant"


def make_ready(config: Config, step: str) -> str | None:
    """Installs the driver, or has macOS ask the person to allow it. None when it was done;
    otherwise why not, in words for the person. It takes as long as a download takes."""
    if config.computer.runs != "machine":
        return NOT_THIS_MACHINE
    if step == "install":
        home = computer.home_of(config)
        try:
            binary = driver.installed(home) or driver.install(
                home, timeout_s=config.computer.base.install_timeout_s
            )
        except driver.DriverError as wrong:
            return str(wrong)
        return commands.not_ready(config, binary)
    if sys.platform != "darwin":
        return ONLY_MACOS
    with computer.base(config):
        return None if permissions.request_permissions_grant() == 0 else NOT_ASKED


async def until_ready(config: Config, asked_again: asyncio.Event) -> None:
    """Waits until the machine lacks nothing, or a person asks for a new session."""
    while not asked_again.is_set():
        if await asyncio.to_thread(computer.lacks, config) is None:
            return
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(asked_again.wait(), config.computer.base.ready_poll_s)
