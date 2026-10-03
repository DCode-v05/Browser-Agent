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

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from bap_browser.errors import ConfigError

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
    popup_adopt_ms: int = setting(3000, "Longest wait for a new tab to load before it is reported")
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
    user_data_dir: str | None = setting(
        None, "Persistent profile folder; none means a fresh profile each session"
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
    ask_before: Literal["risky", "every_action"] = setting(
        "risky", "`every_action` also makes every tool that acts on a page `confirm`"
    )
    redact_patterns: list[str] = setting([], "Regular expressions scrubbed from every result")


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
    show_agent_pointer: bool = setting(
        True, "Draw the target highlight and the agent's pointer over the live picture"
    )


class Agent(Section):
    provider: Literal["anthropic", "scripted"] = setting(
        "anthropic", "Whose model the loop calls. `scripted` replays fixed replies and needs no key"
    )
    model: str = setting("claude-opus-5-5", "The model's name at that provider")
    api_key_env: str = setting(
        "ANTHROPIC_API_KEY",
        "The environment variable that holds the key. The key is never in `config.json`",
    )
    max_steps: int = setting(40, "Tool calls after which the loop stops")
    max_tokens: int = setting(4096, "The most a single reply may be")


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
    sessions: Sessions = Sessions()
    server: Server = Server()
    mcp: Mcp = Mcp()
    viewer: Viewer = Viewer()
    agent: Agent = Agent()
    settings: Settings = Settings()
    logging: Logging = Logging()
    bench: Bench = Bench()


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
    return _validate(data, sources), sources


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
