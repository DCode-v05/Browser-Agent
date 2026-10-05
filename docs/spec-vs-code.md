# bap-browser: Spec compared with the code and the status page

Date: 2026-10-05 · Checked at commit `c31def5` on `main` · Machine: macOS, Python 3.12.5, Node 20.20

This page says what the spec asks for, what the code does today, where `docs/status.md` is right or
wrong, and what is left to build, in order. The full row-by-row tables are in `docs/review/`.

**How to read the figures.** Three kinds of figure appear below, and they are never mixed:
- **Measured here**: I ran the command on this machine on 2026-10-05.
- **Read from code**: a reviewer read the code and tests; nothing was run.
- **From the status page**: `docs/status.md` says so; not re-checked.

---

## 1. Does it work today?

Yes. One command runs an agent in a real browser while a person watches and controls it.

| Check | Result | Kind |
|---|---|---|
| `bap-browser agent --demo --exit-when-done` | Signed up on the demo site and reported "Welcome, Ada" with 3 open invoices | Measured here |
| First run with the real model (`gpt-5.6-luna`, key from `.env`) on "Open example.com and tell me the main heading" | Answer: "The main heading is 'Example Domain.'" The model name and the request shape were accepted | Measured here |
| Real model on Wikipedia (search "Playwright (software)", open the article) | Opened the site, typed the search, submitted, read the article. Steps are in `.bap-browser/events.jsonl` | Measured here |
| Viewer unit tests (`npm --prefix viewer run test`) | 347 passed | Measured here |
| Viewer typecheck, lint, build | No findings; builds | Measured here |
| `ruff format --check`, `ruff check`, `pyright` | No findings | Measured here |
| Python suite (`uv run pytest -q`) | **694 passed, 2 failed** (status page: 696 passed on Windows, Python 3.13) | Measured here |

This closes the status page's open point 1 ("your first run with a real key is the first real run").

### The two tests that fail here

| Test | What happens | Reading |
|---|---|---|
| `tests/service/test_service.py::test_a_persons_commands_act_on_the_session` | Failed on every run (4 of 4). The test sends a mouse press, then Stop straight after, and expects the press to reach the page. Stop is built to jump the queue, so the press is dropped | Either the test is timing-dependent, or a person's last input before Stop should be delivered. This needs a decision |
| `tests/viewer/test_walkthrough.py::test_the_step_drawer_shows_the_evidence` | Failed on 5 of 7 runs. It checks that the step's picture has loaded without waiting for the load | A timing fault in the test |

---

## 2. Where the code stands against the spec

The code is milestone 1, slices 0 to 4, plus the pause, take-over and stop part of slice 6.
Slices 5, 7, 8 and 9 are not built. (Read from code.)

| Area | Built | Partly | Differs | Not built | Rows checked | Full table |
|---|---|---|---|---|---|---|
| Stack, layout, architecture, engine (spec §3 to §5) | 172 | 28 | 10 | 157 | 367 | `review/01-architecture-engine.md` |
| Principles, tools, code tool, safety, connecting agents (§2, §6 to §8, §16) | 53 | 17 | 3 | 93 | 167 | `review/02-tools-safety-agents.md` |
| Viewer: UI, UX, design system (§9, §4.8 client side, §15.19) | 193 | 57 | 8 | 26 | 284 | `review/03-viewer.md` |
| Configuration, performance budget, verification, testing, running (§10 to §13, §17) | 32 | 29 | 1 | 54 | 116 | `review/04-config-performance-tests.md` |
| Feature list rows with a milestone 1 part (§15) | 63 | 31 | – | 67 | 161 | `review/05-delivery-features-status.md` |

The areas overlap (a feature can appear in §5, §6 and §15), so the rows must not be added up.

### The numbers that matter most

| Fact | Figure | Kind |
|---|---|---|
| Tools the spec puts in milestone 1 | 28 | Read from spec §6.2 |
| Tools that exist | 4: `browser_navigate`, `browser_snapshot`, `browser_click`, `browser_type` | Read from code |
| Driver operations built | 15 of 47, with 3 more partly built | Read from code |
| Settings in `config.py` | 135, every default equal to the spec | Read from code |
| Settings that no code reads yet | 59 of 135 | Read from code |
| Settings in the spec with no code (`code`, `bridge`, `permissions`) | 17, all for milestones 2 and 4 | Read from code |
| Settings a live session's settings screen offers | 2 of 23 (colour mode, show where the agent is acting) | Read from code |
| Event types the service sends | 8 of the protocol's 16 | Read from code |
| Tests collected | 696 Python (495 unit, 74 browser, 35 service, 92 viewer) and 347 viewer unit tests | Measured here |
| Browsers the tests launch | Chromium only. Chrome and Edge are passed through to Playwright and never launched in a test | Read from code |

---

## 3. Findings to act on first

### 3.1 Safety

| # | Finding | Why it matters |
|---|---|---|
| S1 | **Site rules are checked only on the address the agent types.** A link click, a form submit, a redirect, a pop-up, a frame, or a person in takeover reaches any address, including blocked sites, private addresses and the cloud-metadata address. Nothing intercepts requests | It is the one safety claim in spec §8.1 that is not true today. The spec marks it milestone 1 (SG-02, SG-24) |
| S2 | **Approvals do not exist.** `safety.action_policies` (including `deny`), `default_action_policy`, `ask_before` and the approval time limits are accepted and ignored. The viewer shows approval cards on recorded sessions only | A deployment that sets `deny` gets no protection and no warning |
| S3 | **59 settings do nothing**, several of them safety switches: `enforce_on_subresources`, `action_policies`, `uploads.allowed_dirs`, `settings.locked`, `sessions.max_concurrent`, `idle_session_s`. `config show` and `config doc` present them as working | False sense of protection. Until built, they should fail loudly or be marked "not yet in force" |
| S4 | **An agent on `bap-browser mcp` cannot be watched or controlled.** The stdio server runs a bare tool layer: no viewer, no pause, no takeover, no stop. `bap-browser serve` and MCP over HTTP are not built | The spec's promise that a person stays in charge holds only for the built-in `agent` command |
| S5 | **The agent is told to call tools that do not exist.** The MCP instructions name screenshots and `browser_request_human`; the snapshot's cut-off notice names `browser_find` | An agent that obeys gets "Unknown tool" |
| S6 | **Small leaks.** A password's length is in the result and the log; the page title is the log line of every snapshot; the query string of an address (the values of a GET form) reaches viewer events and the log | Against spec §8.3 |

### 3.2 The page model

| # | Finding |
|---|---|
| P1 | One tab only. A link that opens a new window leaves the agent on the old page with no notice |
| P2 | Frames are not read. The snapshot lists the `iframe` line and stops, so sign-in and payment forms inside frames are invisible |
| P3 | Dialogs are not handled. No listener is registered, so an alert or confirm is most likely dismissed silently (not confirmed by a run) |
| P4 | Persistent profile and attach are settings that do nothing (`browser.user_data_dir`, `browser.cdp_url`) |
| P5 | The driver is not ready for the milestone 2 bridge: one tool call makes 3 or 4 driver calls where spec §4.9 allows two |

### 3.3 The viewer

| # | Finding |
|---|---|
| V1 | **An event type the viewer does not know blanks its state.** `connection/socket.ts` forwards any event and `state/reducer.ts` has no fallback. The first milestone 2 event (`bridge_changed`) would do it. Confirmed by reading the two files, not by a run |
| V2 | The settings screen has no service behind it. Twenty settings exist only in the viewer's recorded stand-in; "Clear data" says it worked and does nothing |
| V3 | No way to turn off the single-letter keys P, T, A and F (WCAG 2.1.4, level A) |
| V4 | Takeover input is incomplete: Tab never reaches the page, the picture does not get the focus on takeover, and a drag on a phone scrolls the viewer |
| V5 | The seven states the status page lists as not built are all confirmed: session picker, "saving", "working", "handing back", "failed", address "loading", "limit reached" |
| V6 | The viewer keeps its own copies of `viewer.stale_after_s`, `idle_divider_s` and the release chord; the service does not send them |

### 3.4 Not started

Performance budget file and `bench` command, the verify skill, the settings service, the micro VM
image (`deploy/`), `serve`, `doctor`, and milestones 2, 3 and 4.

---

## 4. Is the status page right?

About the code: yes. Every claim that could be checked from the repository was confirmed, and all
23 commit hashes it cites exist. Its faults are in its own header and layout.

| Line | Problem | Fact |
|---|---|---|
| 3 | "Branch `prototype/base`" | Only `main` exists in this repository |
| 3 | "nothing pushed" | `main` is level with `origin/main` on GitHub |
| 3 | "49 commits" | `git log` gives 51 |
| 33 | `REVIEW_THREE_ROW` | A leftover placeholder under the table |
| 221 to 223 | A blank line between decisions 27 and 28 | Rows 28 to 35 will not render as a table |
| 32 | "Of 12 minor findings, 5 fixed and 7 deferred" | The deferred table has 8 rows |
| 60 to 62 | Exit codes | 130 on Ctrl+C is in the spec and the code, missing here |
| Open point 1 | "First run with a real key" | Done on 2026-10-05: it works (section 1) |

Other mismatches between documents:

| # | Mismatch |
|---|---|
| 1 | `CLAUDE.md` says form values never reach a result; the spec and the code show them to the model in a snapshot (never passwords). Still unresolved |
| 2 | `CLAUDE.md` and the spec say no tunable number lives outside `config.py`. About ten do, for example the 64 KiB viewer message limit and the viewer's reconnect delays |
| 3 | Spec §8.1 says cloud metadata is "always blocked"; spec §10.3 and the code make it a switch |
| 4 | Spec §4.4 and §16.4 say `bap-browser mcp` serves the viewer; it starts no service |
| 5 | Spec §16.3 names `start_service(config)`; it does not exist |
| 6 | The Claude Code recipe is written three different ways in the spec, the README and the status page |
| 7 | The spec's layout (§3.2) and the repository differ in about 35 files in each direction |
| 8 | `CLAUDE.md` gotchas describe a Windows checkout; this one is on macOS |

---

## 5. What is left, in order

The order follows the spec's slices, with the status page's "Next" list and its deferred findings
placed where they belong. Where the two documents disagree, the note says so.

| Order | Work | Source |
|---|---|---|
| 0 | Fix the two timing-dependent tests; add a fallback for unknown events in the viewer (V1); repair the status page (section 4) | This review |
| 1 | **The remaining 24 tools**, with what they need: tabs and pop-ups, frames in the snapshot, dialogs, downloads and uploads, console and network logs, screenshots, the `[events]` block; Chrome and Edge launched for real; attach, persistent profile, `doctor`, idle close | Spec slice 5; status "Next" 2 |
| 2 | **Approvals and `browser_request_human`**, with the two missing control states and the viewer's cards acting on the real session | Spec slice 6; status "Next" 3 |
| 3 | **Site rules at the network layer** (S1) | Status "Next" 5. The spec marks it milestone 1 but names no slice. It closes a safety gap, so it should not wait for settings |
| 4 | `bap-browser serve` with MCP over HTTP, so an outside agent can be watched (S4); creating and ending sessions | Spec slice 6. The status page puts it after settings |
| 5 | Settings: catalogue, saved settings, locks, the settings API, the screen wired to it; wire or remove the dead settings (S3) | Spec slice 7; status "Next" 4 |
| 6 | Micro VM image and its configuration | Spec slice 8; status "Next" 6 |
| 7 | Bench, `perf/budget.json`, the verify skill, clean-up after a crash | Spec slice 9; status "Next" 6 |
| 8 | Finish the viewer states (V5), the key switch (V3), takeover input (V4) | Spec slice 1; status open points 3 and 4 |
| 9 | Milestone 1 acceptance list, including three browsers | Spec §14.1 |
| 10 | Milestone 2 (take-over Chrome), milestone 3 (bundled Chromium), milestone 4 (the code tool) | Spec §14.2 to §14.4 |
| 11 | The spec's "next" list: Codex and Hermes recipes, sign-in without the model seeing credentials, detection of human checks, notifications, recording and replay, real-profile copy, speed work, the remaining tools, cloud depth, the reference task set | Spec §14.5. Not in the status page |

The complete list, with the status page's deferred findings (M1 to M21, N1 to N11) placed in it,
is section E of `review/05-delivery-features-status.md`.

---

## 6. The review files

| File | Covers | Lines |
|---|---|---|
| `review/01-architecture-engine.md` | Spec §3, §4, §5 against the driver and the service | 568 |
| `review/02-tools-safety-agents.md` | Spec §2, §6, §7, §8, §16: every tool, every safety rule | 338 |
| `review/03-viewer.md` | Spec §9, §4.8, §15.19: every state, component, token, key, setting | 582 |
| `review/04-config-performance-tests.md` | Spec §10 to §13, §17: every setting key, the budget, the checklist | 371 |
| `review/05-delivery-features-status.md` | Spec §1, §14, §15 and every checkable claim in the status page | 705 |

Each review was done by reading; none of them ran the code. What was run is in section 1.
