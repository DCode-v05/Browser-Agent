# Hermes Agent — browser-use code map

Research date: 2026-10-03. Read-only study; nothing was installed or run.

## 0. Provenance and method

| Item | Value |
|---|---|
| Repo | https://github.com/nousresearch/hermes-agent (MIT, `LICENSE:1-3`, "Copyright (c) 2025 Nous Research") |
| Commit studied | `bd0affe5e5f723579df8902852f5d0c47795f355` (HEAD of `main` via `git ls-remote`) |
| Commit dates | author 2026-09-28T15:14:39Z, committer 2026-10-03T04:22:55Z (GitHub API `/commits/<sha>`) |
| Commit subject | "fix(cli): keep key_env when saving a legacy custom endpoint" |
| Local copy | `<scratch>/research/h/` (17,159 files) |
| Tarball kept | `<scratch>/research/hermes.tar.gz` (78.6 MB) |

**Deviation from the brief.** `git clone --depth 1` failed twice on this machine: the scratch path is 208 characters, Windows long paths are off (`LongPathsEnabled = 0`), so git could not write its pack file (`fatal: '$GIT_DIR' too big`, then `unable to write file ...pack`). I downloaded the source tarball for the exact HEAD SHA from `codeload.github.com` and extracted it instead. Same file content, but there is **no `.git` directory**, so `git log`/`git blame` are not available in the copy. The folder is named `h` (not `hermes-agent`) to keep paths short.

All `path:line` references below are relative to `<scratch>/research/h/`. Items I could not confirm from files are marked **UNVERIFIED**.

---

## 1. Headline findings

1. **The default browser tool is now `browser_exec`, not the `browser_*` family.** With `browser.backend` unset, Hermes exposes a single code-mode tool that runs model-written Python through `browser-harness`; the ten built-in tools plus `browser_cdp`/`browser_dialog` are hidden (`tools/browser_use_cli.py:234-242`, `tools/browser_tool_install.py:149-151`, `website/docs/user-guide/features/browser.md:72-80`).
2. **Hermes implements no browser driving itself.** Page interaction is delegated to three external engines: `agent-browser` (native CLI + daemon, spawned once per command), `browser-harness` (pip package, Python over CDP) and Camofox (REST). Hermes owns session lifecycle, safety policy, redaction, profile snapshotting, a CDP supervisor and the vault.
3. **About 14k lines of Python are browser-specific**, split into a tightly coupled core (4,679 lines in the twelve `tools/browser_tool*.py` files, plus 840 in `tools/browser_use_cli.py`) and a handful of modules that are close to standalone (sections 3 and 12).
4. **Hermes' own benchmark** reports `browser_exec` at −60 % to −66 % total tokens versus the built-in tools at accuracy parity on hard tasks (`evals/browser_use/README.md:52-65`).
5. **Windows:** Hermes claims full native Windows support (`README.md:45,61`). In the browser code, Lightpanda and Bot Desktop are not available on Windows; real-profile browsing needs the browser fully quit.

---

## 2. Documented surface (`website/docs/user-guide/features/browser.md`, 917 lines)

### 2.1 Backends and modes

| Mode | What the docs say | Lines |
|---|---|---|
| Browser Use mode (default driver) | Single `browser_exec` tool; engine is `browser-harness`, a regular Python dependency; composes with any CDP browser source | 72-101 |
| Local browser mode | `agent-browser` CLI + local Chromium, no credentials needed | 592-594 |
| Browser Use cloud | `BROWSER_USE_API_KEY`; stealth, residential proxies, CAPTCHA solving, persistent profiles | 43-54 |
| Browserbase cloud | `BROWSERBASE_API_KEY` + `BROWSERBASE_PROJECT_ID` | 56-66 |
| Firecrawl cloud | `FIRECRAWL_API_KEY`; optional `FIRECRAWL_API_URL`, `FIRECRAWL_BROWSER_TTL` | 103-127 |
| Nous Subscription (Tool Gateway) | Managed Browser Use, no separate key | 39-41 |
| Camofox | Self-hosted Node server wrapping Camoufox (Firefox fork); REST; `CAMOFOX_URL` | 303-389 |
| Lightpanda | Zig headless browser, local engine, no screenshots | 487-511 |
| CDP attach | `/browser connect` to your own Chrome/Brave/Chromium/Edge | 513-574 |
| Real profile | Snapshot of your active profile, real browser binary, headless by default | 163-301 |
| Hybrid routing | Cloud for public URLs, local Chromium sidecar for private/LAN URLs, on by default | 129-161 |

### 2.2 Features

- Accessibility-tree snapshots with `@eN` refs (25); session isolation per task (33); automatic cleanup after inactivity (34); vision analysis (35).
- Concurrent named sessions for `browser_exec` via `session=<name>` — own harness daemon and own browser per name (82).
- `browser_exec` only offered to sessions that also have terminal access (96-101).
- Snapshot truncation at `browser.snapshot_threshold`, full tree saved to `~/.hermes/cache/web/` with a ready-made `read_file` call (672-682, 914).
- `browser_console(expression=...)` JS evaluation; supervisor fast path over a persistent WebSocket (748-757).
- `browser_cdp` raw passthrough, only when a CDP endpoint is reachable at session start (759-799).
- `browser_dialog` + `pending_dialogs` / `frame_tree` in snapshots; dialog policy (801-830).
- Session recording to WebM, `~/.hermes/browser_recordings/`, 72 h retention (859-868).
- Headed mode: visible window, per-turn cleanup skipped (870-886).
- Browserbase stealth table and 402 fallback (888-901).
- Screenshots in `~/.hermes/cache/screenshots/`, cleaned after 24 h (736).
- Camofox: managed persistence, externally managed identity, tab adoption, VNC live view (391-485).
- Limitations listed: text-based interaction, snapshot size, session timeout, cost, **no file downloads** (911-917).

### 2.3 Real-profile browsing (lines 163-301) — details

- Toggle: `browser.use_real_profile: true` (169-173). Off by default (265, 281).
- Copies the **active** profile (`Local State → profile.last_used`) into `~/.hermes/browser-profile/<browser>/`, then launches the **real browser binary** on the copy and attaches (175-190).
- Reason for the real binary: OS-encrypted cookies stay decryptable; a bundled Chromium with mock-keychain switches drops them on macOS (179-183).
- The live profile is never opened; the copy avoids the profile lock and Chrome 136+'s block on debugging the default profile directory (183-187).
- Auth files re-synced on every fresh session launch; only the active profile is copied (187-190).
- Headless by default using Chrome's new headless; `browser.headed: true` / `AGENT_BROWSER_HEADED=1` opens a window; display-less hosts always headless (192-200).
- `browser.real_profile_pin: "Profile 2"` pins the source; a missing pinned directory fails closed (202-214).
- Turning the toggle off deletes `~/.hermes/browser-profile/` on next browser use (216-218).
- **Windows:** a running Chrome/Edge/Brave holds an exclusive lock, so the browser must be fully quit, including tray instances (220-227).
- macOS/Linux: SQLite online backup with a five-second budget; a running Chrome usually blocks `Login Data`, `Login Data For Account`, `Web Data` (229-243).
- `browser.real_profile_autoclose: true` lets Hermes *offer* to close the browser; it runs `hermes browser close-profile` only after user approval, and never loops (245-252).
- Supported: Chrome, Edge, Brave, Brave Origin, Chromium; non-Chromium default fails closed (255-257).
- Under a cloud backend the agent can still open a real-profile local session via the `browser_exec` `local` argument, which exists only when the toggle is on (258-262).
- Scheduled runs: needs the toggle, the `browser` toolset on the job, and pre-saved vault credentials because nothing can be prompted (270-301).

### 2.4 Commands named in the docs

`/browser connect [url]`, `/browser status`, `/browser disconnect` (521-528); `/browser use off` (84); `hermes tools`, `hermes setup tools`, `hermes setup --portal`, `hermes model` (40, 115); `hermes pm install agent-browser` (638); `hermes update` (76, 633); `hermes doctor` (511); `hermes browser close-profile` (248-249); `hermes config set browser.snapshot_threshold 30000` (682); `hermes config set toolsets '["hermes-cli", "browser"]'` (648); installers `--skip-browser` / `-SkipBrowser` (635); `npx playwright install-deps chromium` (644); Termux `npm install -g agent-browser && agent-browser install` (645). `/browser connect` is an interactive-CLI command and is not dispatched by the messaging gateway (517-519).

Code adds `/browser use on` (`hermes_cli/cli_commands_mixin.py:438-448`).

---

## 3. File map

Verdicts: **standalone** = no Hermes imports; **shim** = needs a small shim (a few helper functions); **coupled** = deeply coupled.

### 3.1 Core built-in tool stack (`tools/browser_tool*.py`)

| Path | LOC | Purpose | External deps | Hermes imports | Verdict |
|---|---|---|---|---|---|
| `tools/browser_tool.py` | 1367 | Facade: tool schemas, the 10 tool functions, URL safety, session tables, registry wiring | `agent-browser` binary | `agent.redact`, `hermes_constants`, `utils`, `hermes_cli.config`, `hermes_cli.observability.shared_metrics_loop`, `agent.browser_provider`, `agent.secret_scope`, `tools.environments.local`, `agent.proxy_bypass`, `tools.bot_desktop.runtime`, `tools.url_safety`, `tools.website_policy`, `tools.registry`, `tools.vision_tools`, `agent.display` (lines 22-26, 52-55, 72, 81-91, 99, 906, 1279, 1305-1306) | coupled |
| `tools/browser_tool_session.py` | 918 | Daemon spawn, per-backend session creation, command execution, timeout recovery, lease fence, sandbox wrapping | `agent-browser`, `psutil` (indirect) | `hermes_cli._subprocess_compat`, `pm`, `hermes_cli.browser_runtime`, `tools.bot_desktop.*`, `tools.environments.streams`, `agent.deadline`, `tools.interrupt` (17, 160, 165, 185, 433, 533-534, 683, 689) | coupled |
| `tools/browser_tool_lifecycle.py` | 744 | Inactivity janitor, orphan reaper, teardown, atexit cleanup | `psutil`, `taskkill` on Windows | `hermes_constants`, `agent.secret_scope`, `hermes_cli.env_loader`, `gateway.status`, `tools.process_registry`, `agent.deadline` (17, 121-122, 303, 311-312, 500) | coupled |
| `tools/browser_tool_real_profile.py` | 344 | Launch the real browser on the profile copy and attach `agent-browser` | real browser binary, `requests` | `agent.proxy_bypass`, `hermes_cli.browser_connect`, sibling modules (15-20, 159, 280-281) | coupled |
| `tools/browser_tool_cloud.py` | 268 | Cloud provider resolution, engine/headed/private-URL flags | — | `agent.browser_provider`, `agent.browser_registry`, `hermes_constants`, `plugins.browser.*`, `tools.tool_backend_helpers`, `utils`, `tools.terminal_scope` (10-18, 182) | coupled |
| `tools/browser_tool_lightpanda_fallback.py` | 196 | Lightpanda status and automatic Chrome fallback | `agent-browser` | sibling modules (12-16) | coupled |
| `tools/browser_tool_install.py` | 185 | Find `agent-browser` / Chromium, availability gates | — | `hermes_constants`, `pm`, `hermes_cli.browser_runtime`, `tools.vision_tools` (9, 68, 102, 119, 184) | coupled |
| `tools/browser_tool_eval_policy.py` | 167 | SSRF guard for JS eval, opt-in sensitive-primitive denylist | — | `utils`, `_session`, `_cloud`, origin proxy (9-12) | shim (regex tables are self-contained, 59-83) |
| `tools/browser_tool_vision.py` | 144 | Screenshot analysis: native attach or auxiliary LLM | Pillow (via vision tools) | `hermes_cli.config`, `tools.vision_tools`, `agent.auxiliary_client` (8321 lines), `agent.redact` (11, 62-67, 120, 143) | coupled |
| `tools/browser_tool_cdp.py` | 134 | Normalise a CDP endpoint, dialog-policy config, supervisor start/stop | `requests` | `agent.proxy_bypass`, `hermes_cli.config` (9, 80) | shim |
| `tools/browser_tool_snapshot.py` | 125 | Truncate-and-store of oversized snapshots, output redaction | — | `hermes_constants`, `agent.redact`, `tools.spill_safety`, `tools.credential_files` (43-44, 53, 84) | shim |
| `tools/browser_tool_origin.py` | 87 | Frame-walking proxy that lets the split modules read facade state | — | none | Hermes-internal plumbing, no reuse value |

The split modules read facade state through `tools/browser_tool_origin.py:43-87`, which walks interpreter frames to find the right `tools.browser_tool` module. This is the main reason the core cannot be lifted piecemeal.

### 3.2 Code-mode driver

| Path | LOC | Purpose | External deps | Hermes imports | Verdict |
|---|---|---|---|---|---|
| `tools/browser_use_cli.py` | 840 | `browser_exec`: resolve a CDP endpoint, run `python -m browser_harness.run` with code on stdin, collect output, attach screenshots | `browser-harness==0.1.13` | `hermes_constants`, `utils`, `tools.browser_tool*`, `tools.registry`, `agent.redact`, `tools.vision_tools`, `agent.secret_scope`, `tools.bot_desktop`, `tools.environments.streams` (22-23, 140, 145, 230, 312-314, 380-381, 630-631, 826) | coupled as a file; the pattern itself is ~100 lines |

### 3.3 CDP supervisor and raw CDP

| Path | LOC | Purpose | External deps | Hermes imports | Verdict |
|---|---|---|---|---|---|
| `tools/browser_supervisor.py` | 552 | One persistent CDP WebSocket per task: attach, reconnect, `evaluate_runtime`, `focus_page`, registry | `websockets` | lazy: `agent.redact`, `agent.async_utils` (50 lines), `agent.proxy_bypass` (145 lines), `agent.vault_store.normalize_origin` (48, 61, 285, 375) | shim |
| `tools/browser_supervisor_dialogs.py` | 307 | Native dialog capture plus an injected XHR bridge for backends that auto-dismiss dialogs | — | lazy `agent.redact` (28) | shim |
| `tools/browser_supervisor_frames.py` | 166 | Frame / OOPIF tracking and bounded `frame_tree` | — | none | standalone |
| `tools/browser_cdp_tool.py` | 410 | `browser_cdp` raw passthrough, private-page guard, binary-aware redaction | `websockets` | `tools.registry`, `tools.browser_extension_router`, `agent.redact`, `agent.proxy_bypass`, eval policy (16-17, 58, 120, 173) | shim |
| `tools/browser_dialog_tool.py` | 109 | `browser_dialog` tool | — | supervisor, `tools.registry` (13-14) | shim |

### 3.4 Real-profile and CDP attach helpers

| Path | LOC | Purpose | External deps | Hermes imports | Verdict |
|---|---|---|---|---|---|
| `hermes_cli/browser_connect.py` | 1090 | Default-Chromium detection (Windows registry, macOS LaunchServices, Linux xdg), profile snapshot with SQLite online backup, lock probe, debug-browser launch, dual-stack CDP discovery | `psutil`, stdlib `sqlite3`/`winreg` | `agent.proxy_bypass.is_loopback_host`, `hermes_constants.get_hermes_home`; lazy `hermes_cli.config` (`read_raw_config`, `_secure_dir`, `_secure_file`, `is_managed`) (29-30, 376, 495, 773) | shim |
| `hermes_cli/browser_runtime.py` | 16 | Pick the Chromium executable (override env or PM store) | — | `pm` (7) | coupled to PM |
| `hermes_cli/subcommands/browser.py` | 50 | `hermes browser close-profile` | — | `hermes_cli.browser_connect` | shim |
| `hermes_cli/cli_commands_mixin.py` | (part, ~lines 417-600) | `/browser connect|disconnect|status|use` in the classic CLI | — | CLI internals, i18n | coupled |
| `tui_gateway/methods_browser.py` | 175 | Same connect/disconnect as JSON-RPC for TUI/Desktop | — | gateway server globals | coupled |

### 3.5 Other engines

| Path | LOC | Purpose | External deps | Hermes imports | Verdict |
|---|---|---|---|---|---|
| `tools/browser_camofox.py` | 601 | REST client mapping the tool surface onto a Camofox server | `requests`, Camofox server | `agent.secret_scope`, `hermes_cli.config`, `hermes_constants`, `tools.registry`, `agent.display`, `agent.auxiliary_client` (26-30, 499, 582) | shim (minus vision) |
| `tools/browser_camofox_state.py` | 27 | Stable profile-scoped Camofox identity | — | `hermes_constants` | shim |
| `tools/browser_lightpanda.py` | 340 | Spawn/stop/reap `lightpanda serve` | `lightpanda` binary, `psutil` | `hermes_constants`, `tools.process_registry` (2861 lines), `gateway.status` (2216 lines) (55, 175, 294, 310) | shim; POSIX only |
| `tools/browser_extension_router.py` | 137 | Route tool calls to a registered browser-extension controller | — | `gateway.session_context`, `gateway.browser_control_broker`, `tools.approval_context` | coupled |
| `gateway/browser_control_broker.py` | 512 | Identity-scoped broker for extension controllers | — | gateway | coupled |
| `gateway/browser_control_artifacts.py` | 323 | Upload/download artifact store for that lane | — | gateway | coupled |
| `tui_gateway/methods_browser_control.py` | 217 | RPC for that lane | — | gateway | coupled |
| `tools/bot_desktop/browser.py` | 184 | Shared Chromium on the Linux Bot Desktop | — | bot desktop | coupled, Linux only |

The browser extension itself is not in the repo; only its wire contract is (`apps/shared/src/gateway-contract.generated.ts`, `apps/shared/src/gateway-contract.openrpc.json`).

### 3.6 Cloud providers

| Path | LOC | Purpose | External deps | Hermes imports | Verdict |
|---|---|---|---|---|---|
| `agent/browser_provider.py` | 57 | `BrowserProvider` ABC and session-metadata contract | — | `agent.provider_base` (66 lines) | shim |
| `agent/browser_registry.py` | 61 | Provider registry and auto-detect order | — | `agent.provider_registry` (204 lines) | shim |
| `plugins/browser/_common.py` | 138 | Shared REST lifecycle (create, release, emergency cleanup) | `requests` | `agent.browser_provider` | shim |
| `plugins/browser/browserbase/provider.py` | 116 | Browserbase sessions, 402 fallback | `requests` | `agent.secret_scope.get_secret` | shim |
| `plugins/browser/firecrawl/provider.py` | 69 | Firecrawl `/v2/browser` | `requests` | `agent.secret_scope.get_secret` | shim |
| `plugins/browser/browser_use/provider.py` | 160 | Browser Use cloud, direct key or Nous gateway | `requests` | `agent.secret_scope`, `tools.managed_tool_gateway`, `tools.tool_backend_helpers` (15, 76-77) | coupled (gateway auth) |
| `plugins/browser/*/__init__.py`, `plugin.yaml` | 9 + 7 each | Plugin registration | — | plugin loader | trivial |

### 3.7 Vault

| Path | LOC | Purpose | External deps | Hermes imports | Verdict |
|---|---|---|---|---|---|
| `tools/browser_vault_tool.py` | 770 | Five model tools: list, unlock, fill, save_login, enter_code | — | supervisor, vault backends, `tools.approval_prompt`, `tools.bot_desktop.lease`, `tools.registry`, `agent.redact` | coupled |
| `agent/vault_login_classifier.py` | 333 | Classify page inputs (login, card, address, OTP) and build the fill script | — | none | **standalone** |
| `agent/vault_store.py` | 442 | Fernet-encrypted local store, origin normalisation, TOTP | `cryptography` | `hermes_constants`, `utils.atomic_write_bytes`, lazy `hermes_cli.config._secure_dir` (32-33, 212, 248) | shim |
| `agent/vault_backends/base.py` | 139 | Backend interface and detection | `op`, `bw` CLIs | `agent.vault_store`, `hermes_cli.config`, `agent.secret_sources.onepassword` | shim |
| `agent/vault_backends/onepassword.py`, `bitwarden.py`, `local.py`, `unlock.py`, `__init__.py` | 157, 132, 38, 171, 18 | 1Password / Bitwarden / local backends, unlock prompts | `op`, `bw` | `tools.approval_context` (unlock) | shim / coupled (unlock) |
| `hermes_cli/vault.py`, `hermes_cli/subcommands/vault.py` | 223, 21 | `hermes vault list|add|rm|sources` | — | CLI | coupled |
| `tui_gateway/methods_vault.py` | 185 | Vault RPC | — | gateway | coupled |

Both the vault design and the classifier are ports from Merit-Systems/OpenInstinct, MIT (`tools/browser_vault_tool.py:23-24`, `agent/vault_login_classifier.py:3-4`, `agent/vault_store.py:12-13`).

### 3.8 Evaluation harness

`evals/browser_use/`: `single_run.py` (199), `orchestrate_cloud.py` (184), `benchmark_browser_eval.py` (139), `orchestrate.py` (129), `report.py` (70), `README.md` (114), `tasks/easy.json` (5 tasks), `tasks/hard.json` (6 tasks). `evals/vault_fill_live_e2e.py` (144). Verdict: shim — the task files and oracle approach are reusable; the runners assume a Hermes checkout.

### 3.9 Tests — 76 Python files, 18,868 lines

Purposes below are inferred from file names unless stated; I read only `test_browser_use_harness.py` in full and part of `test_browser_use_cli.py`.

| Area | Files (LOC) |
|---|---|
| Real profile | `tests/tools/test_browser_real_profile.py` (1139), `test_browser_real_profile_pin.py` (93), `tests/hermes_cli/test_browser_connect_real_profile_snapshot_errors.py` (76), `test_browser_connect_default_chromium.py` (186) |
| CDP attach | `tests/hermes_cli/test_cli_browser_connect.py` (162), `test_browser_connect_dual_stack.py` (109), `test_browser_connect_media_permissions.py` (167), `tests/tools/test_browser_cdp_override.py` (384), `test_browser_cdp_tool.py` (624) |
| Supervisor | `tests/tools/test_browser_supervisor.py` (324), `_healthcheck.py` (133), `_reconnect.py` (81), `test_browser_eval_supervisor_path.py` (306) |
| Browser Use mode | `tests/tools/test_browser_use_cli.py` (1229), `test_browser_use_harness.py` (67, read), `test_browser_use_session_expiry.py` (95) |
| Lifecycle | `test_browser_orphan_reaper.py` (525), `test_browser_suspect_recycle.py` (327), `test_browser_cleanup.py` (220), `test_browser_open_timeout.py` (172), `test_browser_command_timeout_race.py` (58), `test_browser_process_tree.py` (59) |
| Safety | `test_browser_snapshot_ssrf.py` (340), `test_browser_ssrf_local.py` (352), `test_browser_eval_ssrf.py` (287), `test_browser_console_ssrf.py` (92), `test_browser_get_images_ssrf.py` (76), `test_browser_secret_exfil.py` (227), `test_browser_hardening.py` (179), `test_browser_private_page_action_guard.py` (120), `test_browser_type_redaction.py` (74) |
| Snapshot/console | `test_browser_snapshot_threshold.py` (218), `test_browser_console.py` (338), `test_browser_eval_shim_args.py` (73) |
| Cloud | `test_browser_cloud_fallback.py` (71), `test_browser_cloud_provider_cache.py` (271), `test_browser_hybrid_routing.py` (189), `test_managed_browserbase_and_modal.py` (311), `tests/plugins/browser/test_browser_provider_plugins.py` (189), `check_parity_vs_main.py` (273) |
| Lightpanda | `test_browser_lightpanda.py` (718), `test_browser_lightpanda_serve.py` (372) |
| Camofox | `test_browser_camofox.py` (312), `_auth.py` (132), `_ensure_tab.py` (66), `_persistence.py` (314), `_private_page_guard.py` (171), `_state.py` (21), `_timeout.py` (20) |
| Vault | `tests/tools/test_browser_vault.py` (828), `tests/agent/test_vault_backends.py` (233), `test_vault_store.py` (49), `tests/tui_gateway/test_vault_methods.py` (177), `tests/hermes_cli/test_vault_sources_shape.py` (49) |
| Extension lane | `test_browser_extension_router.py` (489), `_wiring.py` (87), `tests/gateway/test_browser_control_api.py` (739), `_artifacts.py` (713), `_broker.py` (159), `_broker_hardening.py` (568), `_cloud.py` (589) |
| Install/PM | `test_browser_pm.py` (354), `tests/pm/test_agent_browser_package.py` (48), `tests/hermes_cli/test_browser_runtime.py` (66), `tests/docker/test_stage2_browser_discovery.py` (81) |
| Misc | `test_browser_headed_mode.py` (165), `test_browser_env_loopback_no_proxy.py` (53), `test_bot_desktop_browser.py` (378), `_fence.py` (206), `test_browser_computer_use_profile_cache_keys.py` (91), `test_mcp_parked_probe_no_browser.py` (77) |

Verdict for tests: coupled to their modules. The supervisor tests use an asyncio mock CDP server (`website/docs/developer-guide/browser-supervisor.md:197-203`), which is a reusable idea.

### 3.10 Out of scope but related

Desktop/TUI TypeScript: `apps/desktop/src/app/settings/browser-real-profile-panel.tsx` (96), `vault-settings.tsx` (836), preview browser bar and tests. Docs: `website/docs/developer-guide/browser-supervisor.md` (203), `browser-provider-plugin.md` (153), `website/docs/user-guide/features/credential-vault.md` (122).

### 3.11 Size summary

| Group | Python LOC |
|---|---|
| `tools/browser_*.py` (23 files) | 8,938 |
| Vault (agent + CLI + RPC) | 1,859 |
| `hermes_cli` browser files | 1,156 |
| Gateway extension lane | 1,052 |
| `plugins/browser` | 510 |
| Provider ABC + registry | 118 |
| **Browser subsystem total** | **≈ 14,000** (counted with `wc -l`) |
| Browser tests | 18,868 |

---

## 4. Tool surface as the model sees it

All tools return a JSON string. Common error shape: `{"success": false, "error": "..."}` (`tools/browser_tool.py:622-623`).

### 4.1 Built-in tools (toolset `browser`; visible only when Browser Use mode is off)

Schemas: `tools/browser_tool.py:474-614`.

| Tool | Parameters (default) | Description (abridged) | Success output | Notes and caps |
|---|---|---|---|---|
| `browser_navigate` | `url` (required) | Navigate; must be called first; prefer lighter tools for plain-text endpoints; returns a compact snapshot | `{success, url, title, snapshot, element_count}` plus optional `used_real_profile`, `bot_detection_warning`, `stealth_warning`, `stealth_features`, `fallback_warning` | 742-814. Timeout ≥ 60 s, ≥ 120 s on first open. Auto-snapshot uses `snapshot -c` |
| `browser_snapshot` | `full` (false) | Accessibility tree with `@eN` refs | `{success, snapshot, element_count}` plus `pending_dialogs`, `frame_tree`, `recent_dialogs` when a supervisor is active | 817-848. Truncated at 15,000 chars by default |
| `browser_click` | `ref` (required) | Click `@eN` | `{success, clicked}` | 888-893 |
| `browser_type` | `ref`, `text` (required) | Clear then type | `{success, typed, element}`; typed text passes through the secret redactor | 896-914. Uses agent-browser `fill` |
| `browser_scroll` | `direction` enum `up`/`down` (required) | Scroll | `{success, scrolled}` | 917-926. Fixed 500 px per call |
| `browser_back` | none | History back | `{success, url}` | 929-941 |
| `browser_press` | `key` (required) | Press a key | `{success, pressed}` | 944-948 |
| `browser_get_images` | none | List images | `{success, images:[{src, alt, width, height}], count}` | 1185-1207. `data:` URIs excluded; no count cap |
| `browser_vision` | `question` (required), `annotate` (false) | Screenshot for visual inspection | Native-vision model: multimodal envelope with the image. Otherwise `{success, analysis, screenshot_path, annotations?}` | 1251-1299. Full-page screenshot (`--full`) |
| `browser_console` | `clear` (false), `expression` (optional) | Console + JS errors, or evaluate JS | `{success, console_messages, js_errors, total_messages, total_errors}` or `{success, result, result_type, method?}` | 979-1014, 1085-1118 |

The `browser_snapshot` description still says "truncated or LLM-summarized" (`tools/browser_tool.py:491`), but the code only truncates and stores (`tools/browser_tool.py:713-722`, `tools/browser_tool_snapshot.py:69-108`).

### 4.2 CDP tools (toolset `browser-cdp`; only with a static CDP override and Browser Use mode off)

| Tool | Parameters (default) | Output | Reference |
|---|---|---|---|
| `browser_cdp` | `method` (required), `params` (object), `target_id`, `frame_id`, `timeout` (30, clamp 1–300 s) | `{success, method, result, target_id?}`; with `frame_id`: adds `frame_id`, `session_id` | `tools/browser_cdp_tool.py:260-321, 324-379` |
| `browser_dialog` | `action` enum `accept`/`dismiss` (required), `prompt_text`, `dialog_id` | `{success, action, dialog}` | `tools/browser_dialog_tool.py:16-91` |

Gate: `check_browser_requirements() and _get_cdp_override_raw()` (`tools/browser_cdp_tool.py:382-393`).

### 4.3 Code-mode tool (toolset `browser-use`; the default)

| Tool | Parameters (default) | Output | Reference |
|---|---|---|---|
| `browser_exec` | `code` (required), `session` (name, regex `^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$`), `timeout_s` (300, clamp 5–1800), `local` (false; only present when `browser.use_real_profile` is on) | `{success, exit_code, output, workspace?, session?, stderr?, screenshot_path?}`, or a multimodal envelope when a screenshot was produced and the model has native vision | `tools/browser_use_cli.py:627-721, 787-820` |

- Description = header + pinned helper digest (`tools/browser_use_cli.py:724-775`). Helpers named there: `new_tab(url)`, `goto_url(url)`, `wait_for_load()`, `page_info()`, `js(expr)`, `fill_input(selector, text)`, `click_at_xy(x, y)`, `capture_screenshot()`, `cdp('Domain.method', **kwargs)`, `ensure_real_tab()`.
- State: browser session and workspace persist; Python variables do not (fresh interpreter per call). Functions in `agent_helpers.py` in the workspace are auto-imported (729-731).
- `stderr` capped at 4,000 chars (82, 711-712). `stdout` is redacted but not truncated in this file.
- URL literals in the code are checked against the navigation policy before running (138-141, 635-637).
- Dropped from sessions without the `terminal` tool (`model_tools.py:392-396`; test at `tests/tools/test_browser_use_cli.py:208-222`).

### 4.4 Vault tools (toolset `browser`; visible in both modes)

Schemas: `tools/browser_vault_tool.py:589-679`.

| Tool | Parameters | Output |
|---|---|---|
| `browser_vault_list` | none | `{success, items:[{handle, backend, label, kind, origin, available, identifier?, identifier_type?, two_factor?, allowed_origins?}], locked?, errors?, hint?}` |
| `browser_vault_unlock` | `backend` enum `onepassword`/`bitwarden` (required) | `{success, backend}` or `error_type` in `unlock_cancelled`/`unlock_failed`/`unlock_unavailable` |
| `browser_vault_fill` | `handle` (required) | `{success, filled_fields, backend, kind, origin, next?, fields?}` |
| `browser_vault_save_login` | `label` (optional) | `{success, handle, origin, identifier, identifier_type, fill, next}` |
| `browser_vault_enter_code` | `handle` (optional) | `{success, filled_fields, origin, source, next}` |

Secrets are injected only over the supervisor WebSocket, never via subprocess argv (`tools/browser_vault_tool.py:119-145`). Payment fills need human confirmation (572-582).

### 4.5 Global result caps

Per-result persistence threshold 100,000 chars, per-turn 200,000, inline preview 1,500; MCP tools 50,000 (`tools/budget_config.py:13-20`). Scaled down for small context windows (85-114).

---

## 5. Config keys and environment variables

### 5.1 `browser.*` defaults (`hermes_cli/config_defaults.py:427-497`)

| Key | Default | Meaning | Floors / notes |
|---|---|---|---|
| `browser.backend` | `""` | `""` = Browser Use mode when available; `"browser-use"` = force; `"off"` = built-in tools | YAML `off` parsed as False is treated as `"off"` (`tools/browser_use_cli.py:202-206`) |
| `browser.inactivity_timeout` | `120` | Seconds before an idle session is reaped | Floor 30 (`tools/browser_tool.py:396`) |
| `browser.command_timeout` | `30` | Seconds per agent-browser command | Floor 5 (`tools/browser_tool.py:223`) |
| `browser.snapshot_threshold` | `15000` | Max snapshot chars before truncate-and-store | Floor 1000 (`tools/browser_tool.py:151-152`) |
| `browser.record_sessions` | `False` | Auto-record WebM | |
| `browser.headed` | `False` | Visible window; skips per-turn cleanup | |
| `browser.allow_private_urls` | `False` | Allow private/internal addresses | |
| `browser.engine` | `"auto"` | `auto` / `lightpanda` / `chrome` | Unknown values fall back to `auto` (`tools/browser_tool_cloud.py:211-215`) |
| `browser.auto_local_for_private_urls` | `True` | Hybrid local sidecar under a cloud provider | |
| `browser.cdp_url` | `""` | Persistent CDP endpoint | |
| `browser.use_real_profile` | `False` | Real-profile consent | Read on every call (`tools/browser_tool_cloud.py:244-250`) |
| `browser.real_profile_autoclose` | `False` | Windows: offer to close the locking browser | |
| `browser.real_profile_pin` | `""` | Source profile directory name | Missing directory fails closed |
| `browser.allow_unsafe_evaluate` | `False` | Legacy override of the eval denylist | |
| `browser.restrict_evaluate` | `False` | Opt-in denylist for sensitive JS primitives | |
| `browser.dialog_policy` | `"must_respond"` | `must_respond` / `auto_dismiss` / `auto_accept` | |
| `browser.dialog_timeout_s` | `300` | Safety auto-dismiss | |
| `browser.camofox.managed_persistence` | `False` | Stable profile-scoped userId | |
| `browser.camofox.user_id` | `""` | Externally managed identity | |
| `browser.camofox.session_key` | `""` | Tab match key | |
| `browser.camofox.adopt_existing_tab` | `False` | Reuse an existing tab | |
| `browser.camofox.rewrite_loopback_urls` | `False` | Rewrite loopback page URLs for Docker | |
| `browser.camofox.loopback_host_alias` | `"host.docker.internal"` | Alias used by the rewrite | |
| `browser.extension_control.enabled` | `False` | Browser-extension controller lane | |
| `browser.extension_control.developer_mode` | `False` | Gates `browser_cdp` / `browser_evaluate` on that lane | |

`browser.cloud_provider` has no default entry; it is written by `hermes tools`. Accepted values in code: `local`, `camofox`, `nous` (mapped to `browser-use`), `browser-use`, `browserbase`, `firecrawl`, or a plugin name (`tools/browser_tool_cloud.py:129-142`). A legacy `browser.use_gateway` flag is still read (`tools/browser_use_cli.py:188-199`).

A second, smaller default block exists for the classic CLI loader (`hermes_cli/cli_config_load.py:194-197`).

The config comment for `use_real_profile` says the copy is "driven by Hermes' packaged Chromium" (`hermes_cli/config_defaults.py:449-451`); the code and docs launch the user's real binary (`tools/browser_tool_real_profile.py:180-203`). The comment is stale.

Related keys outside `browser.*`: `auxiliary.vision.timeout` / `temperature` (`tools/browser_tool_vision.py:108-116`), `vault.onepassword.*`, `vault.bitwarden.enabled` (`website/docs/user-guide/features/credential-vault.md:100-108`), `bot_desktop.placement`, `bot_desktop.auto_start` (`tools/bot_desktop/placement.py:38-42`, `runtime.py:404-411`), `agent.disabled_toolsets` (`hermes_cli/config_defaults.py:281`), `plugins.enabled`, `mcp_servers`, `tool_budget.mcp_result_size_chars`.

### 5.2 Environment variables

| Variable | Effect | Source |
|---|---|---|
| `BROWSER_CDP_URL` | Live CDP override; beats `browser.cdp_url` | `tools/browser_tool_cdp.py:59-60` |
| `BROWSER_INACTIVITY_TIMEOUT` | Legacy fallback for the inactivity timeout | `tools/browser_tool.py:392-398` |
| `AGENT_BROWSER_ENGINE` | Engine when config says `auto` | `tools/browser_tool_cloud.py:209-210` |
| `AGENT_BROWSER_HEADED` | Headed mode | `tools/browser_tool_cloud.py:225` |
| `AGENT_BROWSER_ARGS`, `AGENT_BROWSER_CHROME_FLAGS` | Chromium launch flags; setting either disables sandbox auto-injection | `tools/browser_tool_session.py:59-64` |
| `AGENT_BROWSER_EXECUTABLE_PATH` | Chromium override | `hermes_cli/browser_runtime.py:12` |
| `AGENT_BROWSER_SOCKET_DIR`, `AGENT_BROWSER_IDLE_TIMEOUT_MS` | Set per command by Hermes | `tools/browser_tool_session.py:170-172` |
| `AUXILIARY_VISION_MODEL` | Model for `browser_vision` fallback | `tools/browser_tool.py:253-255` |
| `BROWSER_USE_API_KEY` | Browser Use cloud | `plugins/browser/browser_use/provider.py:91` |
| `BROWSERBASE_API_KEY`, `BROWSERBASE_PROJECT_ID`, `BROWSERBASE_BASE_URL` | Browserbase | `plugins/browser/browserbase/provider.py:44-52` |
| `BROWSERBASE_PROXIES` (true), `BROWSERBASE_ADVANCED_STEALTH` (false), `BROWSERBASE_KEEP_ALIVE` (true), `BROWSERBASE_SESSION_TIMEOUT` | Browserbase features | `plugins/browser/browserbase/provider.py:66-69` |
| `FIRECRAWL_API_KEY`, `FIRECRAWL_API_URL`, `FIRECRAWL_BROWSER_TTL` (300) | Firecrawl | `plugins/browser/firecrawl/provider.py:35-57` |
| `CAMOFOX_URL`, `CAMOFOX_API_KEY`, `CAMOFOX_USER_ID`, `CAMOFOX_SESSION_KEY`, `CAMOFOX_ADOPT_EXISTING_TAB`, `CAMOFOX_REWRITE_LOOPBACK_URLS`, `CAMOFOX_LOOPBACK_HOST_ALIAS` | Camofox | `tools/browser_camofox.py:69-77, 176-234` |
| `BU_CDP_WS`, `BU_CDP_URL`, `BU_NAME`, `BU_AUTOSPAWN`, `BH_AGENT_WORKSPACE`, `ANONYMIZED_TELEMETRY` | Contract with `browser-harness` | `tools/browser_use_cli.py:116-122, 158, 285, 649, 663-668` |
| `HERMES_HOME` | State root | `hermes_constants.py:111-118` |
| `TERMINAL_ENV` | Decides whether the browser counts as "local" for SSRF purposes | `tools/browser_tool_cloud.py:182-183` |

Only six keys are passed through to the `agent-browser` subprocess; everything else is scrubbed (`tools/browser_tool.py:33-36, 47-77`).

---

## 6. Runtime selection of driver and backend

### 6.1 Which tool surface the model gets

1. **Camofox active** → built-in tools, routed to the REST client. Active when the stored selection is `camofox`, or (legacy) no selection exists and `CAMOFOX_URL` is set; a CDP override disables it (`tools/browser_camofox.py:93-110`, `tools/browser_use_cli.py:239-240`).
2. Otherwise `browser.backend` decides: `browser-use` → code mode; `off` → built-in; unset → code mode if `browser_harness` is importable or a legacy Browser Use cloud config exists (`tools/browser_use_cli.py:234-242, 275-280`).
3. In code mode `check_browser_requirements()` returns False, which hides every built-in tool and both CDP tools (`tools/browser_tool_install.py:149-151`).
4. `browser_exec` is removed when the session has no `terminal` tool (`model_tools.py:392-396`). The docs say such sessions "keep the default browser tools" (`browser.md:96-101`); I found no code that re-enables them in that case — **UNVERIFIED, possible doc/code mismatch**.
5. If `browser.extension_control.enabled` and a controller is bound to the session, built-in tool calls are served by the extension instead (`tools/browser_extension_router.py:66-99`, `tools/browser_tool.py:1311-1313, 1353-1359`).
6. Availability checks are cached for 30 s process-wide (`tools/registry.py:223`).

### 6.2 Which browser serves built-in tools

`_create_session_for_key` (`tools/browser_tool_session.py:331-342`):

1. CDP override: `BROWSER_CDP_URL` env, then `browser.cdp_url` → `agent-browser --session <name> --cdp <ws>`.
2. Hybrid local sidecar for a private URL under a cloud provider (key `<task>::local`); never uses the real profile (`tools/browser_tool.py:317-331`).
3. Cloud provider → `create_session()`, then attach by CDP; on failure, fall back to local and mark the session degraded (`tools/browser_tool_session.py:305-328`).
4. Local: real-profile copy if consented (fails closed on error) → otherwise a plain local session; `--headed` and `--engine <x>` added as configured (`tools/browser_tool_session.py:247-271, 836-850`).

Cloud provider resolution (`tools/browser_tool_cloud.py:116-155`): explicit `browser.cloud_provider` wins and an unknown name raises; with no selection ever written, auto-detect tries Browser Use then Browserbase. Firecrawl is never auto-selected (`agent/browser_registry.py:28-40`).

### 6.3 Which browser serves `browser_exec`

`_route_backend` and `_resolve_backend_cdp` (`tools/browser_use_cli.py:430-541`). Effective precedence:

1. `BU_CDP_WS` / `BU_CDP_URL` already in the environment (operator override).
2. CDP override (`/browser connect`, `browser.cdp_url`).
3. Real-profile copy, when consented and the backend is local, or when the model passes `local=true`.
4. Cloud provider session's CDP URL. Exception: Browser Use direct-API configs let the harness reach the cloud natively (`BU_AUTOSPAWN`).
5. Lightpanda (`lightpanda serve` per session) if `browser.engine: lightpanda`.
6. Hermes' packaged Chromium, launched through `agent-browser get cdp-url`. The harness is deliberately not allowed to discover the user's installed Chrome (`tools/browser_use_cli.py:395-419`).

A CDP supervisor is attached to the same endpoint so the vault can fill (`tools/browser_use_cli.py:512-526`).

### 6.4 Windows behaviour per backend

| Backend | Windows status | Evidence |
|---|---|---|
| Built-in tools + local Chromium | Supported. PM stages `bin/agent-browser-win32-x64.exe` and Chrome-for-Testing win64; Windows ARM64 runs the x64 build under emulation | `pm/packages.py:919-935, 985-994`; `pm/lock.json:3-10, 49-76` |
| | Windows-specific spawn flags; `.cmd` shim argument escaping | `tools/browser_tool_session.py:115-132, 231-234` |
| | After a command timeout the daemon is always tree-killed, because the named pipe cannot be probed | `tools/browser_tool_session.py:451-456` |
| `browser_exec` | Hermes wrapper has Windows branches (process group, `taskkill /T /F`, drive-letter screenshot paths); two tests are marked for Windows | `tools/browser_use_cli.py:86, 544-554, 569-578`; `tests/tools/test_browser_use_harness.py:12, 28` |
| | Windows support of `browser-harness` itself | **UNVERIFIED** (package is not in the repo) |
| `/browser connect` | Supported: Program Files / LOCALAPPDATA candidates, detached launch, IPv4+IPv6 loopback probing written for a Windows case | `hermes_cli/browser_connect.py:217-222, 727-738, 932-936, 980-985` |
| Real profile | Supported with a hard caveat: the browser must be fully quit; lock probe fails fast | `hermes_cli/browser_connect.py:236-248, 476-489`; `browser.md:220-227, 294-296` |
| | Whether cookies decrypt in the copy on Windows | **UNVERIFIED** (docs explain only the macOS Keychain case, `browser.md:179-183`) |
| Cloud providers | No OS-specific code; REST + CDP attach | `plugins/browser/_common.py`; live behaviour **UNVERIFIED** |
| Camofox | Hermes side is a plain REST client; the server setup shown is `make` / Docker | `browser.md:307-351`; **UNVERIFIED** on Windows |
| Lightpanda | **Not available: no Windows build** | `tools/browser_lightpanda.py:65-67, 201-203` |
| Bot Desktop (shared screen, human takeover) | **Linux only** | `tools/bot_desktop/runtime.py:79-80` |
| Sandbox-flag auto-injection | Linux only (root, Docker, AppArmor) | `tools/browser_tool_session.py:40-56` |

Other Windows facts: Hermes home is `%LOCALAPPDATA%\hermes`, so every `~/.hermes/...` path in the docs maps there (`hermes_constants.py:51-58`; `README.md:61`). The docs suggest `chrome-devtools-mcp` when Hermes runs in WSL2 and Chrome on the Windows host (`browser.md:576-590`).

---

## 7. Python version, binaries, standalone install

### 7.1 Python

- `requires-python = ">=3.11,<3.15"` (`pyproject.toml:15`), but the comment says "we *only* support 3.14" and 3.11 exists only so old installs can update (`pyproject.toml:10-14`).
- Every runtime dependency carries the marker `python_version >= '3.14'` (`pyproject.toml:40-216`). Installing on 3.11–3.13 therefore resolves to no dependencies.
- The lock covers 3.14 only: `environments = ["python_version >= '3.14'"]` (`pyproject.toml:611-614`). PM pins CPython 3.14.7 (`pm/lock.json:502`).
- Direct dependencies are exact-pinned (`pyproject.toml:20-32`).

### 7.2 What a browser-only setup would need

| Component | Version | How Hermes gets it | Reference |
|---|---|---|---|
| `browser-harness` | 0.1.13 | pip, core dependency | `pyproject.toml:130-134` |
| → its dependencies | `cdp-use`, `fetch-use`, `pillow`, `websockets` | pip | `uv.lock:776-784` |
| `websockets` | 15.0.1 | pip, core | `pyproject.toml:127-129` |
| `requests`, `psutil`, `Pillow` | 2.33.0, 7.2.2, 12.3.0 | pip, core | `pyproject.toml:57, 122, 173` |
| `agent-browser` | 0.26.0 | npm tarball unpacked by PM; one native binary kept per platform (`bin/agent-browser-<target>[.exe]`); PM runs no postinstall | `pm/lock.json:3-10`; `pm/packages.py:900-956` |
| Node.js | 26.7.0 pinned by PM | Whether the PM-staged `agent-browser` binary needs Node at runtime is **UNVERIFIED**: one comment calls agent-browser "a Node process loading npm deps" (`tools/browser_tool.py:29-32`), and the version probe runs "under the Hermes-managed Node PATH" (`hermes_constants.py:458-461`) | `pm/lock.json:413-452` |
| Chromium | Chrome for Testing 145.0.7632.6 (Playwright revision 1208), about 170 MB | PM, from `cdn.playwright.dev` | `pm/lock.json:49-76`; `pm/packages.py:959-1028`; `tools/browser_tool.py:182` |
| Linux system libraries | — | `npx playwright install-deps chromium` | `browser.md:643-644` |
| `lightpanda` | user-installed | optional, POSIX only | `tools/browser_lightpanda.py:24-25` |
| Camofox server | user-installed | optional | `browser.md:305-328` |
| `cryptography` | 50.0.1 | pip, needed by the vault | `pyproject.toml:110` |
| `op`, `bw` | user-installed | optional vault backends | `credential-vault.md:53-62` |

PyPI metadata for `browser-harness` 0.1.13 (fetched from pypi.org, not from the repo): `requires_python >=3.11`, "Development Status :: 3 - Alpha", pins `cdp-use==1.4.5`, `fetch-use==0.4.0`, `pillow==12.3.0`, `websockets==15.0.1`, optional extra `mcp`, homepage `github.com/browser-use/browser-harness`, licence field empty. Its internals, licence and helper API are **UNVERIFIED**.

The notes call `agent-browser` a "Vercel Rust/Node CLI". The repo confirms an npm package with native per-platform binaries and mentions a "Rust daemon" (`tools/browser_tool_session.py:218`); it does not name the vendor — **UNVERIFIED**.

`playwright==1.62.0` appears only in the `google-meet` extra (`pyproject.toml:262`). The browser stack does not use the Playwright Python package.

### 7.3 Can the browser subsystem be installed or imported alone?

**No.** There is one distribution, `hermes-agent`, with no browser-only extra; packages are found for `agent`, `tools`, `hermes_cli`, `gateway`, `plugins`, `pm` and more (`pyproject.toml:800-825`).

Importing `tools.browser_tool` pulls at module level `agent.redact` (1352 lines), `hermes_cli.config` (4249 lines), `hermes_cli.observability.shared_metrics_loop`, `agent.browser_provider`, `tools.registry` (1043 lines), `tools.browser_extension_router`, and through `browser_tool_cloud` the bundled provider plugins and `agent.secret_scope` (`tools/browser_tool.py:22-26, 99, 1305-1306`; `tools/browser_tool_cloud.py:10-18`). At call time it reaches `pm`, `tools.bot_desktop` (which imports `tools.terminal_tool` for placement, `tools/bot_desktop/placement.py:45-47`), `gateway.status` (2216 lines), `tools.process_registry` (2861 lines) and `agent.deadline`.

This is a conclusion from reading imports; I did not execute an import.

---

## 8. Plugging an external browser engine into Hermes

Four routes exist, from least to most invasive.

| Route | How | What the model sees | Reference |
|---|---|---|---|
| **MCP server** | Add under `mcp_servers:` in `config.yaml` (stdio `command`/`args`/`env`, or HTTP `url`/`headers`), or `hermes mcp add <name> --command ... --args ...` / `--url` | Tools named `mcp__<server>__<tool>` (clamped to 64 chars), grouped in toolset `mcp-<server>` with the bare server name as an alias | `website/docs/reference/mcp-config-reference.md:17-71`; `tools/mcp_tool_schema.py:153-173`; `tools/mcp_tool_registration.py:130, 329`; `hermes_cli/subcommands/mcp.py:27-37` |
| **Python plugin with tools** | Package exposing `register(ctx)` that calls `ctx.register_tool(name, toolset, schema, handler, check_fn=...)`. Discovery: bundled `plugins/`, user `~/.hermes/plugins/`, project `.hermes/plugins/`, or pip entry point group `hermes_agent.plugins` | Native tool names. User and pip plugins must be listed in `plugins.enabled` | `website/docs/user-guide/features/plugins.md:53-87, 99-132, 151`; `hermes_cli/plugins.py:457-470` |
| **Replace the built-in browser tools** | Same plugin, with `override=True`, plus operator opt-in `plugins.entries.<plugin_id>.allow_tool_override: true` | The built-in names (`browser_navigate`, …) backed by your engine | `hermes_cli/plugins.py:462-476`; `tools/registry.py:666-674` |
| **Browser provider plugin** | Subclass `BrowserProvider`, return `{session_name, bb_session_id, cdp_url, features}`; select with `browser.cloud_provider: <name>` | Nothing new: Hermes' own tools drive whatever CDP URL you return | `website/docs/developer-guide/browser-provider-plugin.md:15-19, 62-112`; `agent/browser_provider.py:7-18` |
| **CDP endpoint only** | Set `browser.cdp_url` or `BROWSER_CDP_URL` to a Chromium you manage | Hermes' tools on your browser | `tools/browser_tool_cdp.py:51-60` |

Details that matter for an MCP-exposed engine:

- MCP ships in the standard install (`website/docs/user-guide/features/mcp.md:31`); the client is `mcp==2.0.0` (`pyproject.toml:401-405`).
- Per-server options include `timeout` (tool call, default 300 s), `connect_timeout` (60 s), `tools.include`/`exclude`, `supports_parallel_tool_calls`, `trust: untrusted`, `lazy` (`mcp-config-reference.md:46-71`; `tools/mcp_tool_common.py:44-47`).
- MCP results are capped at 50,000 chars before spill-to-disk, half the native cap (`tools/budget_config.py:17-20`).
- To avoid two competing browser surfaces, disable the built-in one: `/tools disable browser` or `agent.disabled_toolsets: [browser]` (`website/docs/reference/toolsets-reference.md:47, 55`; `website/docs/user-guide/configuration.md:945-949`; default `[]` at `hermes_cli/config_defaults.py:281`).
- An MCP server named `browser` merges with the built-in toolset rather than replacing it (`toolsets.py:307-315`).
- The user guide still shows single-underscore names `mcp_<server>_<tool>` (`mcp.md:567-579`); the code uses double underscores. The docs lag.
- Hermes is itself an MCP *server* only for messaging conversations (`mcp_serve.py:1-8`), not for its browser tools.

Native tool contract: handler receives `(args: dict, **kwargs)` with `task_id` in kwargs, must return a JSON string, and must return errors rather than raise (`website/docs/developer-guide/adding-tools.md:114-119`).

---

## 9. Performance-relevant numbers

### 9.1 Timeouts

| What | Value | Reference |
|---|---|---|
| agent-browser command | 30 s default, floor 5 s | `tools/browser_tool.py:141, 223` |
| `open` (navigation) | max(command timeout, 60 s) | `tools/browser_tool.py:145, 245-247` |
| First `open` (cold daemon + Chromium) | max(command timeout, 120 s) | `tools/browser_tool.py:146` |
| Post-redirect `about:blank` reset | 10 s | `tools/browser_tool.py:709` |
| Session `close` on teardown | 10 s | `tools/browser_tool_lifecycle.py:707` |
| Current-URL probe for SSRF guard | 5 s | `tools/browser_tool_eval_policy.py:49` |
| CDP `/json/version` discovery | 10 s | `tools/browser_tool_cdp.py:37` |
| `browser_exec` | 300 s default, 5–1800 s | `tools/browser_use_cli.py:79-81` |
| Drain after killing a timed-out exec | 10 s | `tools/browser_use_cli.py:566` |
| Harness daemon reload | 15 s | `tools/browser_use_cli.py:624` |
| `browser_cdp` | 30 s default, 1–300 s; WebSocket close 5 s | `tools/browser_cdp_tool.py:176, 299-302` |
| Supervisor start | 15 s | `tools/browser_supervisor.py:134, 509` |
| Supervisor connect / per CDP call / dialog response / evaluate | 10 s each | `tools/browser_supervisor.py:180, 212, 379, 444` |
| Supervisor stop | 5 s join, 2 s socket close | `tools/browser_supervisor.py:152-162` |
| Dialog bridge install steps | 5 s, 5 s, 3 s | `tools/browser_supervisor_dialogs.py:162-167` |
| Child-frame domain enable | 3 s | `tools/browser_supervisor_frames.py:116` |
| Dialog safety auto-dismiss | 300 s | `tools/browser_supervisor_dialogs.py:53` |
| Real-profile Chrome: wait for debug port | 30 s, polling every 0.25 s | `tools/browser_tool_real_profile.py:208-216` |
| Real-profile lock held by another call | 30 s | `tools/browser_tool.py:270` |
| Real-profile agent-browser helper commands | 15 s | `tools/browser_tool_real_profile.py:89` |
| Auth DB online backup budget | 5 s per database, 256 pages per step, 0.1 s sleep | `hermes_cli/browser_connect.py:397, 429` |
| Close browser holding profile | 15 s total; 8 s terminate, 3 s kill, 0.5 s lock poll | `hermes_cli/browser_connect.py:559-590` |
| Debug-browser launch grace | 2 s, 0.1 s interval | `hermes_cli/browser_connect.py:988-989` |
| TUI connect wait after launch | 10 s | `tui_gateway/methods_browser.py:74` |
| Default browser detection subprocess | 5 s | `hermes_cli/browser_connect.py:253-254` |
| Lightpanda ready | 10 s, 0.1 s poll; binary probe 3 s | `tools/browser_lightpanda.py:27-28, 120` |
| Camofox | command timeout; navigate 60 s; health 5 s; tab adoption 5 s | `tools/browser_camofox.py:36, 130, 248, 387` |
| Cloud session create / close / emergency close | 30 s / 10 s / 5 s | `plugins/browser/_common.py:85, 104, 124` |
| Aux vision LLM | 120 s, temperature 0.1 | `tools/browser_tool_vision.py:108-109` |
| `agent-browser --version` probe | 10 s | `hermes_constants.py:452` |
| Outer tool batch guard | 420 s | `agent/tool_executor.py:132` |
| MCP tool call / connect | 300 s / 60 s | `tools/mcp_tool_common.py:44-47`; `mcp-config-reference.md:57-58` |

### 9.2 Size caps and thresholds

| What | Value | Reference |
|---|---|---|
| Snapshot inline budget | 15,000 chars, floor 1,000 | `tools/browser_tool.py:151-152` |
| Stored full snapshot | 2,000,000 chars | `tools/browser_tool.py:155` |
| Truncation note reserve | `min(110 + len(path), max_chars // 2)`; `read_file` hint uses `limit=200` | `tools/browser_tool_snapshot.py:92, 104` |
| Scroll step | 500 px (Camofox: 5 repeated calls) | `tools/browser_tool.py:921-923` |
| `browser_exec` stderr | 4,000 chars | `tools/browser_use_cli.py:82` |
| Timeout error detail | 1,500 chars | `tools/browser_tool_session.py:94` |
| Non-JSON output echoed | 2,000 chars | `tools/browser_tool_session.py:609` |
| `frame_tree` | 30 entries, OOPIF depth 2 | `tools/browser_supervisor_frames.py:20-21` |
| Recent dialogs ring | 20 | `tools/browser_supervisor_dialogs.py:57` |
| Supervisor WebSocket max message | 50 MiB (`browser_cdp`: unlimited) | `tools/browser_supervisor.py:376`; `tools/browser_cdp_tool.py:176` |
| Camofox annotate context | 3,000 chars of snapshot | `tools/browser_camofox.py:576` |
| Lightpanda "empty snapshot" | < 20 chars | `tools/browser_tool_lightpanda_fallback.py:75` |
| Lightpanda "placeholder screenshot" | < 20,480 bytes | `tools/browser_tool_lightpanda_fallback.py:83` |
| Sandbox screenshot fetch | 16 MiB | `tools/browser_tool_session.py:561` |
| Vision embed | max dimension 1568 px; target 256 KiB (64 KiB–4 MiB); resize target 5 MiB; hard cap 20 MiB base64 | `tools/vision_tools.py:353-367`; `tools/vision_tools_history_budget.py:25-27` |
| Launch stderr tail | 2,000 bytes | `hermes_cli/browser_connect.py:1004` |
| Socket temp dir path | ≤ 50 chars before falling back to `/tmp` | `hermes_constants.py:753` |
| Tool result persistence | 100,000 chars per result, 200,000 per turn, 1,500 preview; MCP 50,000 | `tools/budget_config.py:13-20` |
| Deferred cancel frames (extension lane) | 512 | `gateway/browser_control_broker.py:26` |

### 9.3 Intervals, retention and retries

| What | Value | Reference |
|---|---|---|
| Inactivity timeout | 120 s, floor 30 s | `tools/browser_tool.py:389-398` |
| Janitor loop | every 30 s, 1 s stop granularity | `tools/browser_tool_lifecycle.py:415-437` |
| Orphan reap | at start and every 300 s | `tools/browser_tool.py:404` |
| Orphan grace for untracked daemons | max(3600 s, 20 × inactivity) | `tools/browser_tool.py:408` |
| Shared headed daemon idle | 24 h | `tools/browser_tool_session.py:176` |
| Janitor failures before force-reap | 3 | `tools/browser_tool.py:419` |
| Command retry on backend-level failure | 1 retry (2 attempts) | `tools/browser_tool_session.py:884-905` |
| Supervisor reconnect | 5 failures, backoff 0.5 s doubling to 10 s | `tools/browser_supervisor.py:39, 373, 389-390` |
| Browserbase 402 fallback | drop `keepAlive`, then `proxies` | `plugins/browser/browserbase/provider.py:19-23, 90-97` |
| Free debug port search | 10 ports after 9222 | `hermes_cli/browser_connect.py:951` |
| Screenshot retention | 24 h; scan at most hourly | `tools/browser_tool_lifecycle.py:559-566` |
| Recording retention | 72 h | `tools/browser_tool.py:1156` |
| Availability check cache | 30 s, 512 entries | `tools/registry.py:223-227` |
| Downgrade notice | once per 24 h | `tools/browser_use_cli.py:254` |
| Browser Use managed session | 5 min, proxy country `us` | `plugins/browser/browser_use/provider.py:26-27` |
| Firecrawl session TTL | 300 s | `plugins/browser/firecrawl/provider.py:55` |
| Extension ticket TTL / command timeout | 30 s / 30 s | `gateway/browser_control_broker.py:22-24` |
| Password manager unlock idle | 30 min | `credential-vault.md:58-59` |

### 9.4 Architectural cost drivers

- Each built-in tool call spawns one `agent-browser` process and reads its output from temp files (`tools/browser_tool_session.py:210-238, 716-762`). `browser_console` does two spawns (`tools/browser_tool.py:997-998`). `browser_navigate` does two: open, then snapshot (`tools/browser_tool.py:772, 734`).
- On non-local backends the SSRF guard adds another spawn per content-returning call to read `window.location.href` (`tools/browser_tool_eval_policy.py:44-56`).
- The supervisor fast path avoids a spawn for JS eval (`tools/browser_tool.py:1043-1065`).
- `browser_exec` spawns a fresh Python interpreter per call plus a long-lived harness daemon per session name (`tools/browser_use_cli.py:275-280, 605-609`). With the packaged Chromium it also runs `agent-browser get cdp-url` on every call (`tools/browser_use_cli.py:400-410`).

### 9.5 Hermes' own benchmark (`evals/browser_use/README.md:52-104`)

Run 8–10 August 2026, toscrape-family sites, oracle-checked, n ≤ 3 per cell.

| Model | Arm | OK | Mean tokens | Calls | Wall s |
|---|---|---|---|---|---|
| opus4.8 | built-in tools | 18/18 | 64,594 | 4.1 | 25.2 |
| opus4.8 | `browser_exec` | 18/18 | 25,934 | 2.0 | 17.5 |
| kimi-k3 | built-in tools | 18/18 | 56,464 | 5.3 | 50.0 |
| kimi-k3 | `browser_exec` | 18/18 | 19,230 | 2.4 | 33.3 |

Easy battery: sonnet-5 −30 % tokens at parity; qwen3-coder-30b roughly equal because weak coders retry their code (83-96). Caveats stated by the authors: no anti-bot sites, no heavy SPAs, and the raw per-run files were lost in a reboot; the tables were recovered from transcripts (102-114).

---

## 10. Computer use (paths and size only)

| Path | LOC |
|---|---|
| `tools/computer_use_tool.py` | 29 |
| `tools/computer_use/tool.py` | 964 |
| `tools/computer_use/cua_backend_session.py` | 521 |
| `tools/computer_use/doctor.py` | 474 |
| `tools/computer_use/cua_backend.py` | 430 |
| `tools/computer_use/cua_backend_capture.py` | 407 |
| `tools/computer_use/cua_backend_parse.py` | 271 |
| `tools/computer_use/cua_backend_daemon.py` | 212 |
| `tools/computer_use/schema.py` | 208 |
| `tools/computer_use/cua_backend_driver.py` | 180 |
| `tools/computer_use/backend.py` | 174 |
| `tools/computer_use/cua_backend_input.py` | 171 |
| `tools/computer_use/permissions.py` | 128 |
| `tools/computer_use/vision_routing.py` | 76 |
| `tools/computer_use/__init__.py` | 12 |
| **Total** | **4,257** |

Related: `tools/bot_desktop/` (2,191 Python lines plus `launcher.sh` 297; Linux only), `hermes_cli/subcommands/computer_use.py`, `computer_use_screen.py`, tests under `tests/computer_use/` and `tests/tools/test_computer_use*.py` (largest: `test_computer_use.py`, 2,456). Driver: `cua-driver` 0.21.0 with Windows x64 and ARM64 builds, talked to over MCP stdio (`pm/lock.json:78-105`; `pm/packages.py:847-897`; `pyproject.toml:415-421`). Docs: `website/docs/user-guide/features/computer-use.md` (710).

---

## 11. Corrections to the 2026-10-01 notes

| Note | Finding |
|---|---|
| Commit `357f51c4` | HEAD is now `bd0affe5`, committed 2026-10-03 |
| "About 504k lines of Python" | 895,846 lines of non-test Python in the repo; 795,588 in runtime packages. `agent` + `tools` + `hermes_cli` alone is 508,024, which is probably what the note counted. Tests add 1,274,444 lines in 5,626 files |
| "Dependencies install only on Python 3.14" | Correct in effect, but the mechanism is markers: `requires-python` allows 3.11–3.14, every dependency is gated on `>= 3.14` |
| "`browser-harness` powers the `browser_exec` code-mode tool" | Correct, and incomplete: it is the **default** mode. With default config the model sees `browser_exec` plus five vault tools, not the thirteen tools listed |
| Tool list | The ten built-ins, `browser_cdp` and `browser_dialog` are hidden unless `browser.backend: off` or Camofox is active. `browser_cdp`/`browser_dialog` additionally need a static CDP override |
| "`agent-browser` (Vercel Rust/Node CLI)" | Vendor not stated in the repo (UNVERIFIED). PM stages a native per-platform binary from the npm tarball; the code also refers to a Node process and a Rust daemon, so the Rust/Node description is consistent with the repo |
| Real-profile file locations | Confirmed |
| Supervisor in `tools/browser_supervisor*.py` | Confirmed, three files |
| Cloud providers in `agent/browser_provider.py` and `plugins/browser/*` | Confirmed; also `agent/browser_registry.py` and `plugins/browser/_common.py` |

Not in the notes: Lightpanda engine, Camofox backend, hybrid private-URL sidecar, browser-extension controller lane, Bot Desktop lease fence and sandbox-hosted browser, the benchmark, `browser_exec` named sessions.

Internal inconsistencies found in the repo: the stale `use_real_profile` config comment (section 5.1), the "LLM-summarized" wording in the `browser_snapshot` description (section 4.1), single- versus double-underscore MCP names (section 8), and the terminal-less session claim (section 6.1).

---

## 12. Lift / depend / leave

| Decision | Module | Why |
|---|---|---|
| Lift | `hermes_cli/browser_connect.py` | Cross-platform default-browser detection, lock-aware profile snapshot via SQLite online backup, dual-stack CDP discovery, debug launch. Four small helpers to shim |
| Lift | `tools/browser_supervisor*.py` | Persistent CDP session with reconnect, dialog capture including the XHR bridge, OOPIF tracking, thread-safe sync bridge. Only `websockets` plus four small helpers |
| Lift | `agent/vault_login_classifier.py` | Stdlib only; login/card/address/OTP field classification and origin-checked fill script |
| Lift | `tools/browser_tool_eval_policy.py`, `tools/browser_tool_snapshot.py`, redaction logic in `tools/browser_cdp_tool.py:34-76` | Small, self-contained policy and output-shaping code |
| Lift as reference | `evals/browser_use/tasks/*.json` and the arm design | Ready-made oracle-checked tasks for an A/B of tool surfaces |
| Depend on | `browser-harness`, `agent-browser`, Chrome for Testing | External engines; Hermes only wraps them |
| Re-implement the idea | `tools/browser_use_cli.py` | The contract is small (`BU_CDP_WS`/`BU_CDP_URL`, `BU_NAME`, `BH_AGENT_WORKSPACE`, code on stdin); the file is tied to Hermes session machinery |
| Leave | `tools/browser_tool.py` and its `_session`, `_lifecycle`, `_cloud`, `_install`, `_real_profile`, `_vision` siblings | Frame-walking facade proxy, PM, Bot Desktop lease, profile multiplexing, secret scopes, gateway process helpers |
| Leave | `tools/browser_vault_tool.py`, extension lane, Bot Desktop | Bound to Hermes approval prompts, gateway and Linux desktop |

---

## 13. Not verified

- Anything requiring execution: no import, install, test or browser run was performed.
- Internals, licence, helper signatures and Windows behaviour of `browser-harness` (pip package, not in the repo).
- Internals and vendor of `agent-browser`; exact snapshot text format.
- Live behaviour on Windows for cloud providers, Camofox and real-profile cookie decryption.
- The docs' claim that terminal-less sessions keep the built-in tools.
- Test purposes in section 3.9 (inferred from names).
