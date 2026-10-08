# Auto Mode and safeguards: status

Last brought up to date: 2026-10-08. Branch `feature/auto-mode-safeguards`, not merged.

- What is being built: spec section 18, `docs/bap-browser-spec.md`.
- The review it answers: `docs/index.html` (10 high, 18 medium, 10 low points).
- Every decision and the next step, for whoever goes on: `docs/plans/2026-10-07-auto-mode-and-safeguards.md`.

## In one line

About 75% built. Work was stopped on 2026-10-08 at the user's word, with everything that is finished
committed and pushed. The check on every step, Auto Mode, the guards on what goes out and the guard
on what comes in (marks, the scan, flagged pages) are in. What is left: text a person cannot see,
files that arrive, hardening the service, the attack pages run in a real browser, and the documents.

## Completed (committed and pushed)

| Part | What it does | Where | Proof |
|---|---|---|---|
| The spec after its review | Section 18 says what was decided for each of the 38 points | `docs/bap-browser-spec.md` | The commit |
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
| The rules for what comes in | Characters nobody can see, addresses as shown, marks, the fixed rules of the scan, the model's second opinion | `safeguards/incoming.py`, `scan.py` | `test_incoming.py`, `test_scan.py` |

| What comes in, connected | Every result puts what the page wrote between marks, withholds text addressed to an agent (fixed rules, then a model's second opinion), flags the page, tells the person, and remembers what was read so that copying to another site is noticed. A picture's result says whose words are in it | `safeguards/reading.py`, `tools/browser_tools.py`, `tools/toolkit.py` | `tests/unit/test_reading.py` |

## Pending

| Part | What is left |
|---|---|
| Text a person cannot see | The tests for opacity, size, place, clipping and colour in the page script. Until then, text hidden by a style still reaches the scan as ordinary text: it is scanned, but it is not left out for being unseen |
| The words of events | What happens in the browser by itself (`[events]`) is not yet passed by the fixed rules |
| Files that arrive | A program is never kept; an archive, or a file on the person's own machine, is asked about |
| The service and the record | How long logs are kept; tool hints; the tool list's hash; the `Origin` rule on `/mcp` |
| Optional lists | abuse.ch and the age of a domain. Not started |
| The attack set | The attack pages run in a real browser, the fooled agent, the report, the false-alarm pages |
| The Systems page | The numbers of checked, asked and refused steps for each browser |
| The end | The spec for what changed while building, the README, the connection guide, `/verify`, the pull request |

## What changes for people who use it today

| Change | Why |
|---|---|
| Typing a password, a card number or a one-time code asks the person every time, in every mode. Not on the demo pages | Spec 18.6 |
| With nobody watching, a question that a rule raised is refused, whatever `control.approval_without_viewer` says. A tool the deployment set to `confirm` still follows that setting | The review's point H8 |
| Results say "Nothing on the page changed." after a step that changed nothing | Spec 18.8 |
| Results put what a page wrote between `<<page …>>` marks | Spec 18.5 |
| A new tool, `browser_begin_task`; a new event at the start of a session, `auto_changed` | Spec 18.3, 18.10 |

## Known problems that were there before this work

On this Windows machine: two tests that check a file's mode (`test_accounts`, `test_evals`), two
errors in `test_settings_api` (a test name too long for an environment variable), `pyright` on
`code/worker.py`, and tests of the service and the viewer that fail now and then when the machine is
busy and pass when run by themselves.
