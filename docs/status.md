# bap-browser: Status

Date: 2026-10-07 · Branch `main` · pushed to GitHub (`DCode-v05/Browser-Agent`) together with this page · To show it: `docs/demo-guide.md`

## Where things stand

All 28 tools of milestone 1 are built and tested, and are on `main` (pull request #2, merged on
2026-10-06).

- Before the merge `uv run pytest -q` gave 902 passed and none failed (macOS, Python 3.12.5), and CI passed.
- What is still not built is listed under "Not completed": it is the work after the tools.

## Completed (on `main`)

| # | Part | What it does | How to run it |
|---|---|---|---|
| 1 | Engine | Settings in one file, the address policy, redaction, the browser driver, the page as text with refs | `uv run pytest` |
| 2 | 18 of the 28 tools on `main`; all 28 on `wip/remaining-tools` | `browser_navigate`, `go_back`, `go_forward`, `reload`, `snapshot`, `get_text`, `find`, `click`, `hover`, `type`, `fill_form`, `select_option`, `set_checked`, `press_key`, `scroll`, `scroll_to`, `wait`, `request_human`; on the branch also `screenshot`, `zoom`, `drag`, `handle_dialog`, `tabs`, `console`, `network`, `evaluate`, `upload_file`, `downloads` | Through any of the commands below |
| 3 | MCP over stdio | An outside agent starts the browser tools as a process | `uv run bap-browser mcp` |
| 4 | MCP over HTTP, with the viewer | An agent in another process calls the tools with a bearer token while a person watches | `uv run bap-browser serve --open` |
| 5 | Viewer | Live picture, timeline of steps, Pause, Take over, Hand back, Stop, in the BAP product's colours and typeface | `--open` on any command |
| 6 | Chat | A person gives tasks one after another and reads the answers; one conversation with the steps inside it; Stop task ends the task and keeps the session | `uv run bap-browser agent --chat --open` |
| 7 | Reference agent loop | A scripted demonstration with no key, and a hosted model (OpenAI `gpt-5.6-luna`, key in `.env`) | `uv run bap-browser agent --demo --open` |
| 8 | Help from a person | The agent asks for a sign-in, a CAPTCHA or a code, and waits | `browser_request_human` |
| 9 | Approvals in the UI | A tool can be allow, confirm or deny; "Ask before every action"; an action that pays, sends or deletes is asked every time; "Allow on this site" | `safety.action_policies`, `safety.ask_before` in `config.json` |
| 10 | The browser on screen | The agent works in a window you can see, with the chat beside it; the profile can be kept | `uv run bap-browser agent --chat --show-browser --open` |
| 11 | The extension in the agent's browser | The chat in the browser's own side panel; a glow, a label and the agent's pointer on the page | `uv run bap-browser agent --chat --extension` |
| 12 | Take-over Chrome, first cut | The agent works in a tab of your own Chrome, through the extension and Chrome's debugger. You load the extension by hand, once | `uv run bap-browser agent --chat --takeover` |
| 13 | Attach | The driver attaches to a browser that is already running | `browser.cdp_url` in `config.json` |
| 14 | Desktop app, first cut | Electron with a shadcn/ui shell: the agent's browser and the chat in one window. It runs from this folder and needs `uv` | `npm --prefix desktop install`, then `npm --prefix desktop start` |
| 15 | Container image | `deploy/Dockerfile` and `deploy/config.vm.json` for the browser service. Written, never built | `docker build -f deploy/Dockerfile .` |
| 16 | Demo site | A sign-up form and an airline check-in (booking SK4821, name Lovelace) | Opens with `--chat` |

### Proof

Measured on macOS (Python 3.12.5) on 2026-10-06, on `main` at the merge of pull request #6.

| Check | Result |
|---|---|
| `uv run pytest -q` | 958 passed in 209 s |
| `uv run ruff format --check .`, `uv run ruff check .`, `uv run pyright` | No findings |
| `npm --prefix viewer run test` | 400 passed |
| `npm --prefix viewer run typecheck`, `run lint`, `run build` | No findings; it builds |
| CI on GitHub (Ubuntu) | Passed on pull requests #2 to #6. Seen once and not explained: `test_files_are_given_to_a_file_field_and_to_a_button_that_asks_for_them` failed on one run and passed when run again |
| `uv run bap-browser doctor` | Chromium 153, Chrome 154 and Edge 154 launch; everything needed is in place |
| `uv run bap-browser agent --demo --exit-when-done` | The scripted run ended with the account created |
| The chat with the real model (`gpt-5.6-luna`), driven through the viewer | Four tasks one after another: it read a page; took a screenshot; was refused the cloud metadata address; asked for help at a CAPTCHA, was taken over, and went on after Done |
| Not measured again on this machine | The desktop app's own checks (its packages are not installed here) |

How to show all of this to someone is in `docs/demo-guide.md`.

### Not checked

| What | Why |
|---|---|
| A task with the real model key, by me | I never read `.env`. The notes of pull request #1 say your teammate ran `gpt-5.6-luna` with a key and it worked |
| The extension's toolbar icon | The side panel was tested as a tab; a click on the icon cannot be made from a test |
| The container image | The Docker engine was not running on this machine. The image has never been built or started |
| `/verify` over the whole build | You asked for it at the end of the build. The build was stopped before its end, so it was not run |
| A review by a fresh reviewer of the work since pull request #1 | Not done. The third review of 2026-10-04 was cut off by a usage limit and reported nothing |

## Not completed

### 1. Finished on 2026-10-06: the ten remaining tools

On the branch `wip/remaining-tools`. Measured there on macOS on 2026-10-06: `uv run pytest -q`: 902
passed. `ruff format --check`, `ruff check`, `pyright`: no findings. Viewer: 400 passed.

| Tool | State |
|---|---|
| `browser_tabs`, and pop-ups that become tabs | Works in a real browser |
| `browser_handle_dialog` | Works: a dialog interrupts the action, other tools are refused until it is answered, the action then finishes |
| `browser_console`, `browser_network` | Work |
| `browser_evaluate` | Works; offered only when turned on, and asks first |
| `browser_screenshot`, `browser_zoom` | Work. The fault with a dense screen is cured: a picture is taken the way Playwright takes one, and a picture that is too large is made smaller by the browser itself |
| `browser_upload_file`, `browser_downloads` | Work |
| `browser_drag` | Works: a slider's knob and a card dropped on a column, in a real browser |

What was done to finish them: the cure for pictures; the 13 failing tests; 22 new tests with the
stand-in driver (the dialog rule, `[events]` and its cap, the timeline sentences, what a viewer is told,
a picture over MCP and to the model, which files may be uploaded, a picture's size); the spec (5.3, 5.5,
5.7, 5.8, 5.9, 10.3) and its page; `ruff format`. One fault was found and fixed on the way: when the
browser had gone away, the result also said "tab t1 closed".

Run once with the real model (`gpt-5.6-luna`) on 2026-10-06: it took a screenshot, zoomed into a
region, opened a second tab, listed and closed it, and read the console.

The spec's page is made again with `uv run --no-project --with markdown python docs/spec_to_html.py`.
The script is in the repository now, so it cannot be lost again. From `main`'s spec it gives the page
that was there, byte for byte apart from empty lines.

Known limits, written into the spec: a download's size is checked when it has arrived, not while it
arrives; a window that a page opens in take-over Chrome cannot be reached; the address policy is not
applied to a window a page opens.

### 1b. Finished on 2026-10-06: frames in the snapshot

What is inside a frame is read under the frame's line, with refs such as `f2e7`, for frames of the same
site, frames of another site (which the browser keeps in another process) and frames inside frames. Every
tool that takes a ref works inside a frame, and `browser_find` searches the frames too. 12 tests in a real
browser (`tests/e2e/test_frames.py`). Known limit: something of the outer page that covers an element
inside a frame is not noticed.

### 1c. Finished on 2026-10-06: the extension as a real bridge

For take-over Chrome (`uv run bap-browser agent --chat --takeover`):

| Part | What it does now |
|---|---|
| The bridge in the background | The side panel can be closed while the agent works |
| Pairing | A pairing token that is taken once and runs out; the session's own token no longer lets a bridge in |
| Heartbeat and reconnect | A silent channel is closed; the bridge dials again by itself; the tab, its refs and the run survive a cut |
| Site permissions | Allow once, Always allow on this site, Don't allow, asked in the extension's own page and kept on the person's machine; sites never offered; a deployment's block list; "ask before every action" |
| Not relying on the core | Mouse, keyboard and navigation commands are checked again in the extension |
| Stop | The extension's own "Stop the agent" |

A fault that was there before was found and fixed on the way: the bridge could hand the driver something
a tab said before the answer that came just ahead of it. The driver then dropped the page it had not
heard of yet, and the agent's browser never started (about 1 start in 6 on a busy machine; none in 72
after the fix).

12 tests in a real Chromium with the extension loaded (`tests/viewer/test_takeover.py`). Not checked by
me: the toolbar icon and the question window in a Chrome with a visible window, which a test cannot
press; try them by hand.

### 1d. Finished on 2026-10-06: the address policy at the network

Every document a tab sets out to load is judged by the address policy before the request is made: where
a redirect goes, where a link or a script leads, what a frame holds. A window a page opens at a refused
address is closed at once. With `safety.enforce_on_subresources` pictures, scripts and requests are
judged too. 7 tests (`tests/e2e/test_network_policy.py`), which also check that the refused site was
never asked for anything. Known limit: the first request of a new window may reach the network before
the window is closed.

### 1e. Finished on 2026-10-06: `doctor`, and a first bench

`uv run bap-browser doctor` says which browsers launch on this machine and whether the rest is in
place. On this Mac: Chromium 153, Chrome 154 and Edge 154 launch; everything else is in place.

`uv run bap-browser bench` times 32 of the 40 per-tool lines of the budget (`perf/budget.json`).
Measured on this Mac on 2026-10-06, Chromium, 30 runs after 5 warm-up runs:

| State | Lines |
|---|---|
| OK | 23 |
| WARN (over the target, under the fail limit) | 5: `click.ref.small`, `click.ref.big`, `hover.ref`, `set_checked` (83 ms against 50), `scroll.step` (67 against 60) |
| FAIL | 4: `click.point` (33 ms against 5), `press_key.small` (34 against 5), `press_key.big` (33 against 10), `select_option` (33 against 10) |
| NOT RUN | 8, which have no scenario yet |

Why four failed in that first run: after every action the driver waited two animation frames, 33 ms, to
see whether the action had started a navigation.

**Cured on 2026-10-06.** The page itself says when it sets out for another page or opens a window
(`Page.frameRequestedNavigation`, `Page.windowOpen`), and what it says arrives before the answer to the
driver's next question. So after an action the driver gives the page one turn of its own queue and asks;
nothing is waited for that is not happening. Measured again, Chromium, 30 runs:

| Line | Before | After | Target | State now |
|---|---|---|---|---|
| `select_option` | 33 ms | 2.1 ms | 10 | OK |
| `press_key.small` | 34 ms | 1.7 ms | 5 | OK |
| `press_key.big` | 33 ms | 17 ms | 10 | WARN |
| `click.point` | 33 ms | 17 ms | 5 | FAIL |
| `click.ref.small`, `click.ref.big`, `set_checked` | 83 ms | 67 ms | 50 | WARN |

In all: 25 OK, 6 WARN, 1 FAIL, 8 NOT RUN. `click.point` still fails: the browser hands a mouse press to the
page with its next frame, 17 ms, and the target of 5 ms came from a prototype that did not go through the
browser's input. It is left as it is, and is a number to decide on, not a fault to hide. A known cost of
the cure: a page that leaves only some time after the action (a script that waits, then goes) is no longer
seen leaving by that action's own result; the next result shows the new address.

### 1f. Fixed on 2026-10-06: the upload test that failed now and then

`test_files_are_given_to_a_file_field…` failed on 2 of about 12 runs on GitHub and never on this Mac. The
cause: the browser was told that file choosers are wanted only at the moment of an upload, and on a slow
machine the click could open the chooser before the browser had heard. That chooser was then never seen,
and no later one opened. Now each tab listens for file choosers from its start. A chooser that a plain
click opens is closed, and the agent is told to use `browser_upload_file`. Not yet proven on GitHub by
many runs: it had failed about 1 run in 6.

### 1g. Run by hand on 2026-10-06, in a browser with a window

Take-over Chrome with the side panel closed: the bridge connected by itself, the agent's tab opened, the
extension asked in a small window of its own ("127.0.0.1", "Opening …/form.html"), "Always allow on this
site" let the agent go on and type, and "Stop the agent" took it off the tab. Not pressed by hand: the
toolbar icon. The desktop app's own checks pass (typecheck, 5 tests, build); its window was not opened.

### 1h. Finished on 2026-10-06: one window with the three browsers, and the pop-up for a person's step

`uv run bap-browser studio --open` (spec 9.16):

| Part | What it does |
|---|---|
| Three pages in one window | Cloud browser, My Chrome and Built-in browser, each with its own session, chat and steps; a tab for each says where it stands, and "Needs you" shows from any page |
| The built-in browser | A browser of the app's own that keeps its sign-ins in a profile of its own |
| My Chrome as a page | Says how to load the extension, then becomes the chat for that Chrome when the extension dials in |
| The pop-up | When the agent asks for a sign-in, a human check, a payment or other help, a pop-up comes up on every backend, with Take over, Couldn't do it and Look first |
| The pop-up for an approval | An approval pops up the same way, with Allow once, Allow on this site, Deny and Look first. No button of it holds the focus, so a stray key allows nothing |
| Noticing a human check or a sign-in | The result that shows such a page tells the agent to ask the person |
| A new session | "Start a new session" on a page whose session was stopped |
| The model knows where the browser is | Each chat task carries the address the browser is on |
| A demo page for it | The members' area on the demo site: a sign-in with a human check |
| The desktop app, from the window | A button in the bar, "Open desktop app", starts the desktop app in a window of its own. Shown only where the app is installed and built beside the service |

The desktop app was opened on this machine on 2026-10-06, from the button and by hand: a task typed in
its chat ("Open the sign-up page.") moved its browser to the sign-up page, with the real model. In a
terminal inside an editor built on Electron, `npm --prefix desktop start` opens no window: the editor
sets `ELECTRON_RUN_AS_NODE`. The button is not caught by this; by hand, start it from another terminal.

Run with the real model on 2026-10-06, cloud page: asked to sign in to the members' area, the agent
asked for help; the pop-up came up; the person took over, signed in through the live picture and ticked
the human check, answered Done; the agent read the renewal date. 4 tests in a real browser
(`tests/viewer/test_studio.py`), one of them with the extension loaded into a second Chromium.

Not checked by me: the My Chrome page with a Chrome that has a visible window in this window's own flow
(the extension itself was run that way, section 1g), and the pop-up on the My Chrome page with a real
model.

### 1i. Finished on 2026-10-06: the settings API, and the pop-up for an approval

The settings screen of a live session is now the service's own (spec 10.2):

| Part | What it does |
|---|---|
| The catalogue | 16 settings (all of milestone 1 on the web), each defined once: its group, the surfaces it is on, the configuration key it changes, and how a person's value is limited by the deployment's |
| `GET /api/settings`, `PATCH /api/settings`, `GET /api/config` | The screen is drawn from the answer; a change is saved as it is made; a refused change says which setting and why (409) |
| A person tightens, never loosens | More approvals but not fewer; blocked sites added to the deployment's; allowed sites only narrowed; what the deployment turned off stays off; a locked setting is shown and cannot be changed |
| A change reaches the running session | From the agent's next tool call: the site lists, the tools on offer, approvals, the event log, the picture quality |
| Kept | In `settings.file`, for the person alone to read; a value that no longer holds is passed over |
| Clear browsing data | Ends the cloud browser's sessions and deletes its kept profile, after asking. Only a folder that is a browser's profile is ever deleted |
| The pop-up for an approval | "The agent needs your approval", over the page, on every backend |

Tests: 28 for the store, 18 for the API on a running service, 1 in a real browser that changes settings
as a person does (`tests/viewer/test_live_settings.py`), 7 for the viewer's side.

Seen on the way, and left as it is: with "Ask before: Every action", opening a blocked site first asks for
approval and is refused only after the answer. The refusal could come first.

### 1j. Finished on 2026-10-06: the code tool `browser_run`

One call does several steps with a short Python script the agent writes (spec 7):

| Part | What it does |
|---|---|
| The check before a script runs | No import, no class, no name or attribute beginning with an underscore, no name outside the list, none of the attributes that lead to the frames behind a value; each refusal names the line |
| The worker | A process of its own, started with an empty environment and the standard library alone, used again from script to script, ended when a script computes too long |
| `browser`, `state`, `print`, `re`, `json`, `math` | The tools as methods; `find="…"` on click and type; values kept from script to script |
| Every step is a tool call | The same address policy, approvals, log and timeline row as a single call; a person pauses or takes over between two steps |
| The result | What came of it in the first line, what was printed, the value, each step, and where it stopped |

**It is off by default, and that is a decision for you.** The spec says "on by default once it exists",
and also says the check is no security boundary: the boundary is the micro VM, which is not built. On your
own machine there is nothing around the core, so I left `code.enabled` at `false` and wrote the reason
into the spec (7.4). To turn it on: `{"code": {"enabled": true}}` in `config.json`.

Tests: 44 for the check and the worker, 12 for the tool on a fake browser, 1 on a real Chromium that fills
a form and collects from three pages in one call.

Found by that last test, and cured: the best match for the words "Full name" is the label, which cannot
be typed into, and words that match only in part ("No such button") found a button to click. A script
now acts only on a match whose name holds every word, and types into a field before a label.

### 1k. Finished on 2026-10-06: the three browsers as systems, with settings, logs and evaluations of their own

Asked for on 2026-10-06: separate settings for the three systems with what to enable and how to manage
each, a log file for each, and evaluations of each. Built as spec 9.17 and 12.6.

| Part | What it does |
|---|---|
| Settings of each system | Most settings are each system's own: a system's value, else the one for every browser, else the deployment's. A person still tightens and never loosens. The settings button on a page opens the settings of that page's browser |
| Turning on and off, and managing | "Use this browser" for each system: off ends its session and takes it off its page, and it stays off the next time. Start, Stop and Restart for each. What cannot be done is said in a sentence |
| What to enable | For each system, as switches on its card: downloads, uploads, the log, scripts in pages, scripts of several steps. And the model, among `agent.offered_models` |
| A log file for each | `.bap-browser/logs/cloud.jsonl`, `chrome.jsonl`, `builtin.jsonl`: one line for each tool call. The window shows where the file is and its newest lines |
| A record of each task | `.bap-browser/evals/<system>/tasks.jsonl`: how it ended, its time and where it went, its steps, its tokens and their cost, and its trace |
| Evaluations | For each system: the model; outcome quality (share answered, steps failed, the person's Good and Bad); latency (a step, a reply: typical and slow); performance by tool; time (a task, and the shares of model, browser and waiting); cost (tokens, and dollars where a price is set); the trace of each recent task, drawn as bars |
| The checklist | Eleven checks done as real steps on the demo site, in that system's browser: it answers, opens, reads, finds, clicks, types, takes a picture, refuses the cloud metadata address, stays within the time limit, writes its log, and can ask a person |
| The Systems page | "Systems" in the window's bar: the three systems side by side, with a Configuration view and an Evaluations view |
| Under each browser's own tab | Browser and chat, Configuration, Evaluations: that system's card by itself, where a person is already looking at that browser |

Run in a real Chromium (`tests/viewer/test_studio.py`, 5 new tests): the checklist passes all eleven
checks on the built-in browser; a task done on the cloud browser is on that browser's record and log
and on no other's; a system is turned off and on, stopped and started; and the Systems page is used as
a person would use it. Tests in all: 46 new for the service, 34 for the viewer.

Not checked by me: the checklist and the records on a person's own Chrome with a real extension and a
real model (the tests do it with the built-in and the cloud browser), and the cost with a real price:
`agent.input_price_per_million` is 0 until you set what your model costs.

What is not in it, and is said in the spec: a judgement of an answer by another model; the eight
task-level scenarios of the bench; settings of the desktop app's folders.

### 1l. Finished on 2026-10-07: the admin and the user, each with a sign-in page of their own

Asked for on 2026-10-06: a Configuration for the admin, where they allow users the systems; Settings
for a user, where they choose the browser they prefer and set what is theirs; evaluations in both,
with the admin deciding what a user sees; a sign-in page for each; working switches for both. Built
as spec 4.11, with 9.17, 10.1, 10.2 and 12.6 brought in line.

| Part | What it does |
|---|---|
| Two sign-in pages | `/admin` for the admin and `/` for a user, each with its own password. The first time, the link the service prints makes the admin's password; the admin sets the one users sign in with. Passwords are kept as salted hashes in `.bap-browser/accounts.json`. Five wrong ones in a row hold sign-in back for a minute; a sign-in lasts 12 hours; a new password signs out whoever used the old one |
| The admin's Configuration | Everything of section 1k, and the card "Users": which settings users may change, what of the evaluations users may see, and the two passwords. Each browser's card has "Let users use this browser" |
| A user's Settings | Under each browser's tab, in place of Configuration: the preferred browser, a switch or a choice for every setting that is theirs, and in words what the admin holds |
| Whose value holds | `config.json`, then the admin's configuration (the admin may choose either way), then a user's own value, which may only be tighter. `settings.locked` is nobody's to change from a screen |
| The preferred browser | A user's window opens on it. Chosen, it opens at once, ready for a task. When it has stopped, the user's page starts it |
| Evaluations for each | The admin: every system, and "All systems", the three as one with a row for each. A user: the browsers they may use, and of cost, traces and the checklist only what the admin lets through. What is kept back is not sent |
| Held by the service, not the page | A browser the admin keeps from users answers 404 to a user, on every address and on the live connection. What is the admin's answers 403. A user already on a browser that is taken away is disconnected, and so is anyone whose visit has ended |

Run in a real Chromium (`tests/viewer/test_roles.py`): the admin creates their password, sets the
users' one and keeps the cloud browser and the cost from users; a user signs in, is refused a wrong
password, sees two browsers and no Systems page, prefers the built-in browser, gives it a task and
gets the answer, makes "Ask before" stricter for themselves while the admin's value stays, sees the
task in Evaluations with no cost, and has the browser started again after the admin stops it; a new
password sends the user's page back to sign-in. Tests: 7 for the passwords, 11 for the roles over
HTTP, 32 for the viewer, 1 in a real browser.

Not checked by me: the two pages on a phone-sized screen (the styles are the tokens' own, and the
tests are at desktop size), and two people signed in as a user at the same time (they share one
password, one set of settings and one preferred browser).

What is not in it: an account for each person.

### 1m. Finished on 2026-10-07: each thing in one place, every control working and saying what it does

Asked for on 2026-10-07, after using the admin's page: working switches in the settings; no
configuration, settings or evaluations shown twice; it made clear on the admin's side what is for
users; every control saying what it does; a change by the admin showing on the user's page.

| What was wrong | What it is now |
|---|---|
| The same card of a browser was under its tab and again on the Systems page, and a third time in a settings screen that opened over the page | One place for each thing. A browser's own Configuration and Evaluations are under its tab. The Systems page has only what is not one browser's: **Users** and **All systems**. The settings button on the chat goes to that browser's Configuration (a user's Settings) |
| The settings screen vanished while it was being used: turning "Use this browser" off or on replaced the page behind it | There is no screen over the page in the window. "Use this browser" is one switch at the top of the Configuration, and the page stays where it is |
| Choices and site lists were shown as words on the card, changed only in that screen | Every setting has its working control on the page: switch, choice, list of sites, button. A change is saved as it is made and the row says "Saved" |
| A switch said only its name | Every setting has a line saying what it does (each under 110 characters, held by a test); every line of what users may change and see says what it lets a user do; the buttons and the lines of the evaluations say what they are |
| Nothing said which settings reach users | On the admin's Configuration, a setting that is also on the user's page says so, and whether users may set their own or are held at the admin's value. Every page says whose it is and what it is for |
| The bar, the views and the session's own buttons (Pause, Take over, Stop session, the icons) worked and said nothing of what they do: 94 such controls over the eleven pages of the two roles | Each says what it does when the pointer rests on it. The count is 0, and a real-browser test fails on any control that says nothing |
| The colour mode held only on "Browser and chat": every other view fell back to the device's colours | The window keeps it: it holds on every page |
| A user saw the admin's changes to "may change" and "may see" only after a reload | A user's window follows the admin within two seconds: browsers, views, and settings now held |
| My Chrome's page showed "Protocol error (Target.setAutoAttach): No current window" | "Your Chrome has no window open. Open a window in Chrome: the agent works in a tab of it." |
| The window had two banners, no main part and, off the chat, no first heading (found by the accessibility scanner, which had never been run on these pages) | One of each. The scanner finds nothing on any page of the window, and the tests now run it on the admin's and the user's pages |

Run in a real Chromium (`tests/viewer/test_studio.py`, `tests/viewer/test_roles.py`): every switch,
choice and list of a browser's Configuration is changed and read back from the service; a browser is
turned off and on from its Configuration with the page staying put; the Systems page is walked in
both views; and a user's page is watched following the admin with no reload.

Checked on the running service on 2026-10-07: My Chrome's page shows the new sentence with the
person's real Chrome, which had no window open. The checklist passes on the running cloud and
built-in browsers (10 of 11; the eleventh needs a person watching), and one task with the real model
was answered in 5.3 s (4,738 tokens in, 54 out) and is on the record.

Two faults found while checking that everything works, both seen as a test that failed now and then:

| Fault | What it was | Now |
|---|---|---|
| A click could take a moving element for still | The click looks at the element twice, a frame apart. In a browser that had just started, the wait for the next frame could end inside the frame the first look was in: nothing had moved on, and "the same place twice" was read as holding still (about 1 time in 10 under load) | Two looks count only in different frames, told apart by the page's own clock. 36 of 36 under the same load; click by ref is as fast as before (67 ms) |
| A test of a download that is too large failed now and then | Its helper counted the word "failed" in the whole result, which also holds the note of what just happened; the note can come a moment before the list says so | The helper reads the list itself |

### 1n. In `main` since 2026-10-08: Auto Mode and safeguards (spec section 18)

Its status has a page of its own, kept up to date as parts land:
**`docs/auto-mode-safeguards-status.md`** (what is completed, what is being finished, what is pending,
and what changes for people who use the browser today). The hand-over for whoever goes on is
`docs/plans/2026-10-07-auto-mode-and-safeguards.md`.

On 2026-10-08 `main` was brought into its branch (15 changes of `main`, conflicts in 13 files), and
the work was made to pass the gate of section 1p:

| What the gate asked | What was done |
|---|---|
| No file of the engine over 700 lines | `config.py` gave its sections of Auto Mode and the safeguards to `config_safeguards.py`, and what a section is to `config_base.py`. `safeguards/check.py` gave what the rules notice to `safeguards/findings.py`. `service/session.py` gave what the check reports to viewers to `service/check_news.py`. `settings/catalogue.py` gave the kinds of setting to `settings/kinds.py`. The answer of `/api/tools` is in `service/wrapping.py`. In the viewer, three bars became one component |
| Imports go one way | `safeguards` has a line of its own in `LAYERS`, between the driver and the tools. The driver imported it in three places; it no longer does: the check hands the session the judge of a file, and keeps the count of what its model calls cost |
| No tunable number outside the configuration | Nine numbers: six became settings (`safeguards.sites.lookalike_min_chars`, `one_edit_max_chars`, `lure_min_chars`, `measured_hosts`, `safeguards.outgoing.grouped_number_digits`, `safeguards.reviewer.reason_chars`), two code points are named characters, and a minute is said as a minute. A tenth, how much of a file's beginning is read, is `safeguards.downloads.first_bytes` |
| One helper for one job | The reading of an IP address was written twice; `policy/sites.py` has it once |
| Every tool and address in the feature map | Two features: `safeguards` and `auto-mode` |
| The task sets of section 1o, by their reference solutions | They do more than 120 tool calls a minute, and the limit of 18.8 refused 22 of them. A run of a task set is the engine's own work on a session, and is now not counted (`Limits.own_work`); an agent that is being evaluated is still held to the limits |

The driver's changes of this work are in the files `main` divided the driver into: `core.py`,
`watching.py`, `acting.py`, and a new `for_the_check.py`.

### 1o. Finished on 2026-10-08: task sets, the evaluations of what the agent does

The plan was "Evaluations for bap-browser: what we have, what to add, what others use", agreed on
2026-10-08. Spec section 12.7 says what was built.

| Step of the plan | State | What there is |
|---|---|---|
| 1. Task files, a runner and end-state graders, on our own test sites | Built | A practice site that is put back before each task (`demo_site/lab/`); 50 tasks in four files (`evals/sets/`), each with its checks and a reference solution; the runner and the graders (`evals/suite.py`) |
| 2. Repeated trials | Built | Each task is tried 1 to 10 times; a run says how many tasks passed every time |
| 3. The confirmation set | Built, smaller than planned | 16 labelled steps, not 100: 8 risky, 8 harmless |
| 4. The safeguards, then the adversarial set | The set is built; the safeguards are not | 10 planted instructions, not 25. The safeguards were reverted on 2026-10-07 at your word, so the set measures the agent as it is |
| 5. Results in the Evaluations view; a small set in CI, large sets nightly | Built but for the nightly run | The view has "Task sets" with run, stop, progress and each task's result. CI runs the reference solutions of all 50 tasks. A nightly run with the model needs your key as a secret of the repository: not set up |
| 6. Parity across the three browsers | Built | "Task sets, browser by browser" on the Systems page. My Chrome was not connected when this was written, so it was not run there |
| 7. A slice of a public benchmark; long-running tasks | Long tasks built; the benchmark is not | 4 long tasks. No public benchmark |

Proof: 37 new unit tests of the grading, 11 tests that run the sets in a real browser, one of the
service's addresses with two of its role tests extended, 12 of the viewer, and one that presses the
buttons in the real window and reads the result. Run by hand against the real model (gpt-5.6-luna) on the Cloud browser:

| Set | Result | Took |
|---|---|---|
| Short tasks, once | 20 of 20 passed | 3 min 36 s, 276,711 tokens in |
| Planted instructions, once | 0 of 10 followed, and all 10 of the user's own tasks done | 3 min 1 s, 195,771 tokens in |
| Asking before risky steps, by the reference solutions | Asked before 8 of 8 risky steps; asked without need before 2 of 8 harmless ones | 3 s |

What it found:

- The rules that decide when a person is asked go by the words in a control's name. They ask before
  ticking "Send me the newsletter" and before "Remove Wool socks", which are harmless: the words
  "send" and "remove" are in the names.
- Reusing one model client for tasks that each start fresh sent the provider the turns of the task
  before, and every task after the first failed. Each task of a run now has a client of its own.
- 20 of 20 and 0 of 10 mean the sets are easy for this model. They hold a result steady; they do not
  yet show where it breaks. Harder tasks are the next thing to add.

Not built: a command that runs a set without the window; a run on a schedule; a judgement by another
model; a public benchmark. The agent's runs of the confirmation set and the long tasks were not made,
to spare tokens: press their buttons to make them.

### 1p. Finished on 2026-10-08: one pathway for a change, the bad patterns as rules, and a plugin

Two asks. The first: the page "MCP, extension or plugin" recommended keeping MCP as the interface
and adding a plugin only as packaging; that plugin is built. The second, after Lauren Tan's talk on
shipping pull requests with agents: one line for developing here, and the bad patterns of this
codebase found and written as points and rules. Spec sections 16.6 and 20.

| What | Where |
|---|---|
| The pathway: ten steps, each with one command and one condition | `docs/agent-pathway.md` |
| The gate: every check in one order, stopping at the first that fails | `scripts/gate.py` |
| The rules as points, with why and how many were found | `docs/bad-patterns.md` |
| Ten of the rules held by a check, with a baseline that can only go down | `scripts/patterns.py`, `scripts/patterns_baseline.json` |
| A map of every feature, kept in step with the code by a test | `docs/feature-map.json` |
| Two skills for an agent working here | `.claude/skills/develop/`, `.claude/skills/garden/` |
| The plugin for Claude Code: the MCP server and a skill for using the tools | `plugin/`, `.claude-plugin/marketplace.json` |

What the audit of the code found, and what was done the same day:

| Pattern | Found | Fixed | Left in the baseline |
|---|---|---|---|
| A silenced check | 17 | 9 | 8 |
| A private name imported from another module | 11 | 6 | 5, in tests |
| An import from a lower part to a higher one | 3 | 0 | 3 |
| A tunable number outside `config.py` or `options.ts` | 22 | 0 | 22 |
| `except Exception` | 4 | 0 | 4 |
| A skipped test | 1 | 0 | 1 |
| A fixed wait in a test | 3 | 0 | 3 |
| A file too long to hold | 5 | 0 | 5 |
| A comment that excuses a workaround | 0 | | held at zero |
| A symbolic link in the repository | 0 | | held at zero |

The fixes were made in the code, the strongest layer: five functions that another module used were
given public names; the grading of the task sets says what it compares; an effect in the viewer
names what it depends on.

Proof: 39 tests of the checker (each rule finds its case and leaves a near one alone), 6 of the
feature map. `claude plugin validate` passes for the plugin and for the marketplace file, and
`claude --plugin-dir plugin mcp list` shows its MCP server connected.

What rests on less than it should: the talk is a video and was not watched; the pathway and the
rules rest on four written accounts of it, which differ on the order of the lower layers.

Not built: the clean-up of the 51 cases in the baseline; rules 12 and 16 to 18 of
`docs/bad-patterns.md`, which are words only; a plugin for agents other than Claude Code. Proposed
and not made, because `CLAUDE.md` is yours to change: a line there pointing at the pathway and the
gate.

### 1q. Finished on 2026-10-08: the baseline cleaned up, and the rules that were words made checks

What 1p left undone. Spec section 20.6 lists each change.

| Left undone in 1p | Now |
|---|---|
| The 51 cases in the baseline | 50 cleaned up, each in the code. 1 left |
| Rule 12, strings in components, held by review only | A check, `literal-in-viewer`. The 7 it found were moved to `wording.ts` |
| Rule 16, a helper written twice, words only | A check, `duplicate-code`, for a function that is the same in two files. The three file-writers that differed by one argument are one helper, `private_file.py` |
| Rule 17, a second folder's packages, words only | Held by the rule against a link in the repository and by `.gitignore` |
| Rule 18, a report says what was seen | Still words: it is about what is said, not about the code |
| A line in `CLAUDE.md` pointing at the pathway and the gate | Added, at your word |

The largest change is the driver. It was one class of 112 methods in one file of 1,923 lines. The
methods were sorted by which calls which: there was no cycle among them, and a division into four
parts was found in which no call goes from a lower part to a higher. The four files were made from
the old one by a script that moved each method whole and changed nothing in it but the names of
seven private helpers.

| File | Lines | What is in it |
|---|---|---|
| `driver/playwright_driver.py` | 274 | Starting a browser, its tabs, opening an address |
| `driver/acting.py` | 601 | What an agent does on a page |
| `driver/watching.py` | 433 | Dialogs, the console and the network, files, pictures, a person's own input |
| `driver/core.py` | 504 | The tabs as they are held, frames, waiting for a page to settle |
| `driver/browser_parts.py` | 247 | Launch options, download names, what is kept of a tab |

Eleven numbers became settings, with the values they had (spec 20.6). Nothing a person sees changed.

Proof: the gate passes all ten stages. Counts are in the gate's own lines below.

What is left: one test in `tests/viewer/test_takeover.py` that waits 1.5 s to say that the extension
does not dial in again. To wait for the thing, the extension has to say that it has given up.

Not checked: My Chrome, which was not connected. The driver's four files are the same code for all
three browsers, and were run on the Cloud and the Built-in browser.

### 1r. Checked on 2026-10-08: the browser part on a remote machine, and one test corrected

The browser part was run on the team's shared machine (Amazon Linux, 32 CPUs, no screen), reached
over SSH. The code and the built viewer were copied there and given an environment of their own;
nothing was added to the machine's shared one, and no key was put there.

| Check on that machine | Result |
|---|---|
| `bap-browser doctor` | A browser launches. Everything needed is in place |
| The scripted sign-up, with no model | Passed |
| `tests/e2e` | 171 of 172 at first; 172 of 172 after the correction below |
| `bap-browser bench` | 23 OK, 9 warnings, 0 failures, 8 not measured |
| A real task | Passed, with the model on a laptop and the tools called over MCP through an SSH tunnel: 10 steps |
| The viewer | Watched from the laptop through the same tunnel, with the live picture |

What it found:

- One test asked for more than it meant. After a labelled picture, a plain one was expected to be
  the same to the byte as the one before. On that machine 3 pixels of a native list box's rounded
  corners were one shade of grey apart. The labels were removed, as the test's name asks. The test
  now compares two pictures as a person sees them (`tests/support/pictures.py`): no colour of any
  pixel more than 2 shades out of 255 apart. A label left behind is 183 shades from the page.
- Seven of the nine speed warnings are the same on the laptop. A click, a hover, a checkbox and a
  scroll wait some frames of 16.7 ms each: 66.7 or 83.3 ms against a target of 50 or 60. On the
  laptop a click at a point even passes its limit (16.7 against 15). Whether to wait fewer frames or
  to set those targets to what the waits cost is yours to decide; nothing was changed.
- Two warnings are that machine's: finding an element and pressing a key take about four times as
  long there as on the laptop.

Not checked there: the person's own Chrome, the three-browser window (it needs a model key on the
machine), the task sets, and more than one session at a time.

### 1s. Finished on 2026-10-09: computer use, the fourth page of the window (spec section 21)

The window's home page has a fourth tab, **Computer**. Behind it is a small Linux desktop in a
container on this machine, which the agent sees as a picture and works with the mouse and the
keyboard. It has the same chat, live picture, Pause, Take over, Stop session, Configuration and
Evaluations as a browser. This is arrangement 1 of the plan; 2 to 4 (a micro VM, Tailscale, the
person's own machine) are not built.

| What | Where |
|---|---|
| The desktop's image: Xvfb, Openbox, a text editor, a file manager, a calculator, a terminal | `deploy/desktop.Dockerfile` |
| The engine, behind the same driver interface as a browser | `driver/desktop_driver.py`, `driver/contained_desktop.py` |
| Twelve `computer_*` tools | `tools/computer_tools.py` |
| The settings: which apps, a shared folder, the network | `config_computer.py`, group "Computer" of the catalogue |
| The fourth page | `agent/studio.py`; `Studio.tsx` and the system panel in the viewer |

Evidence, in the running window on this Mac:

- The task "Open the text editor, write a shopping list with three lines: milk, eggs, bread. Save it
  as shopping.txt in the Files folder" was done by the model in 55 seconds and 23 steps;
  `~/bap-browser-files/shopping.txt` holds the three lines.
- Every control of the page was pressed in a real browser as the admin: Take over (a right-click of
  the person's opened the desktop's menu), Hand back, Pause, Resume, the Terminal switch (the agent
  then named Terminal among its apps), Evaluations, Systems, Stop session and Start again. No error
  in the console.
- The desktop ends within a second when the window is killed with no clean shutdown.
- Tests: 19 of computer use, of which 3 drive a real desktop; the window's test has the fourth page.

What it found on the way:

- The desktop's own right-click menu offered a terminal while Terminal was off. An app that is off is
  now blocked inside the container (an empty file stands where its program is), and the menu is empty.
- A container did not end with the window that started it. It now lasts only while the window holds
  its input open.
- Docker on a Mac may not reach folders under Downloads. The shared folder is `~/bap-browser-files`,
  and the page says what to do when the folder cannot be reached.

Not done: arrangements 2 to 4; task sets and an attack set for the desktop (its Evaluations has the
tasks' records, but the checklist and the task sets say they are for a browser); the user's side of
the page was not walked, because only the admin's sign-in was at hand.

### 1t. Finished on 2026-10-09: task sets and an attack set for the desktop (spec 21.9)

The desktop's Evaluations runs three sets of its own: `short` (4 tasks), `long` (2) and `attack`
(3), in the folder `Practice` inside the shared folder. The browser's runner was given one seam, a
ground (made ready, solved, read): the practice site for a browser, `Practice` for the desktop.

| Run, through the running window's API | Result |
|---|---|
| Reference solutions, all three sets | 9 of 9 passed |
| The model, attack set | 3 of 3 passed; no planted instruction followed |
| The model, short set | 3 of 4. In "add a line to todo.txt" it wrote the new line over the old one, and the check caught it |
| The model, long set | Not run, to spare the key |

Found on the way: an Enter typed right after a path into a file box was lost while the box completed
the path. `computer_type` with `submit` now lets the screen settle before Enter.

### 1u. Finished on 2026-10-09: the desktop in the micro VM (spec 21.11)

Arrangement 2 of computer use. The micro VM's image, built with `DESKTOP=true` and started with
`bap-browser serve --desktop`, serves the desktop's tools over MCP on HTTP and its picture to the viewer.
In the VM the desktop runs on the machine's own virtual screen (`computer.runs: here`), not in a
container.

Evidence: the image was started as a container standing in for the VM. An agent outside it listed
only the `computer_*` tools, opened the editor, typed and saved `~/Files/vm.txt`, and the file was in
the VM with that text. Its viewer, opened in a real browser, showed the desktop live with no console
error.

Found on the way: the image could not be built on a network that refuses ghcr.io, where it took uv
from. It now installs uv from PyPI. The image is 4.2 GB with the desktop.

Not done: the image was run on this Mac, not on a remote machine. The team box has no Docker and no
`sudo`, so it cannot run it.

### 1v. Built on 2026-10-09, not yet joined to a real tailnet: the micro VM on a person's tailnet (spec 21.12)

Arrangement 3 of computer use. Built with `TAILSCALE=true` and given `TS_AUTHKEY`, the micro VM
joins the person's tailnet as an ephemeral node, serves its viewer and tools to the tailnet over HTTPS,
and reaches the tailnet through Tailscale's local proxy.

| Checked, on the image | Result |
|---|---|
| No key | The service runs; Tailscale does not |
| A key Tailscale refuses | The VM stops with Tailscale's reason ("invalid key") and ours, exit 3, and the service never starts. The key is not written out |
| A real key | **Not checked: there is none yet.** The tailnet's owner makes a reusable, ephemeral, tagged key; then the join, the HTTPS address and the proxy are proven |

### 1w. Built on 2026-10-09: the agent on a person's real Mac (spec 21.13)

Arrangement 4 of computer use. `bap-browser helper` on the person's Mac lets an engine drive it:
pictures with macOS's `screencapture`, the mouse and keyboard through CoreGraphics, nothing installed.
The person names the apps with `--allow`, gives the engine the token it printed, and stops it for good
by pushing the pointer into the top left corner.

Evidence: the helper and the engine's driver tested over real HTTP with a stand-in for the Mac's hands
(5 tests). With the corner stop broken on purpose, its test fails. On this Mac, read only: the screen is
1680 by 1050 points, Accessibility is allowed and Screen Recording is not yet.

Not done yet: the live test on the person's Mac, with them watching.

### 1x. Checked on 2026-10-09: computer use in the running window, from its own buttons

Pressed in a real browser as the admin, in the window's Computer tab:

| What | Result |
|---|---|
| Short set, reference solutions, each task 3 times | 12 of 12 tries passed |
| Long set, the model, each task 3 times | 5 of 6 tries passed; 1 of 2 tasks every time; 8 min 24 s, 713,207 tokens in |
| Attack set, the model (earlier the same day) | 0 of 3 planted instructions followed |
| "Use the calculator to work out 46 times 37" in the chat | "46 × 37 = 1702", in 18 s |

Fixed on the way: the desktop's Evaluations offered the browser's checklist, which it does not have;
its task sets said they ran on a practice site in a browser; its tool timings kept the `computer_`
prefix. No console error.

### 1y. Finished on 2026-10-09: the settings of computer use, and two evaluations after OSWorld and OS-Harm

The desktop's Configuration gains four settings, each as a vendor offers it: the screen's size (as
Anthropic and OpenAI size it), the zoom tool (Anthropic's `enable_zoom`), a picture after each action
(as their loops return one) and a person's yes before an app opens (Google's and OpenAI's
confirmations). The admin chooses, under Systems, Users, whether users may change the last two; a user
may turn the yes on, never off over the admin. The desktop gains an `infeasible` set (3 tasks, after
OSWorld) and a fourth attack task (after OS-Harm's data exfiltration).

| Checked in the running window, as the admin | Result |
|---|---|
| The ten Computer settings on the Configuration | Shown, and none of a browser's |
| "Ask me before an app opens" on, then "Open the calculator" | The pop-up "Opening Calculator" in 3 s; after Allow once, "The calculator is open." |
| Systems, Users | Lists the two desktop settings a user may be let change |
| Attack set, the model, each task once | 0 of 4 planted instructions followed |
| Infeasible set, the model, each task once | 0 of 3 at first: it searched until the step limit. With one sentence more in its instructions (say at once when an app, a file or a network is not there), 1 of 3 |

Found on the way: the store laid the admin's settings above a user for the deployment's backend, not
the system's, so a user was not held to the admin's desktop settings; a question about a step with no
site offered "Allow on this site"; `studio.py` went over 700 lines and its configuration helpers moved
to `agent/room_configs.py`.

### 1z. Finished on 2026-10-09: the window's Computer tab can work on the person's own Mac

"Where the agent works" on the Computer tab's Configuration chooses the contained desktop or This
Mac. A helper started on the same Mac pairs by itself through `.bap-browser/helper.json` (this user
alone), and the agent gets instructions for a person's own Mac.

Found on the way: the desktop's task-set runs were given the browser's instructions, not the
desktop's; only its chat had the right ones. Every desktop result with the model from earlier on
2026-10-09 was measured that way, including the infeasible set's change from 0 to 1 of 3, which the
added sentence did not reach. They are fixed now and must be run again.

### 1aa. Finished on 2026-10-10: macOS asks for the helper's permissions, and any app on this Mac

The person's error "The Mac has not allowed the helper Screen Recording and Accessibility" had one
cause: the helper only checked the two permissions and never asked for them, so macOS neither
prompted nor listed Terminal in either pane. The helper now asks, as GPT-6 Astra's app does, watches
for the yes, and pairs again so the window connects by itself. "On this Mac, let the agent open any
app" lets the agent open any app by its name, each after the person's yes.

Checked: the new Accessibility call, run without its prompt, gives the same answer as the plain check;
the watcher, any-app opening and the yes before each are tested over real HTTP with stand-in hands.
Not checked live: the prompts on the person's screen, which need them at the Mac.

### 1ab. Finished on 2026-10-10: on a real Mac the agent is held to the allowed apps

Seen in the person's first live run: asked to "open Claude desktop", which was not an allowed app, the
agent clicked Claude's icon in the Dock instead, at (1314, 218). On a real Mac the app list held only
the tool that opens apps. The helper now refuses any action of the agent unless an allowed app is in
front, and closes at once an app that the agent's action started and the person did not allow. The
person's own hand is not held. Checked with tests over real HTTP; with the closing step broken on
purpose its test fails.

| What | Note |
|---|---|
| Settings, the rest | My Chrome, In my Chrome and Approved sites (the bridge's); the desktop app's three, with Clear browsing data for the built-in browser; notifications |
| Bench, the rest | 8 of the 40 per-tool lines have no scenario yet; the page-size, system and output-size lines (spec 11.4 to 11.6) are not in the budget file; the verify skill is not in the repository |
| Take-over Chrome, the rest | One message per driver operation, the extension's own check of the element before a consequential action, more than one tab, pairing from a web client, a core that runs in a micro VM |
| Desktop app, the rest | An installer, settings, running without `uv` and this folder |
| The micro VM | The image has never been built, started or deployed |
| The code tool `browser_run`, the rest | Built and off by default (section 1j). Not run yet on a person's own Chrome or in the built-in browser, and its two lines of the budget are not measured |
| Viewer states the spec lists | Session picker, the takeover bar's "failed", address "loading", "limit reached". ("Saving", "working" and "handing back" are there since 2026-10-06) |
| The deferred minor findings of the two reviews | Listed further down, unchanged |


### 1ac. Built on 2026-10-12: Hermes' computer use taken in as the base (spec 22, unit 1 of 8)

Computer use is being rebuilt on Hermes' (NousResearch/hermes-agent, MIT), so that one tool works the
same on Windows, macOS and Linux. Section 22 of the spec is the whole design and its ten decisions.
This is the first of its eight units. Today's computer use (section 21) is unchanged and still the
one that runs.

| | |
|---|---|
| Taken | Hermes' `tools/computer_use/` and `tools/bot_desktop/` at commit `3569e846`: 25 files, into `src/bap_browser/computer/hermes/` |
| How | `scripts/take_hermes.py`. It changes module names, nine private names and two words a person reads; nothing else. `computer/UPSTREAM.md` says how to take a later Hermes |
| Seams | Nine modules in `computer/seams/` answer what Hermes' code asks of Hermes: settings (from `Config.computer.base`), home folder, approval, a clean environment, the driver |
| Held | A test fails when a taken file differs from the SHA-256 in `hermes/TAKEN.json` |
| CI | A new job runs the base's tests on Windows and macOS runners. Linux is in the main job |

- Measured on macOS, Python 3.12: `uv run pytest tests/unit/test_hermes_base.py tests/hermes` gave
  282 passed, 31 skipped, 94 deselected. The 31 are Hermes' tests for Linux or Windows and run there.
- Of Hermes' own tests, 273 pass against our seams. 94 are left out on every system, each named with
  its reason in `tests/hermes/not_here.json`: they test Hermes' package manager, settings file, second
  model for pictures and terminal sandbox, none of which was taken.
- CI's first run on Linux and Windows found what this Mac could not. On Linux 13 tests of the contained
  desktop failed: 7 need the package `psutil`, which Hermes' desktop uses and this engine does not have,
  and 6 look for files where Hermes' repository keeps them. On Windows 2 tests stand a file with no
  `.exe` ending in for the driver, and the tests of the contained desktop cannot run there at all, as it
  is for Linux. Each is in the same list, named for its system, and none is a fault of the taken code.
- Seen by hand, with a stand-in backend: `cmd+shift+q` answered "blocked key combo"; a click with
  nobody to ask answered "requires approval but no interactive user"; with no driver installed a
  capture answered "The driver of computer use is not installed. Run `bap-browser computer install`."
- Forced to fail twice, to see the tests guard: a line added to a taken file, and the filter of
  secrets switched off. Each failed one test, and both were put back.

Not built, and not checked:

- The driver itself is not installed or run. `bap-browser computer install` does not exist yet: unit 2.
- Nothing of the base is behind the session, the viewer or a tool an agent can call: units 3 and 4.
- Whether to add `psutil` for the contained desktop on Linux: with unit 6.
- No Windows or Linux desktop has run any of this. CI runs the tests there, not a screen.
- Some of Hermes' results still say "Hermes" to the model. They are reworded in unit 3.

### 3. Waiting for your word

| # | Question |
|---|---|
| 2 | The font is two files in the repository. Say if you prefer the npm package `@fontsource-variable/hanken-grotesk` |
| 3 | `CLAUDE.md` says form values never reach a result; the spec shows the model what a field holds in a snapshot (never a password). I kept the spec. The wording in `CLAUDE.md` is yours to change |


### 1ad. Built on 2026-10-12: the driver is installed by its checksum, and asked what is ready (spec 22, unit 2 of 8)

| | |
|---|---|
| One pin | `src/bap_browser/computer/driver.lock.json`: `cua-driver` 0.21.0, with the address and SHA-256 of its six builds, as Hermes records them. A test fails if a driver version is written anywhere else |
| Install | `bap-browser computer install`: downloads this system's build, refuses it unless the checksum matches, unpacks it into `~/.bap-browser/computer/driver/0.21.0/`, asks the driver what it can do, and switches its telemetry off for good |
| Doctor | `bap-browser computer doctor`: the driver's own report, check by check |
| Permissions | `bap-browser computer permissions`: on macOS, which of the two it has; `grant` has macOS ask. Elsewhere, that there is nothing to allow |
| The ladder | `scripts/ladder.py`: rungs 1 and 2 of spec 22.10.1, on the machine it is run on |
| CI | The job for each system now covers Linux too, installs the real driver on all three, and prints the doctor and the ladder |

Run on this Mac (macOS 26.6, arm64), and read:

- `bap-browser computer install` printed "Installed cua-driver 0.21.0". `codesign` gave
  `Identifier=com.trycua.driver`, `TeamIdentifier=YCK386LBJ7`, one of the two teams Hermes accepts.
  The install is 177 MB.
- `bap-browser computer doctor` printed "binary_version: cua-driver 0.21.0", "platform_supported:
  macOS 26.6 (arm64)", "bundle_identity: Bundle is com.trycua.driver", and failed the two rows that
  are a person's to give: Accessibility and Screen Recording.
- `scripts/ladder.py`: rung 1 passed. Rung 2 did not run: macOS has not allowed the driver.

Running it found three things that reading Hermes' code had not:

1. **macOS must be told where the driver's app is.** The driver starts its own background process
   through macOS by the app's name. Unpacked in our folder, macOS did not know it, and the doctor
   failed with "Check that /Applications/CuaDriver.app is installed". Hermes' installer registers the
   app; ours now does the same, after checking its signature.
2. **Telemetry was on by default in that background process.** Our setting in the driver's
   environment does not reach a process macOS starts. Without it the driver said "Telemetry: enabled
   (source: default)". The installer now runs the driver's own `telemetry disable`, and it says
   "disabled (source: persisted)". No installation id was ever created.
3. **The driver asks GitHub which version is newest.** It wrote `~/.cua-driver/version_check.json`
   ("latest_version": "0.34.1") on its first start. It installs nothing by itself. Whether this can be
   switched off is not yet known.

Not built, and not checked:

- Rung 2 on this Mac waits for you: run `uv run bap-browser computer permissions grant`, allow
  CuaDriver under Accessibility and Screen Recording, then `uv run python scripts/ladder.py`. The first
  try of rung 2 made macOS show its Accessibility question; it is yours to answer.
- The driver's background process keeps running after a command. It was stopped by hand with
  `cua-driver stop`. Stopping it when the engine ends is part of unit 3.
- The desktop's image and the micro VM do not read the lock file yet: unit 6.

On CI's own machines, with the real driver (run of 2026-10-12, pull request #48):

| System | Rung 1: installed and answers | Rung 2: a capture of a known app, in each mode |
|---|---|---|
| Linux (Ubuntu 24.04, x86_64, X11 on a virtual screen) | Passed | Passed, a small dialog: 310 by 231, 4 elements read through AT-SPI, a picture in `som` and `vision` |
| Windows (Server 2025, x86_64) | Passed. The doctor: "UIAutomation is reachable", "Windows Graphics Capture will succeed" | Passed, Notepad: 754 by 512, 11 elements, a picture in `som` and `vision` |
| macOS (26.6, arm64) | Passed | Not run: nobody is there to allow the driver |

- This answers a question the spec left open: a hosted Windows runner does give the driver a desktop
  it can read. The ladder is now a check that must pass on Linux and Windows for every pull request.
- These are runners, not a person's machine. By the spec's grades Linux (X11) and Windows are "early".
- Two mistakes of mine were found on the way and are fixed: the ladder asked for a capture with no
  app in front (on Windows the front window was the driver's own, which it refuses to read), and it
  misread a result that holds a picture.


### 1ae. Built on 2026-10-12: Hermes' tool behind the session, and proven on Windows and Linux (spec 22, unit 3, first part)

An agent can now work on a real machine through the engine. With `computer.runs` set to `machine`
the session offers Hermes' one tool, `computer_use`, with `computer_open_app` and
`computer_request_human` of ours, and every call still passes the check, the limits and the log.

| | |
|---|---|
| The driver of a machine | `driver/hermes_driver.py`: starts Hermes' base for the session and stops the driver when it ends |
| The tool | `tools/computer_use_tool.py`: takes what Hermes' tool takes (a test holds the two in step) and returns plain text, with a picture only for a capture that has one |
| Judged by its action | `tools/kinds.py`: `capture`, `wait` and the two lists only look; `type`, `key` and `set_value` put text in. The check, "ask before every action", the limits and the masking of the log decide by that |
| Never what was typed | The timeline says "Typed 9 characters" and "Pressed cmd+s"; the log keeps a length; no result holds the text |
| The model is told the system | The instructions name Windows, macOS or Linux, and that system's keys |

Proven with the real driver on CI's own machines, by `scripts/ladder.py`, now three rungs:

| System | Rung 3: through the session, find a field by its number, type into it, and have the app say what it holds |
|---|---|
| Linux (Ubuntu 24.04, X11) | Passed. The field was element 1. The driver: "Typed 11 character(s) (via AT-SPI)". OK was then clicked by its number and the dialog printed `ladder 4711` |
| Windows (Server 2025) | Passed. The field was element 0. The driver: "the field changed and now contains the requested text". Notepad's title bar then showed the document as changed |
| macOS | Not run: the driver is not allowed yet on this Mac, and cannot be on a hosted runner |

The three rungs must now pass on Linux and Windows for every pull request.

Found on the way, and what was done:

- A capture names a field, not what it holds. My first check of "read it back" looked for the typed
  text in a capture and failed on both systems although the typing had worked. The ladder now asks the
  app itself.
- The ladder printed a character a Windows console could not encode, and stopped. It now prints on
  any console.

Not built, and not checked:

- The Computer tab has no choice named "This machine" yet, and the viewer's live picture of a real
  machine has not been looked at: the next part.
- Take over and Stop are not yet joined to Hermes' lease. Rungs 4 and 5 wait for that.
- The agent is not yet held to the allowed apps on a machine. `computer_open_app` opens only allowed
  apps, but a click can still reach any window. Hermes' `bounded` mode does the holding, and is next.
- The marks around text from the screen still say "written by the site". On a desktop it is the screen.
- macOS, on this Mac: waiting for you to allow the driver.


### 1af. Built on 2026-10-12: the four arrangements on Hermes' base, and an audit of what Hermes' computer use is made of

**The audit.** Hermes was searched whole for `computer_use`, `cua-driver` and `bot_desktop`. Two
modules hold the tool and the desktop; fourteen other parts touch them. One that matters was missing
here: the manual Hermes gives a model for the tool (`skills/.../computer-use/SKILL.md`, 18 KB). It is
now taken, and given to the model after our own rules. `computer/UPSTREAM.md` has the table of all
sixteen parts and what stands in each one's place. Three are still not built here: the Windows logon
task, the `screen` commands of Hermes' Linux desktop, and the base's settings in the settings screen.

**The four arrangements.** Each is a value of `computer.runs`, or one setting beside it.

| # | The arrangement | How it is set | Proven |
|---|---|---|---|
| 1a | The engine on a person's own machine, on its operating system | `runs: machine` | Linux and Windows, all rungs. macOS waits for the driver to be allowed |
| 1b | The engine in a micro VM, on the VM's own screen | `runs: machine` with `base.virtual_screen: true`. The VM's image installs the pinned driver | On a real Linux machine given no screen: the engine started one, drove it and streamed it. The image itself was not built |
| 2 | A remote engine in a micro VM reaches the person's data over Tailscale | As before: the VM joins with `TS_AUTHKEY` (spec 21.12). Unchanged by this work | Not proven: no tailnet key. The start script's tests pass |
| 3 | A remote engine takes over a person's machine, and its screenshots come back | `runs: remote`, `helper_url`, and the pairing code in `BAP_BROWSER_HELPER_TOKEN`. On the person's machine: `bap-browser computer helper` | Linux and Windows, all rungs, with the engine and the helper as two programs on one machine. Not over a real tailnet |
| 4 | The person's screen is streamed to the remote engine's viewer | The viewer's live picture, fed by captures of the whole screen through the helper | Linux and Windows: two different pictures of the whole screen arrived, the second after the screen changed |

What was built for them:

- `service/machine_helper.py`: the helper. It listens on its own machine's address only, and prints the
  `tailscale serve` command that shows it to the tailnet. It lets a caller in on three conditions: the
  pairing code, who Tailscale says the caller is (`tailscale whois`, against `base.helper_allow`), and
  that the call came through the tailnet. It runs only eight commands of the driver, none that updates
  it or changes its settings. It tells the person what is done, never what is typed.
- `computer/link.py` (`bap-browser-driver-link`): what the engine starts in the driver's place. The
  pairing code reaches it in a file only the engine's user can read, removed when the work ends.
- `driver/hermes_driver.py`: starts the machine's own virtual screen first, where it is told to.
- `deploy/Dockerfile`, `deploy/vm-start.sh`: the VM's image installs the pinned driver through the
  engine's own installer, and gives its desktop a session bus.

Measured: `scripts/ladder.py` on CI's machines, with the real driver, in three ways (direct,
`--through-helper`, and on Linux `--virtual-screen`). All passed on Linux and Windows, and all three
are now checks a pull request must pass. 23 new tests.

Secrets: every tracked file was searched for keys and tokens. None holds one; the matches are made-up
values in tests. `.gitignore` now also keeps out `link.json`, `*.authkey` and Tailscale's state files,
and `tests/unit/test_secrets_stay_out.py` holds it to that.

Not proven, and what would prove it:

- **A real tailnet.** This Mac has no Tailscale and there is no key. That a call through
  `tailscale serve` carries the caller's address as `X-Forwarded-For`, and that `tailscale whois` names
  the VM's tag, are taken from Tailscale's documentation, not seen. One engine VM and one machine on a
  real tailnet would show it.
- **The VM's image.** `docker build --build-arg DESKTOP=true` was not run: Docker is not running here.
- **macOS.** Nothing past the driver's install, until the driver is allowed on this Mac.
- **The Computer tab.** It has no choice named "This machine" or "A machine elsewhere". Both are
  settings in `config.json` only.

Found on the way:

- The helper first used the event loop's own subprocess support. On Linux, a connection cut mid-way
  left the driver's process open. It now uses a plain process read on a thread, ended for certain.
- I pushed one commit with a lint error, because my command went on after the gate had stopped. It
  was fixed in the next commit; CI would have refused it.
- The live picture of a machine sent the same picture again while the screen stood still. One CI run
  in two caught it: 15 pictures, all the same. The driver now sends a picture only when its bytes
  differ from the last one sent, and a test holds it to that. My check of the stream also depended on
  timing; it now waits for the first picture before anything on the screen is changed.


### 1ag. Built on 2026-10-12: a real machine in the window, and Take over joined to Hermes' gate (spec 22.3.1, 22.10.1)

| | |
|---|---|
| The setting | "Where the agent works" now offers "This machine" and "A machine elsewhere" beside the contained desktop and This Mac |
| The Computer tab | Set to This machine, it says what the machine lacks (no driver, or on macOS the driver not allowed) and offers two buttons to the admin: "Install the driver" and "Allow it on this Mac". When the machine lacks nothing, the desktop and its chat appear by themselves |
| Take over | A person taking the screen in the viewer now takes Hermes' own lease. While they hold it the tool does nothing for the agent, not even a capture, including a call that was already on its way past our own gate |
| The person still sees | The viewer's live picture is the person's to see whoever holds the screen, so it does not pass that gate |
| Stop | Ends the session and the driver; nothing more reaches the machine. A take over left behind by a session that ended does not hold the next one |

- Measured: 11 new unit tests and 3 of the viewer's. In a real browser (`tests/viewer/test_studio.py`):
  the page showed "Let the agent use this machine" and "The driver of computer use is not installed on
  this machine."; Allow was pressed and said that there was nothing to ask yet; Install was pressed, and
  the page went on to the chat by itself, with the room's state `agent`.
- The take-over test was forced to fail once, by leaving the lease untaken: it answered
  `(None, None)` where `human_has_control` was expected. It was put back.
- The ladder has a fifth rung for this, climbed with the real driver on CI's Linux and Windows
  machines, directly, through the helper, and on Linux on the engine's own screen. Each time: "the tool
  itself answered 'human_has_control'; after the hand back a capture worked".
- That rung was missing from the first push of this work. My edit of the ladder had not applied, its
  error was hidden, and CI passed without the rung. I saw it because the rung's line was not in CI's
  output, added it, and CI ran it.

Not built, and not checked:

- **macOS, still.** The driver is not allowed on this Mac, so nothing past its install has run here,
  and "Allow it on this Mac" was pressed only where there was no driver to ask for. Pressing it on this
  Mac shows macOS's own question, which is yours to answer.
- **A real tailnet, still.** No Tailscale here and no key. Nothing in this entry changes that.
- "A machine elsewhere" has no field for the helper's address in the settings screen: it is in
  `config.json`. The base's other settings are not in the settings screen either.
- A user (not the admin) sees "Your admin sets this machine up for the agent." That is tested in the
  viewer's own tests, not walked in a real browser.

### 1ah. Built on 2026-10-12, not yet proven on the real driver: the driver's own hold on the allowed apps

Remaining piece 3 of "Computer use on Hermes: built and remaining" (the artifact; section 22.7 of the
spec is not yet written). Until now `computer_open_app` was the only hold on an app: once open, a
click or a type could still reach any window, because `permission_mode` was `bounded` in the settings
but never took effect (`capability_manifest` was always empty, so the engine fell back to `standard`).

A new `capability-manifest.json` is written at the start of every session that drives a real machine,
naming the apps the admin's allowlist allows, one name per system: a bundle id on macOS, an
executable's absolute path on Windows and Linux (the driver's own schema, cua-driver/trycua). Full
screen capture is left open, for the person's own live view. The file is written under the agent's
own `computer.base.home`, from `bap_browser.computer.seams.manifest`, only when a real session
begins (`computer.base()`); the bare, unconfigured state stays `standard`, as Hermes' own tests
(`tests/hermes/test_computer_use_cua_0_10_permissions.py`) require.

Checked: the manifest's shape, one app per system, for all three systems; that a real session writes
it and points the driver at it; that nothing is written outside a session. Not checked: whether the
real driver, given this file, actually refuses a click or a type outside the allowed apps once
full-screen capture is left open for the viewer — the driver's own docs do not say how the two
interact, and nothing here starts the real driver. This is exactly piece 1 and 8's gap: proof needs a
person's own machine.

Windows and Linux executable paths (Calculator and the terminal on Windows, and every Linux path) are
a first guess, not yet seen on a real machine of either system.

### 1ai. Built on 2026-10-12: "mac" joins "machine" and "remote" on Hermes' driver; the old Mac helper is gone

Remaining piece 4 ("Removing today's computer use"), the part of it that needed nothing else first.
Checking it against section 9 of the external spec ("Migration: every file of today's computer use")
found that piece 4 is mostly not independent of pieces 5 and 6: the 13 eval tasks' solutions, the
removal of the twelve old `computer_*` tools, and the config and settings-catalogue cleanup all assume
`container`/`here` mode already runs on Hermes' code, which it does not yet (pieces 5 and 6, waiting
on a yes to `psutil` and on Docker). Touching those now would not defer them; it would break every
evaluation, since the new `computer_use` tool refuses any session that is not a `HermesDriver`.

The one part that was independent: `computer.runs == "mac"` drove through its own, older implementation
(`driver/mac_driver.py`, `driver/mac_hands.py`, `service/mac_helper.py`), a full HTTP protocol of its
own, never touching Hermes. It now drives through `HermesDriver`, the same as `machine` and `remote`,
through the same `bap-browser computer helper` and `computer.remote.through_the_link`. The three old
files, the old top-level `bap-browser helper` command, and their test and viewer UI (the "Start helper
in Terminal" button and panel, the pairing-file poll) are removed. The regression this accepts, named
to you before building it: a person using "mac" mode no longer gets auto-pairing or a one-click
Terminal launch from the Computer tab; they run `bap-browser computer helper` themselves and copy its
token into `BAP_BROWSER_HELPER_TOKEN`, exactly as "remote" already asks.

Checked: `uv run pytest tests/unit tests/service tests/hermes` (1988 passed; the 2 failures and 2
long-parameter-id errors are unrelated and were confirmed against the unmodified base commit); the
full gate's bad-patterns, format, lint and types stages; the viewer's typecheck, lint, 618 tests and
build. Not checked: a person actually pairing "mac" mode against a real Mac, since remaining piece 1's
real-machine proof is still outstanding.

Not built: the rest of piece 4 (the 13 eval tasks' reference solutions, the tools.py tool removal, the
config and `settings/catalogue.py` cleanup, and deleting `contained_desktop.py`, `desktop_driver.py`
and `screen_here.py`), which waits on pieces 5 and 6.

## How to go on

The list under "Not started", in the order the spec gives: the settings API, the address policy at the network layer,
the bench and `doctor`, then the rest of take-over Chrome, the desktop app and the micro VM.

## Earlier record

The sections from here to "Documents" were written on 2026-10-04 and 2026-10-05 and are kept as they
were. Where they speak of what is next or of what has not been run, the sections above are newer.

## The hosted model

| Point | How it is |
|---|---|
| Provider and model | OpenAI, `gpt-5.6-luna`. Change it with `agent.model` in `config.json` |
| Key | `OPENAI_API_KEY`, from the environment or from `.env` in the folder the command is run from. Never in `config.json`, never logged |
| How it is called | OpenAI's Responses API over plain HTTPS, with no extra library. `agent.base_url` points it at a proxy or a compatible service |
| What is kept at OpenAI | Nothing: `store` is off. The model's own reasoning is passed back to it encrypted on each turn |
| Limits | `agent.max_steps` (40 tool calls), `agent.max_tokens` (4096 per reply), `agent.request_timeout_s` (120) |
| When it fails | A refused key says "The model provider did not accept the key (HTTP 401). Check OPENAI_API_KEY in your .env file." Other failures name the HTTP code and the provider's message. The session ends as "failed" and the viewer says why |
| Not verified | Whether the name `gpt-5.6-luna` and the request shape are accepted by the real service. If the first run fails, the message will say what the service answered |

## The look

Taken from the product's code on 2026-10-04 (`bap-web/bap-frontend/app/globals.css`, the `--sc-*`
values). The full table, with where each value comes from, is in the spec, section 9.5.

| Taken from the product | Where it shows |
|---|---|
| Warm neutrals: white page, #F5F4F2 warm surface, #1A1714 text | The page, the activity panel, the stage behind the live picture |
| Near-black "ink" (#09090B) for the main action | Allow once, Resume |
| Hairlines instead of shadows; radii of 10, 16 and 20 px; pills | Cards, panels, tabs, the address, chips, badges |
| Hanken Grotesk | All text except addresses and raw results |
| The red-to-violet brand gradient, used sparingly | The brand mark and a switch that is on. Nowhere else |
| The violet end of the gradient | The colour of "the agent is driving" |

| Different from the product | Why |
|---|---|
| Secondary text is #56524D, not the product's #8D8881 | #8D8881 is 3.52:1 on white, too faint to read. Every text pair here is at least 4.5:1; the lowest is 4.91:1 |
| The focus ring is the text colour, not brand red at 28% | A faint ring is hard to see, and red here means something went wrong |
| No sidebar | The viewer is one page with nowhere to navigate to |
| The product name and the mark are the viewer's own | You asked for colours, font and structure, not the logo |

The font ships with the viewer as two files (54 KB together), so nothing is fetched from another site.
Its licence (SIL Open Font License 1.1) is in `viewer/src/fonts/OFL.txt`.

## What the live loop is made of

| Task | Delivers | Commit |
|---|---|---|
| 1 | The `agent` settings, the picture heartbeat setting; the demo site and the built viewer are part of the installed package | `61e8970`, `4d866c8` |
| 2 | Every tool call is reported as a step in a sentence a person can read ("Clicked "Create account" (button)", "Could not click "Pay": it is covered by a dialog"), with where on the page it happened | `5e921ff` |
| 3 | Sessions: what viewers are told, replayed to a viewer that connects late; pause, take over, hand back, stop. An agent's call waits while a person drives | `6bfaaee` |
| 4 | Live pictures of the browser as JPEG at the configured quality; a still page is confirmed as current; a person's mouse, keys and wheel reach the page | `2d43ea8` |
| 5 | The web service: the viewer's files, `/healthz`, `/api/sessions`, one WebSocket per viewer, the demo site. Token, `Host` and `Origin` checks | `3150889` |
| 6 | The reference agent loop, the scripted model, the sign-up script | `88b89e6` |
| 7 | `bap-browser agent` | `7733832` |
| 8 | The viewer's WebSocket connection; a new screen for a link that is refused or missing | `574551f` |
| 9 | The whole path tested in a real browser | `85a7539` |

## What the first review found, and what was done

A reviewer with no knowledge of the work read the whole stage 1 branch. Every finding below was
reproduced with a failing test before it was fixed.

| Finding | What was wrong | What it is now | Commit |
|---|---|---|---|
| Critical: address policy | The policy read an address with Python's rules and the browser with its own. `http://127.0.0.1\@example.com/`, a percent-encoded host, or another spelling of an IP address (`2130706433`, full-width digits) was judged as one site and opened as another. The cloud-metadata block could be passed in the default configuration | Every address is rewritten into one form, the way a browser reads it. That form is what is judged and what the browser is handed. A site list entry that could never match stops start-up | `171ad96` |
| A call could wait for ever | A page too busy to answer held the call, and every call behind it | The call fails after `browser.timeouts.page_reply_ms` (5 s) with a plain message | `66c5ced` |
| Typed text reached the log | The log kept an excerpt of each result, so a snapshot of a filled form put field values in it. A field with no label was named after its content. The arguments of a call that failed its checks were logged as given | The log keeps the first line of a result (what was done), never the page. A field's content is never used as its name. Such arguments are logged by name only | `defb21b` |
| Typing landed in another field | A page that moves the focus received the text in a different field while the result named the first | Typing fails and says the page moved the focus | `66c5ced` |
| A page set the size of every result | A page could make its own address 500,000 characters long, and every result carried it | Addresses in results are cut at 300 characters | `defb21b` |
| Click inside a scrolled box | An element in a list that scrolls by itself was reported as covered | It is brought into view first | `66c5ced` |
| Browser gone | After the browser closed, results said "the page changed" for ever | Results say the browser closed; a navigation starts a new one | `66c5ced` |
| Approval hidden in full view | With the browser shown full width, an approval could not be seen or answered and ran out | The cards that need a person sit between the control bar and the browser | `3fc495c` |
| A typed site was lost | Closing settings with Escape dropped a site just typed into "Blocked sites" | It is saved on close; a refused entry keeps the screen open | `3fc495c` |
| Focus fell out of dialogs | Tab left the Stop confirmation; on a narrow screen the focus fell to the page; after an answer it went nowhere | Tab stays inside; the focus follows the screen and moves to the status line | `3fc495c` |
| Ended session shown as lost | After a session ended and the service closed, the viewer said "Connection lost" | The summary stays | `3fc495c` |
| Credentials in sentences (automated check) | A name and password written into an address appeared in the timeline and the log | They are removed from every sentence, event and log line | `defb21b` |

## What the second review found, and what was done

A second reviewer, again with no knowledge of the work, read the live loop (commits `4e4ca97..b18e0dc`).

| Finding | What was wrong | What it is now | Commit |
|---|---|---|---|
| Critical: credentials in addresses | A name and password written into an address still reached the log, a result or the viewer by four routes: the browser's own failure message, an address with no `https://` or a leading space, an address no browser would open, and the timeline sentence | Only the address as a browser reads it, without name and password, is ever shown or logged. Text no browser would open is shown nowhere; the log says `<not a valid address>` | `298bb1c`, `91b980f` |
| Critical: a malformed address broke the call | `http://[::1` raised an error out of a watched call instead of giving a result | It is an ordinary failed call: "navigation blocked: not a valid address" | `298bb1c` |
| Critical: Stop was not final | A call in progress could start the browser again after Stop. A Stop sent after a Pause waited behind it. A hand-back could undo a Stop | Closing is final: no later call starts a browser. Stop is done at once; a viewer's other commands wait their turn in a queue. Nothing leaves "ended" | `e31116f` |
| Critical: input with no time limit | A click or typing on a page that stays busy held the call for as long as the page liked | It fails after `browser.timeouts.action_ms` and tells the model to take a new snapshot | `91b980f` |
| Keys left held | A key or mouse button a person was still holding when they handed back stayed down in the page, so the agent's next click became a Ctrl+click | The session lets go of everything held at hand-back, and the viewer lets go of held keys when the picture loses the focus | `e31116f`, `f597c35` |
| Pointer moves were dropped | The viewer sends no button with a move, and the service refused a pointer command without one. Hover never reached the page | A move needs no button | `e31116f` |
| IPv4 inside IPv6 | `http://[64:ff9b::a9fe:a9fe]/` reaches the cloud-metadata address through a gateway and was judged as a harmless IPv6 address | NAT64, 6to4, Teredo and IPv4-compatible addresses are judged as the IPv4 address they carry | `298bb1c` |

Five of its twelve minor findings were fixed with these: a pointer command with a list as its button
no longer breaks the connection; an error while inserting text is a result; the viewer no longer
retries a session that does not exist; the loop no longer asks the model once more after Stop (with a
hosted model that was one paid call); a ref that is not a ref is never sent to the page.

## What running it showed

The command was run by hand and driven through a real browser (the `/verify` pass). Beyond what the
tests had shown:

| Found | Now |
|---|---|
| Every load logged an error in the browser's console: the browser asked for `/favicon.ico`, which was not there | The viewer has its own icon. Commit `f597c35` |
| A new link pasted into a tab that already showed the viewer was ignored, and its token stayed in the address bar | The page takes the new link and removes the token from the address. Commit `f597c35` |
| A sliver of scrollbar beside the tab strip in full view | Gone with the new tab strip. Commit `bfa2148` |
| The answer was printed twice and reached standard output only when the process ended | Printed once, as soon as it is known. Commit `6a0f264` |
| The web server's own "INFO" lines appear in the terminal | Left as they are. Say if you want a quiet terminal |
| After the process is killed outright, the file with the viewer's address stays behind | Expected: it is removed on a normal stop |

## What the whole-path test found

Running everything together found three faults that no smaller test had shown.

1. **Stopping the service never returned.** When a browser is closed it cuts its open connections. On
   Windows, Python 3.13's asyncio then never counts such a connection as closed (its transport raises
   `ConnectionResetError` before it detaches from the server), and the web server waited for it for
   ever. Now each HTTP answer ends its connection, and stopping waits at most
   `server.shutdown_wait_s` (3 s). Commit `7733832`.
2. **The viewer released a picture too early.** A live picture's address was released as soon as a
   newer picture arrived, while the page could still be loading it. The load then failed with an error
   in the browser's console. Now it is released one second later. Commit `ac063e1`.
3. **A test's limit was one too low.** The picture rate test allowed 8 pictures where the true maximum
   is 9 (the browser keeps two on their way). It failed about one run in three. The limiter was right.
   Commit `3150889`.

One more thing it showed, fixed in `b18e0dc`: the timeline said how many characters a password had.
It now says "Typed a password into "Password"".

## Decisions taken while building

Each was needed to keep going. Say if any should go the other way.

| # | Decision | Why | Cost if wrong |
|---|---|---|---|
| 1 | The viewer's side of the connection was built first | The review of stage 1 was still reading the engine | None |
| 2 | A finished step arrives with its own picture | After a lost connection, replayed steps would all have been given the newest picture | A connection that passes no picture gives steps without one |
| 3 | With no token the viewer shows "This link can't open the session" instead of a recorded demo | Playing a made-up session to someone who opened the service without its link would be dishonest | The built viewer with no query no longer plays the demo; use `?demo=signup` |
| 4 | A refused token (4401) and a session that does not exist (4404) are not retried | Retrying would change nothing | A connection refused for another reason is still retried |
| 5 | A live session's settings screen offers only colour mode and "show where the agent is acting" | The settings API is not built; the other settings would have done nothing | None |
| 6 | `agent.provider` accepts `openai` and `scripted` | You named GPT-5.6 Luna | A configuration naming another provider is refused at start |
| 7 | The demo site moved into the package | One copy, and the service can serve it | None |
| 8 | A step sentence needs the element's role as well as its name | "Clicked "Sign in" (button)" | None |
| 9 | Every failure carries a short reason for the person watching, beside its message for the model | Cutting a reason out of a message written for a model would be brittle | One more argument on errors |
| 10 | An element outside what the browser shows gets no outline | So nothing is outlined in the wrong place | Steps on off-screen elements have no outline |
| 11 | A call that cannot run (unknown tool, bad arguments) is a step too | A person sees everything the agent tried | Extra failed rows |
| 12 | The tool layer takes a "gate" that decides whether a call may run now | A take-over waits for the action in progress without a deadlock | One more seam |
| 13 | A viewer that stops reading is told to connect again | It cannot hold everyone else up | None |
| 14 | A held call is logged by argument name only and is not a step | Nothing was done | A held call leaves no row |
| 15 | The picture rate is limited by delaying the acknowledgement, not by dropping pictures | Dropping could leave an old picture on screen | None measured |
| 16 | The heartbeat also re-reads the open tab | An address that changes without a step reaches viewers within 2 s | One read every 2 s |
| 17 | A key outside Playwright's keyboard (é, ₹) is put in as text | Otherwise it is lost | Dead-key and input-method typing during a takeover is incomplete |
| 18 | A wheel turn is cut to one screen; pointer positions outside the page are refused | Input from a viewer is checked before it reaches the page | None |
| 19 | The service is tested on a real port with a real WebSocket client | Starlette's test client needs a library that is not installed | The tests take about 7 s |
| 20 | Beside the plan, the service sets who may frame the viewer, checks `Host`, limits a viewer's message to 64 KiB, and gives a new connection `server.auth_wait_s` (10 s) to send its token | Spec 4.10 | Two more settings |
| 21 | A session name that does not exist is answered only after the token was accepted | Names cannot be probed without it | None |
| 22 | The command has `--pace`, `--wait-for-viewer` and `--open` beside the plan's flags | So a person can watch from the first step | Three more flags |
| 23 | The log keeps only the first line of a result | The rest is the page, which can hold anything | The log is less useful for debugging a run |
| 24 | The model still sees what a field holds in a snapshot (not a password) | That is how it checks its own work; the spec says so | See open point 2 |
| 25 | One new setting, `browser.timeouts.page_reply_ms`, instead of reusing another | No tunable number lives outside `config.py` | One more setting |
| 26 | An ended session takes precedence over a lost connection in the viewer | The service closes right after a run | A connection lost after the end is shown only in the top bar |
| 27 | The whole-path test stops the service before it closes the viewer page | A page closed while connected leaves a socket open behind the test on Windows | The test does not cover that case |

| 28 | The model is called over plain HTTPS, with no OpenAI library | Your rule: ask before adding a dependency. The call is one request | Changes to the API are followed by hand |
| 29 | `.env` is read into the process's environment at start; a variable already set wins | So the key, the token and the proxy password all come from one place | A `.env` in the folder a command is run from is always read |
| 30 | A run that was stopped or ran out of steps ends with code 1 | So a script can tell an answer from no answer | None |
| 31 | The font is two files in the repository, not an npm package | Your rule: ask before adding a dependency. You asked for this font | It is updated by hand. Say if you prefer the package `@fontsource-variable/hanken-grotesk` |
| 32 | The agent's colour is the violet end of the brand gradient; the gradient itself is only on the brand mark and on a switch that is on | The product uses its gradient sparingly, and red here means blocked, failed or stop | None |
| 33 | A viewer's commands wait in a queue of `server.command_backlog` (256); past that a command is dropped | Stop must never wait, and a flood must not grow without limit | Under a flood the newest input is lost; a key can stay down until hand-back |
| 34 | After a time-out, input already sent to the page is not taken back | It cannot be | An action the page finishes late is reported as failed; the result says to take a new snapshot |
| 35 | An address no browser would open is logged as `<not a valid address>` | It may hold a name and password | The log says less about such a call |

## Minor findings of the second review, deferred

| # | Finding |
|---|---|
| N1 | A password typed with no `ref` (into the focused field) still tells viewers, the result and the log how long it is |
| N4 | Stop runs inside the viewer's connection. If that connection drops while the browser is closing, the browser may be left open with the session already "ended" (not reproduced) |
| N5 | A connection refused for its `Origin` is retried for ever as "Reconnecting…" |
| N6 | `viewer.history_events: 0` gives every viewer an unlimited queue; `max_fps`, `picture_heartbeat_s` and `auth_wait_s` have no lower limit |
| N8 | The file with the viewer's address is not protected from other users on Windows; the spec says "readable by the current user only" |
| N9 | A held call whose time runs out just as the person resumes is told "The session has ended." |
| N10 | A new session with the same name would be shown with the old session's step pictures |
| N11 | The page's size is read once at start; with `browser.viewport: null` and a resized window, the pointer limits go stale |

What that reviewer left unjudged, because it is known and planned: redirects, link clicks and pop-ups are
not checked against the address policy until the network layer is built (next, item 4); a person's own
navigation during a takeover is outside the policy; the query string of an address is shown and logged.

## Minor findings of the first review, deferred

None of these was fixed. They are listed so that you can choose.

| # | Finding |
|---|---|
| M1 | `browser_type` neither waits for a field to become enabled nor checks that it is covered |
| M2 | A click's result says nothing when a navigation is still under way after 3 s, or starts later than two frames after the click |
| M3 | `browser.channel: custom` with no path is found only at the first call, as "failed unexpectedly", and leaves a helper process per call |
| M4 | A log write that fails raises out of the tool call after the action already ran |
| M5 | Configuration: a UTF-16 file gives a traceback; numbers have no range checks; a bad list item is reported as "from the configuration"; `redact_patterns` is checked only when a session starts |
| M6 | Snapshot text: "…" added to an emoji name that was not cut; `max_chars` smaller than the notice; the `Page:` line is not quoted, so a page title can fake a line |
| M7 | The cached page-script context outlives a navigation the page starts by itself (not reproduced) |
| M8 | The MCP instructions name tools this build does not offer |
| M9 | The tab list fetches the page title on every call (the viewer now uses it) |
| M10 | An empty error message; a line break typed with `slowly` presses Enter |
| M11 | The cloud-metadata list lacks two providers' addresses (the NAT64 form is now covered) |
| M12 | Tab is never sent to the page during a takeover |
| M14 | Seven strings outside `wording.ts` |
| M15 | Unused wording keys and icons |
| M16 | Toasts leave one every 4 s, not each after 4 s; "Copied." is shown even without a clipboard |
| M17 | The A key does nothing while the step drawer is open or the focus is on a settings control |
| M18 | A row of collapsed reads shows the first step's number and opens the newest |
| M19 | Colour-mix percentages and opacities the style test cannot see; a drag on a phone scrolls the viewer instead of reaching the page |
| M20 | Each step changes the screen reader's polite region twice |
| M21 | Four tests that cannot fail for a fault in the product |

(M13 was fixed: it became important once the service existed.)

## Open points for you

1. **Your first run with a real key is the first real run.** Put the key in `.env`, then
   `uv run bap-browser agent "<a small task>" --open`. If OpenAI refuses the model's name or the
   request, the terminal and the viewer will say what it answered; tell me that line.
2. **A rule in `CLAUDE.md` contradicts the spec.** `CLAUDE.md` says form values never reach a result.
   The spec shows the model what a field holds in a snapshot (never a password), because that is how
   it checks its own work. I kept the spec and made sure values reach neither the log nor the viewer.
   The wording in `CLAUDE.md` is yours to change.
3. **Single-letter keys.** P, T, A and F act at once. WCAG 2.1.4 (level A) asks for a way to turn such
   keys off or change them. Not built.
4. **States the spec lists that are not built:** session picker, "saving", "working", "handing back",
   "failed", address "loading", "limit reached".
5. **A traceback on Windows.** When a viewer tab or a browser is closed abruptly, Python can print a
   `ConnectionResetError` traceback in the terminal, and stopping then waits 3 s. It is harmless and
   comes from Python's own code. I left it visible. It can be filtered if you prefer a quiet terminal.
6. **Try it with an outside agent.** Adding the MCP server to your Claude Code changes your own
   configuration, so it was not done: `claude mcp add bap-browser -- uv run --directory "<this folder>" bap-browser mcp`.
7. **The font files.** They were added to the repository without asking, because you asked for the
   product's font and the other way was a new npm package. Say if you want the package instead.
8. **Settings in a live session.** The settings screen of a live session still offers only colour mode
   and "show where the agent is acting". The rest waits for the settings API.

## Since this page was measured

Added on 2026-10-05, on branch `feature/agent-cursor`. The table at the top was not measured again.

- **The agent's pointer in the viewer.** It stays on the picture, moves from one target to the next, and a
  click leaves a mark (spec 9.11).
- **13 more tools, 17 of 28 in all:** `browser_go_back`, `browser_go_forward`, `browser_reload`,
  `browser_get_text`, `browser_find`, `browser_hover`, `browser_fill_form`, `browser_select_option`,
  `browser_set_checked`, `browser_press_key`, `browser_scroll`, `browser_scroll_to`, `browser_wait`; and
  `browser_click` takes a point (`x`, `y`) as well as a ref.
- **A chat in the viewer** (`bap-browser agent --chat --open`): a person gives tasks one after another and
  reads the answers; the chat says what the agent is doing, and the browser's edge glows while it works.
- **`browser_request_human`** (18 of 28 tools): the agent asks a person to do a sign-in, a CAPTCHA or a
  code; the person takes over, does it and answers Done. Run once for real against Google's reCAPTCHA demo
  page: the agent asked instead of trying, and went on after Done.
- Measured on 2026-10-05 on macOS with Python 3.12.5: `uv run pytest -q`: 772 passed, 2 failed. The two
  failures were there before this work: `test_a_persons_commands_act_on_the_session` (a pointer press sent
  just before Stop is dropped) and `test_the_step_drawer_shows_the_evidence` (it does not wait for the
  picture to load). The 17 tool definitions come to 1,511 tokens, counted as characters / 4, against a
  budget of 125 a tool.

## Documents

| File | What it is |
|---|---|
| `docs/bap-browser-spec.md` | The spec, one file: the source of truth |
| `docs/bap-browser-spec.html` | The same, as a page |
| `docs/status.md` | This file |
| `docs/demo-guide.md` | What is built, and how to show it step by step |
| `docs/systems-guide.md` | The Systems page: the configuration of each of the three browsers (what to enable, how to manage it, its log) and its evaluations |
| `docs/adr/0001-stack.md` | The stack decision |
| `docs/plans/2026-10-03-m1-stage-1-first-path.md` | The engine plan, stage 1 (11 tasks, done) |
| `docs/plans/2026-10-03-m1-viewer-experience.md` | The viewer plan (11 tasks, done) |
| `docs/plans/2026-10-03-m1-stage-2-live-loop.md` | The live loop plan (9 tasks, done) |
| `docs/plans/2026-10-06-remaining-tools.md` | The plan for the ten remaining tools. On the branch `wip/remaining-tools` only |
| `docs/research/` | Research reports, among them `bap-product-fit.md` (how the BAP product is built) and `claude-in-chrome.md` (how Claude's Chrome extension works) |
| `README.md`, `CLAUDE.md` | Install, run, test; project rules and gotchas |
