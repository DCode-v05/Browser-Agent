# Auto Mode and safeguards: plan and state

Started 2026-10-07. Branch `feature/auto-mode-safeguards`, cut from `main` at `904d643`.
This file is the hand-over: **read it first after any break.** Tick a box when its tests pass and it
is committed.

## What was asked

1. Build Auto Mode and the safeguards of spec section 18 (`docs/bap-browser-spec.md`), on all three
   browsers.
2. First take in the review of that section (`docs/index.html`: 10 high, 18 medium, 10 low flags),
   change the spec, then build what the changed spec says.
3. Build fast. Ask when in doubt. Run `/verify` over the whole build at the end.

Decided with the user earlier (do not ask again): a check decides each step; fixed rules first, then
a model; the model is OpenAI's through the same plain HTTPS call, with a setting of its own; an
outside agent states its task at the start; known-bad lists are optional, local checks always on;
only what local rules flag goes to a model.

## How to work

- Spec first, then test first, then code. One slice at a time; the whole suite passes before a commit.
- Commands: `uv run pytest -q` (needs `npm --prefix viewer run build`), `uv run ruff format src tests`,
  `uv run ruff check .`, `uv run pyright`, `npm --prefix viewer run test|typecheck|lint|build`.
  Spec page: `uv run --no-project --with markdown python docs/spec_to_html.py`.
- Every tunable value in `src/bap_browser/config.py`. Every string a person reads in
  `viewer/src/wording.ts`. Typed text, page text and the task's words never reach a log.
- Never read `.env`. No new package without asking. Python with backslashes is written with the Write
  tool, never a heredoc.
- Commit messages: one imperative line, no AI attribution. Push the branch after each slice.
- On Windows before this work: `uv run pyright` fails on `code/worker.py` (Unix-only `resource`), and
  two tests in `tests/service/test_settings_api.py` error (a test id too long). Not caused here.

## What the review changes (already decided; the spec is to say all of this)

| Flag | What is done |
|---|---|
| H1 | One classifier of what a control does, with word stems, phrases and Hindi words: `pays`, `sends`, `deletes`, `grants`, `commits`. A finding `paying_step` that needs no cap. Sending without a named control is found too: Enter or Ctrl+Enter in a message box, `submit: true`, a submit button of a form that holds a message field. A click by x and y and a key press with no ref are first turned into the element they land on |
| H2 | A floor in code: a step of class pays, sends, deletes or grants, `cross_site_text`, and a reviewer category of pays, sends, deletes, grants_access or shares_data, is never rated under high. So it can only be asked or refused |
| H3 | The Public Suffix List is shipped as a data file (`policy/public_suffix_list.dat`) with its private section. `two_part_suffixes` is gone |
| H4 | A site an agent declares starts at `added, read`. A named site still passes every site check and is never exempt from the look-alike rule. The open tab keeps the grade it has |
| H5 | Every field of the reviewer's and the scan's input that a page or the agent wrote is inside random-token marks. The fixed rules run over the control's name and the typed text before the reviewer sees them. Passages past the cap are decided by the fixed rules. Rule 3 of 18.1 is reworded to what is true |
| H6 | Unseen text alone never flags a page. Text hidden the screen-reader way (a 1 px clipped box) is kept. An unseen passage reaches the model only when a strong rule hits it |
| H7 | `command_lure` is only the "verify you are human: press Win+R and paste" pattern. `asks_for_secrets` is weak and skips warnings ("never send your password"). The scan's model is told that install instructions for a person are harmless. False-alarm pages: install docs, a bank warning, a page full of screen-reader text |
| H8 | A question raised by a finding, and a reviewer's "ask", are refused when nobody is watching, whatever `control.approval_without_viewer` says. Only a tool's own `confirm` policy still follows that setting |
| H9 | `safety.auto_mode.offered` is `false` by default. The guards are built before the reviewer (order below) |
| H10 | Short secrets are remembered too: runs of 6 or more digits or mixed letters and digits, email addresses, phone numbers. In `risky` a long address to a site not yet visited is unsure as well. The attack page leaks a real-looking 10 to 12 character order number |
| M1 | Reviewer and scan: low reasoning effort, 1500 tokens, 8 s, one retry, a breaker of their own |
| M2 | Files that arrive are judged after the step: run, ask and refuse mean keep, ask and delete |
| M3, M4 | The site of the active tab is judged at every agent call (a set lookup, kept per task), not only when a page loads. So pages loaded by a redirect, a link, a pop-up, a person's own hands or before the task are judged before the agent reads or acts. The network hold stays for hard stops only. A click inside a frame is judged by the frame's site |
| M5 | Unseen-text tests use effective opacity (multiplied through parents), the text's own rendered boxes, `text-indent`, `filter: opacity`, transparent colours, `-webkit-text-fill-color`, zero `clip-path`. Covered text and text on a background picture are known limits |
| M6 | Invisible characters are taken out by Unicode category (Cf, Cc) plus a short list of fillers; the joiners stay only between letters or emoji that need them. Typed text and addresses going out are checked the same way |
| M7 | A name a page wrote, inside one of the engine's own lines, is in double quotes, cut to 80 characters, and passes the fixed rules first |
| M8 | A loop is the same acting call with no change of the page in between; reads in between do not reset it |
| M9 | A page stops being flagged when a whole read of it finds no planted instruction any more |
| M10 | Sensitive-field words match whole words; "PIN code" is a postal code; Aadhaar, PAN, UPI PIN, MPIN added; a field labelled password, or drawn as dots, counts whatever its type |
| M11 | Look-alikes are measured on the registrable name's first label; a brand used as a label needs a lure word (login, secure, verify, account, …) beside it; common-word collisions are exempt by a list; letters come from Unicode's confusables data |
| M12 | A download's name is checked after invisible characters are taken out; archives, HTML and SVG files are asked about on every backend |
| M13 | The log keeps the reviewer's category, never its sentence |
| M14 | A cap that is set and no amount on the page: ask. The formats of amounts are listed |
| M15 | The first-time notice says only what holds |
| M16 | Acceptance and tests corrected; more attack pages (send by Enter, "Post", short secrets, shared hosts, a button that talks to the reviewer, decoy passages, the open tab, install docs, screen-reader text); a pass mark for the real-model cases |
| M17 | A chat task ends with the agent's answer; an MCP task ends with the next one, the session, or its time. `browser_begin_task` is not offered in a chat session |
| M18 | The copy memory is a Bloom filter of 12-character runs; a copy is 13 runs in a row. At most 2 MB a session |
| L1 to L10 | Numbers moved to settings or named as fixed; who owns what between `policy/` and `safeguards/`; one word list, one price; the typed-text exception for an approval; lookups do not hold up a page; more characters allowed after `#`; the clipboard gap named; the step limit is per task; own pages are known by the core's own origin; 0 means no limit when values are compared |

## Order of building (the review's order: guards before the reviewer)

- [x] **0. Spec.** Section 18 changed for every flag above; page regenerated; committed.
- [x] **1. Model client** `safeguards/model.py`: time limit, tries with uneven waits, a breaker for each use, counted cost. The reference loop (`agent/openai_model.py`) uses it.
- [x] **2. Limits and loops** (the viewer's bar is with the viewer helper) `safeguards/limits.py`: steps and minutes of a task, calls a minute, spend, repeated acting calls, "Nothing on the page changed", unknown outcome, questions nobody answers. Viewer: the limit bar and "Allow more".
- [x] **3. Site identity** `policy/sites.py`: the Public Suffix List, registrable name, same site; own pages by origin.
- [x] **4. The task** `safeguards/task.py`: `browser_begin_task`, the grades, domains in a message, events `task_set` and `sites_changed`. Viewer: the task line and site chips.
- [x] **5. The check** `safeguards/check.py` and `findings.py`: the stages in order; today's rules (tool policy, consequential words, site grants) moved in as the first findings; the action classifier (H1); x/y and key presses resolved to elements; findings refused with nobody watching (H8); one line per decision in the log. No reviewer yet: unsure goes to the person.
- [x] **6. What goes out** `safeguards/outgoing.py`: sensitive fields, the copy memory and short secrets, long addresses, files that arrive (after-step path), grant-access screens, money (amounts, caps).
- [x] **7. What comes in** `safeguards/incoming.py` and `scan.py`: unseen text, invisible characters, addresses, marks, quoted names in engine lines, the fixed rules, withholding, flagged pages; then the model's second opinion.
- [ ] **8. Sites** (built: everything on this machine. Not built: the optional lists, abuse.ch and RDAP) `safeguards/sites.py`: look-alikes, confusable letters, `data:` addresses, bare addresses, sensitive sites, the active tab judged at every call; then the optional lists (abuse.ch, RDAP).
- [x] **9. The reviewer and Auto Mode** `safeguards/reviewer.py`: the value `auto` (offered: false), the input with marks, the table, the floor (H2), refuse / ask / run, "Allow once", the pause after refusals, sites added by the reviewer, frames outside the task. Viewer: the chip, the notice, marks on steps, the "Refused" list, the pause bar.
- [x] **10. The record and the service**: retention, control characters, tool hints, the tool list's hash and `GET /api/tools`, `Origin` on `/mcp`.
- [ ] **11. The attack set** (built: 26 attack pages and 4 harmless pages run in a real browser, `tests/e2e/test_attacks.py`. Not built: the fooled agent with its reached / tried / done report, the group in each browser's checklist, the Systems page numbers, the pages listed under "What is left" below) `tests/safety/` and `tests/site/attacks/`: the fooled agent, reached / tried / done, the report, the false-alarm pages; the group in each browser's checklist; the Systems page numbers.
- [ ] **12. Finish** (done: the settings, the README with how an agent connects, the status page. Left: `/verify`, the pull request): settings in the catalogue and the settings screen; README, the connection guide, `docs/status.md`; `/verify`; a pull request.

Attack pages of a slice are written with it, before its code.

## State

| When | What |
|---|---|
| 2026-10-07 | Plan written. Nothing built yet. Next: slice 0, the spec |
| 2026-10-07 | Slice 0 done: section 18 of the spec says every resolution above. Next: slice 1, the model client |
| 2026-10-07 | Slices 1 and 2 done and committed. `safeguards/actions.py`, `task.py`, `reviewer.py` are written with unit tests and not yet wired in. Next: the check (`safeguards/check.py`) and its wiring into `tools/toolkit.py` |
| 2026-10-08 | Slices 3 to 10 done, and the attack pages in a real browser. Next: `/verify` and the pull request; what is not built is listed under "Where the work stands" |

## Where the work stands (2026-10-08): read this before anything else

The status for people is `docs/auto-mode-safeguards-status.md`: keep it up to date as parts land.

Built, tested and committed: slices 0 to 7, 9 and 10; of slice 8 everything that runs on this
machine; of slice 11 the attack pages in a real browser. Since the stop of 2026-10-08 these landed:
text a person cannot see (the page script), the attack set (`tests/e2e/test_attacks.py`), files that
arrive (`PlaywrightDriver._save`, `Toolkit._settle_files`), the words of `[events]` and of a dialog
through the fixed rules (`Reader.own_words`), and slice 10 (`Origin` on `/mcp`, `GET /api/tools`,
`bap-browser config show --tools`, tool hints, `logging.retention_days`).

What is left, in order:

1. Done on 2026-10-08: the work is in `main` (pull request #33), its branch deleted. Before that
   `main` was merged in, the two failures of the run were put right, and the
   work passes the rules of `docs/bad-patterns.md`. A change from here on follows
   `docs/agent-pathway.md` (the skill `develop`): the gate, a pull request, CI. On Windows the gate
   stops at "types" for two Unix-only lines of `code/worker.py`, as it does on `main`: run its
   other stages by hand, and let CI decide that one.
2. **Telling a connected MCP client that the tools changed** (18.9). The tools over HTTP are served
   one request at a time with no connection kept, so there is nobody to tell. Either the endpoint
   keeps sessions, or the spec's line is changed to "a client compares the value of `/api/tools`".
   The user is to decide.
3. **The optional lists** (18.7): abuse.ch and the age of a domain (RDAP). The settings exist and
   are off; nothing reads them.
4. **The Systems page numbers**: checked, asked and refused steps for each browser.
5. **The spending cap in the settings screen** (`safeguards.money.max_amount` is a setting of
   `config.json` only) and the "Known-bad site list" setting.
6. **More of the attack set** (18.13): the fooled agent and its report; the pages `shared_host`,
   `open_tab`, `redirect`, `frame`, `decoys`, `fragment`, `leak_picture`, and the harmless pages
   `address_form` and `forum_post`, as pages in a real browser (their rules have unit tests).
   `open_tab`, `redirect` and `frame` need Auto Mode with a stand-in for the model, as the test
   "a reviewer that was talked round" has.
7. **Two downloads of one name that finish at the same moment** can be given the same place
   (`free_path`, then `save_as`, in `PlaywrightDriver._save`). Seen by a review, not reproduced;
   it was so before this work.

Tests: `uv run pytest tests/unit tests/service -q`, then `tests/e2e`, then `tests/viewer` (build the
viewer first). In the tests' own configuration the marks around page text are off
(`tests/conftest.py`), so that the many tests that say exactly what a result holds stay as they are;
`tests/unit/test_reading.py` and `tests/e2e/test_attacks.py` turn them on. A test that downloads sets
`browser.downloads.dir` to a folder of its own.

Decided while building, and the spec says so: `ip_host` and `young_domain` are for the reviewer in
Auto Mode only; `step_on_sensitive_site` is raised in Auto Mode only, and refuses when nobody watches;
site findings are settled once for a site and task; the confirming words are only "confirm";
`outgoing.decode_min_chars` is 8; a file that needs a yes lies in `downloads/held` and is settled at
the end of the agent's next step; a dialog's words stay in single quotes and are withheld, not cut.

Never again: Python or test text with a backslash through a shell heredoc. It broke a file three
times in this work. Use the edit and write tools for such lines.

## Shapes fixed while building (the spec's 18.10 is to say these; the viewer is built against them)

Events: `task_set {task, from, sites:[{host, grade: named|added_read|added_act}], ts}`, `task_ended {ts}`,
`sites_changed {sites}`, `check_decided {step, stage: rule|reviewer|person|limit, outcome: run|ask|refuse,
findings, reason, said?, refused_id?, ts}`, `refused_allowed {id, ts}`, `page_flagged {tab, site, rule, count, ts}`,
`auto_changed {mode: every_action|risky|auto, state: off|on|paused|waiting_for_task|unavailable, why?, ts}`,
`limit_reached {kind: calls|minutes|spend, limit, scope: task|session, more?, ts}`, `limit_lifted {ts}`,
`questions_unanswered {count, ts}`. `approval_requested` gains `why?: string[]`, `leaves?: {text, from_site,
to_site}`, `amount?`, `said?`. Commands: `resume_auto`, `allow_refused {id}`, `extend_limit`, `drop_site {host}`,
`end_task`.

Helpers at work (each owns only the files named; none commits): site identity and look-alikes
(`policy/sites.py`, `safeguards/lookalikes.py`, the two data files, `scripts/refresh_data.py`); the viewer
parts of 18.10 (everything under `viewer/`, no build).

Module names as built: `safeguards/model.py` (`ModelClient`, `Spend`), `safeguards/limits.py` (`Limits`).
`ModelError` is in `errors.py`. All settings of 18.11 are in `config.py` (`safeguards.*`, `limits.*`,
`safety.auto_mode.*`, `agent.retries`, `logging.retention_days`).

## The spec is to be changed for these (found while building; do it before the slice's commit)

- 18.4 classifier: the sending words are send, sent, sending, post, submit, publish, tweet and the Hindi
  ones; reply, share, forward, invite, comment and apply are gone (they open a form more often than
  they send). A link is classed only as paying, deleting or granting. A phrase outweighs a single
  word ("Cancel order" deletes); between words of the same length the graver class wins.
- 18.10: the events and commands under "Shapes fixed while building" above.
- 18.8: what counts as a change of the page (structure, typed or chosen values, scrolling, focus
  moved by the keyboard); the notice is not added after `browser_hover`; a failed step counts
  towards the repeats but is not told "Nothing on the page changed."

## Where things are (found while reading; keep short)

- The decision for a call is in `src/bap_browser/tools/toolkit.py`: `Toolkit.call` runs `_blocked_by_a_dialog`, `_site_permission` (the extension's question), `_permit` (tool policy, `ask_before`, consequential words, site grants), then `_run`.
- Who is asked: `BrowserSession.ask_approval`, set by `service/session.py` (`_ask_approval`, events `approval_requested` and `approval_closed`).
- Settings a person may change: `settings/catalogue.py`, `settings/store.py`; the admin and user roles are spec 4.11.
- The page script: `driver/snapshot_page.js`. The driver: `driver/playwright_driver.py` (tabs, dialogs, downloads, the network hold for the address policy).
- The reference loop: `agent/loop.py`, `agent/openai_model.py`. The three-browser window: `agent/studio.py`.
