"""The settings of computer use (spec 21.8), with their defaults.

They are part of the configuration: `config.py` holds them in `computer`. They are in a file of
their own because one file would be too long to read.
"""

from __future__ import annotations

from typing import Literal

from bap_browser.config_base import Section, setting


class AllowedApps(Section):
    text_editor: bool = setting(True, "Whether the agent may open the text editor")
    files: bool = setting(True, "Whether the agent may open the file manager")
    calculator: bool = setting(True, "Whether the agent may open the calculator")
    terminal: bool = setting(
        False, "Whether the agent may open the terminal. A terminal runs any command inside the desktop"
    )


class Computer(Section):
    runs: Literal["container", "here"] = setting(
        "container",
        "Where the desktop runs: in a container of its own, or on this machine's own virtual screen. "
        "`here` is for a machine that is itself the boundary, such as the micro VM",
    )
    display: str = setting(":1", "The virtual screen's display, when the desktop runs here")
    image: str = setting(
        "bap-browser-desktop:latest",
        "The container image of the contained desktop. `deploy/desktop.Dockerfile` builds it",
    )
    container_command: str = setting("docker", "The program that runs containers")
    screen_width: int = setting(1280, "Width of the desktop's screen, in pixels")
    screen_height: int = setting(800, "Height of the desktop's screen, in pixels")
    apps: AllowedApps = AllowedApps()
    network: bool = setting(False, "Whether the desktop may reach the network. Off: it has none at all")
    share_folder: bool = setting(
        True, "Whether a folder of this machine is shown in the desktop, as `Files` in its home folder"
    )
    folder: str = setting(
        "~/bap-browser-files",
        "The one folder of this machine the desktop can read and write, when `share_folder` is on. "
        "On a Mac, Docker may not reach Downloads, Documents or Desktop unless it is allowed to",
    )
    start_wait_s: float = setting(30.0, "Longest wait for the desktop's screen to be there after a start")
    command_timeout_s: float = setting(15.0, "Longest wait for one command sent into the desktop")
    type_delay_ms: int = setting(8, "The pause between two characters the agent types")
    settle_ms: int = setting(250, "How long the screen is given to change after an action, before it is read")
    app_open_wait_s: float = setting(8.0, "Longest wait for the window of an app that was opened")
    app_poll_ms: int = setting(200, "How often the desktop is asked whether that window is there")
    frame_ms: int = setting(400, "The pause between two looks at the screen for the live picture")
    frame_jpeg_quality: int = setting(60, "Quality of a picture of the live view")
    scroll_notches_per_step: int = setting(3, "Notches of the mouse wheel in one step of a scroll")
    drag_pause_ms: int = setting(120, "The pause between pressing, moving and letting go in a drag")
    mark_width: int = setting(
        160, "Width of the small picture by which it is told whether the screen has changed"
    )
    window_title_chars: int = setting(80, "How much of a window's title a result holds")
    windows_listed: int = setting(12, "How many open windows a result names at most")
