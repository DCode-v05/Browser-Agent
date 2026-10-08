"""`bap-browser doctor`: whether this machine has what bap-browser needs, and which browsers launch
here (spec 5.2).

It reads nothing it should not: of the model key it says only whether one is set.
"""

from __future__ import annotations

import sys
import tempfile
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Literal, get_args

from bap_browser import __version__
from bap_browser.config import Channel, Config

State = Literal["ok", "missing", "problem"]
"""`missing` is something this machine does not have and may not need: a browser that is not
installed, a key that only one command uses. `problem` is something that stops bap-browser."""

MARKS: dict[State, str] = {"ok": "ok ", "missing": "-- ", "problem": "NO "}
OLDEST_PYTHON = (3, 12)
# What a browser says when it is not on the machine, whichever browser it is.
NOT_INSTALLED = ("is not found at", "Executable doesn't exist", "is not installed")

Launch = Callable[[Config, str], Awaitable[str]]
"""Launches the browser of a channel, opens a page in it and closes it again. Returns the browser's
name and version. Raises when the browser cannot do that."""


@dataclass(frozen=True)
class Finding:
    state: State
    what: str
    detail: str = ""

    @property
    def line(self) -> str:
        return f"  {MARKS[self.state]} {self.what}" + (f": {self.detail}" if self.detail else "")


async def launch_and_open(config: Config, channel: str) -> str:
    """The real thing: the browser is started the way a session starts it, shows a page, and is closed."""
    # Imported here so that the other commands start without loading the browser library.
    from playwright.async_api import async_playwright

    from bap_browser.driver.browser_parts import launch_options

    browser_settings = config.browser.model_copy(
        update={"channel": channel, "headless": True, "cdp_url": None, "user_data_dir": None, "args": []}
    )
    options = launch_options(config.model_copy(update={"browser": browser_settings}), {})
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(**options)
        try:
            page = await browser.new_page()
            await page.goto("about:blank")
            return f"{_product(channel)} {browser.version}"
        finally:
            await browser.close()


def _product(channel: str) -> str:
    """The browser's name as people say it: `msedge-beta` is Edge Beta."""
    if channel in ("chromium", "custom"):
        return "Chromium"
    family, _, flavour = channel.partition("-")
    name = "Edge" if family == "msedge" else "Chrome"
    return f"{name} {flavour.capitalize()}" if flavour else name


async def examine(
    config: Config,
    sources: Mapping[str, str],
    env: Mapping[str, str],
    launch: Launch = launch_and_open,
) -> list[Finding]:
    """Everything the doctor looks at, in the order it is printed."""
    found = [_python(), Finding("ok", f"bap-browser {__version__}"), _configuration(sources)]
    found += await _browsers(config, launch)
    found += [_viewer(), _extension(), _data_dir(config), _model_key(config, env)]
    return found


def healthy(found: list[Finding]) -> bool:
    return all(finding.state != "problem" for finding in found)


def report(found: list[Finding]) -> str:
    problems = sum(finding.state == "problem" for finding in found)
    verdict = (
        "Everything bap-browser needs is in place."
        if not problems
        else f"{problems} thing{'' if problems == 1 else 's'} to put right (marked NO)."
    )
    return "\n".join(["bap-browser doctor", *(finding.line for finding in found), verdict])


def _python() -> Finding:
    version = ".".join(str(part) for part in sys.version_info[:3])
    if sys.version_info[:2] < OLDEST_PYTHON:
        wanted = ".".join(str(part) for part in OLDEST_PYTHON)
        return Finding("problem", f"Python {version}", f"{wanted} or newer is needed")
    return Finding("ok", f"Python {version}")


def _configuration(sources: Mapping[str, str]) -> Finding:
    if not sources:
        return Finding("ok", "Configuration", "every value is at its default")
    count = len(sources)
    return Finding(
        "ok",
        "Configuration",
        f"{count} value{'' if count == 1 else 's'} changed from the default "
        "(bap-browser config show --sources)",
    )


async def _browsers(config: Config, launch: Launch) -> list[Finding]:
    """The browser this configuration uses, which must launch; then every other one it could use."""
    in_use = config.browser.channel
    found: list[Finding] = []
    if config.browser.cdp_url:
        found.append(
            Finding("ok", "Browser in use", "one that is already running (browser.cdp_url); not started here")
        )
    else:
        found.append(await _try(config, in_use, launch, in_use=True))
    for channel in get_args(Channel):
        if channel == "custom" or (channel == in_use and not config.browser.cdp_url):
            continue
        found.append(await _try(config, channel, launch, in_use=False))
    return found


async def _try(config: Config, channel: str, launch: Launch, *, in_use: bool) -> Finding:
    what = f"Browser in use ({channel})" if in_use else f"Browser {channel}"
    if channel == "custom" and not config.browser.executable_path:
        return Finding("problem", what, "browser.executable_path is not set")
    try:
        return Finding("ok", what, f"{await launch(config, channel)} launched and opened a page")
    except Exception as failed:
        said = str(failed).splitlines()[0] if str(failed) else type(failed).__name__
        absent = any(sign in str(failed) for sign in NOT_INSTALLED)
        if not in_use:
            return Finding("missing", what, "not installed" if absent else f"did not launch: {said}")
        fix = (
            "it is not installed. Run: uv run playwright install chromium"
            if absent and channel == "chromium"
            else "it is not installed on this machine"
            if absent
            else f"it did not launch: {said}"
        )
        return Finding("problem", what, fix)


def _viewer() -> Finding:
    built = Path(str(files("bap_browser"))) / "viewer_dist" / "index.html"
    if built.is_file():
        return Finding("ok", "Viewer", "built")
    return Finding("problem", "Viewer", "not built. Run: npm --prefix viewer install, then run build")


def _extension() -> Finding:
    manifest = Path(str(files("bap_browser"))) / "extension" / "manifest.json"
    if manifest.is_file():
        return Finding("ok", "Extension for Chrome", "its files are here (--extension, --takeover)")
    return Finding("missing", "Extension for Chrome", "its files are not in this installation")


def _data_dir(config: Config) -> Finding:
    folder = Path(config.data_dir).expanduser()
    try:
        folder.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryFile(dir=folder):
            pass
    except OSError as failed:
        return Finding("problem", f"Data folder {folder}", f"cannot be written to: {failed.strerror}")
    return Finding("ok", f"Data folder {folder}", "can be written to")


def _model_key(config: Config, env: Mapping[str, str]) -> Finding:
    name = config.agent.api_key_env
    if env.get(name, "").strip():
        return Finding("ok", f"Model key {name}", "set")
    return Finding(
        "missing",
        f"Model key {name}",
        "not set. Only `bap-browser agent` without --demo needs it: put it in a file named .env",
    )
