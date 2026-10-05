# bap-browser audit: spec delivery plan, feature surface and status page against the code

Repo root: `/Users/sharan/Downloads/Prj-Browser`. All paths below are relative to it. `src/` means `src/bap_browser/`. Nothing was modified and `.env` was not read.

**How this was checked.** I read all Python under `src/bap_browser/` in full, `driver/snapshot_page.js` in full, and the viewer's `App.tsx`, `main.tsx`, `protocol.ts`, `state/view.ts`, `state/timeline.ts`, `tokens.css`, `options.ts`, `connection/socket.ts`, `connection/address.ts`, `components/BrowserPane.tsx`, with greps for the rest. No test was run. Tests were only counted with `pytest --collect-only` (no cache, no bytecode written).

**Headline findings**
- The code is milestone 1 slices 0 to 4 plus the pause / take-over / stop part of slice 6. Slices 5, 7, 8 and 9 are not built.
- Only 4 of the spec's 28 milestone 1 tools exist (`src/tools/browser_tools.py:109-137`).
- About 45 configuration keys are defined in `src/config.py` but read by no code (list in section D).
- `docs/status.md` is accurate about the code. Its header is wrong on branch, push state and commit count, and it has four internal defects (C1).
- Of the 161 feature rows with a milestone 1 part: 63 BUILT, 31 PARTIAL, 67 NOT BUILT.

---

## A) Milestone 1 scope check (spec §14.1, lines 2116-2142)

### A1. Slices

| Slice | Item | Verdict | Evidence |
|---|---|---|---|
| 0 Skeleton | Git repository | BUILT | `.git`, 51 commits |
| 0 | `pyproject.toml` with uv, ruff, pyright, pytest | BUILT | `pyproject.toml:1-66`, `uv.lock` |
| 0 | `.gitignore`, `.env.example`, `README.md`, `CLAUDE.md` | BUILT | all present at root |
| 0 | `docs/adr/0001-stack.md` | BUILT | file present |
| 0 | CI workflow running lint and tests | BUILT | `.github/workflows/ci.yml:1-33` (Ubuntu, Chromium only) |
| 1 Viewer experience | Scaffold with checks in CI | BUILT | `viewer/package.json` scripts; `ci.yml:17-21` |
| 1 | Design tokens, both themes | BUILT | `viewer/src/tokens.css:23-180` |
| 1 | Every component and state of §9 | PARTIAL | 10 states in `viewer/src/state/view.ts:7-17`. Missing: session picker (`W.topBar.sessions` is used nowhere), settings "saving" (`W.settings.saving` unused), buttons "working", takeover bar "handing back" / "failed", address "loading", notice "limit reached" (no match in `viewer/src`) |
| 1 | Settings screen | BUILT on recorded data | `viewer/src/components/SettingsScreen.tsx:25`; data from `viewer/src/demo/settings.ts:326` |
| 1 | Keyboard, screen reader, reduced motion | BUILT | `viewer/src/App.tsx:180-204`, `:374-379`; `viewer/src/styles/base.css:173` |
| 1 | Narrow and phone layout | BUILT | `viewer/src/styles/app.css:963`, `:1009` |
| 1 | Shown inside another page | BUILT | `viewer/src/main.tsx:61` (`?embed`); `src/service/app.py:190-192` (frame-ancestors) |
| 1 | Runs on recorded sessions | BUILT | `viewer/src/main.tsx:26-47`; `viewer/src/demo/sessions.ts:150-175` |
| 1 | Screenshot of every state in both themes | UNVERIFIED | 92 tests collect under `tests/viewer`; the screenshots go to the ignored folder `.bap-browser/viewer-shots/`; not run |
| 2 Config and policy | `config.py`, loader | BUILT | `src/config.py:369-508`. Key-by-key comparison with spec §10.3 not done (UNVERIFIED) |
| 2 | `config show`, `init`, `doc` | BUILT | `src/cli.py:45-59`, `:96-125`; `src/config_doc.py:14` |
| 2 | Address policy | BUILT | `src/policy/url_policy.py:61-145`; `src/policy/address.py:33-190` |
| 2 | Redaction | BUILT | `src/policy/redaction.py:13-27` |
| 2 | Error and result types | BUILT | `src/errors.py:4-42`; `src/results.py:6-9` |
| 3 First path | Driver interface | BUILT | `src/driver/base.py:55-96` |
| 3 | Playwright driver, launch Chromium | BUILT | `src/driver/playwright_driver.py:139-161` |
| 3 | `browser_navigate`, `browser_snapshot`, `browser_click`, `browser_type` | BUILT | `src/tools/browser_tools.py:109-137` |
| 3 | In-process and over MCP stdio | BUILT | `src/tools/toolkit.py:38`; `src/mcp/server.py:51-56`; `tests/e2e/test_toolkit_in_process.py` |
| 3 | Done-when: scripted MCP client fills and submits the test form | BUILT | `tests/service/test_mcp.py:52` |
| 4 Live loop | `bap-browser agent` | BUILT | `src/cli.py:65-92`, `:139-192`; `src/agent/command.py:28-82` |
| 4 | Agent loop, scripted model | BUILT | `src/agent/loop.py:30-61`; `src/agent/models.py:62-77`; `src/agent/demo.py:20` |
| 4 | Session service | BUILT (one session) | `src/service/session.py:36`; `src/service/server.py:23` |
| 4 | Event stream | BUILT | `src/service/events.py:49-119` |
| 4 | Live pictures | BUILT | `src/driver/playwright_driver.py:309-355`; `src/service/app.py:158-162` |
| 4 | Done-when: one command, viewer shows each step live | BUILT | `tests/service/test_agent_command.py:59`; `tests/viewer/test_live_session.py` (not run) |
| 5 All tools | Remaining 24 reading, pointer, keyboard, scroll, wait, tab, dialog, file, diagnostic tools | NOT BUILT | only 4 tools in `src/tools/browser_tools.py:109` |
| 5 | Chrome and Edge | PARTIAL | channel is passed to Playwright (`src/driver/playwright_driver.py:52-53`); unit-tested only (`tests/unit/test_driver_options.py:17`); no test launches either |
| 5 | Attach, persistent profile | NOT BUILT | `browser.cdp_url` and `browser.user_data_dir` are defined (`src/config.py:182-185`) and read nowhere; the driver only calls `chromium.launch` (`playwright_driver.py:144`) |
| 5 | `doctor` | NOT BUILT | not in `src/cli.py:43-92` |
| 6 Control | Who is driving | PARTIAL | 4 of the spec's 6 states: `src/service/session.py:21`. No `waiting_approval`, no `person_requested` |
| 6 | Approvals | NOT BUILT | `safety.action_policies`, `control.approval_*` are read nowhere; no `policy/approvals.py`. Viewer side exists (`viewer/src/components/Cards.tsx:24`) but the service ignores `approve` / `deny` (`src/service/session.py:105-119`) |
| 6 | Pause, resume, stop | BUILT | `src/service/session.py:108-117`, `:257-266` |
| 6 | Take over and hand back with remote input | BUILT | `src/service/session.py:123-158`, `:268-285`; `playwright_driver.py:357-402` |
| 6 | `browser_request_human` | NOT BUILT | no such tool; `done` / `could_not` commands ignored |
| 6 | Token, `Host`, `Origin` checks | BUILT | `src/service/app.py:55-56`, `:70-75`, `:82-84`, `:109` |
| 6 | MCP over HTTP with `serve` | NOT BUILT | `mcp.http_path` unused; no `serve` command |
| 6 | Viewer's cards and buttons act on the real session | PARTIAL | buttons yes; cards (approval, help, dialog) run on recorded sessions only |
| 7 Settings | Catalogue, saved settings, locks and limits, settings API | NOT BUILT | no `src/settings/`; `settings.file` and `settings.locked` (`src/config.py:349-350`) unused; no `/api/settings` route (`src/service/app.py:100-107`) |
| 7 | Settings screen reads and saves through the API | NOT BUILT | a live session uses the recorded source limited to two settings: `viewer/src/main.tsx:19`, `:53` |
| 8 Micro VM | `deploy/Dockerfile`, `deploy/config.vm.json` | NOT BUILT | no `deploy/` folder |
| 8 | Public address and origin checks | PARTIAL | `server.public_url` is added to hosts and origins (`src/service/app.py:49-53`); no test in a container |
| 8 | Container launch flags | PARTIAL | `browser.chromium_sandbox` exists (`src/config.py:179`, `playwright_driver.py:43`); no automatic flags when root |
| 9 Verify loop | Bench, `perf/budget.json`, verify skill | NOT BUILT | no `perf/`, no `src/bench/`, no `.claude/`; the `bench` config section (`src/config.py:362-366`) is unused |
| 9 | Test pages | PARTIAL | `tests/site/` holds 16 pages for the tests, not bench pages |
| 9 | Clean-up of browsers left by a crash | NOT BUILT | no such code |

### A2. Acceptance list (spec lines 2133-2142)

| # | Criterion | Verdict | Evidence |
|---|---|---|---|
| 1 | MCP agent fills the form while the viewer shows it; the reference loop does the same from one command | PARTIAL | MCP fills the form (`tests/service/test_mcp.py:52`) but `bap-browser mcp` starts no viewer (`src/mcp/server.py:51-56`). The reference loop with viewer is built |
| 2 | Approve an upload, deny a second, pause and resume, take over and hand back | PARTIAL | pause / resume / take over / hand back built; no approvals, no upload tool |
| 3 | `browser_request_human` answered "Done" | NOT BUILT | tool absent |
| 4 | Same run inside the micro VM image | NOT BUILT | no `deploy/` |
| 5 | Each web setting changes behaviour; a locked one cannot be changed | NOT BUILT | no settings API |
| 6 | Every M1 checklist item ticked | NOT MET | follows from slices 5 to 9 (spec §12.5 was not audited line by line) |
| 7 | No budget line fails | NOT BUILT | no budget file, no bench |
| 8 | Works on Chrome, Chromium and Edge | UNVERIFIED | only Chromium is exercised by tests and CI |

### A3. Milestones 2, 3, 4 and "Next" (spec §14.2-14.5)

| Scope | Verdict | Evidence |
|---|---|---|
| M2 slice 1 Bridge channel (`/bridge`, pairing, bridge driver) | NOT BUILT | no `src/bridge/`, no `bridge_driver.py`, no route |
| M2 slice 2 Extension driver | NOT BUILT | no `extension/` |
| M2 slice 3 Permissions | NOT BUILT | none |
| M2 slice 4 Viewer and settings (backend picker, bridge status, "browser not connected") | NOT BUILT, with pieces present | see the next table |
| M2 slice 5 Conformance | NOT BUILT | none |
| M3 Driver host, desktop settings, conformance | NOT BUILT | no `driver-host` command, no `bridge/host.py` |
| M4 `browser_run` (checker, worker, `browser` object) | NOT BUILT | no `src/code/` |
| Next 1 Codex and Hermes recipes | NOT BUILT | only a Claude Code line in `README.md:24` |
| Next 2 Sign-in without the model seeing credentials | NOT BUILT | |
| Next 3 Automatic detection of sign-in walls and checks | NOT BUILT | |
| Next 4 Notifications, note to the agent | NOT BUILT | |
| Next 5 Recording and replay | NOT BUILT | |
| Next 6 Real-profile copy | NOT BUILT | |
| Next 7 Speed and token work | NOT BUILT | |
| Next 8 Remaining tools (`browser_pdf` and others) | NOT BUILT | |
| Next 9 Cloud depth | NOT BUILT | |
| Next 10 Reference task set | NOT BUILT | |
| Next 11 Admin console, phone keyboard, one-shot CLI | NOT BUILT | |

Pieces of later milestones that are already half-present:

| What | Belongs to | Where |
|---|---|---|
| Backend type lists `takeover_chrome` and `bundled_chromium` | M2 / M3 | `viewer/src/protocol.ts:4`; labels in `viewer/src/wording.ts:187-189` |
| "The agent is working in your own browser" picture state, with a recorded state for it | M2 (UI-31 area) | `viewer/src/state/view.ts:21`, `:48`; `viewer/src/components/BrowserPane.tsx:130-140`; `viewer/src/demo/sessions.ts:145-146`, `:175` |
| Recorded settings for `my_chrome`, `my_chrome_mode`, `approved_sites`, `show_builtin_browser`, `download_folder`, `upload_folders` | M2 / M3 | `viewer/src/demo/settings.ts:42`, `:54`, `:116`, `:154`, `:187`, `:199` |
| A click names the element that covers its target | Next (RB-03) | `src/driver/snapshot_page.js:426` |
| A timed-out action says the page may still be working on it | Next (RB-15), partly | `src/driver/playwright_driver.py:412-415` |
| A step limit per run, in the reference loop only | Next (SG-17 "per session") | `src/agent/loop.py:57-58` |
| Hosted OpenAI model in the built-in loop, using OpenAI's function-tool format | §14.6 lists "native ... OpenAI toolset formats; a built-in agent loop" as Later; IF-09 allows a basic loop in M1 | `src/agent/openai_model.py:36-54` |

The core config accepts only `remote_headless` (`src/config.py:59-62`), so no later backend can be selected by accident.

---

## B) Feature surface (spec §15, lines 2214-2700)

### B1. Row counts by the spec's own marker

Rows are counted by the first word of the Phase cell. "Other" means the cell starts with something else (composite). 354 rows in total.

| Section | Total | M1 | M2 | M3 | M4 | Next | Later | No | Other |
|---|---|---|---|---|---|---|---|---|---|
| 15.1 Lifecycle and sessions | 23 | 12 | 0 | 0 | 0 | 6 | 2 | 3 | 0 |
| 15.2 Browser choice and launch | 22 | 14 | 0 | 0 | 0 | 4 | 3 | 1 | 0 |
| 15.3 Profiles and identity | 17 | 2 | 1 | 0 | 0 | 10 | 4 | 0 | 0 |
| 15.4 Tabs, frames, shadow DOM | 9 | 5 | 0 | 0 | 0 | 1 | 3 | 0 | 0 |
| 15.5 Navigation and waiting | 9 | 6 | 0 | 0 | 0 | 3 | 0 | 0 | 0 |
| 15.6 Observation | 43 | 19 | 0 | 0 | 0 | 13 | 6 | 5 | 0 |
| 15.7 Actions | 18 | 12 | 0 | 0 | 1 | 4 | 1 | 0 | 0 |
| 15.8 Forms, files, dialogs, clipboard | 14 | 7 | 0 | 0 | 0 | 4 | 3 | 0 | 0 |
| 15.9 Scripts and raw protocol | 6 | 1 | 0 | 0 | 0 | 1 | 4 | 0 | 0 |
| 15.10 Robustness | 15 | 3 | 0 | 0 | 1 | 5 | 6 | 0 | 0 |
| 15.11 Code tool | 9 | 1 | 0 | 0 | 5 | 2 | 1 | 0 | 0 |
| 15.12 Detection and network | 9 | 1 | 0 | 0 | 0 | 1 | 3 | 4 | 0 |
| 15.13 Sign-in and secrets | 10 | 0 | 0 | 0 | 0 | 6 | 3 | 1 | 0 |
| 15.14 Safety and governance | 26 | 14 | 5 | 0 | 1 | 2 | 3 | 0 | 1 (SG-14) |
| 15.15 Observability | 10 | 3 | 0 | 0 | 0 | 4 | 2 | 0 | 1 (OS-08) |
| 15.16 Interfaces | 19 | 9 | 0 | 0 | 0 | 2 | 5 | 2 | 1 (IF-18) |
| 15.17 Cloud | 11 | 2 | 0 | 0 | 0 | 5 | 3 | 1 | 0 |
| 15.18 Evaluation | 7 | 4 | 0 | 0 | 0 | 1 | 1 | 0 | 1 (EV-03) |
| 15.19 Viewer | 31 | 23 | 2 | 0 | 0 | 4 | 2 | 0 | 0 |
| 15.20 Backends and bridge | 15 | 4 | 9 | 2 | 0 | 0 | 0 | 0 | 0 |
| 15.21 Settings | 20 | 14 | 1 | 1 | 0 | 2 | 2 | 0 | 0 |
| 15.22 Further ideas | 11 | 0 | 0 | 0 | 0 | 2 | 9 | 0 | 0 |
| **Total** | **354** | **156** | **18** | **3** | **8** | **82** | **66** | **17** | **4** |

Five more rows carry a milestone 1 part without starting with "M1": OB-39, RB-04, AU-04, OS-08, IF-18. That gives 161 rows with a milestone 1 part.

### B2. Every row with a milestone 1 part, against the code

**15.1 Lifecycle and sessions**

| ID | Feature | Verdict | Evidence |
|---|---|---|---|
| LC-01 | Launch a local browser and an isolated context | BUILT | `src/driver/playwright_driver.py:144-146` |
| LC-02 | Headless or visible | BUILT | `playwright_driver.py:41`; `src/config.py:178` |
| LC-04 | Attach over CDP | NOT BUILT | `browser.cdp_url` read nowhere |
| LC-06 | Close a session after no use | NOT BUILT | `timeouts.idle_session_s` (`config.py:94`) read nowhere |
| LC-07 | Clean up browsers left by a crash | NOT BUILT | no code |
| LC-08 | On exit close only what we launched | BUILT (trivially: it only launches) | `playwright_driver.py:143-145`, `:163-167` |
| LC-09 | Several named sessions at once | PARTIAL | the service takes a map of sessions (`src/service/app.py:44`, `:85`) and the viewer takes `?session=` (`viewer/src/main.tsx:48`), but only one session is ever created (`src/agent/command.py:42-43`); `sessions.max_concurrent` unused |
| LC-12 | Container flags when running as root | NOT BUILT | no `geteuid` or `no-sandbox` in `src` |
| LC-14 | Doctor command | NOT BUILT | not in `src/cli.py` |
| LC-18 | One long-lived service for agents and the viewer | PARTIAL | only inside `bap-browser agent` (`src/agent/command.py:42-47`); no `serve`; the MCP server has no viewer |
| LC-19 | One queue per session | BUILT | `src/tools/toolkit.py:50`, `:62` |
| LC-23 | Browser starts on the first tool call | BUILT for MCP and in-process (`src/driver/session.py:55-57`); the `agent` command starts it up front (`src/service/session.py:70`) | |

**15.2 Browser choice and launch options** (all are option mapping, unit-tested in `tests/unit/test_driver_options.py`; none is tested in a browser)

| ID | Feature | Verdict | Evidence |
|---|---|---|---|
| BS-01 | Bundled Chromium | BUILT | `playwright_driver.py:144` |
| BS-02 | Chrome stable, beta, dev, canary | PARTIAL (passed on, never launched in a test) | `config.py:34-45`; `playwright_driver.py:52-53` |
| BS-03 | Edge channels | PARTIAL (same) | same |
| BS-05 | Any Chromium by path | BUILT (untested in a browser) | `playwright_driver.py:48-49` |
| BS-06 | Extra flags, drop default flags | BUILT | `playwright_driver.py:42`, `:46-47` |
| BS-09 | Fixed viewport or window-sized | BUILT | `playwright_driver.py:71-74` |
| BS-10 | Device scale factor | BUILT | `playwright_driver.py:79` |
| BS-11 | Locale, time zone, colour scheme | BUILT | `playwright_driver.py:76-78` |
| BS-12 | User-agent override | BUILT | `playwright_driver.py:80` |
| BS-13 | Geolocation and permissions | BUILT | `playwright_driver.py:83-86` |
| BS-14 | Static proxy | BUILT | `playwright_driver.py:54-61` |
| BS-15 | Extra HTTP headers | BUILT | `playwright_driver.py:87-88` |
| BS-16 | Accept bad certificates | BUILT | `playwright_driver.py:68` |
| BS-17 | Page JavaScript off | BUILT | `playwright_driver.py:69` |

**15.3 Profiles and identity**

| ID | Feature | Verdict | Evidence |
|---|---|---|---|
| PR-01 | Fresh profile per session | BUILT | `playwright_driver.py:146` (new context each start) |
| PR-02 | Persistent profile folder | NOT BUILT | `browser.user_data_dir` read nowhere |

**15.4 Tabs, frames, shadow DOM**

| ID | Feature | Verdict | Evidence |
|---|---|---|---|
| TB-01 | List, open, switch, close tabs | NOT BUILT | one fixed tab `t1` (`playwright_driver.py:33`, `:183`); no `browser_tabs` |
| TB-02 | Pop-ups become tabs | NOT BUILT | no popup handler; `tabs.*` config unused |
| TB-03 | Tab list and recent events on every result | PARTIAL | `[tabs]` block built (`src/tools/toolkit.py:148-152`); no `[events]` block |
| TB-05 | Frames, including cross-site | NOT BUILT | an iframe is listed by name and not read (`snapshot_page.js:290`); `include_iframes` and `max_frame_depth` unused |
| TB-07 | Open shadow DOM | BUILT | `snapshot_page.js:97`, `:369-378`; `tests/e2e/test_snapshot.py:135` |

**15.5 Navigation and waiting**

| ID | Feature | Verdict | Evidence |
|---|---|---|---|
| NV-01 | Open a URL after a policy check | BUILT | `src/tools/browser_tools.py:58-73` |
| NV-02 | Back, forward, reload | NOT BUILT | no such tools |
| NV-03 | Navigation returns the snapshot | BUILT | `browser_tools.py:74-75` |
| NV-04 | Wait for seconds, text, load state | NOT BUILT | no `browser_wait`; `wait_max_s` unused |
| NV-07 | Settle after an action | BUILT | `playwright_driver.py:440-449` |
| NV-08 | Per-action time limit | BUILT | `playwright_driver.py:404-416`; `config.py:83` |

**15.6 Observation**

| ID | Feature | Verdict | Evidence |
|---|---|---|---|
| OB-01 | Snapshot with stable refs and a stale-ref error | BUILT | `snapshot_page.js:223-229`, `:241-245`; `src/errors.py:17-26` |
| OB-02 | Interactive-only or everything | BUILT | `snapshot_page.js:265`, `:283` |
| OB-03 | Snapshot of one part by ref | BUILT | `snapshot_page.js:295-298` |
| OB-04 | Limits on characters, depth, name length | BUILT | `src/driver/snapshot.py:21-33`; `snapshot_page.js:252-261`, `:290` |
| OB-05 | Hidden elements left out | BUILT | `snapshot_page.js:56-62`; `tests/e2e/test_snapshot.py:90` |
| OB-06 | Element boxes | BUILT | `snapshot_page.js:234-237` |
| OB-10 | Clickable things without markup | BUILT | `snapshot_page.js:87-94`, `:277-280` |
| OB-11 | Visible text of a page or element | NOT BUILT | no `browser_get_text` |
| OB-13 | Find by word match | NOT BUILT | no `browser_find`; the cut-off notice still tells the model to use it (`src/driver/snapshot.py:9`) |
| OB-15 | Screenshot | NOT BUILT | no tool; `screenshot.*` config unused |
| OB-16 | Downscale with coordinates mapped back | NOT BUILT | |
| OB-17 | Ref labels on a screenshot | NOT BUILT | |
| OB-18 | Zoom into a region | NOT BUILT | |
| OB-26 | Console log | NOT BUILT | `capture.*` config unused |
| OB-27 | Network log | NOT BUILT | |
| OB-37 | Passwords masked in snapshots | BUILT | `snapshot_page.js:206-207`; `tests/e2e/test_snapshot.py:126` |
| OB-39 | (M1 part) Over-size snapshot is cut and says so | BUILT | `snapshot_page.js:254-258`, `:307` |
| OB-40 | (M1 part) Page text marked untrusted in tool descriptions | PARTIAL | said in the MCP instructions (`src/mcp/server.py:24-25`) and in the loop's prompt (`src/agent/loop.py:20`); not in any tool description (`browser_tools.py:110-136`) |
| OB-42 | The walk stops at the cap | BUILT | `snapshot_page.js:253-258`; `tests/e2e/test_snapshot.py:159` |
| OB-43 | Images only on request, no raw HTML | BUILT (no tool returns either) | `browser_tools.py:109-137` |

**15.7 Actions**

| ID | Feature | Verdict | Evidence |
|---|---|---|---|
| AC-01 | Click by ref or point, buttons, counts, modifiers | PARTIAL | by ref only; no `x`/`y` (`browser_tools.py:30-35`) |
| AC-02 | Hover | NOT BUILT | |
| AC-03 | Drag | NOT BUILT | `input.drag_steps` unused |
| AC-05 | Type: replace, submit, key by key | BUILT | `browser_tools.py:38-43`; `playwright_driver.py:275-307` |
| AC-06 | Fill several fields in one call | NOT BUILT | |
| AC-07 | Set a value by ref | NOT BUILT | |
| AC-08 | Choose a dropdown option | NOT BUILT | |
| AC-09 | Tick or untick | NOT BUILT (a click can do it) | |
| AC-10 | Press a key or shortcut | NOT BUILT | `key_repeat_max` unused |
| AC-12 | Scroll by steps | NOT BUILT | `scroll_step_px` unused |
| AC-13 | Scroll an element into view | NOT BUILT as a tool (a click does it internally, `snapshot_page.js:409`) | |
| AC-18 | Highlight the target, drawn in the viewer | BUILT | `src/service/session.py:194-198`; `viewer/src/components/BrowserPane.tsx:206-227` |

**15.8 Forms, files, dialogs, clipboard**

| ID | Feature | Verdict | Evidence |
|---|---|---|---|
| FF-01 | Upload only from allowed folders | NOT BUILT | `uploads.*` unused |
| FF-02 | Downloads to a set folder with a size limit | NOT BUILT | `downloads.*` unused |
| FF-03 | List downloaded files | NOT BUILT | |
| FF-05 | Dialog policy | NOT BUILT | `dialogs.*` unused; no dialog handler |
| FF-07 | "Leave this page?" dialogs | NOT BUILT | |
| FF-11 | Other tools refused while a dialog is open | NOT BUILT | |
| FF-14 | Oversized download cancelled | NOT BUILT | |

**15.9 to 15.13**

| ID | Feature | Verdict | Evidence |
|---|---|---|---|
| JS-01 | Run a script in the page, off by default, needs approval | NOT BUILT | `javascript.allow_evaluate` unused |
| RB-01 | Wait until an element is ready | PARTIAL | click waits (`snapshot_page.js:394-432`); typing does not (`:442-453`, status finding M1) |
| RB-02 | Stale-ref error that says to re-read | BUILT | `src/errors.py:20-25` |
| RB-04 | (M1 part) Fill a form in one call | NOT BUILT | |
| RB-05 | Fresh snapshot after an action, off by default | BUILT | `browser_tools.py:91-92`, `:104-105`; `config.py:110` |
| CM-09 | The core inside a container or micro VM | NOT BUILT | no `deploy/` |
| SN-04 | (M1 part) Hand a check to a person when the agent asks | NOT BUILT | no `browser_request_human` |
| AU-04 | (M1 part) Pattern redaction | BUILT | `src/policy/redaction.py:24-27`; `src/tools/toolkit.py:83` |

**15.14 Safety and governance**

| ID | Feature | Verdict | Evidence |
|---|---|---|---|
| SG-01 | Allow and block lists with wildcards | BUILT | `src/policy/url_policy.py:49-53`, `:118-121` |
| SG-02 | Enforced on redirects, link clicks, pop-ups, frames | NOT BUILT | only the address given to `browser_navigate` is checked (`browser_tools.py:59`); no request interception anywhere in `src` |
| SG-03 | Listed schemes only, local files off | BUILT | `url_policy.py:93-98` |
| SG-04 | Private-network guard | BUILT (for the navigate tool only) | `url_policy.py:122-144` |
| SG-05 | Cloud metadata always blocked | BUILT (for the navigate tool only) | `url_policy.py:25-29`, `:115-116` |
| SG-06 | Allow, confirm or deny per tool | NOT BUILT | `action_policies`, `default_action_policy`, `ask_before` unused |
| SG-07 | Approval by a person in the viewer | NOT BUILT in the service | viewer card only |
| SG-08 | Redaction on every result | BUILT | `src/tools/toolkit.py:83` |
| SG-11 | (M1 part) Locks and limits set by a deployment | NOT BUILT | `settings.locked` unused |
| SG-20 | Token, localhost, `Host` and `Origin` checks | BUILT for the surfaces that exist | `src/service/app.py:55-56`, `:63-64`, `:70-75`, `:109`; `config.py:264` |
| SG-22 | An approval that times out is denied | NOT BUILT | |
| SG-24 | Only document requests intercepted, cached decisions | NOT BUILT | the cache exists (`url_policy.py:103-110`), the interception does not |
| SG-25 | Nothing reaches the agent while a person drives | BUILT | `src/service/session.py:230-255`, `:121` |
| SG-26 | Typed text and form values masked in events and logs | BUILT, with one gap | `src/tools/event_log.py:22-23`, `:55`. Gap: the result and the log line still give the length of a password, also when a ref is given (`browser_tools.py:101`), although `src/driver/base.py:45` says not even its length is told. Status N1 names only the no-ref case |

**15.15 to 15.18**

| ID | Feature | Verdict | Evidence |
|---|---|---|---|
| OS-01 | Event log, one line per call | BUILT | `src/tools/event_log.py:43-59` |
| OS-04 | A picture for every step | BUILT in the viewer only | `viewer/src/connection/socket.ts:169-172`; nothing is kept by the service |
| OS-05 | Live view | BUILT | `playwright_driver.py:319-355`; `src/service/events.py:81-83` |
| OS-08 | (M1 part) Output size per call | BUILT | `event_log.py:53`; `src/service/session.py:210` |
| IF-01 | Python API | BUILT | `src/tools/toolkit.py:38`; `src/driver/session.py:75-81`; `tests/e2e/test_toolkit_in_process.py` |
| IF-03 | Command line: `mcp`, `serve`, `config`, `doctor`, `bench` | PARTIAL | `mcp`, `config`, `agent` only (`src/cli.py:45-92`) |
| IF-04 | Show where each setting came from | BUILT | `src/cli.py:102-109` |
| IF-05 | MCP over stdio | BUILT | `src/mcp/server.py:51-56` |
| IF-06 | MCP over HTTP | NOT BUILT | |
| IF-08 | Tool definitions usable by any model | BUILT | `src/tools/registry.py:30-32`; used by `src/agent/openai_model.py:40-49` |
| IF-09 | Basic reference loop | BUILT | `src/agent/loop.py:30-61` |
| IF-15 | Event stream for user interfaces | BUILT (8 of the protocol's 16 event types are sent) | `src/service/session.py:74`, `:93`, `:190`, `:195`, `:206`, `:221`, `:292`, `:311`. Never sent: `approval_*`, `help_*`, `dialog_*`, `download_saved`, `settings_changed` (`viewer/src/protocol.ts:45-53`) |
| IF-18 | (M1 part) Claude Code recipe | BUILT as text, never run | `README.md:24`; status open point 6 |
| IF-19 | Scripted MCP client for tests | BUILT | `tests/service/test_mcp.py:38-52` |
| CL-01 | Any remote CDP endpoint, through attach | NOT BUILT | |
| CL-02 | Our own headless Chromium image | NOT BUILT | |
| EV-01 | End-to-end suite on three browsers | PARTIAL | 74 tests on Chromium only |
| EV-04 | (M1 part) Safety pages: hidden text, blocked addresses, forbidden scripts | PARTIAL | hidden text (`tests/site/hidden.html`, `tests/e2e/test_snapshot.py:90`) and blocked addresses (`tests/e2e/test_address_policy.py:53`); no script tests (no code tool); no `tests/safety/` |
| EV-06 | Performance bench with budgets | NOT BUILT | |
| EV-07 | Snapshot checked against Playwright's accessibility snapshot | BUILT | `tests/e2e/test_snapshot.py:81-86` |

**15.19 Viewer** ("recorded only" means the viewer part exists and works on recorded sessions, and the service never sends the event or acts on the command)

| ID | Feature | Verdict | Evidence |
|---|---|---|---|
| UI-01 | Design tokens, light and dark | BUILT | `viewer/src/tokens.css:23-180` |
| UI-02 | Split view and full view | BUILT | `viewer/src/App.tsx:71`, `:118`, `:258` |
| UI-03 | Session picker with state badges | NOT BUILT | a session-name chip only (`App.tsx:270-273`); `W.topBar.sessions` unused |
| UI-04 | Live frame over a binary WebSocket | BUILT | `src/service/app.py:159-160`; `viewer/src/connection/socket.ts:125-128` |
| UI-05 | Tab strip and address bar | PARTIAL | drawn (`BrowserPane.tsx:35-52`, `:60-72`); `select_tab` is ignored by the service; one tab only |
| UI-06 | Control border and label | BUILT | `viewer/src/state/view.ts:87-152`; `BrowserPane.tsx:184`, `:230` |
| UI-07 | Status line with action and elapsed time | BUILT | `view.ts:37-41`; `viewer/src/components/StatusPanel.tsx:130` |
| UI-08 | Target highlight and agent pointer | BUILT | `BrowserPane.tsx:206-227` |
| UI-09 | Timeline rows, reads collapsed, idle gaps | BUILT | `viewer/src/state/timeline.ts:30-58` |
| UI-10 | Step drawer with picture and raw result | PARTIAL | picture, timing, address and the summary sentence (`viewer/src/components/Timeline.tsx:98-159`); no raw result exists in the protocol |
| UI-11 | Approval card | PARTIAL (recorded only) | `viewer/src/components/Cards.tsx:24` |
| UI-12 | Pause, resume, stop | BUILT | `App.tsx:193-195`, `:356-372`; `src/service/session.py:108-117` |
| UI-13 | Take over and hand back with remote input | BUILT | `BrowserPane.tsx:150-175`; `src/service/session.py:123-158` |
| UI-14 | Help card | PARTIAL (recorded only) | `Cards.tsx:46` |
| UI-15 | Dialog card | PARTIAL (recorded only) | `Cards.tsx:60` |
| UI-16 | Blocked, ended, disconnected, link refused, stale picture | BUILT | `view.ts:65-85`, `:133-143`, `:53` |
| UI-17 | Keyboard, announcements, reduced motion | BUILT | `App.tsx:180-204`, `:374-379`; `styles/base.css:173`. Single-letter keys cannot be turned off (status open point 3) |
| UI-18 | Summary card and counters | BUILT | `Cards.tsx:99`; `App.tsx:252` |
| UI-19 | Autonomy mode switch in settings | PARTIAL (recorded only) | `viewer/src/demo/settings.ts:69` |
| UI-22 | (M1 part) Blocked and allowed sites, clearing browser data | PARTIAL (recorded only) | `demo/settings.ts:131`, `:143`, `:222` |
| UI-25 | Read-only view of the effective settings | PARTIAL | drawn from fixed sample values (`demo/settings.ts:357-366`), also in a live session; `/api/config` does not exist |
| UI-28 | Shown inside another page | BUILT | `viewer/src/main.tsx:61`; `src/service/app.py:190-192` |
| UI-29 | Phone-width layout, tap and drag during takeover | PARTIAL | layout built (`styles/app.css:963`, `:1009`); no `touch-action` rule in `viewer/src/styles`, which matches status M19 (a drag scrolls the viewer) |

**15.20 Backends and bridge**

| ID | Feature | Verdict | Evidence |
|---|---|---|---|
| BK-01 | One contract on every surface | BUILT for the one backend that exists | `src/tools/registry.py:23-32` |
| BK-02 | Same tools in-process, stdio and HTTP | PARTIAL | in-process and stdio; not HTTP |
| BK-03 | Remote headless in the micro VM | PARTIAL | the driver is built; no VM image |
| BK-04 | Driver interface of plain data | BUILT, with one exception | `src/driver/base.py:55-96`; `start_frames` takes a callback and a config object (`:84`) |

**15.21 Settings**

| ID | Feature | Verdict | Evidence |
|---|---|---|---|
| SE-01 | Settings screen | PARTIAL | built on a recorded answer; a live session offers two settings (`viewer/src/main.tsx:19`, `:53`) |
| SE-02 | (M1 part) Web and mobile sets | PARTIAL (recorded only) | `demo/settings.ts:326-340` |
| SE-03 | Settings a deployment can lock | NOT BUILT | `settings.locked` unused; one locked row in the recording (`demo/settings.ts:289`) |
| SE-04 | Tighten but not loosen | NOT BUILT in the service | refusal reasons exist in the viewer only (`viewer/src/settings/types.ts:48`) |
| SE-05 | One catalogue in code | NOT BUILT | the only catalogue is the viewer's recording (`demo/settings.ts`); no `src/settings/` |
| SE-06 | Settings API | NOT BUILT | no route |
| SE-07 | (M1 part) Shows the preferred browser | PARTIAL (recorded only) | `demo/settings.ts:19` |
| SE-08 | Approval mode chosen by the person | PARTIAL (recorded only) | `demo/settings.ts:69` |
| SE-09 | Blocked and allowed sites, person and deployment | PARTIAL | the deployment's lists work through config (`config.py:217-218`); the person's side is recorded only |
| SE-11 | Keep sign-ins between sessions | NOT BUILT | needs a persistent profile |
| SE-12 | (M1 part) Clear browsing data, cloud browser | NOT BUILT | no route; the recorded source does nothing (`demo/settings.ts:355`) |
| SE-13 | Downloads and uploads on or off | NOT BUILT | config keys unused |
| SE-15 | Colour mode | BUILT | `viewer/src/App.tsx:107-112`; kept in a live session (`main.tsx:19`) |
| SE-16 | Picture quality for the live view | PARTIAL | works as deployment config (`src/service/session.py:84-85`); a person cannot change it in a live session |

Totals for the 161 rows with a milestone 1 part: **63 BUILT, 31 PARTIAL, 67 NOT BUILT.** Rows qualified in the table (for example "BUILT in the viewer only", "BUILT for the navigate tool only") are counted under their leading verdict; RB-01 is counted as PARTIAL.

### B3. Rows marked for later that the code already implements

| ID | Marker | What exists | Evidence |
|---|---|---|---|
| RB-03 | Next | A click that is covered names the covering element | `src/driver/snapshot_page.js:426` |
| RB-15 | Next | Partly: a timed-out action says the page may still be working and asks for a new snapshot | `src/driver/playwright_driver.py:412-415` |
| SG-17 | M4 for scripts; per session Next | Partly: `agent.max_steps` in the reference loop only | `src/agent/loop.py:57-58` |
| UI-31 | M2 | Partly: the "own browser" placeholder and its recorded state | `viewer/src/state/view.ts:48`; `BrowserPane.tsx:130-140` |
| SE-10, SE-14 | M2, M3 | As recorded settings rows only | `viewer/src/demo/settings.ts:154`, `:199` |

No other later-milestone row has code behind it.

---

## C) Status page check (`docs/status.md`)

### C1. Internal problems in the file

| Line | Problem | Fact |
|---|---|---|
| 3 | "Branch `prototype/base`" | WRONG. `git branch -a` shows only `main`, `remotes/origin/main`, `remotes/origin/HEAD`. No `prototype/base` exists |
| 3 | "nothing pushed" | WRONG. `main` is level with `origin/main` (remote `github.com/DCode-v05/Browser-Agent`); HEAD `c31def5` is on the remote |
| 3 | "49 commits on the branch" | WRONG as a total. `git log --oneline \| wc -l` gives 51; 50 at `bfa2148`. The earlier version of the page said 40 at `efe9d72`, where the count is 41, so the page appears to leave out the first commit each time |
| 3 | "Date: 2026-10-04" | The last commit (`c31def5`, "Status Partitially Updated") is dated 2026-10-05 06:03 +0530 and changed only this file |
| 33 | `REVIEW_THREE_ROW` | A stray placeholder directly under the table. It suggests a row for a third review was meant and never written |
| 221-223 | Blank line between decisions 27 and 28 | Splits the table; rows 28 to 35 have no header row and will not render as a table |
| 32 vs 234-243 | "Of 12 minor findings, 5 fixed and 7 deferred" | The deferred table has 8 rows (N1, N4, N5, N6, N8, N9, N10, N11). IDs run to N11 and three are absent (N2, N3, N7), which fits neither 12 found nor 5 fixed |
| 251 | "None of these was fixed" | M9 and M11 carry notes of partial change and M13 was fixed (line 276). The count of 20 rows is right (M1-M12, M14-M21) |
| 60-62 | Exit codes | Omits 130 on Ctrl+C, which the spec lists (line 2795) and the code returns (`src/cli.py:187-188`) |
| 301-313 | Documents table | Omits `docs/browser-agent-perception.html`, which exists and is in the spec's layout (line 126) |

All 23 commit hashes cited exist (`git cat-file -t` returns `commit` for each): bfa2148, 61e8970, 4d866c8, 5e921ff, 6bfaaee, 2d43ea8, 3150889, 88b89e6, 7733832, 574551f, 85a7539, 171ad96, 66c5ced, defb21b, 3fc495c, 298bb1c, 91b980f, e31116f, f597c35, 6a0f264, ac063e1, b18e0dc, 4e4ca97. Their subjects match what the page says each delivered.

### C2. "Where things stand" table

| Claim | Verdict | Evidence |
|---|---|---|
| One command runs an agent, a person can pause, take over, hand back, stop | CONFIRMED | `src/agent/command.py:28-82`; `src/service/session.py:105-119` |
| 696 tests: 495 unit, 74 browser, 35 service, 92 viewer | CONFIRMED as counts (collection gives exactly 696 = 495 + 74 + 35 + 92). "Passing" CANNOT CHECK: not run | |
| ruff, pyright clean | CANNOT CHECK (not run) | |
| Viewer unit tests: 347 passed | CANNOT CHECK (not run; about 221 test declarations, 12 of them tables) | |
| Viewer typecheck, lint, build | CANNOT CHECK. A built viewer is present in `src/bap_browser/viewer_dist/` | |
| axe scan on every state inside the 92 viewer tests | CANNOT CHECK by running; `axe-core` is a dependency (`viewer/package.json`) and `tests/viewer/conftest.py:139` has `accessibility_violations` | |
| The whole path is tested in `tests/viewer/test_live_session.py` | CONFIRMED that the test exists (136 lines); result not run | |
| Run by hand; Stop after Pause ended in 74 ms | CANNOT CHECK FROM CODE | |
| Hosted model: 13 tests against a stand-in server | CONFIRMED | 13 collected in `tests/unit/test_openai_model.py`; stand-in at `tests/support/model_stand_in.py` |
| With no key: the quoted message and code 2 | CONFIRMED | `src/cli.py:165-169`, `:33-35`; `tests/service/test_agent_command.py:94` |
| "There is no key on this side"; never run against the real service | CANNOT CHECK. A `.env` file exists in this checkout (not read) | |
| Review counts (1 critical + 9 important; 4 critical + 3 important) | CANNOT CHECK FROM CODE; the fixes listed are in the code (C6) | |

### C3. Options of `agent` and exit codes

| Claim | Verdict | Evidence |
|---|---|---|
| `--demo` | CONFIRMED | `src/cli.py:70-74`, `:148-152` |
| `--open` opens the viewer and starts once connected | CONFIRMED | `cli.py:84-86`; `src/agent/command.py:48-52` |
| `--wait-for-viewer` | CONFIRMED | `cli.py:81-83`; `command.py:50-52` |
| `--pace`, default 1 | CONFIRMED | `cli.py:75-80`. It acts only with `--demo` (`cli.py:152`), as the page says |
| `--exit-when-done` | CONFIRMED | `cli.py:87-91`; `command.py:72-74` |
| Exit 0 when answered | CONFIRMED | `cli.py:192` |
| Exit 1 when the model failed, the step limit was reached, or a person stopped | CONFIRMED | `cli.py:189-191`; `src/agent/loop.py:47`, `:58` |
| Exit 2 for a wrong command or configuration | CONFIRMED | `cli.py:33-35` (argparse also exits 2) |
| Answer printed in the terminal, viewer stays open until Ctrl+C | CONFIRMED | `command.py:71-74`. After a model failure the service stops at once (`command.py:65-68`, `:80-82`); the viewer keeps the summary (`viewer/src/state/view.ts:71-82`) |
| `?demo=signup`, `?state=<name>`, `&theme=dark` | CONFIRMED | `viewer/src/main.tsx:26-29`, `:56-57` |

### C4. Hosted-model table

| Claim | Verdict | Evidence |
|---|---|---|
| Provider OpenAI, model `gpt-5.6-luna`, changed with `agent.model` | CONFIRMED | `src/config.py:324-327`; `src/agent/openai_model.py:37` |
| Key from `OPENAI_API_KEY`, environment or `.env` in the run folder | CONFIRMED | `config.py:328-331`; `src/cli.py:30`, `:163-164`; `src/env_file.py:29` (the environment wins) |
| Key never in `config.json`, never logged | CONFIRMED by reading | the key appears only in the request header (`openai_model.py:103`); the 401 message does not pass on the provider's text (`:123-128`) |
| Responses API over plain HTTPS, no extra library | CONFIRMED | `openai_model.py:100-107` (`urllib`, `{base_url}/responses`); no OpenAI package in `pyproject.toml:7-14` |
| `agent.base_url` for a proxy | CONFIRMED | `config.py:332-345` |
| `store` is off; reasoning passed back encrypted | CONFIRMED | `openai_model.py:52-53`, `:91-92` |
| Limits: `max_steps` 40, `max_tokens` 4096, `request_timeout_s` 120 | CONFIRMED | `config.py:336-338`; used at `src/agent/loop.py:57`, `openai_model.py:51`, `:107` |
| 401 message text | CONFIRMED | `openai_model.py:125-128` |
| Other failures name the HTTP code and the provider's message | CONFIRMED | `openai_model.py:129-133` |
| Session ends as "failed" and the viewer says why | CONFIRMED | `src/agent/command.py:65-67`; `src/service/session.py:93-95` |
| Whether the real service accepts the name and request shape | CANNOT CHECK FROM CODE (the page says so itself) | |

### C5. The look

| Claim | Verdict | Evidence |
|---|---|---|
| White page, #F5F4F2 surface, #1A1714 text | CONFIRMED | `viewer/src/tokens.css:27`, `:29`, `:33` |
| Ink #09090B for the main action | CONFIRMED | `tokens.css:35`; `viewer/src/styles/base.css:112-113` |
| Radii 10, 16, 20 px; pills; hairlines | CONFIRMED | `tokens.css:78-81`, `:31`, `:86` |
| Hanken Grotesk | CONFIRMED | `tokens.css:5-21`, `:53` |
| Gradient only on the brand mark and a switch that is on | CONFIRMED | two uses: `styles/app.css:38`, `styles/settings.css:224` |
| Agent colour is the violet end of the gradient | CONFIRMED | `tokens.css:38` and the last stop at `:48` (#6E3B83) |
| Secondary text #56524D, not #8D8881; #8D8881 is 3.52:1 on white | CONFIRMED | `tokens.css:34`; I computed 3.52 for #8D8881 on white |
| Every text pair at least 4.5:1, lowest 4.91:1 | PARTLY CHECKED | the pairs I computed are all above 4.5 (lowest found: success on its tint, 4.93). The full set is computed in `viewer/src/tokens.test.ts`, not run |
| Focus ring is the text colour | CONFIRMED | `tokens.css:37` |
| No sidebar | CONFIRMED | `viewer/src/App.tsx:258-332` |
| Font ships as two files, 54 KB together | CONFIRMED | 19,588 + 34,704 = 54,292 bytes in `viewer/src/fonts/` |
| Licence in `viewer/src/fonts/OFL.txt` | CONFIRMED | file present |
| Values taken from `bap-web/bap-frontend/app/globals.css` | CANNOT CHECK (that file is not in this repository) | |

### C6. Review fixes and "what running it showed" (spot-checked in code)

| Claim | Verdict | Evidence |
|---|---|---|
| One canonical address is judged and handed to the browser | CONFIRMED | `src/policy/address.py:33-57`; `src/tools/browser_tools.py:59-61` |
| A site-list entry that cannot match stops start-up | CONFIRMED | `src/config.py:234-243` |
| A call fails after `page_reply_ms` (5 s) | CONFIRMED | `config.py:89-91`; `src/driver/page_script.py:37-46` |
| The log keeps the first line of a result | CONFIRMED | `src/tools/event_log.py:55` |
| A field's content is never its name | CONFIRMED | `src/driver/snapshot_page.js:346-350` |
| Bad arguments logged by name only | CONFIRMED | `event_log.py:33-35`; `src/tools/toolkit.py:78` |
| Typing fails when the page moves the focus | CONFIRMED | `snapshot_page.js:456-460` |
| Addresses in results cut at 300 characters | CONFIRMED | `src/driver/session.py:32-33` (uses `snapshot.max_text_chars`, 300) |
| Click inside a scrolled box is brought into view | CONFIRMED | `snapshot_page.js:419-425` |
| Browser gone: result says so; a navigation starts a new one | CONFIRMED | `src/driver/session.py:47-57` |
| Credentials in addresses are never shown or logged; `<not a valid address>` | CONFIRMED | `address.py:63-74`; `event_log.py:25`; `playwright_driver.py:202-205` |
| `http://[::1` is an ordinary failed call | CONFIRMED | `src/policy/url_policy.py:83-88`; `browser_tools.py:64-67` |
| Stop is final and immediate | CONFIRMED | `src/driver/session.py:45-46`, `:58-61`; `src/service/app.py:130-133`; `src/service/session.py:288-290` |
| Input fails after `action_ms` | CONFIRMED | `playwright_driver.py:404-416` |
| Held keys are let go at hand-back and when the picture loses focus | CONFIRMED | `src/service/session.py:160-174`, `:269`; `viewer/src/components/BrowserPane.tsx:169-172`, `:202` |
| A pointer move needs no button | CONFIRMED | `src/service/session.py:134-136` |
| NAT64, 6to4, Teredo, IPv4-compatible judged as IPv4 | CONFIRMED | `address.py:124-146` |
| The five minor fixes (list as button, insert-text error, no retry of a missing session, no extra model call after Stop, a non-ref never sent to the page) | CONFIRMED | `src/service/session.py:133`; `playwright_driver.py:381-392`; `viewer/src/connection/socket.ts:36`; `src/agent/loop.py:46-47`, `:55-56`; `src/tools/toolkit.py:125-131` |
| The viewer has its own icon | CONFIRMED | `viewer/public/favicon.svg` |
| A new link in an open tab is taken and the token removed | CONFIRMED | `viewer/src/main.tsx:40-44`; `viewer/src/connection/address.ts:14-22` |
| The answer is printed once, as soon as known | CONFIRMED | `src/agent/command.py:70-71` |
| The state file is removed on a normal stop | CONFIRMED | `src/service/server.py:88-91` |
| Each HTTP answer ends its connection; stopping waits at most 3 s | CONFIRMED | `src/service/app.py:195`; `server.py:66`; `config.py:270` |
| A replaced picture is released one second later | CONFIRMED | `socket.ts:38`, `:157-164` |
| The rate test allows 9 pictures | CONFIRMED | `tests/e2e/test_live_view.py:101` |
| Timeline says "Typed a password into ..." | CONFIRMED | `src/tools/sentences.py:94-95` |
| The web server's INFO lines appear in the terminal | CANNOT CHECK without running | |

### C7. Decisions 1 to 35

| # | Verdict | Evidence |
|---|---|---|
| 1 Viewer connection built first | CONFIRMED | commit `574551f` precedes `61e8970` in `git log` |
| 2 A finished step arrives with its own picture | CONFIRMED | `socket.ts:143-146`, `:169-172` |
| 3 No token shows "This link can't open the session" | CONFIRMED | `viewer/src/main.tsx:49-50` |
| 4 4401 and 4404 are not retried | CONFIRMED | `socket.ts:36`, `:113-116` |
| 5 Live settings offer only colour mode and the agent pointer | CONFIRMED | `main.tsx:19`, `:53` |
| 6 `agent.provider` accepts `openai` and `scripted` | CONFIRMED | `config.py:324` |
| 7 The demo site moved into the package | CONFIRMED | `src/bap_browser/demo_site/`; `src/service/app.py:105` |
| 8 A step sentence carries the role | CONFIRMED | `src/tools/sentences.py:49-50` |
| 9 Every failure carries a short reason | CONFIRMED | `src/errors.py:7-10` |
| 10 An off-screen element gets no outline | CONFIRMED | `snapshot_page.js:489-491` |
| 11 A call that cannot run is a step too | CONFIRMED | `src/tools/toolkit.py:69-78` |
| 12 The tool layer takes a gate | CONFIRMED | `src/tools/gate.py:18-25`; `toolkit.py:44`, `:62` |
| 13 A viewer that stops reading is told to connect again | CONFIRMED | `src/service/events.py:32-34`; `src/service/app.py:151-153` |
| 14 A held call is logged by name only and is not a step | CONFIRMED | `toolkit.py:63-68` |
| 15 The rate is limited by delaying the acknowledgement | CONFIRMED | `playwright_driver.py:345-355` |
| 16 The heartbeat re-reads the open tab | CONFIRMED | `src/service/session.py:188` |
| 17 A key outside Playwright's keyboard is put in as text | CONFIRMED | `playwright_driver.py:381-387` |
| 18 A wheel turn is cut to one screen; outside positions refused | CONFIRMED | `src/service/session.py:128`, `:152-153` |
| 19 The service is tested on a real port with a real WebSocket client | CONFIRMED | `tests/service/test_service.py:16-17` |
| 20 Frame rule, `Host` check, 64 KiB limit, `auth_wait_s` 10 | CONFIRMED | `src/service/app.py:109`, `:190`, `:78`; `src/service/server.py:20`, `:63`; `config.py:269` |
| 21 A missing session is answered only after the token | CONFIRMED | `app.py:82-88` |
| 22 `--pace`, `--wait-for-viewer`, `--open` | CONFIRMED | `src/cli.py:75-86` |
| 23 The log keeps only the first line | CONFIRMED | `event_log.py:55` |
| 24 The model still sees field values, not passwords | CONFIRMED | `snapshot_page.js:204-207` |
| 25 One new setting `page_reply_ms`. Its reason, "no tunable number lives outside `config.py`" | Setting CONFIRMED (`config.py:89`). The reason is not true of the code: see D, item 9 |
| 26 An ended session takes precedence over a lost connection | CONFIRMED | `viewer/src/state/view.ts:71-85` |
| 27 The whole-path test stops the service before closing the page | CONFIRMED | `tests/viewer/test_live_session.py:110-114`, `:134-135` |
| 28 Plain HTTPS, no OpenAI library | CONFIRMED | `openai_model.py:10-13`; `pyproject.toml:7-14` |
| 29 `.env` is read at start; a variable already set wins | CONFIRMED | `cli.py:30`; `env_file.py:29` |
| 30 A stopped or step-limited run ends with code 1 | CONFIRMED | `cli.py:189-191` |
| 31 The font is two files, not an npm package | CONFIRMED | `viewer/src/fonts/`; no fontsource in `viewer/package.json` |
| 32 Agent colour and gradient use | CONFIRMED | `tokens.css:38`, `:48`; two uses of the gradient |
| 33 A command queue of `server.command_backlog` (256); beyond it dropped; Stop never waits | CONFIRMED | `config.py:271-273`; `app.py:130-136` |
| 34 After a time-out, input already sent is not taken back | CONFIRMED | `playwright_driver.py:411-416` |
| 35 An unreadable address is logged as `<not a valid address>` | CONFIRMED | `event_log.py:25` |

### C8. Deferred findings N1 to N11 (second review)

| # | Verdict (is the fault still in the code?) | Evidence |
|---|---|---|
| N1 | CONFIRMED, and wider than stated: the length reaches the result and the log also when a ref is given; only the viewer sentence hides it | `browser_tools.py:101`; `event_log.py:23`; `sentences.py:93-99` |
| N4 | CONFIRMED as structure (Stop runs inside the connection's listen task); the failure itself was not reproduced by the reviewer | `app.py:125-133` |
| N5 | CONFIRMED | refused `Origin` closes with 1008 (`app.py:40`, `:73-75`); the viewer treats only 4401 and 4404 as final (`socket.ts:36`) |
| N6 | CONFIRMED | `events.py:87` (`maxlen or None` gives no limit at 0); `config.py:281-284`, `:269`, `:312` have no bounds; `1 / max_fps` at `playwright_driver.py:350` |
| N8 | CONFIRMED | only a POSIX mode is set: `server.py:97` |
| N9 | CONFIRMED | `src/service/session.py:243-244` (falls back to `ENDED` when control is `agent` again) |
| N10 | CONFIRMED | kept pictures are released only when the session name differs: `socket.ts:139-141` |
| N11 | CONFIRMED | size read once: `src/service/session.py:71`, used at `:127` |
| N2, N3, N7 | Not listed in the page; presumably among the fixed ones. CANNOT CHECK which finding each was | |
| Left unjudged: redirects, link clicks and pop-ups unchecked; a person's own navigation outside the policy; query strings shown and logged | CONFIRMED | no interception in `src`; `address.py:63-65` removes only credentials |

### C9. Deferred findings M1 to M21 (first review)

| # | Verdict | Evidence |
|---|---|---|
| M1 | CONFIRMED | `snapshot_page.js:442-453` (no wait, no cover check) |
| M2 | CONFIRMED by reading | `playwright_driver.py:440-449` returns silently when `settle_ms` runs out |
| M3 | CONFIRMED | `ConfigError` raised inside `start()` (`playwright_driver.py:50-51`, `:144`) after Playwright was started (`:142-143`) and outside the `except PlaywrightError` (`:151`); it reaches `toolkit.py:113-119` as "failed unexpectedly" |
| M4 | CONFIRMED | `toolkit.py:85` is not guarded; `event_log.py:57-59` |
| M5 | CONFIRMED | only `JSONDecodeError` is caught (`config.py:449-453`); plain `int` fields throughout; `config.py:505` ("the configuration"); patterns compiled at `src/driver/session.py:23` |
| M6 | CONFIRMED | `snapshot_page.js:45-49` (length in UTF-16 units, cut in code points), `:252` (budget can go negative), `:300` (`Page:` not quoted) |
| M7 | CANNOT CHECK (not reproduced by the reviewer either) | |
| M8 | CONFIRMED | `src/mcp/server.py:21-26` names screenshots and `browser_request_human`. Related and not listed: `src/driver/snapshot.py:9` names `browser_find` |
| M9 | CONFIRMED | `playwright_driver.py:177-183` |
| M10 | PARTLY CONFIRMED | `keyboard.type` with a line break is at `playwright_driver.py:291-292`; "an empty error message" most likely means `first_line` at `:92-93`, which would raise on an empty message (my reading, not tested) |
| M11 | CONFIRMED that the list is short (two host names, four addresses); which two providers are meant CANNOT CHECK | `url_policy.py:25-29` |
| M12 | CONFIRMED | `BrowserPane.tsx:160-161` |
| M14 | CONFIRMED in kind; I found 6, the page says 7 | `App.tsx:325`; `Timeline.tsx:43`; `BrowserPane.tsx:34`, `:36`, `:47`, `:66` |
| M15 | CONFIRMED for wording keys (`W.topBar.sessions`, `W.settings.saving`, `W.frame.blockedPage` are used nowhere); icons not checked | `viewer/src/wording.ts:179`, `:197`, `:127` |
| M16 | CONFIRMED | one timer for the newest toast only (`App.tsx:139-144`); `navigator.clipboard?.writeText` (`SettingsScreen.tsx:413`) |
| M17 | CONFIRMED | the drawer stops key events (`Timeline.tsx:111-112`); controls are skipped at `App.tsx:184` |
| M18 | CONFIRMED | the key comes from the first step, the row points at the newest (`timeline.ts:41`, `:47`) |
| M19 | PARTLY CONFIRMED | no `touch-action` rule in `viewer/src/styles`; the colour-mix part not checked |
| M20 | CONFIRMED by reading | `App.tsx:213` with `view.ts:37-41` (label, then summary) |
| M21 | CANNOT CHECK (the four tests are not named) | |

### C10. Open point 4, "states the spec lists that are not built"

| State | Verdict | Evidence |
|---|---|---|
| Session picker | CONFIRMED not built | `W.topBar.sessions` unused; no component |
| Settings "saving" | CONFIRMED not built | `W.settings.saving` unused |
| Buttons "working" | CONFIRMED not built | no match in `viewer/src` |
| Takeover bar "handing back", "failed" | CONFIRMED not built | no match |
| Address "loading" | CONFIRMED not built | `BrowserPane.tsx:60-72` has loaded and blocked only |
| Notice "limit reached" | CONFIRMED not built | no match |
| Not in the page's list | Two of the spec's six control states are never produced by the service (`waiting_approval`, `person_requested`); the viewer has them on recorded data only | `src/service/session.py:21` |

Other open points: point 2 (CLAUDE.md contradicts the spec) CONFIRMED and still unresolved (`CLAUDE.md:25`). Point 3 (single-letter keys) CONFIRMED (`App.tsx:193-199`, no setting). Point 8 CONFIRMED. Points 1, 5, 6, 7 CANNOT CHECK FROM CODE.

### C11. "Next, in order" (lines 315-323)

| # | Item | Verdict |
|---|---|---|
| 1 | Test with a real key | CANNOT CHECK |
| 2 | "The remaining 24 tools" | CONFIRMED as arithmetic: 28 in spec §6.2, 4 built. The list in brackets leaves out hover, drag, keys, dialogs, console, network, evaluate and `browser_request_human`; "frames" is not a tool |
| 3 | Approvals | CONFIRMED not built |
| 4 | Settings API | CONFIRMED not built |
| 5 | Address policy at the network layer | CONFIRMED not built |
| 6 | MCP over HTTP with `serve`, micro VM image, bench, verify loop | CONFIRMED not built |
| 7 | Milestones 2, 3, 4 | CONFIRMED not built |

Plan claims in the Documents table: stage 1 has 11 tasks, viewer 11, live loop 9, all ticked or present in the plans. CONFIRMED.

---

## D) Mismatches between spec, status.md, README.md, CLAUDE.md and the code

| # | Mismatch | Where |
|---|---|---|
| 1 | Branch and push state. status: `prototype/base`, nothing pushed. CLAUDE.md: "Work on a branch ... nothing is pushed". Repo: `main` only, level with `origin/main` on GitHub | `docs/status.md:3`; `CLAUDE.md:27` |
| 2 | Form values. CLAUDE.md says they never reach a result; the spec and the code show them to the model in a snapshot (not passwords). Flagged in status open point 2, not resolved | `CLAUDE.md:25`; `snapshot_page.js:204-207` |
| 3 | Password length. `driver/base.py:45` says not even its length is told to anyone; the result and the log give it | `browser_tools.py:101`; `event_log.py:23` |
| 4 | Exit code 130 is in the spec and the code, missing from status | spec line 2795; `cli.py:188`; `status.md:60-62` |
| 5 | `--wait-for-viewer` is in the spec, status and code; README does not mention it | `README.md:26-30` |
| 6 | Claude Code recipe is written three ways: spec `claude mcp add bap-browser -- bap-browser mcp`; README adds `uv run`; status adds `uv run --directory "<this folder>"` | spec line 2724; `README.md:24`; `status.md:295` |
| 7 | Spec §16.5 says a person watching the reference loop has "approvals"; none exist | spec line 2807 |
| 8 | Spec §6.1 says every result ends with `[tabs]` and `[events]`; only `[tabs]` is built. The model is told about tools that do not exist | `toolkit.py:148-152`; `src/mcp/server.py:21-26`; `src/driver/snapshot.py:9` |
| 9 | "No tunable number anywhere else" (CLAUDE.md, spec, decision 25). Numbers outside `config.py`: `server.py:20` (64 KiB), `openai_model.py:22` (300), `service/session.py:33` (32), `playwright_driver.py:35` (2 frames), `sentences.py:19-22`, `socket.ts:37-38` (reconnect delays, 1 s), `main.tsx:17`, and `options.ts:17-23`, which copies `viewer.stale_after_s`, `idle_divider_s` and `takeover.release_chord` because the service does not send them |
| 10 | "Every string a person reads is in `wording.ts`" (CLAUDE.md) against six hard-coded labels (status M14 says seven) | `CLAUDE.md:44`; C9 M14 |
| 11 | Config keys that exist and do nothing, about 45 of them. The generated reference (`config doc`) and `config show` present them as working settings. Whole sections: `browser.screenshot`, `text`, `find`, `capture`, `tabs`, `dialogs`, `downloads`, `uploads`, `javascript`, `control.approval_*`, `handoff_timeout_s`, `site_grant_lifetime`, `sessions`, `settings`, `bench`. Single keys: `backend.offered`, `data_dir`, `cdp_url`, `user_data_dir`, `idle_session_s`, `wait_max_s`, `popup_adopt_ms`, `include_iframes`, `max_frame_depth`, `scroll_step_px`, `drag_steps`, `key_repeat_max`, `enforce_on_subresources`, `default_action_policy`, `action_policies`, `ask_before`, `mcp.http_path`, `viewer.stale_after_s`, `idle_divider_s`, `takeover.release_chord`, `theme`, `show_agent_pointer` | grep of `src/bap_browser` outside `config.py` finds no reader |
| 12 | Spec §3.2 layout against the repo. Missing: `config.example.json`, `perf/`, `deploy/`, `.claude/skills/verify/`, `keys.py`, `settings/`, `bridge/`, `code/`, `bench/`, `policy/approvals.py`, `service/settings_api.py`, `control.py`, `auth.py`, `screencast.py`, `remote_input.py`, `driver/screenshots.py`, `dialogs.py`, `downloads.py`, `network_log.py`, `tests/safety/`, `extension/`. Present and not in the layout: `agent/`, `demo_site/`, `env_file.py`, `config_doc.py`, `policy/address.py`, `tools/toolkit.py`, `sentences.py`, `observer.py`, `gate.py`, `event_log.py`, `driver/session.py`, `page_script.py`, `service/server.py`, `tests/support/` | spec lines 116-187 |
| 13 | Spec stack lists Pillow; it is not a dependency (no screenshots yet) | spec line 103; `pyproject.toml:7-14` |
| 14 | Spec §14.6 lists "a built-in agent loop" and "native ... OpenAI toolset formats" as Later, while slice 4 and IF-09 put a basic loop in M1 and the code calls OpenAI with function tools. Consistent only if "built-in" means a full agent; worth one clarifying sentence in the spec | spec lines 2126, 2204, 2563 |
| 15 | Stage 2 plan text is stale: it says the hosted model is not added and `agent.provider` accepts only `scripted`; its `step_finished(..., url)` signature differs from the code (`tabs`) | `docs/plans/2026-10-03-m1-stage-2-live-loop.md:7`, `:27`, `:45`; `src/tools/observer.py:16-18` |
| 16 | CLAUDE.md gotchas describe a Windows checkout with a long path containing spaces; this checkout is on macOS at a short path with no spaces | `CLAUDE.md:30-33` |
| 17 | Spec header still says "Date: 2026-10-03 · Status: draft" although commit `6c0aa46` (2026-10-04) changed it | spec line 3 |
| 18 | Order of remaining work differs between spec and status (see E) | |

Agreement worth noting: the `agent` options, the hosted-model facts and the design tokens are the same in spec §16.5 / §10.3 / §9.5, status and code.

---

## E) Future work, in one order

The order follows the spec (§14.1 slices, then milestones, then §14.5), with status.md's "Next, in order" and deferred findings placed where they belong. "Status #n" is the item number in status.md lines 317-323.

| Order | Work | Source | Where the documents differ |
|---|---|---|---|
| 0 | First run with a real key; fix what it shows | Status #1 | Not in the spec |
| 0a | Repair status.md: branch, push state, commit count, `REVIEW_THREE_ROW`, the split decisions table, the 12 / 5 / 7 count, exit code 130 | This audit (C1) | |
| 0b | Decide the CLAUDE.md rule on form values; decide whether a password's length may appear in results and logs (N1, wider than stated) | Status open point 2; N1 | |
| 1 | Finish slice 1 gaps: session picker, "saving", "working", "handing back", "failed", address "loading", "limit reached"; a way to turn off single-letter keys | Spec slice 1; status open points 3, 4 | Status lists these as open points, not in its "Next" list |
| 2 | Slice 5: the remaining 24 tools | Spec slice 5; status #2 | Same position |
| 2a | With slice 5: frames in the snapshot, tabs and pop-ups, the `[events]` block, dialogs, downloads and uploads, console and network logs, screenshots | Spec slice 5, §6.1; stage 1 plan line 83 | Status folds these into "24 tools" |
| 2b | With slice 5: Chrome and Edge run for real, attach, persistent profile, `doctor`, idle close | Spec slice 5 | Missing from status "Next" |
| 2c | Findings that belong here: M1, M2, M3, M4, M6, M7, M8 (and the `browser_find` notice), M9, M10 | Status deferred list | |
| 3 | Slice 6: approvals; `browser_request_human`; the `waiting_approval` and `person_requested` states; the cards acting on the real session | Spec slice 6; status #3 | Status names approvals only |
| 3a | Slice 6: MCP over HTTP with `serve`; creating and ending sessions over the API; several sessions | Spec slice 6 | Status moves this to #6, after settings |
| 3b | Findings that belong here: N4, N5, N6, N8, N9, N10, N11, M12, M19 (phone drag) | Status deferred list | |
| 4 | Address policy at the network layer: redirects, link clicks, pop-ups, frames (SG-02, SG-24); a person's own navigation; M11 | Status #5; spec feature rows SG-02 and SG-24 are M1 | The spec names no slice for it. Status puts it after settings. It closes a known safety gap, so the spec's M1 marker argues for doing it no later than slice 6 |
| 5 | Slice 7: settings catalogue, saved settings, locks and limits, the settings API, `/api/config`, clear browsing data; the screen wired to it; send `viewer.*` values to the viewer; remove or wire the dead config keys; M5 | Spec slice 7; status #4 | Status puts this before the network layer and before `serve` |
| 6 | Slice 8: `deploy/Dockerfile`, `deploy/config.vm.json`, container flags, the run from outside the container at desktop and phone width | Spec slice 8; status #6 | Same relative order |
| 7 | Slice 9: bench, bench pages, `perf/budget.json`, the verify skill, clean-up after a crash | Spec slice 9; status #6 | Status does not mention crash clean-up |
| 8 | Milestone 1 acceptance, items 1 to 8, including the §12.5 checklist and three browsers | Spec lines 2133-2142 | Not in status |
| 9 | Viewer polish findings: M14, M15, M16, M17, M18, M20; test quality M21; the Windows traceback (open point 5) | Status deferred list | No place in the spec |
| 10 | Milestone 2: bridge channel, extension, permissions, viewer and settings, conformance | Spec §14.2; status #7 | Same |
| 11 | Milestone 3: driver host, desktop settings, conformance | Spec §14.3; status #7 | Same |
| 12 | Milestone 4: `browser_run` | Spec §14.4; status #7 | Same |
| 13 | Connect Codex and Hermes, publish recipes; try the Claude Code recipe for real (open point 6) | Spec §14.5 item 1 | Status stops at milestone 4 and lists nothing from §14.5 |
| 14 | Sign-in without the model seeing credentials | §14.5 item 2 | Not in status |
| 15 | Automatic detection of sign-in walls and human checks | §14.5 item 3 | Not in status |
| 16 | Notifications and a note to the agent | §14.5 item 4 | Not in status |
| 17 | Recording, replay, clean-up of old files | §14.5 item 5 | Not in status |
| 18 | Real-profile copy | §14.5 item 6 | Not in status |
| 19 | Speed and token work | §14.5 item 7 | Not in status |
| 20 | Remaining tools: `browser_pdf`, `browser_storage`, `browser_emulate`, `browser_mouse`, `browser_record`, `browser_network_request`, `browser_extract` | §14.5 item 8 | Not in status |
| 21 | Cloud depth: provider adapters, a network guard that resolves names itself, WebRTC | §14.5 item 9 | Not in status |
| 22 | Reference task set turned into budget lines | §14.5 item 10 | Not in status |
| 23 | Admin console, phone on-screen keyboard during takeover, one-shot CLI calls with a skill file | §14.5 item 11 | Not in status |
| Later | §14.6 list | Spec | Not in status |

Summary of the disagreements on order and content:
1. Status places the settings API (#4) before the network-layer policy (#5) and before MCP over HTTP (#6); the spec places `serve` and MCP over HTTP in slice 6, before settings.
2. The network-layer policy is a status item with no slice in the spec, although the spec marks SG-02 and SG-24 as M1.
3. Status "Next" leaves out `browser_request_human` by name, Chrome and Edge, attach, persistent profile, `doctor`, crash clean-up, the acceptance list, and all of §14.5.
4. Status item 1 (the real-key run) and the deferred findings have no place in the spec's plan.
