# Audit: spec §10, §11, §12, §13, §17 against the code (read-only)

Repo: `/Users/sharan/Downloads/Prj-Browser`. Nothing was modified and `.env` was never read. I ran `bap-browser config show/doc`, `bench` and `serve` from the scratchpad folder, and `pytest --collect-only` with the cache off. **No test was run**, so "passes" is unverified everywhere; `docs/status.md` claims 696 passed on 2026-10-04.

Headline: all 135 keys in `config.py` match the spec defaults, but 59 of them are read by nothing. The whole of §11 (budget, bench), the verify skill, the settings service and the micro VM image do not exist.

## 1. Key table (spec 10.3 against `src/bap_browser/config.py`)

"Read" means read in `src/` outside `config.py` and `config_doc.py`. "same" means the code default equals the spec default.

| Key | Spec default | Code default | Verdict | Read outside config.py |
|---|---|---|---|---|
| `data_dir` | `.bap-browser` | same | MATCH | defined but unused |
| `backend.kind` | `remote_headless` | same (the only value accepted) | MATCH | yes, `service/session.py:77` (reported only) |
| `backend.offered` | `["remote_headless"]` | same | MATCH | defined but unused |
| `browser.channel` | `chromium` | same | MATCH | yes, `driver/playwright_driver.py:50-53` |
| `browser.executable_path` | none | same | MATCH | yes, `playwright_driver.py:48` |
| `browser.headless` | true | same | MATCH | yes, `:41` |
| `browser.chromium_sandbox` | true | same | MATCH | yes, `:43` |
| `browser.cdp_url` | none | same | MATCH | defined but unused |
| `browser.user_data_dir` | none | same | MATCH | defined but unused |
| `browser.args` | `[]` | same | MATCH | yes, `:42` |
| `browser.ignore_default_args` | `[]` | same | MATCH | yes, `:46` |
| `browser.viewport` | `{1280, 800}` | same | MATCH | yes, `:71-74` |
| `browser.device_scale_factor` | none | same | MATCH | yes, `:79` |
| `browser.user_agent` | none | same | MATCH | yes, `:80` |
| `browser.locale` | none | same | MATCH | yes, `:76` |
| `browser.timezone_id` | none | same | MATCH | yes, `:77` |
| `browser.color_scheme` | none | same | MATCH | yes, `:78` |
| `browser.geolocation` | none | same | MATCH | yes, `:83` |
| `browser.permissions` | `[]` | same | MATCH | yes, `:85` |
| `browser.extra_http_headers` | `{}` | same | MATCH | yes, `:87` |
| `browser.ignore_https_errors` | false | same | MATCH | yes, `:68` |
| `browser.javascript_enabled` | true | same | MATCH | yes, `:69` |
| `browser.proxy.server` | none | same | MATCH | yes, `:54` |
| `browser.proxy.bypass` | none | same | MATCH | yes, `:56` |
| `browser.timeouts.launch_ms` | 30000 | same | MATCH | yes, `:44` |
| `browser.timeouts.navigation_ms` | 30000 | same | MATCH | yes, `:148` |
| `browser.timeouts.action_ms` | 10000 | same | MATCH | yes, `:147, 244, 407` |
| `browser.timeouts.page_reply_ms` | 5000 | same | MATCH | yes, `:158, 179` |
| `browser.timeouts.load_wait_ms` | 5000 | same | MATCH | yes, `:465` |
| `browser.timeouts.settle_ms` | 3000 | same | MATCH | yes, `:200, 445` |
| `browser.timeouts.frame_ms` | 100 | same | MATCH | yes, `:245, 443` |
| `browser.timeouts.popup_adopt_ms` | 3000 | same | MATCH | defined but unused |
| `browser.timeouts.wait_max_s` | 30 | same | MATCH | defined but unused |
| `browser.timeouts.idle_session_s` | 900 | same | MATCH | defined but unused |
| `browser.snapshot.default_mode` | `interactive` | same | MATCH | yes, `tools/browser_tools.py:50` |
| `browser.snapshot.max_chars` | 20000 | same | MATCH | yes, `browser_tools.py:53` |
| `browser.snapshot.max_depth` | 60 | same | MATCH | yes, `driver/snapshot.py:25` |
| `browser.snapshot.max_name_chars` | 120 | same | MATCH | yes, `snapshot.py:26` |
| `browser.snapshot.max_value_chars` | 200 | same | MATCH | yes, `snapshot.py:27` |
| `browser.snapshot.max_text_chars` | 300 | same | MATCH | yes, `snapshot.py:28`, `driver/session.py:32` |
| `browser.snapshot.max_options` | 25 | same | MATCH | yes, `snapshot.py:29` |
| `browser.snapshot.max_frame_depth` | 4 | same | MATCH | defined but unused |
| `browser.snapshot.include_iframes` | true | same | MATCH | defined but unused |
| `browser.snapshot.include_shadow_dom` | true | same | MATCH | yes, `snapshot.py:30` |
| `browser.snapshot.include_bboxes` | false | same | MATCH | yes, `browser_tools.py:54` |
| `browser.snapshot.after_navigation` | true | same | MATCH | yes, `browser_tools.py:74` |
| `browser.snapshot.after_action` | false | same | MATCH | yes, `browser_tools.py:91, 104` |
| `browser.screenshot.format` | `png` | same | MATCH | defined but unused |
| `browser.screenshot.jpeg_quality` | 80 | same | MATCH | defined but unused (the `jpeg_quality` in the driver is the viewer level's) |
| `browser.screenshot.max_dimension` | 1568 | same | MATCH | defined but unused |
| `browser.screenshot.full_page` | false | same | MATCH | defined but unused |
| `browser.screenshot.annotate_by_default` | false | same | MATCH | defined but unused |
| `browser.text.max_chars` | 20000 | same | MATCH | defined but unused |
| `browser.find.default_limit` | 10 | same | MATCH | defined but unused |
| `browser.find.max_limit` | 50 | same | MATCH | defined but unused |
| `browser.capture.console` | true | same | MATCH | defined but unused |
| `browser.capture.network` | true | same | MATCH | defined but unused |
| `browser.capture.max_console_entries` | 500 | same | MATCH | defined but unused |
| `browser.capture.max_network_entries` | 500 | same | MATCH | defined but unused |
| `browser.capture.max_entry_chars` | 2000 | same | MATCH | defined but unused |
| `browser.tabs.max_tabs` | 20 | same | MATCH | defined but unused |
| `browser.tabs.focus_new_tabs` | true | same | MATCH | defined but unused |
| `browser.dialogs.policy` | `agent` | same | MATCH | defined but unused |
| `browser.dialogs.timeout_s` | 120 | same | MATCH | defined but unused |
| `browser.dialogs.default_prompt_text` | `""` | same | MATCH | defined but unused |
| `browser.downloads.enabled` | true | same | MATCH | defined but unused |
| `browser.downloads.dir` | `.bap-browser/downloads` | same | MATCH | defined but unused |
| `browser.downloads.max_size_mb` | 500 | same | MATCH | defined but unused |
| `browser.uploads.enabled` | true | same | MATCH | defined but unused |
| `browser.uploads.allowed_dirs` | `[".bap-browser/uploads"]` | same | MATCH | defined but unused |
| `browser.javascript.allow_evaluate` | false | same | MATCH | defined but unused |
| `browser.javascript.max_result_chars` | 20000 | same | MATCH | defined but unused |
| `browser.input.scroll_step_px` | 400 | same | MATCH | defined but unused |
| `browser.input.type_delay_ms` | 0 | same | MATCH | yes, `playwright_driver.py:285` |
| `browser.input.slow_type_delay_ms` | 40 | same | MATCH | yes, `playwright_driver.py:285` |
| `browser.input.drag_steps` | 15 | same | MATCH | defined but unused |
| `browser.input.key_repeat_max` | 100 | same | MATCH | defined but unused |
| `code.enabled` | true | absent | IN SPEC NOT IN CODE | n/a (milestone 4) |
| `code.timeout_s` | 60 | absent | IN SPEC NOT IN CODE | n/a |
| `code.max_timeout_s` | 300 | absent | IN SPEC NOT IN CODE | n/a |
| `code.max_steps` | 50 | absent | IN SPEC NOT IN CODE | n/a |
| `code.max_output_chars` | 12000 | absent | IN SPEC NOT IN CODE | n/a |
| `safety.allowed_domains` | `[]` | same | MATCH | yes, `policy/url_policy.py:71` |
| `safety.blocked_domains` | `[]` | same | MATCH | yes, `url_policy.py:70` |
| `safety.allowed_schemes` | `["http","https","about","data","blob"]` | same | MATCH | yes, `url_policy.py:97` |
| `safety.allow_file_urls` | false | same | MATCH | yes, `url_policy.py:95` |
| `safety.block_private_networks` | false | same | MATCH | yes, `url_policy.py:122` |
| `safety.block_cloud_metadata` | true | same | MATCH | yes, `url_policy.py:115` |
| `safety.enforce_on_subresources` | false | same | MATCH | defined but unused |
| `safety.policy_cache_s` | 5 | same | MATCH | yes, `url_policy.py:109` |
| `safety.default_action_policy` | `allow` | same | MATCH | defined but unused |
| `safety.action_policies` | `{"browser_evaluate":"confirm","browser_upload_file":"confirm"}` | same | MATCH | defined but unused |
| `safety.ask_before` | `risky` | same | MATCH | defined but unused (the viewer's stand-in uses the name only) |
| `safety.redact_patterns` | `[]` | same | MATCH | yes, `driver/session.py:23` |
| `control.hold_timeout_s` | 300 | same | MATCH | yes, `service/session.py:233` |
| `control.approval_timeout_s` | 180 | same | MATCH | defined but unused |
| `control.approval_timeout_choices_s` | `[60,180,300,600]` | same | MATCH | defined but unused |
| `control.handoff_timeout_s` | 900 | same | MATCH | defined but unused |
| `control.approval_without_viewer` | `deny` | same | MATCH | defined but unused |
| `control.site_grant_lifetime` | `session` | same | MATCH | defined but unused |
| `sessions.max_concurrent` | 4 | same | MATCH | defined but unused |
| `server.host` | `127.0.0.1` | same | MATCH | yes, `service/server.py:44, 54`, `service/app.py:50` |
| `server.public_url` | none | same | MATCH | yes, `app.py:49` |
| `server.port` | 8765 | same | MATCH | yes, `server.py:36` |
| `server.token_env` | `BAP_BROWSER_TOKEN` | same | MATCH | yes, `server.py:34` |
| `server.auth_wait_s` | 10 | same | MATCH | yes, `app.py:78` |
| `server.shutdown_wait_s` | 3 | same | MATCH | yes, `server.py:37, 66` |
| `server.command_backlog` | 256 | same | MATCH | yes, `app.py:94` |
| `server.state_file` | `.bap-browser/service.json` | same | MATCH | yes, `server.py:91, 95` |
| `mcp.server_name` | `bap-browser` | same | MATCH | yes, `mcp/server.py:54` |
| `mcp.http_path` | `/mcp` | same | MATCH | defined but unused (no MCP over HTTP) |
| `viewer.quality` | `standard` | same | MATCH | yes, `service/session.py:85` |
| `viewer.quality_levels.standard` | `{24, 70, 1280}` | same | MATCH | yes, by name through `getattr`, `session.py:85` |
| `viewer.quality_levels.data_saver` | `{8, 50, 800}` | same | MATCH | yes, same line |
| `viewer.quality_levels.high` | `{30, 85, 1600}` | same | MATCH | yes, same line |
| `viewer.history_events` | 500 | same | MATCH | yes, `session.py:48` |
| `viewer.stale_after_s` | 5 | same | MATCH | defined but unused; the viewer holds its own copy, `viewer/src/options.ts:18` |
| `viewer.picture_heartbeat_s` | 2 | same | MATCH | yes, `session.py:183` |
| `viewer.idle_divider_s` | 10 | same | MATCH | defined but unused; viewer copy at `options.ts:19` |
| `viewer.takeover.release_chord` | `Ctrl+Alt+Enter` | same | MATCH | defined but unused; viewer copy at `options.ts:20` |
| `viewer.theme` | `system` | same | MATCH | defined but unused |
| `viewer.embed_origins` | `[]` | same | MATCH | yes, `app.py:51, 110` |
| `viewer.show_agent_pointer` | true | same | MATCH | defined but unused by the service; the viewer keeps it itself |
| `settings.file` | `.bap-browser/settings.json` | same | MATCH | defined but unused |
| `settings.locked` | `[]` | same | MATCH | defined but unused |
| `bridge.pairing_ttl_s` | 120 | absent | IN SPEC NOT IN CODE | n/a (milestone 2) |
| `bridge.heartbeat_s` | 15 | absent | IN SPEC NOT IN CODE | n/a |
| `bridge.dead_after_s` | 45 | absent | IN SPEC NOT IN CODE | n/a |
| `bridge.op_timeout_ms` | 15000 | absent | IN SPEC NOT IN CODE | n/a |
| `bridge.reconnect_grace_s` | 30 | absent | IN SPEC NOT IN CODE | n/a |
| `bridge.max_message_mb` | 16 | absent | IN SPEC NOT IN CODE | n/a |
| `permissions.mode` | `act_on_allowed_sites` | absent | IN SPEC NOT IN CODE | n/a (milestone 2) |
| `permissions.default_site_permission` | `ask` | absent | IN SPEC NOT IN CODE | n/a |
| `permissions.blocked_sites` | `[]` | absent | IN SPEC NOT IN CODE | n/a |
| `permissions.consequential_words` | 15 words | absent | IN SPEC NOT IN CODE | n/a |
| `permissions.preview_timeout_s` | 120 | absent | IN SPEC NOT IN CODE | n/a |
| `permissions.allow_evaluate` | false | absent | IN SPEC NOT IN CODE | n/a |
| `agent.provider` | `openai` | same | MATCH | yes, `cli.py:159` |
| `agent.model` | `gpt-5.6-luna` | same | MATCH | yes, `agent/openai_model.py:37` |
| `agent.api_key_env` | `OPENAI_API_KEY` | same | MATCH | yes, `cli.py:163` |
| `agent.base_url` | `https://api.openai.com/v1` | same | MATCH | yes, `openai_model.py:101` |
| `agent.request_timeout_s` | 120 | same | MATCH | yes, `openai_model.py:107` |
| `agent.max_steps` | 40 | same | MATCH | yes, `agent/loop.py:57` |
| `agent.max_tokens` | 4096 | same | MATCH | yes, `openai_model.py:51` |
| `logging.level` | `INFO` | same | MATCH | yes, `cli.py:131, 175` |
| `logging.event_log` | `.bap-browser/events.jsonl` | same | MATCH | yes, `tools/event_log.py:41` |
| `logging.log_tool_args` | true | same | MATCH | yes, `event_log.py:48` |
| `logging.max_result_chars` | 2000 | same | MATCH | yes, `event_log.py:55` |
| `bench.runs` | 30 | same | MATCH | defined but unused |
| `bench.warmup` | 5 | same | MATCH | defined but unused |
| `bench.budget_file` | `perf/budget.json` | same | MATCH | defined but unused; the file does not exist |
| `bench.results_dir` | `.bap-browser/bench` | same | MATCH | defined but unused |

Key counts, 152 rows:

| Verdict | Count |
|---|---|
| MATCH | 135 |
| DEFAULT DIFFERS | 0 |
| IN SPEC NOT IN CODE | 17 (`code` 5, `bridge` 6, `permissions` 6) |
| IN CODE NOT IN SPEC | 0 |

Of the 135 keys in code, 76 are read and 59 are defined but unused. `config doc` prints 135 key rows.

### Tunable numbers outside `config.py` (suspects)

| Where | Value |
|---|---|
| `src/bap_browser/driver/playwright_driver.py:35` | `SETTLE_FRAMES = 2` |
| `src/bap_browser/service/server.py:20` | `LARGEST_VIEWER_MESSAGE = 64 * 1024` |
| `src/bap_browser/service/session.py:33` | `LONGEST_KEY_NAME = 32` |
| `src/bap_browser/agent/openai_model.py:22` | `LONGEST_REFUSAL = 300` |
| `src/bap_browser/tools/sentences.py:19, 22` | `ROW_CHARS = 59`, `SHORTEST_NAME = 12` |
| `src/bap_browser/cli.py:78` | `--pace` default 1.0 second |
| `src/bap_browser/service/server.py:34` | token length 32 (borderline) |
| `viewer/src/options.ts:17-23` | `staleAfterS 5`, `idleDividerS 10`, `releaseChord` are copies of `viewer.*` defaults, not sent by the service; `toastMs 4000` and `tickMs 1000` have no key at all |
| `viewer/src/connection/socket.ts:37-38` | `DEFAULT_RECONNECT_MS = [500, 1000, 2000, 5000]`, `DEFAULT_RELEASE_AFTER_MS = 1000` |
| `viewer/src/main.tsx:17` | `HEARTBEAT_MS = 2000` (recorded demo only) |
| `viewer/src/App.tsx:329`, `viewer/src/components/BrowserPane.tsx:111` | fallback viewport 1280×800 |
| `viewer/scripts/record_demo.py:21-22` | 1280×800 and `JPEG_QUALITY = 72` (developer script) |

Not tunables: WebSocket close codes (`service/app.py:37-40`), metadata addresses, default ports. Not checked: the limits passed to `_number()` in `service/session.py`. `driver/snapshot_page.js` has no numeric literal of two or more digits.

## 2. Requirement tables

### §10.1, 10.2, 10.4

| Spec ref | Requirement | Verdict | Evidence | Missing / different |
|---|---|---|---|---|
| 10.1 | Every tunable value lives in `config.py` | PARTIAL | 135 keys with defaults | The suspects above; no automated search enforces it |
| 10.1 | Precedence: defaults < config.json < environment < user settings < per-session | PARTIAL | `config.py:419-431`; live run: file 7000 lost to env 9000; `tests/unit/test_config.py` (`test_environment_wins_over_the_file`, `test_session_options_win_over_the_environment`) | The user-settings layer does not exist. Code order is defaults < file < env < session |
| 10.1 | Nested sections merge; lists and single values replaced | BUILT | `deep_merge`, `config.py:391`; `test_nested_sections_merge_and_lists_are_replaced` | None |
| 10.1 | File found at command-line path, then `$BAP_BROWSER_CONFIG`, then `./config.json` | BUILT | `_find_file`, `config.py:435`; `--config` on `show`, `mcp`, `agent` | None |
| 10.1 | Env prefix `BAP_BROWSER__SECTION__KEY`, value read as JSON | BUILT | `ENV_PREFIX`, `_env_layer` (`config.py:20, 459`); CI uses `BAP_BROWSER__BROWSER__CHROMIUM_SANDBOX` | A value that is not JSON is kept as plain text (not in the spec) |
| 10.1 | User settings kept in `settings.file`, with locks, tighten-only and per-surface limits | NOT BUILT | `settings.file` and `settings.locked` are unused | The whole layer |
| 10.1 | Per-session options limited to six keys | PARTIAL | `SESSION_KEYS`, `config.py:23`; `test_a_setting_outside_the_session_list_is_refused` | Nothing in `src/` passes `session=`; two of the six (`cdp_url`, `user_data_dir`) are read by nothing |
| 10.1 | Unknown key stops start-up, naming it | BUILT | `extra="forbid"`, `_validate` (`config.py:499`); live: `error: unknown setting 'browser.nonsense' (from bad.json)`, exit 2 | An unknown top-level section from the environment is reported as "from the configuration", not "environment" |
| 10.1 | Secrets only from environment or `.env`; `.env` read at start; environment wins | BUILT | `env_file.py`; `cli.py:30`; proxy credentials at `playwright_driver.py:31-59`; `tests/unit/test_env_file.py` (6 functions); `test_the_configuration_holds_no_secret` | None |
| 10.1 | `config show` and `--sources` (source tracking) | BUILT | `cli.py:96`; `load_config_with_sources`; live output shows `(c.json)` and `(environment)` per key | None |
| 10.1 | `config init [--full]` | BUILT | `cli.py:113`; refuses to overwrite; 3 tests in `tests/unit/test_cli.py` | None |
| 10.1 | `config doc` generates the reference so it cannot drift | PARTIAL | `config_doc.py`; `test_doc_has_every_section_and_key` spot-checks 5 strings | Nothing compares the output with spec 10.3. Layout differs: one table per section, where the spec groups sections and joins keys on one row |
| 10.2 | Settings catalogue in `settings/catalogue.py` | NOT BUILT | No such file or folder | All of it |
| 10.2 | Settings screen drawn from the service's catalogue | DIFFERS | `viewer/src/demo/settings.ts` holds a client-side catalogue of 22 entries, kept in memory; `viewer/src/main.tsx:19` keeps only `colour_mode` and `show_agent_pointer` live | The spec has 23 entries (`notify_when_needed`, phase "Next", is absent). No saved file, nothing reaches the service |
| 10.2 | `GET` and `PATCH /api/settings`, refusal reasons, `settings_changed` event | NOT BUILT | Routes are only `/healthz`, `/api/sessions`, `/api/sessions/{name}/ws` (`service/app.py:102-104`) | All of it |
| 10.2 | `GET /api/config` for "About" | NOT BUILT | No route | All of it |
| 10.4 | Developer example is valid | BUILT | Loaded with `config show`, exit 0 | `downloads.dir` and `action_policies` are accepted but read by nothing |
| 10.4 | `deploy/config.vm.json` | PARTIAL | The spec's content loads, exit 0 | The file and `deploy/` do not exist |

### §11 Performance budget

| Spec ref | Requirement | Verdict | Evidence | Missing / different |
|---|---|---|---|---|
| 11.1 | Reference, published and target figures held as data | NOT BUILT | No `perf/`; figures exist only in the spec and `docs/research/performance.md` | `perf/budget.json` |
| 11.2 | Judging rules (median of 30 after 5 warm-up, 5% tolerance, p95, three browsers, two consecutive runs) | NOT BUILT | `bench.runs` and `bench.warmup` defined, unused | A bench that applies them |
| 11.3 | 42 per-tool lines | NOT BUILT | Only 4 tools exist (`tools/browser_tools.py:111-131`: navigate, snapshot, click, type); no timing code | Every line; 24 of the tools named |
| 11.4 | 15 page-size lines at 1,000, 10,000 and 50,000 elements | NOT BUILT | `tests/site/big.html?n=` generates a list of any size; `tests/e2e/test_snapshot.py::test_the_walk_stops_at_the_output_cap` checks behaviour, not time | Timed scenarios |
| 11.5 | 18 system lines (cold start, memory, live-view rate, leftovers, web vitals and others) | NOT BUILT | Related function tests only: `tests/e2e/test_live_view.py::test_the_rate_is_limited`, `tests/service/test_service.py::test_stopping_is_given_a_time_limit` | Every measurement |
| 11.6 | Output-size lines | PARTIAL | `tests/unit/test_registry.py::test_the_definitions_stay_small` (500 tokens for 4 tools, pro rata of 3,500 for 28); snapshot cap tests; `test_a_page_cannot_make_a_result_as_long_as_it_likes` | Not budget lines; no check of the 9-control form at 700 characters (unverified); `get_text`, `find`, `console`, screenshot do not exist |
| 11.7 | Next-step tool lines | NOT BUILT | Tools absent | Later work |
| 11.8 | Task-level reference figures | NOT BUILT | Reference only; no task set | Not due yet |
| 11.9 | Design requirements from the measurements | PARTIAL | No fixed pause (waits use `settle_ms` and `frame_ms`); walk stops at the cap; binary frames with `max_fps` as a setting (`app.py:35`, `playwright_driver.py:341-352`); per-host cache (`url_policy.py:109`) | No request interception at all; nothing measured on Chrome or Edge; "driver started once per service" unverified |
| 11.10 | Lines inside the micro VM image and for bridged backends | NOT BUILT | No image, no bridge | All of it |

### §12.1 to 12.4 Verification loop

| Spec ref | Requirement | Verdict | Evidence | Missing / different |
|---|---|---|---|---|
| 12.1, 12.2 | Budget file `perf/budget.json` | NOT BUILT | `perf/` absent | The file |
| 12.1 | `bap-browser bench` | NOT BUILT | CLI: `invalid choice: 'bench' (choose from 'config', 'mcp', 'agent')` | The command |
| 12.1 | Test pages in `tests/site/` and generated list pages | BUILT | 16 pages, including `big.html` | None |
| 12.1, 12.4 | Verify skill `.claude/skills/verify/SKILL.md` | NOT BUILT | `.claude/` absent | The skill |
| 12.1 | Commands in `CLAUDE.md` | PARTIAL | Install, test, format, types and viewer commands are there | No bench command |
| 12.3 | Bench table and `.bap-browser/bench/<timestamp>.json` | NOT BUILT | Nothing writes there | All of it |
| 12.4 steps 1-4 | Format, lint, types, tests, viewer checks | PARTIAL | `.github/workflows/ci.yml` runs all of them | Ubuntu and Chromium only; the spec says Chromium, Chrome and Edge |
| 12.4 step 5 | Smoke: service, scripted MCP client, form task, clean log | PARTIAL | `tests/service/test_mcp.py::test_an_agent_over_stdio_fills_and_submits_the_form`; `tests/service/test_agent_command.py` | No standalone smoke; no check for new ERROR or WARNING log lines (unverified) |
| 12.4 step 6 | No browser process alive after shutdown | NOT BUILT | No process-list check in `tests/` | The check |
| 12.4 step 7 | Bench, no FAIL | NOT BUILT | No bench | — |
| 12.4 step 8 | Viewer states: every state, console, accessibility, screenshots, both themes | BUILT | `tests/viewer/test_states.py` (state × theme × size, axe, shots to `.bap-browser/viewer-shots/`) | "Every state in the spec" not checked against §9.3 |
| 12.4 step 9 | Micro VM smoke | NOT BUILT | No `deploy/` | — |
| 12.4 end | Stop hook and fresh-context reviewer | NOT BUILT | No hooks | Optional in the spec |

### §12.5 Checklist (milestone 1): does a proof exist today?

| Item | Verdict | Proof today / what is missing |
|---|---|---|
| Every tool returns its documented result on three browsers | PARTIAL | `tests/e2e/*` (74 collected) cover 4 tools on Chromium only |
| Outside agent completes the form task over MCP | BUILT | `tests/service/test_mcp.py` |
| Python agent completes it in-process | BUILT | `tests/e2e/test_toolkit_in_process.py` |
| Form task with the core inside the micro VM image | NOT BUILT | No image |
| Person can watch, approve, pause, stop, take over, hand back | PARTIAL | `tests/unit/test_service_session.py`, `tests/service/test_service.py`, `tests/viewer/test_live_session.py`. Approval exists only in the viewer's recorded demo (`tests/viewer/test_walkthrough.py`); the service has no approvals |
| No image unless asked | PARTIAL | True by construction (`mcp/server.py` returns text only); no test over every tool |
| No raw HTML | PARTIAL | `tests/e2e/test_snapshot.py::test_page_text_cannot_break_the_shape_of_the_snapshot` (content not read, unverified); no test over every tool |
| Every observation respects its cap | PARTIAL | Cap tests in `tests/e2e/test_snapshot.py`, `tests/unit/test_toolkit.py`; the named proof (bench output-size lines) is absent |
| Suite passes with no new warnings | BUILT | `filterwarnings = ["error"]` in `pyproject.toml`; pass not verified by me |
| No browser process left after 100 cycles | NOT BUILT | No such test |
| Errors come back as results | BUILT | `tests/unit/test_toolkit.py` (`test_bad_calls_are_results_not_crashes`, `test_an_unexpected_failure_does_not_stop_the_toolkit`) |
| Blocked addresses stay blocked through redirects, clicks, pop-ups, frames | PARTIAL | The policy is checked only in `browser_navigate` (`tools/browser_tools.py:59`); the driver intercepts nothing. `tests/unit/test_url_policy.py` and `tests/e2e/test_address_policy.py` cover address spellings, not those four paths |
| Hidden text never in a snapshot | BUILT | `tests/e2e/test_snapshot.py::test_text_that_is_not_rendered_never_appears` |
| Passwords and typed text never in snapshot, event, log, timeline | BUILT | `test_snapshot.py::test_a_password_is_shown_as_dots`; `test_toolkit.py`; `test_service_session.py::test_what_a_person_types_is_neither_logged_nor_told_to_viewers`; `tests/unit/test_what_reaches_a_watcher.py` |
| Token required; wrong `Host` or `Origin` refused | BUILT | `tests/service/test_service.py` (token, other host, other site's page, listed origin). The micro VM half is untested |
| Approval that times out is denied | NOT BUILT | `control.approval_timeout_s` is unused |
| No tunable outside `config.py` | PARTIAL | No search test; suspects listed above |
| Every key has a default and is in the generated reference | PARTIAL | `test_default_matches_the_spec` covers 126 of 135 keys (9 `browser.*` emulation keys missing); no doc-versus-spec comparison |
| Unknown key stops start-up | BUILT | `tests/unit/test_config.py` (two tests) |
| Web, mobile, desktop sets exactly as 10.2 | PARTIAL | `viewer/src/demo/settings.test.ts` ("web has 16 settings and mobile 13 in milestone 1") tests the client stand-in only |
| Changing each web setting changes behaviour | PARTIAL | Only viewer-held settings act: `tests/viewer/test_walkthrough.py::test_a_setting_changes_what_the_viewer_does` |
| Locked setting refused; never loosen | PARTIAL | `viewer/src/demo/settings.test.ts` ("a locked setting is refused"); no API; no `would_loosen` test found (unverified) |
| Only design tokens | BUILT | `viewer/src/styles/styles.test.ts` (a test, not a lint rule) |
| Every state has label, icon, screenshot | BUILT | `tests/viewer/test_states.py`; list not compared with §9.3 |
| Wording follows 9.6 | PARTIAL | Strings are in `viewer/src/wording.ts`; the review is manual |
| Keyboard and focus ring | BUILT | `tests/viewer/test_walkthrough.py::test_the_keyboard_reaches_every_control_and_shows_where_it_is` |
| State changes announced | NOT BUILT | No live-region test found in `tests/viewer` or `viewer/src/App.test.tsx` (searched `aria-live`, `role=status`; unverified) |
| Contrast 4.5:1 and 3:1 | BUILT | `viewer/src/tokens.test.ts` |
| Reduced motion | BUILT | `test_walkthrough.py::test_with_reduced_motion_nothing_animates` |
| Nothing depends on colour alone (greyscale shots) | NOT BUILT | No greyscale shots; nearest is `test_states.py::test_who_is_driving_is_said_in_words_on_the_picture` |
| No budget line is FAIL | NOT BUILT | No bench |
| Every warning has a note | NOT BUILT | No budget file |
| Milestones 2, 3, 4 (11 items) | NOT BUILT | No extension, bridge, driver host or `browser_run` |

### §13 Testing

| Layer | Verdict | Evidence | Missing / different |
|---|---|---|---|
| Unit | PARTIAL | `tests/unit` (18 files): config, address policy, control state, wording | Settings catalogue, locks and limits are tested only in the viewer's vitest; "key names" unverified |
| End to end | PARTIAL | `tests/e2e` (9 files), 4 tools | Chromium only; no dialogs, pop-ups, tabs, uploads, downloads, drag, hover, shortcuts, canvas, persistent profile |
| Snapshot correctness | BUILT | `test_snapshot.py::test_roles_and_names_agree_with_playwrights_accessibility_snapshot` | — |
| Service | PARTIAL | `tests/service` (4 files): pause, takeover, stop, history on connect, MCP over stdio | No approvals, no request for a person, no MCP over HTTP |
| Settings | NOT BUILT | No API | All of it |
| Viewer components | BUILT | 11 vitest files, 221 `it(` declarations | Not run by me |
| Viewer end to end | BUILT | `tests/viewer` (3 files): states, keyboard, axe, both themes, reduced motion, phone width | "Shown inside another page" only as a header test in `test_service.py` |
| Safety | BUILT | `tests/service/test_service.py`, `tests/unit/test_what_reaches_a_watcher.py` | — |
| Micro VM | NOT BUILT | — | Image and test |
| Performance | NOT BUILT | — | Bench |
| Agent smoke (manual) | NOT BUILT | `docs/status.md`: the real model "has not been run against the real service" | A real run |
| Bridge, Backend conformance, Permissions, Code tool (4 rows) | NOT BUILT | — | Later milestones |
| Rules: real browser and service, only the model replaced | PARTIAL | e2e and service tests use real ones; warnings are errors | `tests/support/fakes.py` exists, so some unit tests use a stand-in driver (unverified how many) |

### §17 Running it

| Spec ref | Requirement | Verdict | Evidence | Missing / different |
|---|---|---|---|---|
| 17.1 | Long-path guidance | BUILT | `CLAUDE.md` gotcha on `UV_PROJECT_ENVIRONMENT` | — |
| 17.1 | Chrome and Edge from installed copies | PARTIAL | Channel passed through (`playwright_driver.py:52`; `tests/unit/test_driver_options.py`) | Never exercised in a real browser test |
| 17.1 | Tools: uv, Python 3.12+, Node for the viewer | BUILT | `pyproject.toml`, `README.md` | CI has no Windows job |
| 17.1 | Closing a session ends the whole process tree | PARTIAL | `test_navigation.py::test_closing_twice_is_harmless` | No leftover-process check |
| 17.1 | Real-profile copy | NOT BUILT | — | Next step in the spec |
| 17.2 | `deploy/Dockerfile` | NOT BUILT | No Dockerfile anywhere | The image |
| 17.2 | Image contents | NOT BUILT | Wheel does carry the viewer (`tests/service/test_packaging.py`) | The image |
| 17.2 | Runs without root | NOT BUILT | — | — |
| 17.2 | `bap-browser serve --config …` | NOT BUILT | CLI rejects `serve`; the service starts only inside `agent` | The command |
| 17.2 | `deploy/config.vm.json` | NOT BUILT | Keys exist and load | The file |
| 17.2 | Token from the environment | BUILT | `service/server.py:34`; `test_the_token_can_come_from_the_environment` | — |
| 17.2 | Core checks `Host`, `Origin`, token | BUILT | `service/app.py:49-64`; tests in `test_service.py` | — |
| 17.2 | Sandbox switch | BUILT | `playwright_driver.py:43`; used in CI | — |
| 17.2 | Small `/dev/shm` does not crash Chromium | NOT BUILT | No such launch flag in `src/` | — |
| 17.2 | Kept sign-ins through `browser.user_data_dir` | NOT BUILT | Key unused; no persistent context | — |
| 17.2 | Stop signal closes every session and browser | PARTIAL | Ctrl+C path in `agent/command.py:81-82` | No signal handler found in `src/` |

## 3. Test counts per folder

| Folder | Files | Test functions (`def test_` / `async def test_`) | `parametrize` decorators | Collected by pytest |
|---|---|---|---|---|
| `tests/unit` | 18 | 181 | 18 | 495 |
| `tests/e2e` | 9 | 68 | 1 | 74 |
| `tests/service` | 4 | 35 | 0 | 35 |
| `tests/viewer` | 3 | 22 | 8 | 92 |
| Total | 34 | 306 | 27 | 696 |

- `test_default_matches_the_spec` alone expands to 126 cases.
- The viewer has 11 vitest files with 221 `it(` declarations and 14 `.each` uses; `docs/status.md` says 347 pass (not run).
- No test selects Chrome or Edge.

## 4. Ten most important gaps

1. **No performance system.** `perf/budget.json`, `bap-browser bench` and all of §11 are absent; four `bench.*` keys point at nothing.
2. **No settings service.** No `settings/catalogue.py`, no `/api/settings`, no `/api/config`, no user-settings layer. The viewer's settings screen runs on an in-memory stand-in.
3. **59 of 135 keys do nothing.** Some are safety-shaped and would mislead a deployer: `safety.action_policies`, `safety.ask_before`, `safety.default_action_policy`, `safety.enforce_on_subresources`, `control.approval_*`, `sessions.max_concurrent`, `browser.timeouts.idle_session_s`.
4. **Address policy covers only `browser_navigate`.** Nothing checks redirects, link clicks, pop-ups or frames, which the checklist requires.
5. **No approvals or request-for-a-person in the service.** These exist only in the viewer's recorded demo.
6. **No micro VM.** No `deploy/`, Dockerfile, `serve` command, signal handling or `/dev/shm` handling.
7. **4 of 28 tools exist**, tested on Chromium only; CI is Ubuntu only.
8. **Persistent profile and attach are not wired.** `browser.user_data_dir` and `browser.cdp_url` are accepted per session but read by nothing, and no code passes per-session options.
9. **Tunables outside `config.py`.** `LARGEST_VIEWER_MESSAGE`, `SETTLE_FRAMES`, `LONGEST_KEY_NAME`, `LONGEST_REFUSAL`, the viewer's reconnect delays, toast and tick times, and the viewer's copies of `viewer.stale_after_s`, `idle_divider_s` and `release_chord`.
10. **No verify skill and no drift check.** `.claude/skills/verify/SKILL.md` is absent, there is no leftover-process test, and nothing compares `config doc` with spec 10.3 (9 keys also miss the defaults test).

## 5. Counts per verdict

| Section | BUILT | PARTIAL | NOT BUILT | DIFFERS | Rows |
|---|---|---|---|---|---|
| §10.1, 10.2, 10.4 | 8 | 5 | 4 | 1 | 18 |
| §11 | 0 | 2 | 8 | 0 | 10 |
| §12.1 to 12.4 | 2 | 3 | 8 | 0 | 13 |
| §12.5 milestone 1 | 13 | 12 | 7 | 0 | 32 |
| §12.5 later milestones | 0 | 0 | 11 | 0 | 11 |
| §13 (the four later-milestone layers counted singly) | 4 | 4 | 8 | 0 | 16 |
| §17 | 5 | 3 | 8 | 0 | 16 |
| **Total** | **32** | **29** | **54** | **1** | **116** |

Unverified: whether any test passes; whether the viewer state list equals spec §9.3; what the HTML-shape test asserts; how many unit tests use the stand-in driver; whether the driver starts once per service; whether a live-region or `would_loosen` test exists under another name.
