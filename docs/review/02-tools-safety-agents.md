# bap-browser: spec vs code audit (§2, §6, §7, §8, §16)

Read-only audit; nothing was modified and `.env` was not read. I read the code and the tests but did not run the test suite (it writes logs and caches), so "test" in the evidence means "a test exists that asserts this", not "I saw it pass".

Path shorthand: `SRC/` = `/Users/sharan/Downloads/Prj-Browser/src/bap_browser/`, `T/` = `/Users/sharan/Downloads/Prj-Browser/tests/`. Spec = `/Users/sharan/Downloads/Prj-Browser/docs/bap-browser-spec.md`.

**Headline:** the spec assigns **28 tools to milestone 1** (25 always present + 3 configuration-dependent). The code has **4**: `browser_navigate`, `browser_snapshot`, `browser_click`, `browser_type` (`SRC/tools/browser_tools.py:109-137`; pinned by `T/unit/test_registry.py:10` and `T/service/test_mcp.py:15`). 24 are missing. With milestone 4, next and later tools the spec names 42 tools; 4 exist.

---

## 1. Complete tool table

### Milestone 1 (spec §6.2, lines 677-753)

| # | Tool | Spec parameters (default) | Verdict | Evidence | Missing / different |
|---|---|---|---|---|---|
| 1 | `browser_navigate` | `url` | BUILT | `SRC/tools/browser_tools.py:19-20, 58-76, 110-115`; `SRC/policy/address.py:43-44`; `T/unit/test_toolkit.py:21-34` | Result is "Navigated to <final address>" plus the snapshot; `https://` is added. The snapshot can be switched off with `browser.snapshot.after_navigation`. The address reported is where the browser ended up, and a redirect target is not policy-checked (see §8.1). |
| 2 | `browser_go_back` | none | NOT BUILT | no handler; no driver method (`SRC/driver/base.py:55-96`) | M1 slice 5 |
| 3 | `browser_go_forward` | none | NOT BUILT | same | M1 slice 5 |
| 4 | `browser_reload` | none | NOT BUILT | same | M1 slice 5 |
| 5 | `browser_snapshot` | `mode` (`interactive`), `ref`, `max_chars` (20,000), `include_bboxes` (false) | BUILT | `SRC/tools/browser_tools.py:23-27, 46-55, 79-80, 116-123`; `SRC/driver/snapshot_page.js:247-309`; `T/e2e/test_snapshot.py` | All four parameters present. `max_chars` can lower the cap, never raise it. Caveats: content inside iframes is not read (only the `iframe` line is listed, `snapshot_page.js:289-290`); the JSON schema shows no default for `mode` or `max_chars` (defaults are stripped, `SRC/tools/registry.py:42-46`). |
| 6 | `browser_get_text` | `ref`, `max_chars` (20,000) | NOT BUILT | none; `browser.text.max_chars` exists in config only (`SRC/config.py:121-122`) | M1 slice 5 |
| 7 | `browser_find` | `query`, `limit` (10, max 50) | NOT BUILT | config keys only (`SRC/config.py:125-127`) | M1 slice 5. The snapshot's truncation notice already tells the model to "use `browser_find`" (`SRC/driver/snapshot.py:9`). |
| 8 | `browser_screenshot` | `full_page` (false), `annotate` (false) | NOT BUILT | config keys only (`SRC/config.py:113-118`); MCP returns text content only (`SRC/mcp/server.py:40`) | M1 slice 5 |
| 9 | `browser_zoom` | `region [x0,y0,x1,y1]` | NOT BUILT | none | M1 slice 5 |
| 10 | `browser_click` | `ref`, or `x` and `y`; `button` (`left`); `click_count` (1, up to 3); `modifiers` | PARTIAL | `SRC/tools/browser_tools.py:30-35, 83-93, 124-129`; `SRC/driver/playwright_driver.py:236-273`; `T/unit/test_toolkit.py:68`, `T/e2e/test_actions.py:90-178` | `ref` is required; there is no `x`/`y` form. `button`, `click_count` (1-3) and `modifiers` (Alt, Control, Meta, Shift) are built. Result wording matches: `Clicked e7 (button "Create account")`, then `Navigated to …` on a second line. |
| 11 | `browser_hover` | `ref`, or `x` and `y` | NOT BUILT | none (a person's pointer move exists for takeover only, `playwright_driver.py:357`) | M1 slice 5 |
| 12 | `browser_drag` | `from_ref`/`from_xy`; `to_ref`/`to_xy` | NOT BUILT | `browser.input.drag_steps` in config only | M1 slice 5 |
| 13 | `browser_type` | `text`; `ref`; `clear` (true); `submit` (false); `slowly` (false) | BUILT | `SRC/tools/browser_tools.py:38-43, 96-106, 130-136`; `playwright_driver.py:275-307`; `T/e2e/test_actions.py:26-90, 210-230` | All five parameters. Result: `Typed 17 characters into e3 (textbox "Email")`; with no ref, "into the focused element (…)". Known open faults in `docs/status.md`: M1 (does not wait for an enabled or uncovered field), M10 (a line break typed with `slowly` presses Enter). |
| 14 | `browser_fill_form` | `fields`: list of `{ref, value}` | NOT BUILT | none | M1 slice 5 |
| 15 | `browser_select_option` | `ref`, `values` | NOT BUILT | none | M1 slice 5. A `<select>` cannot be set by any existing tool except by clicking. |
| 16 | `browser_set_checked` | `ref`, `checked` | NOT BUILT | none (a checkbox can be toggled with `browser_click`) | M1 slice 5 |
| 17 | `browser_press_key` | `keys`; `repeat` (1, up to 100); `ref` | NOT BUILT | `browser.input.key_repeat_max` in config only; Enter is reachable only through `browser_type submit` | M1 slice 5 |
| 18 | `browser_scroll` | `direction`; `amount` (1, up to 20); `ref`, or `x`,`y` | NOT BUILT | `browser.input.scroll_step_px` in config only | M1 slice 5 |
| 19 | `browser_scroll_to` | `ref` | NOT BUILT | none (click scrolls its target into view by itself, `snapshot_page.js:408-410`) | M1 slice 5 |
| 20 | `browser_wait` | one of `text`, `text_gone`, `load_state`, `seconds`; `timeout_s` | NOT BUILT | `browser.timeouts.wait_max_s` in config only | M1 slice 5 |
| 21 | `browser_handle_dialog` | `action`; `prompt_text` | NOT BUILT | `browser.dialogs.*` in config only; the driver registers no dialog handler (`playwright_driver.py:154-156`) | M1 slice 5. Unverified: what a page `alert()` does to a call today. With no handler Playwright dismisses dialogs by itself, so the `agent` dialog policy is not in force. |
| 22 | `browser_tabs` | `action` (`list`/`new`/`switch`/`close`); `tab_id`; `url` | NOT BUILT | one fixed tab `t1` (`playwright_driver.py:33, 177-183`) | M1 slice 5. Pop-ups and `target=_blank` pages are not adopted; `browser.tabs.*` unused. |
| 23 | `browser_console` | `level`; `clear` (false); `limit` (50) | NOT BUILT | `browser.capture.*` in config only | M1 slice 5 |
| 24 | `browser_network` | `filter`; `failed_only`; `clear`; `limit` (50) | NOT BUILT | same | M1 slice 5 |
| 25 | ◐ `browser_evaluate` | `expression` | NOT BUILT | `browser.javascript.allow_evaluate` in config only | M1 slice 5 (needs approvals, slice 6) |
| 26 | ◐ `browser_upload_file` | `ref`, `paths` | NOT BUILT | `browser.uploads.*` in config only | M1 slice 5 (needs approvals, slice 6) |
| 27 | ◐ `browser_downloads` | none | NOT BUILT | `browser.downloads.*` in config only | M1 slice 5 |
| 28 | `browser_request_human` | `reason` (≤300 chars); `kind`; `timeout_s` | NOT BUILT | named in the MCP instructions (`SRC/mcp/server.py:24`) but no such tool; `control.handoff_timeout_s` in config only | M1 slice 6; M1 acceptance item 3 depends on it |

### Milestone 4 (§6.3)

| # | Tool | Spec parameters | Verdict | Evidence | Notes |
|---|---|---|---|---|---|
| 29 | ◐ `browser_run` | `code`; `timeout_s` (60, up to 300) | NOT BUILT | no code, no `code.*` config section (`SRC/config.py:369-384`) | M4, as the spec plans |

### Next (§6.4) and later (§6.5)

| # | Tool | Verdict | Assigned to |
|---|---|---|---|
| 30 | `browser_sign_in` | NOT BUILT | Next (§14.5 item 2) |
| 31 | `browser_pdf` | NOT BUILT | Next (item 8) |
| 32 | `browser_storage` | NOT BUILT | Next (item 8) |
| 33 | `browser_emulate` | NOT BUILT | Next (item 8) |
| 34 | `browser_mouse` | NOT BUILT | Next (item 8) |
| 35 | `browser_record` | NOT BUILT | Next (item 8) |
| 36 | `browser_network_request` | NOT BUILT | Next (item 8) |
| 37 | `browser_extract` | NOT BUILT | Next (item 8) |
| 38 | optional `tab_id` on every tool | NOT BUILT | Next (item 7) |
| 39 | snapshot options "only what changed" / "only what is visible" | NOT BUILT | Next (item 7) |
| 40 | `browser_cdp` | NOT BUILT | Later |
| 41 | `browser_webmcp` | NOT BUILT | Later |
| 42 | `browser_act` | NOT BUILT | Later |
| 43 | `browser_vision` | NOT BUILT | Later |
| 44 | `browser_clipboard` | NOT BUILT | Later |

§6.6 "Not building" (CAPTCHA solving, hiding automation): complied with; no such code exists.

---

## 2. Tables per spec section

### §2 Principles

| Ref | Requirement | Verdict | Evidence | Missing / different |
|---|---|---|---|---|
| 2.1-1 | Main input is the accessibility tree with element IDs | BUILT | `SRC/driver/snapshot_page.js:223-309`; `T/e2e/test_snapshot.py:54-90` | Own page script, not the browser's accessibility tree; a test compares roles and names with Playwright's. |
| 2.1-2 | Screenshots for checking results; returned only when asked | PARTIAL | `SRC/mcp/server.py:40` | No tool ever returns an image (so "only when asked" holds), but there is no screenshot tool at all. M1 slice 5. |
| 2.1-3 | No tool returns raw HTML | BUILT | all four handlers return snapshot text or a sentence | |
| 2.1-4 | Never full page plus screenshot each turn; every observation capped; default is the interactive tree | BUILT | `SRC/tools/browser_tools.py:50-53`; `snapshot_page.js:252-260`; `SRC/driver/session.py:29-33`; `T/unit/test_toolkit.py:54, 357` | |
| 2.2-5 | Simple tools by element ID: click, type, select, press | PARTIAL | tool table | click and type only; select and press missing |
| 2.2-6 | Code tool for multi-step work, built after the three backends | NOT BUILT | | M4, as planned |
| 2.3-7 | Viewer always shows who is driving, in words | PARTIAL | `SRC/service/session.py:287-293` (`control_changed`); `viewer/src/wording.ts:13, 28, 107` | True under `bap-browser agent`. Under `bap-browser mcp` there is no viewer at all (`SRC/mcp/server.py:51-56`). Viewer rendering itself was not audited. |
| 2.3-8 | Stop, pause, take over always one action away | PARTIAL | `SRC/service/session.py:105-119`; `SRC/service/app.py:130-133`; `T/unit/test_stop_is_final.py` | Same limit: only in the `agent` command path. |
| 2.3-9 | Risky tools wait for approval; no answer means no | NOT BUILT | `safety.action_policies`, `control.approval_*` are read by nothing | M1 slice 6 |
| 2.3-10 | Human checks go to a person; never solved; browser never disguised | PARTIAL | no solver or stealth code anywhere in `SRC/` | `browser_request_human` missing; a person can only take over by hand. |
| 2.4-11 | Safe by default | PARTIAL | `SRC/config.py:220-232` | File addresses off and metadata blocked by default; but no network-layer check and no approvals. |
| 2.4-12 | Every tunable in configuration; no tunable number in code | PARTIAL | `SRC/config.py` | Numbers outside config: `--pace` default 1.0 (`SRC/cli.py:78`), `SETTLE_FRAMES = 2` (`playwright_driver.py:35`), `ROW_CHARS = 59`, `SHORTEST_NAME = 12` (`SRC/tools/sentences.py:19-22`), `LONGEST_REFUSAL = 300` (`SRC/agent/openai_model.py:22`), `LONGEST_KEY_NAME = 32` (`SRC/service/session.py:33`), 64 KiB viewer message (`SRC/service/server.py:20`), 8 password dots (`snapshot_page.js:207`). Addresses in results are capped by reusing `snapshot.max_text_chars` (`SRC/driver/session.py:32`). |
| 2.4-13 | Every "done" backed by a measured check | PARTIAL | `docs/status.md:21-32` | Test proofs are recorded; the bench, `perf/budget.json` and the verify skill (slice 9) do not exist. |
| 2.4-14 | The minimum; features wait for their phase | UNVERIFIED | | Judgement call. Note: config already carries about 60 keys for unbuilt features (slice 2 asks for this). |
| 2.4-15 | One contract; thin backend adapters | PARTIAL | `SRC/driver/base.py:55-96` | The seam exists; only one backend (`backend.kind` accepts only `remote_headless`, `SRC/config.py:59`). |
| 2.4-16 | Person's own browser protected on their machine | NOT BUILT | | M2 |

### §6.1 Conventions and counts

| Ref | Requirement | Verdict | Evidence | Missing / different |
|---|---|---|---|---|
| 6.1 | Names start with `browser_` | BUILT | `browser_tools.py:109-137` | |
| 6.1 | Ref is `e12` or, in a frame, `f2e7` | PARTIAL | `SRC/tools/registry.py:13` | The pattern accepts `f2e7`, but no frame ref is ever produced; frames are not read. `browser.snapshot.include_iframes` and `max_frame_depth` are unused. |
| 6.1 | Coordinates in the pixels of the last screenshot | NOT BUILT | | No tool takes coordinates. |
| 6.1 | State block `[tabs] t1* https://… \| t2 …` | BUILT | `SRC/tools/toolkit.py:148-152`; `T/unit/test_toolkit.py:26` | Always one tab. |
| 6.1 | State block `[events] …` (tab opened/closed, dialog, download, navigation blocked) | NOT BUILT | `toolkit.py:148-152` | Nothing collects such events for the agent. |
| 6.1 | Short plain text; nothing empty | BUILT | `toolkit.py:150-151` | |
| 6.1 | Unknown arguments rejected | BUILT | `registry.py:17-20, 53-54`; `T/unit/test_registry.py:19` | |
| 6.1 | ◐ tools exist only when enabled | NOT BUILT | `TOOLS` is a fixed tuple | No mechanism to offer a tool by configuration. |
| 6.1 | Every tool on every backend | NOT BUILT | | One backend. M2/M3. |
| 6.2 | 28 tools: 25 always + 3 conditional | DIFFERS | `T/unit/test_registry.py:10` | 4 tools. |
| 6.3 | 29 tools with `browser_run`, on by default | NOT BUILT | | M4 |
| 6.6 | No CAPTCHA solver, no hiding automation | BUILT | absence | |

### §7 Code tool (all milestone 4)

| Ref | Requirement | Verdict | Missing / different |
|---|---|---|---|
| 7.1 | `browser_run` runs a short Python script | NOT BUILT | nothing exists |
| 7.2 | Script sees `browser`, `state`, `print`, `re`/`json`/`math`, listed built-ins | NOT BUILT | |
| 7.2 | `find="…"` on click and type; `StepError` | NOT BUILT | `StepError` not in `SRC/errors.py` |
| 7.3 | Result: output, last value as JSON, step list, failure note, state block | NOT BUILT | |
| 7.4 | Worker process, restarted on time-out | NOT BUILT | |
| 7.4 | Parsed and checked before running | NOT BUILT | |
| 7.4 | Every `browser.` call goes through policy, approvals, control state | NOT BUILT | The seam it needs exists: every call already passes `Toolkit.call` and its gate (`toolkit.py:57-89`). |
| 7.4 | Bounded by `code.timeout_s`, `code.max_steps`, `code.max_output_chars` | NOT BUILT | No `code` section in `SRC/config.py`. |
| 7.4 | Worker gets no secrets or token | NOT BUILT | |
| 7 end | Mode handing the script the real Playwright page | NOT BUILT | Next item, as planned |

### §8 Safety

| Ref | Requirement | Verdict | Evidence | Missing / different |
|---|---|---|---|---|
| 8.1 | Checked for every navigation the agent asks for | BUILT | `browser_tools.py:58-72`; `T/unit/test_toolkit.py:37` | Blocked before the browser starts. |
| 8.1 | Enforced again at the network layer (redirects, link clicks, pop-ups, frames) | NOT BUILT | no `page.route` or request interception anywhere in `SRC/driver/` | M1 (status "Next" item 5). A click on a link, a form submit, a redirect, a frame or a person in takeover reaches any address, including blocked sites, private addresses and cloud metadata. |
| 8.1 | Rewrite as a browser reads it: `\`→`/`, percent-decoded host, `xn--`, every IP spelling | BUILT | `SRC/policy/address.py:33-57, 77-110, 149-170`; `T/unit/test_url_policy.py:208-261`; `T/e2e/test_address_policy.py:41-64` | Unverified: that Python's IDNA rules match Chrome for every international name; the code refuses four known-divergent characters (`address.py:30`). |
| 8.1 | The one form is what is judged and what the browser gets | BUILT | `url_policy.py:81-89`; `browser_tools.py:60-61, 73`; `T/e2e/test_address_policy.py:67` | |
| 8.1 | Unopenable address refused as "not a valid address" | BUILT | `address.py:16, 36-37`; `url_policy.py:86-88` | |
| 8.1 | Order: files, scheme, metadata, block list, allow list, private, resolution | BUILT | `url_policy.py:91-145` | Matches. |
| 8.1 | Default schemes `http`, `https`, `about`, `data`, `blob` | BUILT | `SRC/config.py:219` | |
| 8.1 | Domain lists: empty allow = all; `example.com` = host + subdomains; `*.` = subdomains only; block wins | BUILT | `url_policy.py:49-53, 118-121`; `T/unit/test_url_policy.py:239` | |
| 8.1 | An entry with scheme, port or path stops start-up | BUILT | `SRC/config.py:234-243`; `address.py:179-190`; `T/unit/test_config.py:287` | |
| 8.1 | Cloud metadata "always blocked" | DIFFERS | `SRC/config.py:222`; `url_policy.py:115` | It is a setting (`safety.block_cloud_metadata`, default on) and can be switched off. Spec §10.3 line 1563 lists the same key, so the spec contradicts itself. Status M11: two providers' addresses are missing from the list. |
| 8.1 | Private networks allowed locally; `block_private_networks` for cloud | BUILT | `url_policy.py:122-145`; `T/unit/test_url_policy.py:127-152` | |
| 8.1 | Sub-resources checked only with `enforce_on_subresources` | NOT BUILT | key exists (`config.py:223`), nothing reads it | Turning it on does nothing. |
| 8.1 | Only document requests intercepted; decisions cached per host | PARTIAL | cache: `url_policy.py:103-110`; `T/unit/test_url_policy.py:163` | The cache is built; there is no interception to limit. |
| 8.2 | Each tool is `allow`, `confirm` or `deny` | NOT BUILT | `safety.action_policies` and `default_action_policy` are read by nothing | M1 slice 6. A `deny` in config is silently ignored, and tool names in it are not validated. |
| 8.2 | Defaults: `confirm` for upload and evaluate | NOT BUILT | default value present in `config.py:226-228` only | Those tools do not exist. |
| 8.2 | Approval card: Allow once / Allow on this site / Deny; no answer = deny | NOT BUILT | `SRC/service/session.py:105-119` handles no approval command | The viewer has card UI for recorded sessions only (not audited). |
| 8.2 | "Ask before: Every action" makes acting tools `confirm` | NOT BUILT | `safety.ask_before` unused | M1 slice 6/7 |
| 8.2 | A person can never ask for less than the deployment requires | NOT BUILT | no settings API; `settings.locked` unused | M1 slice 7 |
| 8.3 | Model never sees text that is not rendered | BUILT | `snapshot_page.js:56-62, 106-127`; `T/e2e/test_snapshot.py:90` | Covers the spec's own list. Not covered, and not required by the spec: zero opacity, off-screen or same-colour text; `aria-label`, `title` and `alt` text are shown as names. |
| 8.3 | Password values never in snapshots, results, events, logs | BUILT | `snapshot_page.js:205-207`; `sentences.py:93-95`; `SRC/tools/event_log.py:22-23`; `T/e2e/test_snapshot.py:126` | The value never appears. Its length does: in the result (`browser_tools.py:101`) and the log, and in the viewer when typed with no `ref` (status N1). `SRC/driver/base.py:45` says not even the length is told to anyone. |
| 8.3 | Name and password in an address never in results, events, logs | BUILT | `address.py:63-74`; `SRC/driver/session.py:29-33`; `event_log.py:24-25`; `T/unit/test_what_reaches_a_watcher.py:57-99` | Unverified: the snapshot's own `URL:` line comes from `location.href` (`snapshot_page.js:301`) and relies on the browser dropping credentials. |
| 8.3 | Nothing typed, no snapshot or screenshot, while a person is in control | BUILT | `SRC/service/session.py:121-158, 230-255`; `T/unit/test_service_session.py` | Calls are held; a person's input is not logged or published. |
| 8.3 | Model never sees the service token or viewer address | BUILT | `SRC/agent/command.py:23-25, 47`; `SRC/service/server.py:93-99` | They go to stderr and a 0600 state file, never into a result. Unverified edge: with `allow_file_urls` on, the agent could open the state file. |
| 8.3 | `safety.redact_patterns` replaced by `[REDACTED]` in every result | BUILT | `SRC/policy/redaction.py`; `toolkit.py:64, 73, 81-87`; `T/unit/test_toolkit.py:139, 293` | Also applied to log arguments and viewer sentences. |
| 8.3 | A non-password field value is shown to the model in a snapshot | BUILT | `snapshot_page.js:190-221` | |
| 8.3 | Typed text and field values never reach the event log or viewer events | PARTIAL | `event_log.py:54-55`; `T/unit/test_toolkit.py:323-334` | Typed text is kept out. Leaks that remain: the log line for `browser_snapshot` is the page title (`"Page: Fake"` in the test); an address query string, which holds the values of a GET form, reaches `step_finished`/`tab_changed` events and the log (`session.py:203-213`; `T/service/test_mcp.py:82` shows `?name=Ada%20Lovelace`); password length as above. |
| 8.3 | A field with no label is never named after its content | BUILT | `snapshot_page.js:344-350`; `T/e2e/test_toolkit_in_process.py:47` | |
| 8.4 | Human checks: agent calls `browser_request_human`, person answers "Done" | NOT BUILT | | M1 slice 6 |
| 8.4 | Never solves a check, alters the fingerprint or hides automation | BUILT | absence; `playwright_driver.py:38-89` | A deployment can still set `browser.user_agent`, `args` and `ignore_default_args` in config. |
| 8.4 | Automatic detection of checks | NOT BUILT | | Next item 3, as planned |
| 8.5 | MCP instructions say page content is untrusted data | BUILT | `SRC/mcp/server.py:21-26`; `T/service/test_mcp.py:29` | |
| 8.5 | Tool descriptions say the same | NOT BUILT | `browser_tools.py:110-136` | None of the four descriptions mentions it. The reference loop's own prompt does (`SRC/agent/loop.py:20-21`). |
| 8.5 | Marked boundaries, classifier | NOT BUILT | | Later, as planned |
| 8.6 | M1: consequential actions confirmed by the agent's own harness | NOT BUILT | `SRC/agent/loop.py` | By design outside the core. The shipped reference loop confirms nothing. |
| 8.6 | M1: a person can choose to approve every action | NOT BUILT | `safety.ask_before` unused | M1 |
| 8.6 | M2: core and bridge classify consequential actions | NOT BUILT | | M2 |
| 8.7 | Limit: address check and browser resolve names separately | BUILT (limit holds as stated) | `url_policy.py:7-8, 131-145` | |
| 8.7 | Limit: site rules are two lists | BUILT (as stated) | `config.py:217-218` | |
| 8.7 | A deployment can lock a setting | NOT BUILT | `config.py:350` unused | M1 slice 7 |
| 8.7 | Limit: no consequential classification until M2 | BUILT (as stated) | | |
| 8.8 | Agent's tab group only | NOT BUILT | | M2 |
| 8.8 | Site permission `ask`/`allow`/`block` with three answers | NOT BUILT | | M2 |
| 8.8 | Sites never offered; `permissions.blocked_sites` | NOT BUILT | no `permissions` config section | M2 |
| 8.8 | Action classes Read / Act / Consequential | NOT BUILT | | M2 |
| 8.8 | Modes `ask_before_acting`, `act_on_allowed_sites` | NOT BUILT | | M2 |
| 8.8 | Preview with Confirm/Cancel and `preview_timeout_s` | NOT BUILT | | M2 |
| 8.8 | What counts as consequential; `consequential_words` | NOT BUILT | | M2 |
| 8.8 | "Always allow" does not cover consequential | NOT BUILT | | M2 |
| 8.8 | `evaluate` refused on take-over Chrome | NOT BUILT | | M2 |
| 8.8 | Extension's own Stop button | NOT BUILT | | M2 |
| 8.8 | "Being debugged" banner left in place | NOT BUILT | | M2 |
| 8.8 | Refusal result wording ("Do not try another way…") | NOT BUILT | | M2 |
| 8.8 | Bundled Chromium: same permissions, shown by the desktop app | NOT BUILT | | M3 |
| 8.8 | From M2 the same classification on remote headless | NOT BUILT | | M2 |

### §16 Connecting agents

| Ref | Requirement | Verdict | Evidence | Missing / different |
|---|---|---|---|---|
| 16.1 | MCP instructions, exact text | BUILT | `SRC/mcp/server.py:21-26`; `T/service/test_mcp.py:29-35` | Word for word. It names `browser_request_human` and screenshots, which do not exist (see contradictions). |
| 16.1 | Extra sentence when `browser_run` is offered | NOT BUILT | instructions are one constant | M4 |
| 16.1 | Extra sentence on take-over Chrome | NOT BUILT | | M2 |
| 16.2 | Claude Code over stdio: `claude mcp add bap-browser -- bap-browser mcp` | BUILT | `SRC/cli.py:61-63, 128-136`; `T/service/test_mcp.py:52` | Tested with a scripted MCP client; never tried with real Claude Code (status open point 6). |
| 16.2 | Claude Code over HTTP at `/mcp` with a bearer token | NOT BUILT | no `serve` command (`cli.py:43-92`); no `/mcp` route (`SRC/service/app.py:100-107`); `mcp.http_path` unused | M1 slice 6 |
| 16.2 | Codex recipe | NOT BUILT | | First next-step item |
| 16.2 | Hermes recipe | NOT BUILT | | First next-step item |
| 16.3 | In-process use: `load_config`, `open_session`, `Toolkit`, `tools.call(...)`, `page.text` | BUILT | `SRC/__init__.py:3`; `SRC/driver/__init__.py:3`; `SRC/tools/__init__.py:5`; `T/e2e/test_toolkit_in_process.py:17` | A plain `Toolkit(session)` has no viewer and no pause/takeover gate. |
| 16.3 | `start_service(config)` or `bap-browser serve` for the viewer and settings API | DIFFERS | no `start_service` anywhere | The working equivalent is `ServiceSession` + `Service` (`SRC/agent/command.py:42-46`), undocumented. No settings API. |
| 16.4 | Python core: library in-process, viewer served by the same process | PARTIAL | as above | Viewer yes, through the undocumented classes; settings API no. |
| 16.4 | Any language, child process: `bap-browser mcp`, viewer served by that child | PARTIAL | `SRC/mcp/server.py:51-56` | The tools work; the child serves no viewer, prints no viewer address and writes no state file. Spec §4.4 says it does. |
| 16.4 | Separate process: `bap-browser serve`, MCP over HTTP, `server.public_url` | NOT BUILT | | M1 slice 6 |
| 16.4 | Product backend passes config and token in the environment; micro VM | PARTIAL | `SRC/config.py:20-21, 435-443`; `SRC/service/server.py:34` | `BAP_BROWSER_CONFIG`, `BAP_BROWSER__…` and `BAP_BROWSER_TOKEN` work. No `deploy/` image (slice 8). `public_url` is used for host and origin checks only; the printed viewer address still uses `server.host` (`server.py:42-49`). |
| 16.5 | `bap-browser agent "<task>"` and `agent --demo --open` | BUILT | `SRC/cli.py:65-92, 139-192`; `T/service/test_agent_command.py:59` | |
| 16.5 | One process, free port, viewer address on stderr, answer alone on stdout | BUILT | `SRC/agent/command.py:42-47, 70-71` | |
| 16.5 | Runs until done, step limit, or a person stops | BUILT | `SRC/agent/loop.py:45-61`; `T/unit/test_agent_loop.py:100-163` | From reading, not run: at the step limit without `--exit-when-done`, the terminal says "The session has ended" but the session is only closed after Ctrl+C (`command.py:75-82`), and that Ctrl+C then exits 1, not 130. |
| 16.5 | `--demo` | BUILT | `cli.py:148-152`; `SRC/agent/demo.py`; `T/e2e/test_agent_demo.py:37` | |
| 16.5 | `--open` | BUILT | `command.py:48-52` | |
| 16.5 | `--wait-for-viewer` | BUILT | `command.py:50-52` | |
| 16.5 | `--pace SECONDS`, default 1 | BUILT | `cli.py:75-80`; `SRC/agent/models.py:74-76` | Default lives in the CLI, not in config. |
| 16.5 | `--exit-when-done` | BUILT | `command.py:72-74` | |
| 16.5 | Hosted model: OpenAI `gpt-5.6-luna`, Responses API, key from `OPENAI_API_KEY` or `.env`, plain message with no key | BUILT | `SRC/config.py:324-338`; `SRC/agent/openai_model.py:36-54, 98-105`; `cli.py:30, 163-169`; `T/service/test_agent_command.py:94-131` | Unverified against the real service: `docs/status.md:12-15` says it was only run against a stand-in server. |
| 16.5 | `store` off; reasoning passed back encrypted | BUILT | `openai_model.py:52-53, 77, 91-92`; `T/unit/test_openai_model.py:39, 85` | |
| 16.5 | Exit codes 0 / 1 / 2 / 130 | BUILT | `cli.py:31-35, 187-192` | Edge, from reading: a browser that fails to start raises `BrowserError`, which is not caught, so the command ends with a traceback. |
| 16.5 | Loop steps 1-3 | BUILT | `loop.py:43-61` | |
| 16.5 | Model behind one interface; hosted and scripted | BUILT | `SRC/agent/models.py:50-77`; `openai_model.py` | `agent.provider: scripted` is refused outside `--demo` (`cli.py:159-162`). |
| 16.5 | Same definitions and tool layer; no way around policy, control states, log | BUILT | `command.py:57`; `SRC/service/session.py:50` | |
| 16.5 | Person sees every step with pause, take over, stop, approvals | PARTIAL | `session.py:194-227, 105-119` | Approvals not built. |
| 16.5 | Limits `agent.max_steps`, `agent.max_tokens`; a stopped session ends the loop | BUILT | `loop.py:46-58`; `openai_model.py:51` | |
| 16.5 | Final answer printed; event log holds the steps | BUILT | `command.py:71`; `T/service/test_agent_command.py:59` | |
| 16.5 | No memory, planning, sub-agents, retries | BUILT | `loop.py` | |

---

## 3. EXTRA: in code, not in the audited spec sections

Some of these may be specified in sections I was not asked to read (§4, §5, §9, §10); I checked only where noted.

**Tool layer**
- A "gate" that admits or holds each call, and a step observer (`SRC/tools/gate.py`, `observer.py`); person-readable step sentences (`sentences.py`, cites spec 9.7).
- `browser.snapshot.after_action` appends a snapshot to click and type results (`browser_tools.py:91-92, 104-105`; in spec §10.3).
- `browser_type` with `submit` also reports "Navigated to …".
- Unknown tool result lists the available tools (`toolkit.py:95-96`).
- Catch-all "failed unexpectedly" result (`toolkit.py:113-119`).
- "The browser closed. Open a page with browser_navigate to start it again." and restart on navigate (`SRC/driver/session.py:39-62`).
- Addresses in results cut at 300 characters.
- A call that could not run is logged by argument name and type only (`event_log.py:33-35`).
- Hand-back note put in front of the agent's next result (`SRC/service/session.py:268-286`; spec §4.5).

**Address policy beyond §8.1**
- IPv4 carried inside IPv6 (mapped, 6to4, Teredo, NAT64, IPv4-compatible) judged as the IPv4 address (`address.py:124-146`).
- Private name suffixes `.localhost`, `.local`, `.internal`, `.lan`, `.home.arpa`, and single-label names, blocked under `block_private_networks` (`url_policy.py:30, 127`).
- A name that cannot be resolved is blocked under `block_private_networks`.
- Metadata host names `metadata.google.internal`, `metadata.goog`.
- Control characters and IPv6 zone ids refused.
- `safety.block_cloud_metadata` off-switch; `safety.policy_cache_s`.

**CLI and agent**
- `config show [--sources]`, `config init [--full]`, `config doc`, `--version`, `--config` (in §14.1 slice 2).
- `.env` is read for every command, not only `agent` (`cli.py:30`).
- `agent.provider`, `agent.api_key_env`, `agent.base_url`, `agent.request_timeout_s`.
- The model's interim text is printed to stderr (`loop.py:52-53`).
- A model failure ends the session as "failed" with the reason shown to viewers (`command.py:65-68`).
- 401 message that never repeats the key (`openai_model.py:122-128`).
- The reference loop has its own system prompt naming only the four real tools (`loop.py:16-22`); it does not use the MCP instructions.
- Demo site shipped in the package and served at `/demo-site` (`app.py:105`).

**Dead settings.** At least 60 keys in `SRC/config.py` are accepted and documented by `config doc` but read by no code (found by a text search, so this is a lower bound). They include: `safety.enforce_on_subresources`, `safety.action_policies`, `safety.default_action_policy`, `safety.ask_before`; all of `control.*` except `hold_timeout_s`; `browser.uploads.*`, `browser.downloads.*`, `browser.capture.*`, `browser.tabs.*`, `browser.find.*`, `browser.screenshot.*`, `browser.javascript.allow_evaluate`, `browser.dialogs.timeout_s` and `default_prompt_text`; `browser.cdp_url`, `browser.user_data_dir`; `timeouts.wait_max_s`, `idle_session_s`, `popup_adopt_ms`; `snapshot.include_iframes`, `max_frame_depth`; `input.scroll_step_px`, `drag_steps`, `key_repeat_max`; `sessions.max_concurrent`; `mcp.http_path`; `settings.file`, `settings.locked`; `bench.*`; `data_dir`; `backend.offered`; several `viewer.*` keys.

### Contradictions inside the repo

1. **MCP instructions name tools that do not exist.** `SRC/mcp/server.py:23-24` tells every agent to "Take a screenshot" and to "call browser_request_human". Neither exists. An agent that obeys gets an error result: "Unknown tool 'browser_request_human'. Available: …". `T/service/test_mcp.py:29` pins the text, so it cannot be changed without changing the test and the spec. Status lists it as M8.
2. **`CLAUDE.md:24` vs spec §8.3 vs code.** `CLAUDE.md` says form values never reach a result. The spec and the code (`snapshot_page.js:205-207`) show non-password values to the model in a snapshot. The code follows the spec (status open point 2).
3. **`CLAUDE.md:22` and `config.py:4`** say no tunable number lives outside `config.py`; the constants under 2.4-12 do.
4. **`SRC/driver/base.py:45`** says not even a password's length is told to anyone; the tool result and the event log carry it.
5. **Frames.** `snapshot_page.js:289` says "a frame is read separately", the ref pattern accepts `f2e7`, and config has `include_iframes` (default true) and `max_frame_depth`. No code reads a frame. Spec §5.3-5.4 says frames appear in the snapshot.
6. **Spec §8.1 "Cloud metadata: always blocked"** vs spec §10.3 and `config.py:222`, where it is a switch.
7. **Spec §4.4 and §16.4** say `bap-browser mcp` serves the viewer and prints its address; `SRC/mcp/server.py:51-56` starts no service. `config.py:266` documents `server.port` as "`bap-browser mcp` uses a free port instead"; it opens no port.
8. **Spec §16.3** names `start_service(config)`; it does not exist.
9. **Spec §8.5** says tool descriptions state that page content is untrusted; none does.
10. **Snapshot truncation notice** (`SRC/driver/snapshot.py:9`) tells the model to use `browser_find` and to scroll; neither tool exists.
11. **`BadInput` hint** "Use browser_click for buttons, checkboxes and links" (`playwright_driver.py:432-433`) is fine today, but the spec's control-state wording differs from the code: spec §5.10 "A person is in control of this session. Call again to keep waiting." vs `SRC/service/session.py:27` "A person is in control of the browser, so nothing was done. Call again to keep waiting."
12. **`docs/status.md:33`** contains a leftover placeholder line, `REVIEW_THREE_ROW`.

---

## 4. The 10 most important gaps for future work

1. **The address policy is not enforced at the network layer (M1).** Only the address given to `browser_navigate` is checked. Link clicks, form submits, redirects, pop-ups, frames and a person in takeover bypass the block list, the private-network block and the cloud-metadata block. This is the one safety claim in §8.1 that is false today.
2. **24 of the 28 milestone 1 tools are missing (M1 slice 5).** No scrolling, key press, select, wait, tabs, dialogs, screenshot, text, find, back/forward/reload, hover, drag, console, network, files or evaluate. `browser_click` also lacks the `x`/`y` form.
3. **Approvals and the tool policy do not exist (M1 slice 6).** `safety.action_policies` (including `deny`), `default_action_policy`, `ask_before` and the approval time-outs are accepted and ignored. There is no "waiting for approval" state in the service.
4. **`browser_request_human` is missing while the instructions tell agents to call it (M1 slice 6, acceptance item 3).** Either build it or stop advertising it.
5. **An outside agent over `bap-browser mcp` cannot be watched or controlled.** The stdio server uses a bare toolkit: no viewer, no pause, no takeover, no stop. `bap-browser serve`, MCP over HTTP and `start_service` are absent (M1 slice 6). Human oversight exists only for the reference loop.
6. **Dead settings give a false sense of protection.** About 60 documented keys do nothing, several of them safety switches (`enforce_on_subresources`, `action_policies`, `uploads.allowed_dirs`, `settings.locked`, `sessions.max_concurrent`, `idle_session_s`). Until built, they should fail loudly or be marked "not yet in force" in `config doc`.
7. **The state block and page model are single-tab and frame-blind.** No `[events]` line, one fixed tab `t1`, pop-ups not adopted, dialogs not handled, iframe content not read. Sign-in and payment forms inside frames are invisible to the agent.
8. **Residual leaks against §8.3.** Password length in the result and log; the page title as the log line of every `browser_snapshot`; query strings (GET form values) in viewer events and the log. Tool descriptions also lack the "untrusted data" statement of §8.5.
9. **The rest of milestone 1 is unbuilt:** settings API and locks (slice 7), micro VM image and `public_url` handling (slice 8), bench, budget file and verify loop (slice 9). The hosted model has never been run against the real API, and the Claude Code recipe has never been tried with real Claude Code.
10. **Later milestones are untouched, as planned:** take-over Chrome permissions (§8.8, M2), bundled Chromium (M3), the code tool (§7, M4), Codex and Hermes recipes (next). Small fixes found on the way: the step-limit path leaves the session open and returns exit 1 on Ctrl+C; a browser start failure ends in a traceback.

---

## 5. Counts per verdict

| Table | BUILT | PARTIAL | DIFFERS | NOT BUILT | UNVERIFIED | Rows |
|---|---|---|---|---|---|---|
| Tools (M1 28, M4 1, next 8 + 2 options, later 5) | 3 | 1 | 0 | 40 | 0 | 44 |
| §2 Principles | 3 | 9 | 0 | 3 | 1 | 16 |
| §6 conventions and counts | 5 | 1 | 1 | 5 | 0 | 12 |
| §7 Code tool | 0 | 0 | 0 | 10 | 0 | 10 |
| §8 Safety | 22 | 2 | 1 | 29 | 0 | 54 |
| §16 Connecting agents | 20 | 4 | 1 | 6 | 0 | 31 |
| **Total** | **53** | **17** | **3** | **93** | **1** | **167** |

Milestone 1 tools alone: 3 BUILT, 1 PARTIAL, 24 NOT BUILT out of 28.

Of the 93 NOT BUILT rows, roughly: 24 tools plus about 20 requirements belong to milestone 1; 14 §8.8 rows plus a few others to milestone 2 or 3; 11 to milestone 4 (the code tool); 15 tools and options plus a few items to "next" or "later". Three §8 rows marked BUILT are "known limits" that simply hold as the spec states them.

### Not verified

- No test was run; pass/fail status comes from `docs/status.md` (696 passed on 2026-10-04), not from me.
- The viewer (`viewer/src`) was not audited beyond two text searches.
- Whether `location.href` in the snapshot's `URL:` line can ever carry credentials.
- What a page `alert()` or `confirm()` does to a tool call today.
- Parity of Python's international-name handling with Chrome beyond the tested cases.
- The step-limit and browser-start-failure exit paths are from reading the code, not from running it.
- The dead-settings list comes from a text search and is a lower bound.

### Key files

- `/Users/sharan/Downloads/Prj-Browser/docs/bap-browser-spec.md`
- `/Users/sharan/Downloads/Prj-Browser/docs/status.md`
- `/Users/sharan/Downloads/Prj-Browser/CLAUDE.md`
- `/Users/sharan/Downloads/Prj-Browser/src/bap_browser/tools/browser_tools.py`
- `/Users/sharan/Downloads/Prj-Browser/src/bap_browser/tools/toolkit.py`
- `/Users/sharan/Downloads/Prj-Browser/src/bap_browser/tools/event_log.py`
- `/Users/sharan/Downloads/Prj-Browser/src/bap_browser/policy/url_policy.py`
- `/Users/sharan/Downloads/Prj-Browser/src/bap_browser/policy/address.py`
- `/Users/sharan/Downloads/Prj-Browser/src/bap_browser/mcp/server.py`
- `/Users/sharan/Downloads/Prj-Browser/src/bap_browser/agent/command.py`
- `/Users/sharan/Downloads/Prj-Browser/src/bap_browser/agent/loop.py`
- `/Users/sharan/Downloads/Prj-Browser/src/bap_browser/cli.py`
- `/Users/sharan/Downloads/Prj-Browser/src/bap_browser/config.py`
- `/Users/sharan/Downloads/Prj-Browser/src/bap_browser/driver/playwright_driver.py`
- `/Users/sharan/Downloads/Prj-Browser/src/bap_browser/driver/snapshot_page.js`
- `/Users/sharan/Downloads/Prj-Browser/src/bap_browser/service/session.py`
