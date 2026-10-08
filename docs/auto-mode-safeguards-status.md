# Auto Mode and safeguards: status

Last brought up to date: 2026-10-08. Branch `feature/auto-mode-safeguards`, not merged.

- What is being built: spec section 18, `docs/bap-browser-spec.md`.
- The review it answers: `docs/index.html` (10 high, 18 medium, 10 low points).
- Every decision and the next step, for whoever goes on: `docs/plans/2026-10-07-auto-mode-and-safeguards.md`.

## In one line

About 90% built. Every step is checked before it runs, Auto Mode works, what comes in and what goes
out is guarded, files that arrive are judged, the service is hardened, and 17 attack pages are run in
a real browser. What is left is listed under "Pending": mainly the optional outside lists, a few
numbers and settings in the window, more attack pages, and the final check with the pull request.

## Completed (built, tested, committed and pushed)

| Part | What it does | Where | Proof |
|---|---|---|---|
| The spec after its review | Section 18 says what was decided for each of the 38 points, and what changed while building | `docs/bap-browser-spec.md` | The commits |
| The model client | One call to the provider with a time limit, further tries with a growing uneven wait, a breaker for each use, the cost counted | `safeguards/model.py` | `tests/unit/test_model_client.py` |
| Limits and loops | A task stops at its steps, its minutes, the calls in a minute and the cost of model calls; "Allow more"; a step repeated on a page that does not change is told at the 3rd time and not run at the 6th; a step whose answer was lost says so; questions nobody answers stop being waited for | `safeguards/limits.py`, the page script's change counter | `test_limits.py`, `test_toolkit_limits.py`, `tests/e2e/test_loops.py` |
| What a site is | The Public Suffix List and Unicode's look-alike letters, shipped as data | `policy/sites.py`, `scripts/refresh_data.py` | `test_sites.py` |
| Look-alike sites | A name one letter from a protected one; a protected name beside a lure word; mixed writing systems | `safeguards/lookalikes.py` | `test_lookalikes.py` |
| The task and its sites | The person's message, or what an outside agent declares; the grades named, added for reading, added for acting | `safeguards/task.py` | `test_task.py` |
| What a step does | Pays, sends, deletes, grants or confirms, by words, phrases and Hindi words | `safeguards/actions.py` | `test_actions.py` |
| The reviewer's table and floor | A model's rating becomes run, ask or refuse in code; a paying, sending or deleting step never runs on a model's word | `safeguards/reviewer.py` | `test_reviewer.py` |
| The check on every call | The stages in order: hard stops, the person's own browser, what is always a person's, every action, what the rules are unsure of. One line of the log for each decision | `safeguards/check.py`, `tools/toolkit.py` | `test_check.py` |
| Auto Mode | The reviewer rates what the rules are unsure of; refusals with "Allow once"; a pause after refusals in a row; sites outside the task; not offered until a deployment turns it on | `check.py`, `service/session.py` | `test_auto_mode.py`, with a stand-in for the model |
| What goes out | Typing a password, a card or a code is asked of a person; text read on one site and sent to another; short secrets however they are packed; long addresses; screens that give an app access; the amount of a payment, and caps | `safeguards/outgoing.py`, `check.py` | `test_outgoing.py`, `test_check.py` |
| Bad and sensitive sites | Look-alikes, pages with no site of their own, sensitive sites, judged at every call of the agent | `check.py` | `test_check.py` |
| `browser_begin_task` | An outside agent states its task once; a change needs the person's yes; not offered in a chat | `tools/browser_tools.py`, `toolkit.py` | `test_begin_task.py` |
| Settings | Auto, "Offer Auto", the page scan, copying between sites, sensitive sites, steps in one task; the groups "Safety" and "Limits" | `settings/catalogue.py` | `test_settings_store.py` |
| The viewer | The mode chip, the first-time notice, the task line and its sites, marks on steps, the extended question, the "Refused" list, the flagged-page notice, the pause bar, the limit bar | `viewer/src` | The viewer's own tests |
| What comes in | Every result puts what the page wrote between marks, withholds text addressed to an agent (fixed rules, then a model's second opinion), flags the page, tells the person, and remembers what was read so that copying to another site is noticed. A picture's result says whose words are in it | `safeguards/incoming.py`, `scan.py`, `reading.py` | `test_incoming.py`, `test_scan.py`, `test_reading.py` |
| Text a person cannot see | Text hidden by opacity, size, colour, clipping or its place off the page is left out of what the agent reads. Short text clipped for screen readers is kept. Hidden text addressed to an agent flags the page | `driver/snapshot_page.js` | `tests/e2e/test_attacks.py` |
| The engine's own lines | A name or a dialog's words that a page wrote, inside a result, a refusal or the `[events]` line, is withheld when it is addressed to an agent | `reading.py`, `toolkit.py` | `test_reading.py` |
| Files that arrive | A program is never kept, whatever its name says. An archive, an HTML or SVG file, and any file on the person's own machine, waits in a folder of its own and is kept only with the person's yes; with nobody watching it is deleted | `driver/playwright_driver.py`, `toolkit.py`, `outgoing.py` | `test_outgoing.py`, three tests in `tests/e2e/test_attacks.py` |
| The service and the record | Another web page cannot call the tools (`Origin` on `/mcp`); `GET /api/tools` and `bap-browser config show --tools` give one value for the tools on offer; the tools carry read-only hints; log lines older than 30 days are removed | `service/app.py`, `service/server.py`, `tools/event_log.py`, `tools/registry.py`, `mcp/server.py`, `cli.py` | `tests/unit/test_record.py`, `test_cli.py`, `tests/service/test_serve.py`, `test_service.py` |
| The attack set, in a real browser | 17 attack pages and 4 harmless pages: planted instructions (plain, hidden, in attributes, in invisible characters, in an inbox), a page that imitates the engine, a page that talks to the check, sending by Enter, paying, deleting, granting access, a password field, a leaked order number, downloads | `tests/site/attacks/`, `tests/site/harmless/`, `tests/e2e/test_attacks.py` | 25 tests |
| The documents | The spec for what changed while building, the README (what is on, how to turn Auto Mode on, how an agent connects), this page, the plan | `docs/`, `README.md` | Read them |

## Pending

| Part | What is left | Size |
|---|---|---|
| The end | `/verify` over the whole build, then the pull request | Small |
| Telling a connected agent that the tools changed | The spec asks for it (18.9). The tools over HTTP keep no connection, so there is nobody to tell. Either the endpoint is changed to keep one, or the spec says "a client compares the value of `/api/tools`". **Your decision** | Small or medium |
| Optional outside lists | abuse.ch (known-bad sites and files) and the age of a domain. The settings exist and are off; nothing uses them yet | Medium |
| The Systems page | The numbers of checked, asked and refused steps for each browser | Small |
| Two settings in the settings screen | The spending cap for one step, and the "Known-bad site list" switch. The cap works today from `config.json` | Small |
| More of the attack set | An agent that is fooled on purpose, with its report of reached / tried / done; and about twelve more pages as real-browser tests (Spanish wording, a picture, text that loads late, shared hosts, a redirect, a frame, and others). Their rules are tested without a browser today | Medium |

## What changes for people who use it today

| Change | Why |
|---|---|
| Typing a password, a card number or a one-time code asks the person every time, in every mode. Not on the demo pages | Spec 18.6 |
| With nobody watching, a question that a rule raised is refused, whatever `control.approval_without_viewer` says. A tool the deployment set to `confirm` still follows that setting | The review's point H8 |
| Results say "Nothing on the page changed." after a step that changed nothing | Spec 18.8 |
| Results put what a page wrote between `<<page …>>` marks | Spec 18.5 |
| A new tool, `browser_begin_task`; a new event at the start of a session, `auto_changed` | Spec 18.3, 18.10 |
| A downloaded program (`.exe`, `.msi`, a script) is deleted and never kept. An archive asks first. On a person's own machine every download asks first | Spec 18.6 |
| A file's name in the `[events]` line is in double quotes: `download saved: "report.txt"` | Spec 18.5 |
| A request to `/mcp` from another web page is refused with 403 | Spec 18.9 |
| Lines of the logs older than 30 days are removed (`logging.retention_days`; 0 keeps everything) | Spec 18.9 |

## Known problems that were there before this work

On this Windows machine: two tests that check a file's mode (`test_accounts`, `test_evals`), two
errors in `test_settings_api` (a test name too long for an environment variable), `pyright` on
`code/worker.py`, and tests of the service and the viewer that fail now and then when the machine is
busy and pass when run by themselves.
