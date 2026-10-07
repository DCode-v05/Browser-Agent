"""Every setting and its default.

A deployment overrides values with config.json, then environment variables, then per-session
options. No tunable value is written anywhere else in the code.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, ValidationError, field_validator

from bap_browser.errors import ConfigError
from bap_browser.policy.address import site_pattern

ENV_PREFIX = "BAP_BROWSER__"
CONFIG_PATH_ENV = "BAP_BROWSER_CONFIG"
DEFAULT_CONFIG_FILE = "config.json"
SESSION_KEYS = frozenset(
    {
        "backend.kind",
        "browser.channel",
        "browser.headless",
        "browser.viewport",
        "browser.user_data_dir",
        "browser.cdp_url",
    }
)

Channel = Literal[
    "chromium",
    "chrome",
    "chrome-beta",
    "chrome-dev",
    "chrome-canary",
    "msedge",
    "msedge-beta",
    "msedge-dev",
    "msedge-canary",
    "custom",
]
ActionPolicy = Literal["allow", "confirm", "deny"]


class Section(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def setting(default: Any, meaning: str) -> Any:
    """A setting with its default and the sentence the generated reference shows for it."""
    return Field(default=default, description=meaning)


class Backend(Section):
    kind: Literal["remote_headless"] = setting("remote_headless", "The backend a new session uses")
    offered: list[Literal["remote_headless"]] = setting(
        ["remote_headless"], "The backends a person may choose from on this deployment"
    )


class Viewport(Section):
    width: int = setting(1280, "Page width in CSS pixels")
    height: int = setting(800, "Page height in CSS pixels")


class Geolocation(Section):
    latitude: float
    longitude: float


class Proxy(Section):
    server: str | None = setting(None, "Static proxy; its user and password come from the environment")
    bypass: str | None = setting(None, "Hosts that skip the proxy, separated by commas")


class Timeouts(Section):
    launch_ms: int = setting(30000, "Launch or attach")
    navigation_ms: int = setting(30000, "A navigation")
    action_ms: int = setting(10000, "One action, including waiting for the element")
    load_wait_ms: int = setting(5000, "Longest wait for the load event after a navigation")
    settle_ms: int = setting(3000, "Longest wait for the page to settle after an action")
    frame_ms: int = setting(
        100, "Longest wait for the next animation frame, on a page that is not being painted"
    )
    page_reply_ms: int = setting(
        5000, "Longest wait for the page to answer. A page too busy to answer fails the call"
    )
    popup_adopt_ms: int = setting(3000, "Longest wait for a new tab to load before it is reported")
    change_wait_ms: int = setting(
        300, "Longest wait for the page to say, after a step, whether anything in it changed"
    )
    wait_max_s: int = setting(30, "Ceiling for `browser_wait`")
    idle_session_s: int = setting(900, "Close a session unused for this long; 0 means never")


class Snapshot(Section):
    default_mode: Literal["interactive", "all"] = setting("interactive", "Or `all`")
    max_chars: int = setting(20000, "Output cap")
    max_depth: int = setting(60, "Nesting cap")
    max_name_chars: int = setting(120, "Longest accessible name")
    max_value_chars: int = setting(200, "Longest value")
    max_text_chars: int = setting(300, "Longest line of text")
    max_options: int = setting(25, "Options listed for a dropdown")
    max_frame_depth: int = setting(4, "Nested frames read")
    include_iframes: bool = setting(True, "Read frames")
    include_shadow_dom: bool = setting(True, "Read open shadow roots")
    include_bboxes: bool = setting(False, "Add each element's box")
    after_navigation: bool = setting(True, "Navigation tools return a snapshot")
    after_action: bool = setting(False, "Action tools return a snapshot")


class Screenshot(Section):
    format: Literal["png", "jpeg"] = setting("png", "Or `jpeg`")
    jpeg_quality: int = setting(80, "Quality when the format is jpeg")
    max_dimension: int = setting(1568, "Longest side sent to the model")
    full_page: bool = setting(False, "Default area")
    annotate_by_default: bool = setting(False, "Draw ref labels")


class Text(Section):
    max_chars: int = setting(20000, "Cap for `browser_get_text`")


class Find(Section):
    default_limit: int = setting(10, "Matches returned")
    max_limit: int = setting(50, "Most matches a call may ask for")


class Capture(Section):
    console: bool = setting(True, "Keep the console log")
    network: bool = setting(True, "Keep the network log")
    max_console_entries: int = setting(500, "Per tab")
    max_network_entries: int = setting(500, "Per tab")
    max_entry_chars: int = setting(2000, "Per message")
    read_limit: int = setting(50, "Most entries one call of `browser_console` or `browser_network` returns")
    max_state_events: int = setting(
        20, "What happened in the browser by itself is told in the next result: the newest so many"
    )


class Tabs(Section):
    max_tabs: int = setting(20, "Most tabs open at once")
    focus_new_tabs: bool = setting(True, "Switch to pop-ups")


class Dialogs(Section):
    policy: Literal["agent", "auto_accept", "auto_dismiss"] = setting(
        "agent", "Or `auto_accept`, `auto_dismiss`"
    )
    timeout_s: int = setting(120, "Then dismissed")
    default_prompt_text: str = setting("", "For auto-accepted prompts")


class Downloads(Section):
    enabled: bool = setting(True, "Let the agent download files")
    dir: str = setting(".bap-browser/downloads", "Where downloads are saved")
    max_size_mb: int = setting(500, "Larger downloads are cancelled")


class Uploads(Section):
    enabled: bool = setting(True, "Let the agent upload files")
    allowed_dirs: list[str] = setting([".bap-browser/uploads"], "Empty means uploads are blocked")


class JavaScript(Section):
    allow_evaluate: bool = setting(False, "Offer `browser_evaluate`")
    max_result_chars: int = setting(20000, "Cap for a script's result")


class Input(Section):
    scroll_step_px: int = setting(400, "One scroll step")
    type_delay_ms: int = setting(0, "Per key when typing normally")
    slow_type_delay_ms: int = setting(40, "Per key with `slowly`")
    drag_steps: int = setting(15, "Pointer moves in a drag")
    key_repeat_max: int = setting(100, "Most repeats of one key press")


class Browser(Section):
    channel: Channel = setting("chromium", "See section 5.2")
    executable_path: str | None = setting(None, "Required for `custom`; overrides any channel")
    headless: bool = setting(True, "Run without a window")
    chromium_sandbox: bool = setting(
        True, "Chromium's own sandbox. Turned off only inside a micro VM that cannot support it"
    )
    cdp_url: str | None = setting(None, "Attach to a running or remote browser instead of launching")
    cdp_target: str | None = setting(
        None,
        "With `cdp_url`: the page to drive is the one whose address holds this. None means the first page",
    )
    user_data_dir: str | None = setting(
        None, "Persistent profile folder; none means a fresh profile each session"
    )
    kept_profile_dir: str = setting(
        "~/.bap-browser/browser-profile",
        "The profile folder used when a profile must be kept and `user_data_dir` names none. Keep it short",
    )
    args: list[str] = setting([], "Extra launch flags")
    ignore_default_args: list[str] = setting([], "Default launch flags to drop")
    viewport: Viewport | None = setting(Viewport(), "`null` means sized to the window")
    device_scale_factor: float | None = setting(None, "High-density emulation")
    user_agent: str | None = setting(None, "Emulation; none means the browser's own")
    locale: str | None = setting(None, "Emulation; none means the browser's own")
    timezone_id: str | None = setting(None, "Emulation; none means the browser's own")
    color_scheme: Literal["light", "dark", "no-preference"] | None = setting(
        None, "Emulation; none means the browser's own"
    )
    geolocation: Geolocation | None = setting(None, "`{latitude, longitude}`")
    permissions: list[str] = setting([], "Permissions granted in advance")
    extra_http_headers: dict[str, str] = setting({}, "Added to every request")
    ignore_https_errors: bool = setting(False, "Accept bad certificates (development only)")
    javascript_enabled: bool = setting(True, "Page scripts on or off")
    proxy: Proxy = Proxy()
    timeouts: Timeouts = Timeouts()
    snapshot: Snapshot = Snapshot()
    screenshot: Screenshot = Screenshot()
    text: Text = Text()
    find: Find = Find()
    capture: Capture = Capture()
    tabs: Tabs = Tabs()
    dialogs: Dialogs = Dialogs()
    downloads: Downloads = Downloads()
    uploads: Uploads = Uploads()
    javascript: JavaScript = JavaScript()
    input: Input = Input()


class AutoMode(Section):
    offered: bool = setting(False, "Whether a person may choose `auto` for `safety.ask_before`")
    refusals_in_a_row: int = setting(3, "Refusals by the check in a row after which Auto Mode pauses")
    refusals_per_session: int = setting(20, "Refusals by the check in one session after which it pauses")
    steps_shown: int = setting(12, "The earlier steps the check's model is given")
    earlier_tasks_shown: int = setting(3, "The earlier messages of the person the check's model is given")
    allow_once_s: int = setting(300, 'How long "Allow once" holds for the step it was pressed for')


class Safety(Section):
    allowed_domains: list[str] = setting([], "Empty means every site that is not blocked")
    blocked_domains: list[str] = setting([], "A block always wins")
    allowed_schemes: list[str] = setting(["http", "https", "about", "data", "blob"], "URL schemes")
    allow_file_urls: bool = setting(False, "Let the agent open local files")
    block_private_networks: bool = setting(False, "Set `true` for cloud")
    block_cloud_metadata: bool = setting(True, "Refuse cloud metadata addresses")
    enforce_on_subresources: bool = setting(False, "Also check images, scripts and requests")
    policy_cache_s: int = setting(5, "How long a per-host decision is reused")
    default_action_policy: ActionPolicy = setting("allow", "For tools not listed")
    action_policies: dict[str, ActionPolicy] = setting(
        {"browser_evaluate": "confirm", "browser_upload_file": "confirm"}, "Per tool"
    )
    ask_before: Literal["risky", "every_action", "auto"] = setting(
        "risky",
        "`every_action` also makes every tool that acts on a page `confirm`. With `auto` a check "
        "decides each step, and a person is asked only about the risky ones (section 18.4)",
    )
    auto_mode: AutoMode = AutoMode()
    redact_patterns: list[str] = setting([], "Regular expressions scrubbed from every result")

    @field_validator("allowed_domains", "blocked_domains", mode="after")
    @classmethod
    def _sites_that_can_match(cls, sites: list[str]) -> list[str]:
        """An entry that could never match would leave a site unblocked without anyone noticing."""
        for index, entry in enumerate(sites):
            try:
                site_pattern(entry)
            except ValueError as exc:
                raise ValueError(f"entry {index + 1} ({entry!r}): {exc}") from None
        return sites


class Permissions(Section):
    mode: Literal["act_on_allowed_sites", "ask_before_acting"] = setting(
        "act_on_allowed_sites", "Or `ask_before_acting`. See section 8.8"
    )
    default_site_permission: Literal["ask", "block"] = setting(
        "ask", "For a site the person has not decided on. Or `block`"
    )
    blocked_sites: list[str] = setting([], "Sites the bridge always refuses. A person cannot remove from it")
    consequential_words: list[str] = setting(
        [
            "pay",
            "buy",
            "order",
            "purchase",
            "checkout",
            "subscribe",
            "send",
            "delete",
            "remove",
            "transfer",
            "confirm",
            "publish",
            "authorize",
            "authorise",
            "grant",
        ],
        "A control whose name holds one of these makes the action consequential",
    )
    preview_timeout_s: int = setting(120, "Then a preview is cancelled")


class Control(Section):
    hold_timeout_s: int = setting(
        300, "How long an agent's call waits while a person is in control or the session is paused"
    )
    approval_timeout_s: int = setting(180, "Then a pending approval is denied")
    approval_timeout_choices_s: list[int] = setting([60, 180, 300, 600], "The waits a person may choose from")
    handoff_timeout_s: int = setting(900, "Then a request for a person returns `timed_out`")
    approval_without_viewer: Literal["deny", "allow"] = setting("deny", "Or `allow`")
    site_grant_lifetime: Literal["session", "none"] = setting(
        "session", 'How long "Allow on this site" lasts. `none` means it is not remembered'
    )


class Sessions(Section):
    max_concurrent: int = setting(4, "Most sessions open at once")


class Server(Section):
    host: str = setting("127.0.0.1", "The interface to listen on")
    public_url: str | None = setting(None, "The address clients use to reach the service in the micro VM")
    port: int = setting(8765, "`bap-browser mcp` uses a free port instead")
    token_env: str = setting("BAP_BROWSER_TOKEN", "If unset, a token is generated at start")
    state_file: str = setting(".bap-browser/service.json", "Holds the viewer address for the local user")
    extension_dir: str = setting(
        "bap-browser-extension",
        "Where the extension for Chrome is put, for a person to load it from. Not a hidden folder: "
        "the browser's file chooser must show it",
    )
    desktop_dir: str = setting(
        "desktop", "The folder of the desktop app, for the window of three browsers to open it from"
    )
    desktop_close_wait_s: int = setting(5, "How long the desktop app is given to close before it is ended")
    auth_wait_s: int = setting(10, "How long a new viewer connection may take to send its token")
    shutdown_wait_s: int = setting(3, "How long stopping waits for open connections to finish")
    command_backlog: int = setting(
        256, "How many of a viewer's commands may wait their turn. More than that are dropped"
    )


class Bridge(Section):
    pairing_ttl_s: int = setting(120, "How long a pairing token can be used")
    heartbeat_s: int = setting(15, "How often a bridge reports that it is alive")
    dead_after_s: int = setting(45, "A channel silent for this long is closed")
    op_timeout_ms: int = setting(15000, "One driver operation")
    reconnect_grace_s: int = setting(30, "How long a tool call waits for a bridge that is reconnecting")
    max_message_mb: int = setting(16, "Largest message accepted on the channel")


class Mcp(Section):
    server_name: str = setting("bap-browser", "The name agents see")
    http_path: str = setting("/mcp", "Where MCP over HTTP is served")


class QualityLevel(Section):
    max_fps: int
    jpeg_quality: int
    max_width: int


class QualityLevels(Section):
    standard: QualityLevel = setting(
        QualityLevel(max_fps=24, jpeg_quality=70, max_width=1280),
        "Upper limit on frames sent, frame quality and frame width",
    )
    data_saver: QualityLevel = setting(
        QualityLevel(max_fps=8, jpeg_quality=50, max_width=800), "For a slow or metered connection"
    )
    high: QualityLevel = setting(
        QualityLevel(max_fps=30, jpeg_quality=85, max_width=1600), "For a fast connection"
    )


class Takeover(Section):
    release_chord: str = setting("Ctrl+Alt+Enter", "Keys that leave the live frame")


class Viewer(Section):
    quality: Literal["standard", "data_saver", "high"] = setting(
        "standard", "Which level the live picture uses"
    )
    quality_levels: QualityLevels = QualityLevels()
    history_events: int = setting(500, "Replayed when a viewer connects")
    stale_after_s: int = setting(5, 'When "Live" becomes the stale notice')
    idle_divider_s: int = setting(10, "Gap that becomes an idle divider")
    picture_heartbeat_s: int = setting(2, "How often the service confirms a still picture is current")
    takeover: Takeover = Takeover()
    theme: Literal["system", "light", "dark"] = setting("system", "Or `light`, `dark`")
    embed_origins: list[str] = setting(
        [], "Pages allowed to show the viewer inside themselves, and to open its WebSocket"
    )
    pointer_hold_ms: int = setting(
        600, "How long the outline and the click mark stay after the agent has acted, in milliseconds"
    )
    show_agent_pointer: bool = setting(
        True, "Draw the target highlight and the agent's pointer over the live picture"
    )


class Agent(Section):
    provider: Literal["openai", "scripted"] = setting(
        "openai", "Whose model the loop calls. `scripted` replays fixed replies and needs no key"
    )
    model: str = setting("gpt-5.6-luna", "The model's name at that provider")
    offered_models: list[str] = setting(
        [], "Other models at that provider that a person may choose in the settings screen"
    )
    input_price_per_million: float = setting(
        0.0,
        "What a million tokens sent to the model cost, in US dollars. 0 means not known: no cost is shown",
    )
    output_price_per_million: float = setting(
        0.0, "What a million tokens the model wrote cost, in US dollars. 0 means not known"
    )
    api_key_env: str = setting(
        "OPENAI_API_KEY",
        "The variable, in the environment or in `.env`, that holds the key. The key is never in `config.json`",
    )
    base_url: str = setting(
        "https://api.openai.com/v1",
        "Where the provider's API is. Change it for a proxy or a compatible service",
    )
    request_timeout_s: int = setting(120, "Longest wait for one reply from the model")
    retries: int = setting(2, "Further tries of a call to the model that failed")
    max_steps: int = setting(40, "Tool calls after which the loop stops")
    max_tokens: int = setting(4096, "The most a single reply may be")
    max_task_chars: int = setting(4000, "Longest task a person may send from the viewer's chat")

    @field_validator("base_url", mode="after")
    @classmethod
    def _a_web_address(cls, address: str) -> str:
        if not address.startswith(("https://", "http://")):
            raise ValueError("write the address with https:// in front")
        return address


class CheckModel(Section):
    name: str = setting("", "The model of the reviewer and the scan. Empty means `agent.model`")
    timeout_s: int = setting(8, "Longest wait for one answer. A step waits for it")
    max_tokens: int = setting(1500, "The most one answer may be, its reasoning counted")
    reasoning_effort: Literal["", "none", "minimal", "low", "medium", "high"] = setting(
        "low", "How much the model thinks before it answers. Empty sends no such setting"
    )
    retries: int = setting(1, "Further tries of a failed call")
    backoff_base_ms: int = setting(500, "The wait before the second try. It doubles with each try")
    backoff_max_ms: int = setting(8000, "The longest wait between two tries")
    retry_after_max_s: int = setting(30, "The longest wait the provider may ask for")
    breaker_failures: int = setting(3, "Failed calls in a row after which no call is made for a while")
    breaker_cooldown_s: int = setting(60, "How long no call is made then")
    input_price_per_million: float | None = setting(
        None, "What a million tokens sent to this model cost. None means the agent's price"
    )
    output_price_per_million: float | None = setting(
        None, "What a million tokens this model wrote cost. None means the agent's price"
    )


class ReviewerShown(Section):
    name_chars: int = setting(80, "How much of a control's name the check's model is given")
    typed_chars: int = setting(200, "How much of the text a step types")
    address_chars: int = setting(300, "How much of an address")
    sample_chars: int = setting(80, "How much of text that was copied from another site")


class Actions(Section):
    pays: list[str] = setting(
        [
            "pay",
            "pays",
            "paying",
            "payment",
            "buy",
            "buying",
            "purchase",
            "order",
            "checkout",
            "check out",
            "place order",
            "book now",
            "reserve",
            "donate",
            "subscribe",
            "transfer",
            "top up",
            "भुगतान",
            "खरीदें",
            "ऑर्डर करें",
            "बुक करें",
        ],
        "A control whose name holds one of these pays",
    )
    sends: list[str] = setting(
        [
            "send",
            "sent",
            "sending",
            "post",
            "submit",
            "publish",
            "tweet",
            "भेजें",
            "पोस्ट करें",
            "जमा करें",
            "सबमिट",
        ],
        "A control whose name holds one of these sends something to other people",
    )
    deletes: list[str] = setting(
        [
            "delete",
            "deleting",
            "remove",
            "erase",
            "discard",
            "clear all",
            "cancel order",
            "unsubscribe",
            "deactivate",
            "close account",
            "हटाएं",
            "हटाएँ",
            "मिटाएं",
            "रद्द करें",
        ],
        "A control whose name holds one of these deletes",
    )
    grants: list[str] = setting(
        ["authorize", "authorise", "grant", "grant access", "allow access"],
        "A control whose name holds one of these gives access",
    )
    commits: list[str] = setting(
        ["confirm", "finish", "complete", "proceed", "पुष्टि करें"],
        "A control whose name holds one of these makes something final",
    )
    message_words: list[str] = setting(
        ["message", "comment", "reply", "review", "post", "body", "subject", "to", "recipient"],
        "A field whose name or label holds one of these is a message box",
    )


class TaskLimits(Section):
    max_chars: int = setting(2000, "The longest task `browser_begin_task` takes")
    max_sites: int = setting(20, "The most sites it takes")


class Incoming(Section):
    unseen_text: bool = setting(True, "Leave out text a person cannot see")
    min_opacity: float = setting(0.05, "Text at or below this opacity is unseen")
    min_font_px: float = setting(3, "Text in a smaller font is unseen")
    min_contrast: float = setting(1.15, "Text whose colour is this close to its background is unseen")
    contrast: bool = setting(True, "The colour test. Off when the snapshot's budget does not allow it")
    screen_reader_max_chars: int = setting(
        200, "Text that is only clipped, as sites do for screen readers, is kept up to this length"
    )
    strip_invisible: bool = setting(True, "Take out characters nobody can see")
    hidden_message_chars: int = setting(8, "So many such characters in one result are a hidden message")
    fragment_max_chars: int = setting(64, "The longest end of an address, after `#`, that is shown")
    query_value_max_chars: int = setting(120, "The longest value in an address's query that is shown")
    mark_page_text: bool = setting(True, "Put what a page wrote between marks in every result")
    name_chars: int = setting(80, "How much of a name a page wrote is shown inside one of the engine's lines")
    scan: Literal["off", "local", "local_then_model"] = setting(
        "local_then_model",
        "Read page text for planted instructions: not at all, by fixed rules, or by fixed rules and "
        "then a model for what they flag",
    )
    max_passages: int = setting(5, "The most passages of one result that go to the model")
    passage_chars: int = setting(600, "The longest passage")


class Outgoing(Section):
    sensitive_fields: bool = setting(True, "Ask before typing a password, a card number or a code")
    sensitive_words: dict[str, list[str]] = setting(
        {
            "password": ["password", "passcode", "passphrase"],
            "card": ["card number", "cvv", "cvc", "security code"],
            "code": ["one-time code", "verification code", "otp", "pin", "mpin", "upi pin", "atm pin"],
            "identity": [
                "social security",
                "ssn",
                "aadhaar",
                "aadhar",
                "pan number",
                "pan card",
                "iban",
                "routing number",
                "account number",
            ],
        },
        "A field whose name or label holds one of these, as whole words, is sensitive. By kind",
    )
    cross_site_text: bool = setting(True, "Notice text that was read on one site and goes to another")
    min_chars: int = setting(24, "The shortest copied text that counts")
    run_chars: int = setting(12, "The length of the runs a copy is found by")
    filter_bits: int = setting(1_048_576, "The size of the memory of one site, in bits")
    filter_hashes: int = setting(4, "How many places of that memory one run marks")
    remember_chars_per_site: int = setting(250_000, "After so much text a site's memory begins again")
    remember_sites: int = setting(16, "The most sites remembered, the newest kept")
    secrets_per_site: int = setting(2000, "The most short secrets remembered for one site")
    decode_min_chars: int = setting(12, "The shortest run of Base64 or hexadecimal that is unpacked")
    question_chars: int = setting(300, "How much of the text that would leave the person is shown")
    long_address_chars: int = setting(200, "An address whose path and query are longer than this is long")
    grant_access: bool = setting(True, "Ask before agreeing to give an app access to an account")
    consent_addresses: list[str] = setting(
        [
            "accounts.google.com/o/oauth2/*",
            "accounts.google.com/signin/oauth*",
            "login.microsoftonline.com/*/oauth2/*authorize*",
            "login.live.com/oauth20_authorize*",
            "appleid.apple.com/auth/authorize*",
            "github.com/login/oauth/authorize*",
            "www.facebook.com/*dialog/oauth*",
            "slack.com/oauth/*",
            "*.okta.com/oauth2/*",
            "*.auth0.com/authorize*",
        ],
        "Where the screens are on which an app is given access: host and path, `*` for anything",
    )


class ArrivingFiles(Section):
    risky_extensions: list[str] = setting(
        [
            "exe",
            "msi",
            "msix",
            "appx",
            "bat",
            "cmd",
            "com",
            "scr",
            "pif",
            "ps1",
            "vbs",
            "js",
            "jse",
            "wsf",
            "hta",
            "lnk",
            "reg",
            "jar",
            "apk",
            "dmg",
            "pkg",
            "app",
            "deb",
            "rpm",
            "sh",
            "iso",
            "img",
            "cab",
            "docm",
            "xlsm",
            "pptm",
        ],
        "A downloaded file with one of these endings is never kept",
    )
    ask_extensions: list[str] = setting(
        ["zip", "rar", "7z", "tar", "gz", "tgz", "bz2", "xz", "html", "htm", "xhtml", "mht", "mhtml", "svg"],
        "A downloaded file with one of these endings is asked about on every backend",
    )
    ask: Literal["own_machine", "never", "always"] = setting(
        "own_machine",
        "Which downloads a person is asked about: those on their own machine, none, or every one",
    )


class Money(Section):
    max_amount: float = setting(0, "The most one paying step may show. 0 means no cap")
    max_session_total: float = setting(0, "The most the approved paying steps of a session may add up to")
    currency: str = setting("", "The currency the caps are in, as a three-letter code. Empty means any")


class AbuseCh(Section):
    enabled: bool = setting(False, "Ask abuse.ch whether a host or a file is known to be bad")
    key_env: str = setting("ABUSE_CH_AUTH_KEY", "The variable that holds the key for abuse.ch")
    timeout_s: int = setting(2, "Longest wait for its answer")


class Rdap(Section):
    enabled: bool = setting(False, "Ask a domain's registry when the domain was registered")
    young_days: int = setting(30, "A domain younger than this is noticed")
    timeout_s: int = setting(2, "Longest wait for its answer")


class SensitiveSites(Section):
    money: list[str] = setting(
        [
            "paypal.com",
            "stripe.com",
            "wise.com",
            "chase.com",
            "bankofamerica.com",
            "wellsfargo.com",
            "hdfcbank.com",
            "icicibank.com",
            "onlinesbi.sbi",
            "axisbank.com",
            "paytm.com",
            "phonepe.com",
            "coinbase.com",
            "binance.com",
            "zerodha.com",
        ],
        "Banks, payment services, brokers and exchanges",
    )
    identity: list[str] = setting(
        [
            "accounts.google.com",
            "myaccount.google.com",
            "login.microsoftonline.com",
            "login.live.com",
            "account.microsoft.com",
            "appleid.apple.com",
            "account.apple.com",
        ],
        "Sign-in and account pages of the large providers",
    )
    health: list[str] = setting(["healthcare.gov", "nhs.uk", "abdm.gov.in"], "Health services")
    government: list[str] = setting(
        [
            "irs.gov",
            "ssa.gov",
            "login.gov",
            "gov.uk",
            "incometax.gov.in",
            "uidai.gov.in",
            "digilocker.gov.in",
            "passportindia.gov.in",
        ],
        "Government services",
    )


class SiteChecks(Section):
    lookalike: bool = setting(True, "Notice a site whose name looks like a protected name")
    mixed_script: bool = setting(True, "Notice a site whose name is written with look-alike letters")
    ip_hosts: bool = setting(True, "Notice a site that is a bare public IP address")
    protected: list[str] = setting(
        [
            "google.com",
            "gmail.com",
            "youtube.com",
            "microsoft.com",
            "outlook.com",
            "office.com",
            "apple.com",
            "icloud.com",
            "amazon.com",
            "amazon.in",
            "paypal.com",
            "facebook.com",
            "instagram.com",
            "whatsapp.com",
            "linkedin.com",
            "twitter.com",
            "netflix.com",
            "github.com",
            "dropbox.com",
            "yahoo.com",
            "adobe.com",
            "docusign.com",
            "stripe.com",
            "coinbase.com",
            "binance.com",
            "chase.com",
            "wellsfargo.com",
            "bankofamerica.com",
            "hdfcbank.com",
            "icicibank.com",
            "axisbank.com",
            "paytm.com",
            "phonepe.com",
            "flipkart.com",
            "irctc.co.in",
            "fedex.com",
        ],
        "The names a look-alike is measured against, besides the task's own sites",
    )
    lure_words: list[str] = setting(
        [
            "login",
            "signin",
            "sign-in",
            "logon",
            "secure",
            "security",
            "verify",
            "verification",
            "account",
            "update",
            "support",
            "billing",
            "payment",
            "wallet",
            "auth",
            "confirm",
            "recover",
            "unlock",
            "bank",
            "help",
        ],
        "A protected name in a host is a lure when one of these stands beside it",
    )
    common_words: list[str] = setting(
        [
            "apply",
            "ample",
            "maple",
            "goggle",
            "paypay",
            "strip",
            "stride",
            "strive",
            "stripes",
            "chose",
            "chasm",
            "cease",
            "phase",
            "chaise",
            "amazing",
            "adore",
            "abode",
            "fedora",
            "flipcart",
            "twitch",
        ],
        "Names that sit one letter from a protected name and are never taken for a look-alike",
    )
    sensitive: SensitiveSites = SensitiveSites()
    cache_s: int = setting(3600, "How long an answer about a site is kept")
    abuse_ch: AbuseCh = AbuseCh()
    rdap: Rdap = Rdap()


class Safeguards(Section):
    model: CheckModel = CheckModel()
    reviewer: ReviewerShown = ReviewerShown()
    actions: Actions = Actions()
    task: TaskLimits = TaskLimits()
    incoming: Incoming = Incoming()
    outgoing: Outgoing = Outgoing()
    downloads: ArrivingFiles = ArrivingFiles()
    money: Money = Money()
    sites: SiteChecks = SiteChecks()


class Limits(Section):
    max_calls: int = setting(500, "Tool calls in one task, or in a session with no task. 0 means no limit")
    max_task_minutes: int = setting(60, "Minutes one task may take. 0 means no limit")
    max_calls_per_minute: int = setting(120, "Tool calls in one minute. 0 means no limit")
    rate_wait_s: int = setting(10, "How long a call waits for the minute to allow it before it is refused")
    max_model_spend_usd: float = setting(
        0, "What the engine's own model calls may cost in one session, in US dollars. 0 means no limit"
    )
    extend_calls: int = setting(100, 'The steps "Allow more" adds')
    extend_minutes: int = setting(15, 'The minutes "Allow more" adds')
    repeat_notice: int = setting(3, "The same step with nothing changed: the time the agent is told")
    repeat_refuse: int = setting(6, "The same step with nothing changed: the time it is not run")
    unanswered_in_a_row: int = setting(
        3, "Questions that ran out unanswered in a row, after which further ones are refused at once"
    )


class Settings(Section):
    file: str = setting(".bap-browser/settings.json", "Where a person's saved settings are kept")
    locked: list[str] = setting([], "Settings a person cannot change")


class Logging(Section):
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = setting("INFO", "Log level")
    event_log: str | None = setting(".bap-browser/events.jsonl", "One line per tool call; `null` disables")
    log_tool_args: bool = setting(
        True, "Arguments are logged with typed text and form values replaced by their length"
    )
    max_result_chars: int = setting(2000, "Result excerpt kept per line")
    systems_dir: str = setting(
        ".bap-browser/logs", "Where each browser of the three-browser window writes a log of its own"
    )
    shown_lines: int = setting(200, "The most lines of a log the window shows at once")
    retention_days: int = setting(
        30, "Lines of the logs and records older than this are removed. 0 keeps everything"
    )


class Code(Section):
    enabled: bool = setting(
        False,
        "Offer `browser_run`, which runs a script the agent writes. Off until the core runs in its "
        "micro VM: that is the boundary a script cannot cross, and the check before a script runs is not",
    )
    timeout_s: int = setting(
        60, "How long a script may compute. The time its steps take in the browser is not counted"
    )
    max_timeout_s: int = setting(300, "The longest `timeout_s` a call may ask for")
    max_steps: int = setting(50, "The steps in the browser one script may do")
    max_output_chars: int = setting(12000, "What a script printed, and its value, are each cut to this")
    max_code_chars: int = setting(20000, "The longest script that is taken")
    max_message_chars: int = setting(
        1_000_000, "The most a script may hand the core at once: the arguments of one step, or its result"
    )
    max_memory_mb: int = setting(512, "What the worker may hold, on a system that enforces such a limit")


class Auth(Section):
    file: str = setting(
        ".bap-browser/accounts.json", "Where the sign-in passwords are kept, as salted hashes"
    )
    min_chars: int = setting(8, "The shortest password that is taken")
    max_chars: int = setting(200, "The longest password that is taken")
    session_hours: int = setting(12, "How long a sign-in lasts")
    max_failures: int = setting(5, "Wrong passwords in a row before sign-in is held back")
    lock_s: int = setting(60, "How long sign-in is held back then, in seconds")


class Evals(Section):
    enabled: bool = setting(
        True, "Keep a record of each task a browser of the window does: its time, its steps, its tokens"
    )
    dir: str = setting(".bap-browser/evals", "Where those records are kept, in a folder for each browser")
    max_task_chars: int = setting(200, "How much of a task's own words, and of its answer, a record keeps")
    recent_tasks: int = setting(20, "The tasks the window lists for a browser, newest first")
    max_tasks_read: int = setting(2000, "The newest records a summary is made from")
    step_budget_ms: int = setting(2000, "The checklist's limit for one step in the browser")


class Bench(Section):
    runs: int = setting(30, "Samples per line")
    warmup: int = setting(5, "Runs thrown away first")
    budget_file: str = setting("perf/budget.json", "The performance budget")
    results_dir: str = setting(".bap-browser/bench", "Where bench results are written")


class Config(Section):
    data_dir: str = setting(
        ".bap-browser", "Where downloads, logs, saved settings, bench results and the state file go"
    )
    backend: Backend = Backend()
    browser: Browser = Browser()
    safety: Safety = Safety()
    control: Control = Control()
    permissions: Permissions = Permissions()
    bridge: Bridge = Bridge()
    sessions: Sessions = Sessions()
    server: Server = Server()
    mcp: Mcp = Mcp()
    viewer: Viewer = Viewer()
    agent: Agent = Agent()
    safeguards: Safeguards = Safeguards()
    limits: Limits = Limits()
    settings: Settings = Settings()
    logging: Logging = Logging()
    code: Code = Code()
    auth: Auth = Auth()
    evals: Evals = Evals()
    bench: Bench = Bench()
    # For each key a layer set, the layer: a file, the environment or the session. Not a setting.
    _sources: dict[str, str] = PrivateAttr(default_factory=dict[str, str])

    @property
    def sources(self) -> Mapping[str, str]:
        """Where each value that was set came from, for a person who asks (spec 9.12)."""
        return self._sources


def defaults() -> Config:
    return Config()


def deep_merge(base: Mapping[str, Any], over: Mapping[str, Any]) -> dict[str, Any]:
    """Nested sections merge; lists and single values are replaced."""
    out = dict(base)
    for key, value in over.items():
        if isinstance(value, Mapping) and isinstance(out.get(key), Mapping):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def load_config(
    path: str | Path | None = None,
    *,
    env: Mapping[str, str] | None = None,
    session: Mapping[str, Any] | None = None,
) -> Config:
    return load_config_with_sources(path, env=env, session=session)[0]


def load_config_with_sources(
    path: str | Path | None = None,
    *,
    env: Mapping[str, str] | None = None,
    session: Mapping[str, Any] | None = None,
) -> tuple[Config, dict[str, str]]:
    """The effective configuration, and for each overridden key the layer that set it."""
    env = os.environ if env is None else env
    layers: list[tuple[str, Mapping[str, Any]]] = []
    file = _find_file(path, env)
    if file is not None:
        layers.append((file.name, _read_file(file)))
    layers.append(("environment", _env_layer(env)))
    layers.append(("session", _session_layer(session or {})))

    data: dict[str, Any] = defaults().model_dump()
    sources: dict[str, str] = {}
    for name, layer in layers:
        data = deep_merge(data, layer)
        for key in _leaf_keys(layer):
            sources[key] = name
    config = _validate(data, sources)
    config._sources = dict(sources)  # pyright: ignore[reportPrivateUsage]
    return config, sources


def _find_file(path: str | Path | None, env: Mapping[str, str]) -> Path | None:
    named = path if path is not None else env.get(CONFIG_PATH_ENV)
    if named:
        file = Path(named)
        if not file.is_file():
            raise ConfigError(f"config file not found: {file}")
        return file
    default = Path(DEFAULT_CONFIG_FILE)
    return default if default.is_file() else None


def _read_file(file: Path) -> Mapping[str, Any]:
    try:
        # utf-8-sig also reads a file that a Windows editor saved with a byte-order mark.
        data = json.loads(file.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ConfigError(
            f"{file.name}: not valid JSON (line {exc.lineno}, column {exc.colno}: {exc.msg})"
        ) from exc
    if not isinstance(data, dict):
        raise ConfigError(f"{file.name}: the top level must be an object")
    return data


def _env_layer(env: Mapping[str, str]) -> dict[str, Any]:
    layer: dict[str, Any] = {}
    for name, raw in env.items():
        if not name.startswith(ENV_PREFIX):
            continue
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            value = raw
        _set_dotted(layer, name[len(ENV_PREFIX) :].lower().split("__"), value, name)
    return layer


def _session_layer(session: Mapping[str, Any]) -> dict[str, Any]:
    layer: dict[str, Any] = {}
    for key, value in session.items():
        if key not in SESSION_KEYS:
            raise ConfigError(f"'{key}' cannot be set per session")
        _set_dotted(layer, key.split("."), value, key)
    return layer


def _set_dotted(layer: dict[str, Any], parts: list[str], value: Any, origin: str) -> None:
    node = layer
    for part in parts[:-1]:
        child = node.setdefault(part, {})
        if not isinstance(child, dict):
            raise ConfigError(f"{origin} conflicts with another value for '{part}'")
        node = child
    node[parts[-1]] = value


def _leaf_keys(layer: Mapping[str, Any], prefix: str = "") -> Iterator[str]:
    for key, value in layer.items():
        if isinstance(value, Mapping) and value:
            yield from _leaf_keys(value, f"{prefix}{key}.")
        else:
            yield f"{prefix}{key}"


def _validate(data: dict[str, Any], sources: Mapping[str, str]) -> Config:
    try:
        return Config.model_validate(data)
    except ValidationError as exc:
        first = exc.errors()[0]
        key = ".".join(str(part) for part in first["loc"])
        where = sources.get(key, "the configuration")
        if first["type"] == "extra_forbidden":
            raise ConfigError(f"unknown setting '{key}' (from {where})") from None
        raise ConfigError(f"bad value for '{key}' (from {where}): {first['msg']}") from None
