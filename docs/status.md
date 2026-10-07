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
person's real Chrome, which had no window open.

### 1m. Specified on 2026-10-07, not built: Auto Mode and safeguards

The spec has a new section 18, written to be built from. No code of it exists yet.

| Part | What the spec says |
|---|---|
| Auto Mode (18.3, 18.4) | A third choice of "Ask before", for each of the three browsers, off by default. Fixed rules settle what they can; a model that never reads the page judges the rest against the task; a step that pays, sends, deletes or gives a password still goes to the person; a step with no part in the task is refused and the agent goes on. An outside agent states its task once with a new tool, `browser_begin_task` |
| What comes in (18.5) | Text a person cannot see is left out; page text is marked; planted instructions are found by rules on this machine, checked by a model, and withheld |
| What goes out (18.6) | Passwords, cards and codes; text copied from one site to another; files that can run programs; screens that grant access; the amount of a payment, and a cap |
| Where the browser goes (18.7) | The task's sites; look-alike sites; sensitive sites; optional known-bad lists of abuse.ch |
| When something fails (18.8) | The check fails closed; limits on steps, time and money; repeated calls; a step whose outcome is not known |
| The record, what a person sees, settings, where the code goes (18.9 to 18.12) | All given with defaults and wording |
| Tests and order (18.13 to 18.15) | An attack set of 25 pages with a fooled agent, nine slices to build in, and the list it is accepted by |

Decided with you by dialog before it was written: a check decides, like Claude Code's auto mode;
rules first, then a model; the model is OpenAI's with a setting of its own; an outside agent states
its task at the start; Auto Mode is off until a person turns it on; known-bad lists are optional and
local checks always on; only what local rules flag goes to a model.

Not decided by you, and written as I judged best, to be changed if you see it otherwise: the limits'
defaults (500 steps and 60 minutes a session), the pause after 3 refusals in a row or 20 in a session,
that a paying, sending or deleting step is asked of you even when you asked for it, that a download on
your own machine is checked before it is kept, and the lists of sensitive and protected sites.

The research behind it, each claim with its source: `docs/research/auto-mode.md`,
`prompt-injection.md`, `web-threats.md`, `fallbacks.md`, `safeguards-map.md`,
`anthropic-safeguards.md`, `mcp-security.md`.

### 2. Not started

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

### 3. Waiting for your word

| # | Question |
|---|---|
| 2 | The font is two files in the repository. Say if you prefer the npm package `@fontsource-variable/hanken-grotesk` |
| 3 | `CLAUDE.md` says form values never reach a result; the spec shows the model what a field holds in a snapshot (never a password). I kept the spec. The wording in `CLAUDE.md` is yours to change |

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
