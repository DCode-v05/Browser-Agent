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


class DesktopOfTheBase(Section):
    geometry: str = setting("1440x900", "The contained desktop's screen, width by height in pixels")
    auto_start: bool = setting(
        False, "Whether a Linux machine with no screen starts the contained desktop on the first action"
    )
    min_free_memory_mb: int = setting(
        1536, "The free memory, in megabytes, below which the contained desktop refuses to start"
    )
    idle_stop_minutes: int = setting(
        30, "How long the contained desktop may stand unused before it is stopped. 0 never stops it"
    )
    placement: Literal["auto", "terminal", "gateway"] = setting(
        "auto", "Where the contained desktop lives: with the sandbox when there is one, or on this machine"
    )


class Base(Section):
    """What Hermes' computer use is set to (spec 22.8). The names on the right of each are Hermes' own."""

    capture_after_mode: Literal["som", "vision", "ax"] = setting(
        "som",
        "What a capture that follows an action holds: numbered picture, picture alone, or elements alone",
    )
    max_image_dimension: int = setting(
        1456, "The longest edge of a picture the driver returns, in pixels. 0 leaves it as it is"
    )
    ax_max_elements: int = setting(
        800,
        "How many elements the driver reads of one window at most. 0 sets no bound. Hermes' own is 200, "
        "which in an app with large menus ends before its page is reached",
    )
    delivery: Literal["auto", "background", "foreground"] = setting(
        "auto",
        "Whether the agent's input goes to a window in the background, leaving the person's pointer and "
        "window alone, or to the window in front. `auto`: in the background on a person's machine, and "
        "in front on a desktop nobody is at, the contained one and the micro VM's",
    )
    elements_shown: int = setting(
        60, "How many elements of a window a capture names in its text. The page comes before the menus"
    )
    permission_mode: Literal["standard", "bounded"] = setting(
        "bounded", "Whether the driver itself holds the agent to the allowed apps (`bounded`) or not"
    )
    capability_manifest: str = setting(
        "",
        "The file that says what the driver may touch, when the mode is `bounded`. Written from the allowed apps",
    )
    also_allowed: list[str] = setting(
        [],
        "More apps the agent may work in on a real machine, beside the ones switched on: a macOS bundle id, "
        "or a program's full path",
    )
    allowed_for: str = setting(
        "12h", "How long the driver keeps the list of allowed apps it was started with, such as `12h`"
    )
    allowed_idle: str = setting(
        "2h",
        "How long the driver may stand unused before that list ends, such as `2h`. A new session starts it again",
    )
    no_overlay: Literal["auto", "on", "off"] = setting(
        "auto",
        "Whether the driver's pointer overlay is left out. `auto` decides by the system, as Hermes does",
    )
    native_wayland: bool = setting(False, "On Linux: whether the driver uses a Wayland session directly")
    driver_telemetry: bool = setting(False, "Whether the driver may send its makers anonymous usage figures")
    allow_unsigned_driver: bool = setting(
        False,
        "On macOS: whether a driver that is not signed by its makers may be started. For their developers",
    )
    autostart: bool = setting(
        False,
        "On Windows: whether the driver's logon task is registered, for a machine driven with nobody signed in",
    )
    driver_command: str = setting(
        "", "Another driver to start in place of the pinned one, by its path or its name. For development"
    )
    home: str = setting(
        "~/.bap-browser/computer",
        "Where computer use keeps the driver it installed, its captures and who holds the screen",
    )
    install_timeout_s: float = setting(120.0, "Longest wait for the driver's download, when it is installed")
    register_timeout_s: float = setting(
        15.0, "On macOS: longest wait for the system to take note of the driver's app after it is installed"
    )
    helper_allow: list[str] = setting(
        ["tag:bap-vm"],
        "Who on the tailnet the helper on a person's machine lets in: Tailscale tags, or the logins of people",
    )
    helper_tailnet: bool = setting(
        True,
        "Whether the helper takes calls from the tailnet. Off, it takes them from its own machine alone",
    )
    helper_run_timeout_s: float = setting(30.0, "Longest wait for one command the helper runs of the driver")
    helper_message_bytes: int = setting(
        67108864, "The largest message the helper and its link carry, in bytes. A screenshot is in one"
    )
    pairing_bytes: int = setting(18, "How many random bytes the helper's pairing code is made of")
    whois_timeout_s: float = setting(5.0, "Longest wait for Tailscale to say who a caller is")
    ready_poll_s: float = setting(
        5.0, "How often the window looks whether a machine that lacked something is ready now"
    )
    virtual_screen: bool = setting(
        False,
        "Whether the engine starts this machine's own virtual screen before it drives it. For a machine "
        "with no screen that is itself the boundary: the micro VM",
    )
    manual: bool = setting(
        True, "Whether the model is given Hermes' own manual for the tool, after this engine's rules"
    )
    desktop: DesktopOfTheBase = DesktopOfTheBase()


class Computer(Section):
    runs: Literal["container", "here", "machine", "remote"] = setting(
        "container",
        "Where the desktop runs: in a container of its own, on this machine's own virtual screen "
        "(`here`, for a machine that is itself the boundary, such as the micro VM), on this machine's "
        "own screen through Hermes' driver, on Windows, macOS or Linux (`machine`), or on a person's "
        "machine elsewhere, a Mac among them, "
        "through the helper they run there and the tailnet (`remote`)",
    )
    helper_url: str = setting(
        "http://127.0.0.1:8796", "Where the helper on the person's Mac answers, when the desktop is `mac`"
    )
    helper_token_env: str = setting(
        "BAP_BROWSER_HELPER_TOKEN",
        "The variable, in the environment or in `.env`, that holds the token the helper printed",
    )
    helper_port: int = setting(8796, "The port the helper listens on, on the person's Mac")
    display: str = setting(":1", "The virtual screen's display, when the desktop runs here")
    image: str = setting(
        "bap-browser-desktop:latest",
        "The container image of the contained desktop. `deploy/desktop.Dockerfile` builds it",
    )
    container_command: str = setting("docker", "The program that runs containers")
    screen: Literal["1024x768", "1280x800", "1366x768"] = setting(
        "1280x800", "The desktop's screen, width by height in pixels. Sizes the vendors recommend for a model"
    )
    ask_before_apps: bool = setting(False, "Whether a person is asked before the agent opens an app")
    mac_any_app: bool = setting(
        False,
        "On the person's own Mac: whether the agent may open any app by its name. Each opening asks them first",
    )
    apps: AllowedApps = AllowedApps()
    base: Base = Base()
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
    settle_ms: int = setting(250, "How long the screen is given to change after an action, before it is read")
    app_open_wait_s: float = setting(8.0, "Longest wait for the window of an app that was opened")
    app_poll_ms: int = setting(200, "How often the desktop is asked whether that window is there")
    frame_ms: int = setting(400, "The pause between two looks at the screen for the live picture")
    window_title_chars: int = setting(80, "How much of a window's title a result holds")
    windows_listed: int = setting(12, "How many open windows a result names at most")

    @property
    def screen_width(self) -> int:
        return int(self.screen.split("x")[0])

    @property
    def screen_height(self) -> int:
        return int(self.screen.split("x")[1])
