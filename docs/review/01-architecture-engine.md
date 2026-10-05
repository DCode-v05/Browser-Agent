# Spec vs code audit: §3, §4, §5 of `docs/bap-browser-spec.md`

Read-only; nothing was changed and `.env` was not opened. Nothing was run: every verdict comes from reading code and tests.

Paths are relative to `/Users/sharan/Downloads/Prj-Browser/src/bap_browser/` unless they start with `tests/`, `viewer/`, `docs/` or a root file name. "M1 slice N" is the slice in spec §14.1; "Next #N" is §14.5.

**In short:** the code is slices 0 to 4 of milestone 1: one backend (`remote_headless`), one tab, four tools (navigate, snapshot, click, type), the live picture, and pause / take over / hand back / stop. Everything else in these sections is absent, mostly as the spec's later slices plan.

## 1. Tables

### §3.1 Stack

| Spec ref | Requirement | Verdict | Evidence | What is missing / different |
|---|---|---|---|---|
| 3.1 | Python 3.12+, uv, `uv.lock` | BUILT | `pyproject.toml:6`, `uv.lock` | |
| 3.1 | Playwright behind a driver interface | BUILT | `driver/base.py:55`, `driver/playwright_driver.py:111` | |
| 3.1 | CDP for the live picture | BUILT | `driver/playwright_driver.py:150,156,324` | |
| 3.1 | CDP for takeover input | DIFFERS | `driver/playwright_driver.py:357-402` | Spec: direct CDP. Code: Playwright's `mouse` and `keyboard` API |
| 3.1 | CDP for document-only request checks | NOT BUILT | none | `docs/status.md` "Next" item 5 |
| 3.1 | Pydantic settings, unknown keys rejected | BUILT | `config.py:49-50,506` | |
| 3.1 | Starlette on uvicorn, one WebSocket per viewer | BUILT | `service/app.py:100`, `service/server.py:56` | |
| 3.1 | Official MCP SDK, stdio | BUILT | `mcp/server.py:51-56` | |
| 3.1 | MCP streamable HTTP mounted in the Starlette app | NOT BUILT | no `/mcp` route in `service/app.py:101-107` | M1 slice 6. `mcp.http_path` exists in config only |
| 3.1 | Pillow for downscaling and ref labels | NOT BUILT | not in `pyproject.toml:7-14` | Arrives with screenshots, M1 slice 5 |
| 3.1 | Viewer in TypeScript/React/Vite; built files ship in the package | BUILT | `viewer/package.json`, `pyproject.toml:31-34`, `service/app.py:46-48`, `tests/service/test_packaging.py:10` | |
| 3.1 | Micro VM image `deploy/Dockerfile` | NOT BUILT | no `deploy/` | M1 slice 8 |
| 3.1 | Extension | NOT BUILT | no `extension/` | Milestone 2 |
| 3.1 | Driver host | NOT BUILT | no `driver-host` command | Milestone 3 |
| 3.1 | ruff, pyright, pytest, pytest-asyncio | BUILT | `pyproject.toml:19-25,36-68`, `.github/workflows/ci.yml:25-29` | |
| 3.1 | `tsc --noEmit`, ESLint, Vitest + Testing Library, axe-core, npm lock | BUILT | `viewer/package.json`, `viewer/package-lock.json`, `ci.yml:17-21` | axe-core is a dependency; how it is run was not checked |
| 3.1 | Versions pinned in lockfiles (Playwright 1.63.0) | BUILT | `uv.lock:474-475` | |
| 3.1 | Stack recorded in `docs/adr/0001-stack.md` | BUILT | file exists | Content not compared |

### §3.2 Layout

| Spec ref | Requirement | Verdict | Evidence | What is missing / different |
|---|---|---|---|---|
| 3.2 | `README.md` | BUILT | exists | |
| 3.2 | `CLAUDE.md` | BUILT | exists | |
| 3.2 | `pyproject.toml`, `uv.lock` | BUILT | exist | |
| 3.2 | `config.example.json` | NOT BUILT | absent | `bap-browser config init` writes a starter instead (`cli.py:113`) |
| 3.2 | `.env.example` | BUILT | exists | |
| 3.2 | `.gitignore` | BUILT | exists | |
| 3.2 | `docs/bap-browser-spec.md` | BUILT | exists | |
| 3.2 | `docs/bap-browser-spec.html` | BUILT | exists | |
| 3.2 | `docs/browser-agent-perception.html` | BUILT | exists | |
| 3.2 | `docs/adr/` | BUILT | `0001-stack.md` | |
| 3.2 | `docs/plans/` | BUILT | 3 plans | |
| 3.2 | `docs/research/` | BUILT | 6 reports | |
| 3.2 | `perf/budget.json` | NOT BUILT | absent | M1 slice 9. `bench.budget_file` points at it (`config.py:365`) |
| 3.2 | `deploy/Dockerfile` | NOT BUILT | absent | M1 slice 8 |
| 3.2 | `deploy/config.vm.json` | NOT BUILT | absent | M1 slice 8 |
| 3.2 | `.claude/skills/verify/SKILL.md` | NOT BUILT | absent | M1 slice 9 |
| 3.2 | `config.py` | BUILT | `config.py` | |
| 3.2 | `errors.py` | BUILT | `errors.py` | |
| 3.2 | `results.py` | BUILT | `results.py` | |
| 3.2 | `keys.py` | NOT BUILT | absent | Key-name handling, with the press tool in M1 slice 5 |
| 3.2 | `settings/catalogue.py` | NOT BUILT | absent | M1 slice 7 |
| 3.2 | `settings/store.py` | NOT BUILT | absent | M1 slice 7 |
| 3.2 | `driver/base.py` | BUILT | `driver/base.py` | |
| 3.2 | `driver/playwright_driver.py`: launch, attach, tabs, actions | PARTIAL | `driver/playwright_driver.py` | Launch only. No attach, one tab, two actions (click, type) |
| 3.2 | `driver/bridge_driver.py` | NOT BUILT | absent | Milestone 2 |
| 3.2 | `driver/snapshot.py`: assembly, refs, caps | DIFFERS | `driver/snapshot.py:12-34` | It only builds the script's arguments. Assembly, refs and caps are in `snapshot_page.js`; the ref counter is in `playwright_driver.py:121,233` |
| 3.2 | `driver/snapshot_page.js` | BUILT | `driver/snapshot_page.js` | |
| 3.2 | `driver/screenshots.py` | NOT BUILT | absent | M1 slice 5 |
| 3.2 | `driver/dialogs.py` | NOT BUILT | absent | M1 slice 5 |
| 3.2 | `driver/downloads.py` | NOT BUILT | absent | M1 slice 5 |
| 3.2 | `driver/network_log.py` | NOT BUILT | absent | M1 slice 5 |
| 3.2 | `bridge/protocol.py` | NOT BUILT | absent | Milestone 2 |
| 3.2 | `bridge/gateway.py` | NOT BUILT | absent | Milestone 2 |
| 3.2 | `bridge/host.py` | NOT BUILT | absent | Milestone 3 |
| 3.2 | `policy/url_policy.py` | BUILT | exists | Content is outside these sections |
| 3.2 | `policy/approvals.py` | NOT BUILT | absent | M1 slice 6 |
| 3.2 | `policy/redaction.py` | BUILT | `policy/redaction.py` | |
| 3.2 | `tools/registry.py`: definitions and dispatch | DIFFERS | `tools/registry.py`, `tools/toolkit.py:57` | Registry holds definitions only; dispatch is in `tools/toolkit.py` |
| 3.2 | `tools/browser_tools.py`: the tools of §6 | PARTIAL | `tools/browser_tools.py:109-137` | 4 tools: navigate, snapshot, click, type |
| 3.2 | `code/checker.py` | NOT BUILT | absent | Milestone 4 |
| 3.2 | `code/worker.py` | NOT BUILT | absent | Milestone 4 |
| 3.2 | `code/api.py` | NOT BUILT | absent | Milestone 4 |
| 3.2 | `service/app.py`: routes, WebSocket, lifecycle | BUILT | `service/app.py` | Start and stop of the server live in `service/server.py` |
| 3.2 | `service/settings_api.py` | NOT BUILT | absent | M1 slice 7 |
| 3.2 | `service/session.py`: queue, timeline, history, limits | PARTIAL | `service/session.py`, `service/events.py:51` | No limits (idle time-out, session count). The queue is a lock in `tools/toolkit.py:50` |
| 3.2 | `service/control.py` | DIFFERS | `service/session.py:228-297` | No such file; control lives in `service/session.py`. Approvals and help requests are absent |
| 3.2 | `service/events.py`: event types | DIFFERS | `service/events.py` | Holds the hub, history and per-viewer queue. Events are plain dicts built in `service/session.py` |
| 3.2 | `service/auth.py` | DIFFERS | `service/app.py:49-65,70-84,109` | No such file; token, Host and Origin checks are in `app.py` |
| 3.2 | `service/screencast.py` | DIFFERS | `driver/playwright_driver.py:309-355`, `service/session.py:176-190` | No such file |
| 3.2 | `service/remote_input.py` | DIFFERS | `service/session.py:123-174` | No such file |
| 3.2 | `mcp/server.py`: stdio and HTTP | PARTIAL | `mcp/server.py` | stdio only |
| 3.2 | `bench/` | NOT BUILT | absent | M1 slice 9 |
| 3.2 | `cli.py` | PARTIAL | `cli.py:38-93` | Has `config show/init/doc`, `mcp`, `agent`. No `serve`, `doctor`, `driver-host` |
| 3.2 | `viewer_dist/` (generated) | BUILT | `.gitignore`, `pyproject.toml:34` | Folder itself not inspected, as instructed |
| 3.2 | `viewer/` with `src/tokens.css`, `components/`, `state/`, `protocol.ts` | BUILT | all present | |
| 3.2 | `extension/` | NOT BUILT | absent | Milestone 2 |
| 3.2 | `tests/unit/` | BUILT | exists | |
| 3.2 | `tests/e2e/` | BUILT | exists | |
| 3.2 | `tests/service/` | BUILT | exists | |
| 3.2 | `tests/viewer/` | BUILT | exists | |
| 3.2 | `tests/safety/` | NOT BUILT | absent | Safety tests sit in `tests/unit` and `tests/e2e/test_address_policy.py` |
| 3.2 | `tests/site/` | BUILT | 16 pages | |

"Each folder has one purpose and a small interface" was not judged.

### §4.1 to §4.4 Shape, backends, parts, transports

| Spec ref | Requirement | Verdict | Evidence | What is missing / different |
|---|---|---|---|---|
| 4.1 | One contract: the same tools whatever the transport | BUILT | `tools/toolkit.py:57`, `mcp/server.py:29-48` | |
| 4.1 | The core is one library | BUILT | package `bap_browser` | |
| 4.1 | Three tiers; the core runs in a micro VM | NOT BUILT | no `deploy/` | M1 slice 8 |
| 4.1 | On a developer's machine: core runs directly, browser launches locally, viewer at a local address | BUILT | `agent/command.py:42-49` | |
| 4.2 | `remote_headless`: the core launches the browser, Playwright driver | BUILT | `driver/playwright_driver.py:139-161` | |
| 4.2 | `takeover_chrome` | NOT BUILT | `config.py:59` allows only `remote_headless` | Milestone 2 |
| 4.2 | `bundled_chromium` | NOT BUILT | same | Milestone 3 |
| 4.2 | Surfaces (web, mobile, desktop) and the backends each offers | NOT BUILT | no surface notion in the service; `backend.offered` is never read | M1 slice 7 |
| 4.2 | Every backend gives the same tools, results and events | NOT BUILT | one backend only | Milestones 2 and 3 |
| 4.2 | A backend states its operations; a tool needing a missing one is not offered | NOT BUILT | none | Milestone 2 |
| 4.3 | Driver: every action, snapshots and screenshots | PARTIAL | `driver/base.py:55-96` | See §5.1 |
| 4.3 | Tool layer: definitions, policy check, redaction, event log | BUILT | `tools/toolkit.py`, `tools/browser_tools.py:59`, `tools/event_log.py` | |
| 4.3 | Session: one browser, call queue, timeline, history, limits | PARTIAL | `service/session.py:36-66` | No limits: `sessions.max_concurrent` and `timeouts.idle_session_s` are never read |
| 4.3 | Control: who is driving, approvals, requests for a person | PARTIAL | `service/session.py:228-297` | Who is driving only |
| 4.3 | Settings | NOT BUILT | none | M1 slice 7 |
| 4.3 | Agent gateway: MCP over stdio and HTTP, calls become queued session work | PARTIAL | `mcp/server.py:51-56` | stdio only. It uses a bare `Toolkit`, with no `ServiceSession`, so no control and no viewer |
| 4.3 | Viewer gateway: serves viewer, streams events and frames, takes commands and input, serves settings | PARTIAL | `service/app.py:69-98,115-155` | Settings not served |
| 4.3 | Bridge gateway | NOT BUILT | none | Milestone 2 |
| 4.3 | Extension | NOT BUILT | none | Milestone 2 |
| 4.3 | Driver host | NOT BUILT | none | Milestone 3 |
| 4.3 | Script worker | NOT BUILT | none | Milestone 4 |
| 4.3 | Viewer | BUILT | `viewer/src/` | Not audited here |
| 4.3 | Bench | NOT BUILT | none | M1 slice 9 |
| 4.3 | Each part tested alone | BUILT | `tests/e2e/*` (driver on local pages), `tests/unit/test_service_session.py` with `tests/support/fakes.py` (control, fake driver), `tests/service/test_service.py` and `test_mcp.py` (scripted clients) | Viewer on a recorded stream not checked |
| 4.4 | In-process | BUILT | `tests/e2e/test_toolkit_in_process.py:17` | |
| 4.4 | `bap-browser mcp`: whole core, one default session, viewer address on the error stream and in the state file | PARTIAL | `cli.py:128-136`, `mcp/server.py:51-56` | Tools over stdio work. No service starts, so no viewer, no address printed, no state file |
| 4.4 | `bap-browser serve` | NOT BUILT | no such command | M1 slice 6 |
| 4.4 | Browser starts on the first tool call | DIFFERS | `driver/session.py:55-57` (lazy), `service/session.py:68-70`, `agent/command.py:44` | Lazy under `mcp`. Under `agent`, `ServiceSession.start()` launches it before any call |
| 4.4 | Playwright driver process starts once per service | DIFFERS | `driver/playwright_driver.py:142` | Each driver start calls `async_playwright().start()`: once per session, and again after a crash restart |

### §4.5 Who is driving

| Spec ref | Requirement | Verdict | Evidence | What is missing / different |
|---|---|---|---|---|
| 4.5 | Agent state: calls run | BUILT | `service/session.py:51,247-253` | |
| 4.5 | Waiting for approval | NOT BUILT | `ControlState` at `service/session.py:21` lacks it | M1 slice 6 |
| 4.5 | Person requested (`browser_request_human`) | NOT BUILT | no such tool | M1 slice 6 |
| 4.5 | Person: calls wait; nothing reaches the agent | BUILT | `service/session.py:110-111,238-246` | |
| 4.5 | Paused: calls wait | BUILT | `service/session.py:108-109` | |
| 4.5 | Ended: returns "the session was ended by a person" | BUILT | `service/session.py:29,235-237` | "The session has ended." when not ended by a person |
| 4.5 rule 1 | Held for `control.hold_timeout_s`, then a plain message, not an error | BUILT | `service/session.py:25-28,233-245`, `tools/toolkit.py:63-68` | |
| 4.5 rule 2 | Takeover begins when the action in progress finishes | BUILT | `service/session.py:56,257-266` | |
| 4.5 rule 3 | Hand-back note: address before and after, tabs opened or closed, take a fresh snapshot | PARTIAL | `service/session.py:268-285` | Tabs opened or closed are not reported |
| 4.5 rule 4 | Approval unanswered within `approval_timeout_s` is denied | NOT BUILT | none | M1 slice 6 |
| 4.5 rule 5 | No viewer: "confirm" tool denied; `approval_without_viewer` | NOT BUILT | none; `hub.viewers` (`service/events.py:61`) exists but is unused for this | M1 slice 6 |
| 4.5 rule 6 | Code-tool steps check who is driving | NOT BUILT | none | Milestone 4 |
| 4.5 rule 7 | Bridge disconnected: wait `reconnect_grace_s`, then a plain message | NOT BUILT | none | Milestone 2 |

### §4.6 One tool call, end to end

| Spec ref | Requirement | Verdict | Evidence | What is missing / different |
|---|---|---|---|---|
| 4.6 step 1 | Call arrives in-process or over MCP | BUILT | `tools/toolkit.py:57`, `mcp/server.py:38` | MCP over stdio only |
| 4.6 step 2 | Calls run one at a time, in order | BUILT | `tools/toolkit.py:50,62` | A lock, not a queue; same effect |
| 4.6 step 3 | Control checks who is driving | BUILT | `tools/toolkit.py:62`, `service/session.py:230-255` | |
| 4.6 step 3 | "Confirm" tools ask the viewer | NOT BUILT | `safety.action_policies` never read | M1 slice 6 |
| 4.6 step 4 | Policy check, then the driver acts | BUILT | `tools/browser_tools.py:59-73` | Only navigation is checked |
| 4.6 step 4 | Bridged operation and the bridge's own permission rules | NOT BUILT | none | Milestone 2 |
| 4.6 step 5 | Tab list appended | BUILT | `tools/toolkit.py:83,148-152` | |
| 4.6 step 5 | Recent events appended | NOT BUILT | none | Needs dialogs, downloads, console: M1 slice 5 |
| 4.6 step 5 | Then redaction, then the event log | BUILT | `tools/toolkit.py:83-85` | |
| 4.6 step 6 | "Step started" and "step finished" events; viewer keeps the frame as the step's picture | BUILT | `service/session.py:194-216`, `viewer/src/connection/socket.ts:143-147` | |
| 4.6 step 7 | Result returns to the agent | BUILT | `tools/toolkit.py:89` | |

### §4.7 HTTP surface

| Spec ref | Requirement | Verdict | Evidence | What is missing / different |
|---|---|---|---|---|
| 4.7 | `GET /` viewer files, no access check | BUILT | `service/app.py:106` | |
| 4.7 | `GET /api/sessions`, token | BUILT | `service/app.py:61-67,103` | Returns `{"sessions":[{"id","state"}]}` |
| 4.7 | `POST /api/sessions` | NOT BUILT | none | M1 slice 6 (`serve`) |
| 4.7 | `DELETE /api/sessions/{id}` | NOT BUILT | none | M1 slice 6 |
| 4.7 | `GET /api/sessions/{id}/ws`, token first, matching Origin | BUILT | `service/app.py:69-98,104` | |
| 4.7 | `GET /api/settings?surface=` | NOT BUILT | none | M1 slice 7 |
| 4.7 | `PATCH /api/settings` | NOT BUILT | none | M1 slice 7 |
| 4.7 | `GET /api/config` | NOT BUILT | none | Only the CLI `config show --sources` (`cli.py:96`) |
| 4.7 | `POST /api/browsing-data/clear` | NOT BUILT | none | No slice named |
| 4.7 | `/mcp` | NOT BUILT | none | M1 slice 6 |
| 4.7 | `POST /api/bridge/pairings` | NOT BUILT | none | Milestone 2 |
| 4.7 | `/bridge` | NOT BUILT | none | Milestone 2 |
| 4.7 | `GET /healthz`, no data | BUILT | `service/app.py:58-59,102` | |

### §4.8 Viewer protocol

| Spec ref | Requirement | Verdict | Evidence | What is missing / different |
|---|---|---|---|---|
| 4.8 | One WebSocket per viewer and session | BUILT | `service/app.py:104` | |
| 4.8 | First message carries the token; nothing sent before it | BUILT | `service/app.py:76-84`, `tests/service/test_service.py:190` | |
| 4.8 | Text is JSON; binary is one type byte plus a JPEG | BUILT | `service/app.py:35,158-162` | |
| 4.8 replay 1 | `session_started` always first | BUILT | `service/events.py:102-103` | |
| 4.8 replay 2 | Last `viewer.history_events` events; current `control_changed` and `tab_changed` when older ones were dropped | BUILT | `service/events.py:51,104-112` | |
| 4.8 replay 3 | Newest picture | BUILT | `service/events.py:113-114` | |
| 4.8 replay 4 | `caught_up` | BUILT | `service/app.py:93` | |
| 4.8 | Same replay on reconnect | BUILT | `service/app.py:89-93` | Viewer keeping its earlier pictures not checked |
| 4.8 | Bad token closes with 4401; viewer does not retry | BUILT | `service/app.py:37,82-84`, `viewer/src/connection/socket.ts:36,113` | |
| 4.8 S→V | `session_started` with `session, agent, backend, browser, viewport, ts` | BUILT | `service/session.py:72-82` | |
| 4.8 S→V | `control_changed` with `state, since` | PARTIAL | `service/session.py:292` | Sends `agent`, `paused`, `person` only. `ended` is never sent this way (only `session_ended`, `service/session.py:93-97`) |
| 4.8 S→V | `step_started` with `step, tool, label, target, ts` | BUILT | `service/session.py:194-198` | The spec's example also shows `session`; the field table does not, and the code does not send it |
| 4.8 S→V | `step_finished` with `step, ok, ms, chars, summary, url` | BUILT | `service/session.py:204-214` | |
| 4.8 S→V | `tab_changed`, tabs with `id, title, url, active, attention` | PARTIAL | `service/session.py:303-311` | No `attention` |
| 4.8 S→V | `approval_requested` | NOT BUILT | none | M1 slice 6 |
| 4.8 S→V | `approval_closed` | NOT BUILT | none | M1 slice 6 |
| 4.8 S→V | `help_requested` | NOT BUILT | none | M1 slice 6 |
| 4.8 S→V | `help_closed` | NOT BUILT | none | M1 slice 6 |
| 4.8 S→V | `dialog_opened` | NOT BUILT | none | M1 slice 5 |
| 4.8 S→V | `dialog_closed` | NOT BUILT | none | M1 slice 5 |
| 4.8 S→V | `download_saved` | NOT BUILT | none | M1 slice 5 |
| 4.8 S→V | `picture_current` with `ts` | BUILT | `service/session.py:189-190` | |
| 4.8 S→V | `caught_up` with `ts` | BUILT | `service/app.py:93` | |
| 4.8 S→V | `navigation_blocked` with `url, reason, ts` | BUILT | `service/session.py:218-226` | |
| 4.8 S→V | `settings_changed` | NOT BUILT | none | M1 slice 7 |
| 4.8 S→V | `bridge_changed` | NOT BUILT | none | Milestone 2 |
| 4.8 S→V | `session_ended` with `reason, detail, ts` | PARTIAL | `service/session.py:88-97` | `timeout` is never sent (no idle time-out). `person`, `agent`, `failed` are |
| 4.8 S→V | frame | BUILT | `service/session.py:176-178`, `service/events.py:81-83` | |
| 4.8 V→S | `auth` | BUILT | `service/app.py:82` | |
| 4.8 V→S | `approve` | NOT BUILT | ignored by `service/session.py:105-119` | M1 slice 6 |
| 4.8 V→S | `deny` | NOT BUILT | ignored | M1 slice 6 |
| 4.8 V→S | `pause` | BUILT | `service/session.py:108` | |
| 4.8 V→S | `resume` | BUILT | `service/session.py:112` | |
| 4.8 V→S | `stop` | BUILT | `service/session.py:116`, `service/app.py:130-133` | |
| 4.8 V→S | `take_over` | BUILT | `service/session.py:110` | |
| 4.8 V→S | `hand_back` | BUILT | `service/session.py:114` | |
| 4.8 V→S | `done` | NOT BUILT | ignored | M1 slice 6 |
| 4.8 V→S | `could_not` | NOT BUILT | ignored | M1 slice 6 |
| 4.8 V→S | `pointer` | BUILT | `service/session.py:131-142` | Only while a person drives |
| 4.8 V→S | `key` | BUILT | `service/session.py:143-149` | The viewer's `code` field is ignored |
| 4.8 V→S | `wheel` | BUILT | `service/session.py:150-155` | |
| 4.8 V→S | `select_tab` | NOT BUILT | ignored | M1 slice 5 |
| 4.8 | `picture_current` every `viewer.picture_heartbeat_s` while the page is still | BUILT | `service/session.py:180-190` | |
| 4.8 | Viewer calls the picture stale after `viewer.stale_after_s` | PARTIAL | `viewer/src/state/view.ts:53`, `viewer/src/options.ts:18` | The viewer has its own value (5). The service does not deliver the setting. Not traced further |
| 4.8 | `caught_up` sent after the replay | BUILT | `service/app.py:91-93`, `viewer/src/connection/socket.ts:134-138` | Viewer toast behaviour not checked |
| 4.8 | `approval_closed` with `unwatched` | NOT BUILT | none | M1 slice 6 |
| 4.8 | Typed text never in an event; `browser_type` carries the character count only | BUILT | `tools/sentences.py:93-99`, `tests/unit/test_service_session.py:383` | A password field says "a password", not a count |
| 4.8 | Take-over Chrome sends no frames by default | NOT BUILT | none | Milestone 2 |

### §4.9 Bridge channel

Nothing exists: no `bridge/` folder, no `/bridge` route, no `bridge.*` keys in `config.py`.

| Spec ref | Requirement | Verdict | Evidence | What is missing / different |
|---|---|---|---|---|
| 4.9 | Bridge connects out to the core; no inbound port | NOT BUILT | none | Milestone 2 |
| 4.9 | Take-over Chrome flow, steps 1 to 6 | NOT BUILT | none | Milestone 2 |
| 4.9 | Bundled Chromium flow, steps 1 to 5 (`bap-browser driver-host`) | NOT BUILT | none | Milestone 3 |
| 4.9 | `hello` message | NOT BUILT | none | Milestone 2 |
| 4.9 | `op` message | NOT BUILT | none | Milestone 2 |
| 4.9 | `result` message | NOT BUILT | none | Milestone 2 |
| 4.9 | `event` message | NOT BUILT | none | Milestone 2 |
| 4.9 rule 1 | One message per driver operation; `hello` lists them | NOT BUILT | none | Milestone 2 |
| 4.9 rule 2 | Same page-reading script in every backend | NOT BUILT | one file, one backend: `driver/snapshot_page.js` | Milestone 2 |
| 4.9 rule 3 | One trip per tool call, two at most | NOT BUILT | `tools/toolkit.py:71,82`, `tools/browser_tools.py:85,92` | Today a click makes 3 or 4 driver calls (locate, click, tabs, optional snapshot). This needs rework before a bridge |
| 4.9 rule 4 | Operations answered in order; `bridge.op_timeout_ms` | NOT BUILT | none | Milestone 2 |
| 4.9 rule 5 | Pairing token: single use, `bridge.pairing_ttl_s` | NOT BUILT | none | Milestone 2 |
| 4.9 rule 6 | Heartbeat, dead-channel close, reconnect, tabs and refs survive | NOT BUILT | none | Milestone 2 |
| 4.9 rule 7 | Tools, policy, redaction, control, timeline stay in the core | NOT BUILT | none | Milestone 2 |
| 4.9 rule 8 | One conformance suite against every backend | NOT BUILT | e2e tests use `PlaywrightDriver` and `driver.page` directly (`tests/e2e/conftest.py:14`) | Milestone 2 slice 5 |

### §4.10 Protecting the service

| Spec ref | Requirement | Verdict | Evidence | What is missing / different |
|---|---|---|---|---|
| 4.10 | Listens on `127.0.0.1` only on a developer's machine | BUILT | `config.py:264`, `service/server.py:54` | |
| 4.10 | In the VM: `server.host`; `server.public_url` is the address clients use | PARTIAL | `service/app.py:49-53`, `service/server.py:43-49` | `public_url` feeds the Host and Origin checks, but the printed viewer address is always `http://host:port` |
| 4.10 | Random token at start, or from the environment | BUILT | `service/server.py:34` | |
| 4.10 | MCP over HTTP needs the bearer token | NOT BUILT | no `/mcp` | M1 slice 6 |
| 4.10 | The API needs the bearer token | BUILT | `service/app.py:55-56,62-64` | Constant-time compare |
| 4.10 | Token in the address fragment, kept for the tab's life, removed from the address bar | BUILT | `service/server.py:49`, `viewer/src/connection/address.ts:9-29`, `viewer/src/main.tsx:33-36` | |
| 4.10 | Every request's Host must be the local or public address | BUILT | `service/app.py:41,50,109` | |
| 4.10 | WebSocket Origin must be the viewer's own or listed | BUILT | `service/app.py:70-75` | A connection with no Origin header is accepted (line 73). Browsers always send one |
| 4.10 | Embedding only by origins in `viewer.embed_origins` | BUILT | `service/app.py:190-193`, `tests/service/test_service.py:99,118` | |
| 4.10 | Viewer address in the state file (current user only) and on the error stream | PARTIAL | `service/server.py:93-99`, `agent/command.py:47` | Done under `agent`. Under `mcp` no service starts. The 0600 mode was not checked on Windows |
| 4.10 | Viewer address never in a tool result | BUILT | no code path adds it | |
| 4.10 | Token, typed text and passwords never in a log, event or result | BUILT | `tools/event_log.py:19-30`, `tools/sentences.py:93`, `driver/snapshot_page.js:207`, `service/server.py:59-60` | A normal field's text appears as `value=` in later snapshots, as §5.4 intends |
| 4.10 | A bridge is accepted only with a pairing token | NOT BUILT | none | Milestone 2 |

### §5.1 Driver interface

| Spec ref | Requirement | Verdict | Evidence | What is missing / different |
|---|---|---|---|---|
| 5.1 | Tool layer talks only to the interface | BUILT | `tools/*.py` import only `driver.base` and `driver.session` | |
| 5.1 | Every backend implements it | PARTIAL | `driver/playwright_driver.py:111` | One implementation |
| 5.1 | Every operation takes and returns plain data | PARTIAL | `driver/base.py:84` | `start_frames` takes a callback and a config object; neither can travel as a bridge message |
| 5.1 Lifecycle | start | BUILT | `driver/base.py:56`, `driver/playwright_driver.py:139` | |
| 5.1 Lifecycle | close | BUILT | `driver/base.py:58`, `driver/playwright_driver.py:163` | |
| 5.1 Lifecycle | is alive | BUILT | `driver/base.py:60`, `driver/playwright_driver.py:169` | |
| 5.1 Lifecycle | description | BUILT | `driver/base.py:62`, `driver/playwright_driver.py:172-175` | Always says "Chromium <version>", even for Chrome or Edge |
| 5.1 Tabs | list | PARTIAL | `driver/playwright_driver.py:177-183` | Always one tab, `t1` |
| 5.1 Tabs | new | NOT BUILT | none | M1 slice 5 |
| 5.1 Tabs | switch | NOT BUILT | none | M1 slice 5 |
| 5.1 Tabs | close | NOT BUILT | none | M1 slice 5 |
| 5.1 Tabs | pop-ups adopted as tabs | NOT BUILT | no `context.on("page")` | M1 slice 5 |
| 5.1 Navigation | go to | BUILT | `driver/playwright_driver.py:192-209` | |
| 5.1 Navigation | back | NOT BUILT | none | M1 slice 5 |
| 5.1 Navigation | forward | NOT BUILT | none | M1 slice 5 |
| 5.1 Navigation | reload | NOT BUILT | none | M1 slice 5 |
| 5.1 Navigation | wait for load state | PARTIAL | `driver/playwright_driver.py:462-465` | Internal only; not an interface operation |
| 5.1 Navigation | wait for text | NOT BUILT | none | M1 slice 5 |
| 5.1 Navigation | wait for text gone | NOT BUILT | none | M1 slice 5 |
| 5.1 Navigation | wait seconds | NOT BUILT | none | M1 slice 5 |
| 5.1 Observation | snapshot | BUILT | `driver/base.py:74`, `driver/playwright_driver.py:220-234` | |
| 5.1 Observation | visible text | NOT BUILT | none | M1 slice 5 |
| 5.1 Observation | find | NOT BUILT | none | M1 slice 5 |
| 5.1 Observation | screenshot | NOT BUILT | none | M1 slice 5 |
| 5.1 Observation | zoom | NOT BUILT | none | M1 slice 5 |
| 5.1 Elements | resolve a ref to an element and its box | BUILT | `driver/base.py:72`, `driver/playwright_driver.py:211-218`, `driver/snapshot_page.js:485-492` | Box is `None` when the element is off screen |
| 5.1 Elements | stale refs raise a stale-ref error | BUILT | `driver/playwright_driver.py:215,230,424`, `errors.py:17` | |
| 5.1 Pointer | click by ref or point | PARTIAL | `driver/playwright_driver.py:236-273` | By ref only |
| 5.1 Pointer | hover | NOT BUILT | none | M1 slice 5 |
| 5.1 Pointer | drag | NOT BUILT | none | M1 slice 5 |
| 5.1 Keyboard | type | BUILT | `driver/playwright_driver.py:275-307` | |
| 5.1 Keyboard | fill | NOT BUILT | none | `type` with `clear=True` replaces the content; no separate operation. M1 slice 5 |
| 5.1 Keyboard | select | NOT BUILT | none | M1 slice 5 |
| 5.1 Keyboard | check | NOT BUILT | none | M1 slice 5; a click toggles a checkbox today |
| 5.1 Keyboard | press | NOT BUILT | none | M1 slice 5 |
| 5.1 Scrolling | scroll by steps | NOT BUILT | none | M1 slice 5 |
| 5.1 Scrolling | scroll to element | NOT BUILT | none | Click scrolls into view internally (`driver/snapshot_page.js:409`) |
| 5.1 Dialogs | pending dialog | NOT BUILT | none | M1 slice 5 |
| 5.1 Dialogs | accept | NOT BUILT | none | M1 slice 5 |
| 5.1 Dialogs | dismiss | NOT BUILT | none | M1 slice 5 |
| 5.1 Files | upload | NOT BUILT | none | M1 slice 5 |
| 5.1 Files | list downloads | NOT BUILT | none | M1 slice 5 |
| 5.1 Diagnostics | console entries | NOT BUILT | none | M1 slice 5 |
| 5.1 Diagnostics | network entries | NOT BUILT | none | M1 slice 5 |
| 5.1 Diagnostics | evaluate | NOT BUILT | none | M1 slice 5 |
| 5.1 Live view | start frames | BUILT | `driver/playwright_driver.py:309-334` | |
| 5.1 Live view | stop frames | BUILT | `driver/playwright_driver.py:313-317` | |
| 5.1 Live view | pointer input | BUILT | `driver/playwright_driver.py:357-370` | |
| 5.1 Live view | key input | BUILT | `driver/playwright_driver.py:372-392` | |
| 5.1 Live view | wheel input | BUILT | `driver/playwright_driver.py:394-402` | |

### §5.2 Browsers and launch modes

| Spec ref | Requirement | Verdict | Evidence | What is missing / different |
|---|---|---|---|---|
| 5.2 | `remote_headless`: Playwright's Chromium by default, any channel | BUILT | `driver/playwright_driver.py:38-53,144` | |
| 5.2 | Fresh profile by default | BUILT | `driver/playwright_driver.py:146` | |
| 5.2 | Kept profile when `browser.user_data_dir` is set | NOT BUILT | key at `config.py:183` is never read | M1 slice 5 |
| 5.2 | Headless; the person sees the live picture | BUILT | `driver/playwright_driver.py:41,324` | |
| 5.2 | `takeover_chrome` | NOT BUILT | none | Milestone 2 |
| 5.2 | `bundled_chromium` | NOT BUILT | none | Milestone 3 |
| 5.2 mode | Fresh profile | BUILT | `driver/playwright_driver.py:144-146` | |
| 5.2 mode | Persistent profile | NOT BUILT | no `launch_persistent_context` | M1 slice 5 |
| 5.2 mode | Attach over CDP; never closes a browser it did not start | NOT BUILT | `browser.cdp_url` (`config.py:182`) is never read | M1 slice 5 |
| 5.2 mode | Real-profile copy | NOT BUILT | none | Next #6 |
| 5.2 channel | `chromium` | BUILT | `driver/playwright_driver.py:52`, `tests/unit/test_driver_options.py:8` | |
| 5.2 channel | `chrome`, `chrome-beta`, `chrome-dev`, `chrome-canary` | BUILT | `config.py:36-39`, `driver/playwright_driver.py:52-53` | Option passed on; no test launches Chrome |
| 5.2 channel | `msedge` and its three variants | BUILT | `config.py:40-43` | Same: never launched in a test |
| 5.2 channel | `custom` with `browser.executable_path` | BUILT | `driver/playwright_driver.py:48-51`, `tests/unit/test_driver_options.py:21,27` | |
| 5.2 | Headless and visible both supported | BUILT | `driver/playwright_driver.py:41` | |
| 5.2 option | viewport | BUILT | `driver/playwright_driver.py:71-74` | |
| 5.2 option | device scale | BUILT | `driver/playwright_driver.py:79` | |
| 5.2 option | user agent | BUILT | `driver/playwright_driver.py:80` | |
| 5.2 option | locale | BUILT | `driver/playwright_driver.py:76` | |
| 5.2 option | time zone | BUILT | `driver/playwright_driver.py:77` | |
| 5.2 option | colour scheme | BUILT | `driver/playwright_driver.py:78` | |
| 5.2 option | geolocation | BUILT | `driver/playwright_driver.py:83-84` | |
| 5.2 option | permissions | BUILT | `driver/playwright_driver.py:85-86` | |
| 5.2 option | extra headers | BUILT | `driver/playwright_driver.py:87-88` | |
| 5.2 option | proxy | BUILT | `driver/playwright_driver.py:54-61` | Set at launch; credentials from the environment |
| 5.2 option | certificate checks | BUILT | `driver/playwright_driver.py:68` | |
| 5.2 option | JavaScript on or off | BUILT | `driver/playwright_driver.py:69` | |
| 5.2 | `browser.chromium_sandbox` setting | BUILT | `config.py:179`, `driver/playwright_driver.py:43` | |
| 5.2 | Sandbox turned off in `deploy/config.vm.json` | NOT BUILT | no file | M1 slice 8 |
| 5.2 | `bap-browser doctor` | NOT BUILT | no such command | M1 slice 5 |

### §5.3 Tabs, frames and shadow DOM

| Spec ref | Requirement | Verdict | Evidence | What is missing / different |
|---|---|---|---|---|
| 5.3 | Tab ids `t1`, `t2`, … never reused in a session | PARTIAL | `driver/playwright_driver.py:33,183` | One constant id. After a crash restart the new page is `t1` again |
| 5.3 | A pop-up or `target=_blank` link becomes a tab; `focus_new_tabs` | NOT BUILT | setting never read | M1 slice 5. Today a new window is not seen at all |
| 5.3 | Browser-internal pages never handed to the agent | NOT BUILT | no tab tracking | M1 slice 5 |
| 5.3 | Take-over Chrome: only the agent's tab group | NOT BUILT | none | Milestone 2 |
| 5.3 | A frame appears as an `iframe` line | BUILT | `driver/snapshot_page.js:21,159,290`, `tests/e2e/test_snapshot.py:202` | |
| 5.3 | Frame contents under that line, refs with a frame prefix (`f2e7`) | NOT BUILT | `driver/snapshot_page.js:290` stops at the frame; `driver/page_script.py:95-98` uses the main frame only | M1 slice 5 ("frames" in `docs/status.md` Next 2). `tools/registry.py:13` already accepts the prefix |
| 5.3 | Open shadow roots read as part of the page | BUILT | `driver/snapshot_page.js:96-103`, `tests/e2e/test_snapshot.py:135` | |

### §5.4 Snapshot

| Spec ref | Requirement | Verdict | Evidence | What is missing / different |
|---|---|---|---|---|
| 5.4 | Header lines `Page:`, `URL:`, `Scroll:` | BUILT | `driver/snapshot_page.js:300-302` | |
| 5.4 | Line format, indented by nesting | BUILT | `driver/snapshot_page.js:223-239`, `tests/e2e/test_snapshot.py:54` | |
| 5.4 | `interactive` mode: controls, headings, dialogs, alerts | BUILT | `driver/snapshot_page.js:27-32,276` | |
| 5.4 | `all` mode adds text and structure | BUILT | `driver/snapshot_page.js:20-26,265-268,283` | |
| 5.4 | `ref` returns that subtree | BUILT | `driver/snapshot_page.js:295-298`, `tests/e2e/test_snapshot.py:173` | |
| 5.4 | Refs stable while the document is loaded | BUILT | `driver/snapshot_page.js:7,224-229`, `tests/e2e/test_snapshot.py:67` | |
| 5.4 | Refs never reused across navigations | BUILT | `driver/playwright_driver.py:121,227,233`, `tests/e2e/test_snapshot.py:73` | |
| 5.4 | Stale-ref message | BUILT | `errors.py:21-25` | Exact wording |
| 5.4 | Left out: `display:none`, `visibility:hidden`, `aria-hidden`, `inert`, script, style, template | BUILT | `driver/snapshot_page.js:13,56-62`, `tests/e2e/test_snapshot.py:90` | |
| 5.4 | Password value shown as dots | BUILT | `driver/snapshot_page.js:207`, `tests/e2e/test_snapshot.py:126` | Always 8 dots, so the length is hidden too |
| 5.4 | Role `clickable`: handler attribute, tab index, own pointer cursor | BUILT | `driver/snapshot_page.js:87-94,277-280` | Only `onclick` counts as a handler; tab index must be 0 or more |
| 5.4 cap | `max_chars` 20,000 | BUILT | `config.py:99`, `tools/browser_tools.py:53`, `driver/snapshot_page.js:252` | |
| 5.4 cap | `max_depth` 60 | BUILT | `config.py:100`, `driver/snapshot_page.js:290` | |
| 5.4 cap | names 120 | BUILT | `config.py:101`, `driver/snapshot_page.js:130` | |
| 5.4 cap | values 200 | BUILT | `config.py:102`, `driver/snapshot_page.js:194,207` | |
| 5.4 cap | text 300 | BUILT | `config.py:103`, `driver/snapshot_page.js:266` | |
| 5.4 cap | 25 options per dropdown | BUILT | `config.py:104`, `driver/snapshot_page.js:197-198` | |
| 5.4 cap | frame nesting 4 | NOT BUILT | `max_frame_depth` (`config.py:105`) is never read | With frames, M1 slice 5 |
| 5.4 | Cap notice text | BUILT | `driver/snapshot.py:9`, `driver/snapshot_page.js:307` | Exact wording |
| 5.4 | Script injected into each frame | PARTIAL | `driver/page_script.py:94-98` | Main frame only |
| 5.4 | Runs in an isolated world through a CDP session | BUILT | `driver/page_script.py:97-98,109-116`, `tests/e2e/test_navigation.py:31` | |
| 5.4 req 1 | Walk stops at the output cap | BUILT | `driver/snapshot_page.js:254-258,304-306`, `tests/e2e/test_snapshot.py:159` | |
| 5.4 req 2 | No style lookup per element on the common path | PARTIAL | `driver/snapshot_page.js:56-62,87-94,277` | `checkVisibility()` runs on every element. The cursor lookup also runs for elements with a role that is not listed (`p`, `li`, `td` in interactive mode), not only those with no role |
| 5.4 req 3 | `browser_find` reuses the snapshot; change counter from a mutation observer | NOT BUILT | none | M1 slice 5 |
| 5.4 req 4 | Ref table held as weak references | BUILT | `driver/snapshot_page.js:6-7,241-245` | |
| 5.4 | Playwright's accessibility snapshot is the test check, not the engine | BUILT | `tests/e2e/test_snapshot.py:81-86` | |

### §5.5 Screenshots

| Spec ref | Requirement | Verdict | Evidence | What is missing / different |
|---|---|---|---|---|
| 5.5 | Visible area by default; full page on request | NOT BUILT | none; `browser.screenshot.*` never read | M1 slice 5 |
| 5.5 | Captured in the output format; re-encoded only to downscale or label | NOT BUILT | none | M1 slice 5 |
| 5.5 | Downscaled to `max_dimension`; coordinates mapped back | NOT BUILT | none | M1 slice 5 |
| 5.5 | `annotate` | NOT BUILT | none | M1 slice 5 |
| 5.5 | `browser_zoom` | NOT BUILT | none | M1 slice 5 |
| 5.5 | No screenshot unless a call asks | BUILT | no screenshot code exists | True by absence. The live picture is a separate CDP screencast |

### §5.6 Actions and waiting

| Spec ref | Requirement | Verdict | Evidence | What is missing / different |
|---|---|---|---|---|
| 5.6 | Wait until visible, stable, enabled, not covered, up to `action_ms` | BUILT | `driver/snapshot_page.js:394-432`, `driver/playwright_driver.py:240-249` | |
| 5.6 | On time-out, say which failed and what covers it | BUILT | `driver/snapshot_page.js:404-429`, `driver/playwright_driver.py:436-438`, `tests/e2e/test_actions.py:152` | |
| 5.6 | No fixed pauses; settle (no navigation in flight, scroll steady) up to a ceiling | PARTIAL | `driver/playwright_driver.py:35,440-449` | Waits two animation frames, then for a started navigation. Scroll steadiness is not checked. Typing without `submit` does not settle (line 306) |
| 5.6 | Result says whether the page navigated and where | BUILT | `tools/browser_tools.py:89-90,102-103`, `tests/e2e/test_actions.py:104` | |
| 5.6 | Scrolling reports position and bottom | NOT BUILT | no scroll tool | M1 slice 5 |
| 5.6 | Key names accepted in every dialect and normalised | NOT BUILT | no `keys.py`, no press tool | M1 slice 5. Click modifiers accept only `Alt`, `Control`, `Meta`, `Shift` (`tools/browser_tools.py:14`) |

### §5.7 Dialogs

| Spec ref | Requirement | Verdict | Evidence | What is missing / different |
|---|---|---|---|---|
| 5.7 | `agent` policy: action returns with the dialog's text; `browser_handle_dialog` | NOT BUILT | no dialog listener in `driver/` | M1 slice 5 |
| 5.7 | Only five tools run while a dialog is open | NOT BUILT | none | M1 slice 5 |
| 5.7 | `auto_accept` with `default_prompt_text` | NOT BUILT | `browser.dialogs.*` never read | M1 slice 5 |
| 5.7 | `auto_dismiss` | NOT BUILT | none | M1 slice 5. With no listener, Playwright dismisses dialogs itself and nobody is told; not confirmed by a run |
| 5.7 | Dismissed after `browser.dialogs.timeout_s` | NOT BUILT | none | M1 slice 5 |
| 5.7 | Open dialog shown in the viewer as a card | NOT BUILT | no `dialog_opened` event | M1 slice 5 |

### §5.8 Files

| Spec ref | Requirement | Verdict | Evidence | What is missing / different |
|---|---|---|---|---|
| 5.8 | Uploads: file inputs and custom buttons, `allowed_dirs`, approval by default | NOT BUILT | none | M1 slice 5; approval in slice 6 |
| 5.8 | Downloads: saved to `dir`, numbered duplicates, cancelled over `max_size_mb` | NOT BUILT | none | M1 slice 5 |
| 5.8 | Permission prompts never shown; permissions only from `browser.permissions` | PARTIAL | `driver/playwright_driver.py:85-86` | Listed permissions are granted. Nothing suppresses a prompt in a visible window; not tested |

### §5.9 Console and network logs

| Spec ref | Requirement | Verdict | Evidence | What is missing / different |
|---|---|---|---|---|
| 5.9 | Last `max_console_entries` console messages and page errors per tab | NOT BUILT | `browser.capture.*` never read | M1 slice 5 |
| 5.9 | Last `max_network_entries` requests per tab | NOT BUILT | the only request listener counts navigations (`driver/playwright_driver.py:467-469`) | M1 slice 5 |

### §5.10 Errors

| Spec ref | Requirement | Verdict | Evidence | What is missing / different |
|---|---|---|---|---|
| 5.10 | Every failure returned as a result; the service never crashes on a bad call | BUILT | `tools/toolkit.py:91-119`, `tests/service/test_mcp.py:38` | |
| 5.10 | Bad input | BUILT | `errors.py:13`, `tools/toolkit.py:97-101`, `tools/registry.py:50-57` | The example message ("give either ref or both x and y") has no tool yet |
| 5.10 | Stale ref | BUILT | `errors.py:17-26` | |
| 5.10 | Policy | BUILT | `errors.py:29-34`, `tools/browser_tools.py:62-71`, `policy/url_policy.py:125` | Same form as the example |
| 5.10 | Approval denied | NOT BUILT | no class, no approvals | M1 slice 6 |
| 5.10 | Not ready | BUILT | `driver/playwright_driver.py:436-438` | Same form as the example. Raised as `BrowserError`; there is no class of its own |
| 5.10 | Dialog open | NOT BUILT | none | M1 slice 5 |
| 5.10 | Control, not flagged as an error | BUILT | `service/session.py:25-28`, `tools/toolkit.py:64` | Wording differs: "A person is in control of the browser, so nothing was done. Call again to keep waiting." |
| 5.10 | Browser: the driver's own message, shortened | BUILT | `driver/playwright_driver.py:92-93,153,204` | First line only |

## 2. EXTRA: in the code, not in these spec sections

**Commands and packages**
- `bap-browser agent` with `--demo`, `--pace`, `--wait-for-viewer`, `--open`, `--exit-when-done` (`cli.py:65-92`), and the `agent/` package (`command.py`, `loop.py`, `models.py`, `openai_model.py`, `demo.py`). Spec §16.5 describes the loop; the §3.2 layout does not list the folder. This is the only path that starts the service today.
- `config show/init/doc` (`cli.py:45-59`), `config_doc.py`, `env_file.py` (reads `.env` from the working folder), `__main__.py`.
- Built-in demo site: `demo_site/` and a `/demo-site` route with no token (`service/app.py:105`).

**Files the layout does not list**
- `driver/page_script.py` (isolated-world caller, reply time limit, one retry when the document changes).
- `driver/session.py` (`BrowserSession`: lazy start, crash handling).
- `policy/address.py`.
- `tools/toolkit.py`, `gate.py`, `observer.py`, `event_log.py`, `sentences.py`.
- `service/server.py`.
- `tests/support/`, `docs/status.md`, `.github/workflows/ci.yml`, `.gitattributes`, `viewer/scripts/record_demo.py`, and an untracked `memory/` folder at the root.

**Driver**
- `Driver.viewport()` (`driver/base.py:66`).
- Snapshot option `include_bboxes`, which adds `[box=x,y,w,h]` (`driver/snapshot_page.js:234-237`).
- Element states beyond the spec's example: `[mixed]`, `[disabled]`, `[readonly]`, `[expanded]`, `[collapsed]`, `[selected]`, `[pressed]`.
- `Located.secret` marks password fields.
- A crashed or closed browser is restarted only by `browser_navigate`; other calls are told "The browser closed…" (`driver/session.py:39-62`).
- Page-busy protection: every page call and every input has a time limit (`driver/page_script.py:37-46`, `driver/playwright_driver.py:404-416`). Settings `page_reply_ms`, `frame_ms`, `load_wait_ms`, `settle_ms`.
- Typing checks that the page did not move focus away (`driver/snapshot_page.js:456-460`); `slowly` and `type_delay_ms`.
- Click options `button`, `click_count`, `modifiers`.
- Load failures in plain words for the viewer (`driver/playwright_driver.py:97-108`); every error carries a short `reason` (`errors.py:7-10`).
- Addresses are stripped of user name and password and capped in length (`driver/session.py:29-33`).
- Launch settings `browser.args` and `ignore_default_args`; proxy credentials from `BAP_BROWSER_PROXY_USERNAME` and `BAP_BROWSER_PROXY_PASSWORD`.
- Frame rate limited by delaying the screencast acknowledgement (`driver/playwright_driver.py:345-355`); quality levels `standard`, `data_saver`, `high`.

**Service**
- WebSocket close codes beyond 4401: 4404 no such session, 1013 viewer fell behind, 1008 wrong origin (`service/app.py:38-40`).
- A slow viewer is dropped and told to start over (`service/events.py:14,32-34`); unsent pictures are replaced by newer ones.
- `server.auth_wait_s`, `server.command_backlog` (extra commands dropped), `server.shutdown_wait_s`, 64 KB limit on a viewer message (`service/server.py:20`).
- `stop` jumps the command queue (`service/app.py:130-133`).
- Response headers `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `Connection: close` (`service/app.py:191-196`).
- Keys and buttons a person still holds are released on hand-back (`service/session.py:160-174`); a wheel turn is cut to one screen (`:151-153`).
- `tab_changed` is re-sent on the heartbeat when the address changed without a step (`service/session.py:188`).
- `EventHub.wait_for_viewer()` (`service/events.py:92`).
- The state file is deleted when the service stops (`service/server.py:88-91`).
- `websockets` is a direct dependency (`pyproject.toml:13`), not in the stack table.

## 3. The 10 most important gaps

1. **`bap-browser mcp` has no viewer and no control.** It runs a bare toolkit (`mcp/server.py:53-54`), and `bap-browser serve` with `/mcp` over HTTP does not exist. An MCP agent cannot be watched, paused or taken over; only the built-in `agent` command can. (§4.4, §4.7; M1 slice 6)
2. **Most of the driver interface is missing.** 15 of 47 operations are built and 3 are partial. Missing: tabs, back/forward/reload, waits, visible text, find, screenshot, zoom, hover, drag, select, check, press, scroll, dialogs, files, console, network, evaluate. (§5.1; M1 slice 5)
3. **One tab only, and pop-ups are invisible.** A link that opens a new window leaves the agent on the old page with no notice. (§5.3)
4. **Frames are not read.** The snapshot lists the `iframe` line and stops; the script runs in the main frame only, so there are no `f…` refs and the frame-depth cap is unused. Payment and sign-in frames cannot be used. (§5.3, §5.4)
5. **No dialog handling.** No listener is registered; an alert or confirm is most likely dismissed silently by Playwright while the agent and the viewer learn nothing. The default should be `agent`. (§5.7)
6. **Approvals and help requests are absent.** No `waiting_approval` or `person_requested` state, no `approve`/`deny`/`done`/`could_not` commands, no approval or help events. `safety.action_policies` is read by nothing. (§4.5, §4.6, §4.8; M1 slice 6)
7. **Session management over HTTP is missing.** No create or delete session, settings, config or clear-browsing-data routes. The session limit and idle time-out are settings that nothing reads. (§4.7, §4.3)
8. **Persistent profile and attach are settings that do nothing.** `browser.user_data_dir` and `browser.cdp_url` validate and are then ignored, with no warning. Chrome and Edge channels are passed through but never launched in a test; `doctor` is missing. (§5.2; M1 slice 5)
9. **The driver seam is not ready for a bridge.** One tool call makes 3 or 4 driver calls where §4.9 allows two; `start_frames` takes a callback; Playwright starts once per session, not once per service; e2e tests reach into `driver.page`, so they are not a conformance suite. (§4.4, §4.9, §5.1)
10. **Micro VM pieces.** No `deploy/`; the printed viewer address ignores `server.public_url`; the document-only request check over CDP is absent, so redirects and link clicks are not checked by the address policy. (§3.1, §4.10; M1 slice 8)

Smaller points: the snapshot's cursor lookup runs for more elements than the spec allows (§5.4 req 2); `control_changed` never carries `ended`; `tab_changed` has no `attention`; the tab id `t1` is reused after a crash restart; "recent events" are not appended to results.

## 4. Counts

| Section | BUILT | PARTIAL | DIFFERS | NOT BUILT | Rows |
|---|---|---|---|---|---|
| 3.1 Stack | 11 | 0 | 1 | 6 | 18 |
| 3.2 Layout | 26 | 5 | 7 | 24 | 62 |
| 4.1 to 4.4 | 8 | 6 | 2 | 13 | 29 |
| 4.5 Who is driving | 6 | 1 | 0 | 6 | 13 |
| 4.6 One tool call | 8 | 0 | 0 | 3 | 11 |
| 4.7 HTTP surface | 4 | 0 | 0 | 9 | 13 |
| 4.8 Viewer protocol | 28 | 4 | 0 | 16 | 48 |
| 4.9 Bridge channel | 0 | 0 | 0 | 15 | 15 |
| 4.10 Protecting the service | 9 | 2 | 0 | 2 | 13 |
| 5.1 Driver interface | 15 | 5 | 0 | 30 | 50 |
| 5.2 Browsers and launch modes | 22 | 0 | 0 | 8 | 30 |
| 5.3 Tabs, frames, shadow DOM | 2 | 1 | 0 | 4 | 7 |
| 5.4 Snapshot | 22 | 2 | 0 | 2 | 26 |
| 5.5 Screenshots | 1 | 0 | 0 | 5 | 6 |
| 5.6 Actions and waiting | 3 | 1 | 0 | 2 | 6 |
| 5.7 Dialogs | 0 | 0 | 0 | 6 | 6 |
| 5.8 Files | 0 | 1 | 0 | 2 | 3 |
| 5.9 Logs | 0 | 0 | 0 | 2 | 2 |
| 5.10 Errors | 7 | 0 | 0 | 2 | 9 |
| **Total** | **172** | **28** | **10** | **157** | **367** |

Of the 157 NOT BUILT rows, about 45 belong to milestones 2 to 4 or "Next"; the rest are milestone 1 slices 5 to 9. EXTRA items are listed in part 2 and not counted.

## Could not verify

- Nothing was executed, so the 696-test figure in `docs/status.md` is not confirmed.
- What happens today when a page opens a dialog or asks for a permission (stated from Playwright's documented default).
- Chrome and Edge launches (no test launches them).
- Whether the state file's 0600 mode protects it on Windows.
- Viewer-side behaviour was only spot-checked: no retry after 4401, token handling, step pictures, the stale rule. `viewer/src` was not audited in full; how `viewer/src/options.ts` gets its values was not traced.
- `policy/url_policy.py` and `policy/address.py` were not read in full (they belong to §8).
- `src/bap_browser/viewer_dist/`, `viewer/dist/`, `_lastmile/`, `.venv/`, `node_modules/` were not inspected, as instructed.
- The contents of `docs/adr/0001-stack.md`, `README.md` and `CLAUDE.md` were not compared with the spec; only their existence was checked.