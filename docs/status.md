# bap-browser: Status

Date: 2026-10-04 · Branch `prototype/base` · 40 commits on the branch · nothing pushed

## Where things stand

The engine, the viewer and the service are now connected. One command runs an agent in a real
browser while a person watches it in the viewer and can pause it, take over the browser, hand it
back and stop it. This is the "live loop" you asked for: a basic agent loop with the system built
around it, so the whole path can be checked.

The agent in that loop follows a fixed script (it signs up on a demo site that ships with
bap-browser). It uses the same tools, the same browser and the same service a real model would. A
real model is not connected yet; you chose "scripted only for now".

| Part | State | Proof (measured on 2026-10-04 at commit `efe9d72`) |
|---|---|---|
| Whole Python suite | Passing | `uv run pytest -q`: 603 passed, exit code 0. 408 unit, 73 in a real browser against the engine, 31 against the real service and commands, 91 of the built viewer in a real browser |
| Python checks | Clean | `uv run ruff format --check .`, `uv run ruff check .`, `uv run pyright`: no findings |
| Viewer unit tests | Passing | `npm --prefix viewer run test`: 323 passed |
| Viewer checks | Clean | `npm --prefix viewer run typecheck`, `run lint`: no findings. `run build`: builds |
| The whole path | Proven | `tests/viewer/test_live_session.py`: 10 of 10 runs passed with exit code 0. Four screenshots in `.bap-browser/viewer-shots/live-*.png` |
| The command | Works | `uv run bap-browser agent --demo --exit-when-done --pace 0`: exit code 0, the answer on standard output, 10 lines in the event log, no browser process left behind (7 before, 7 after) |
| Review of stage 1 | Done, all fixed | 1 critical and 9 important findings fixed, each with a test that failed first. 20 minor findings deferred (listed below) |
| Review of the live loop | Running | A fresh reviewer is reading commits `4e4ca97..b18e0dc`. Its findings are not in this document yet |

## Try it

```bash
npm --prefix viewer install
npm --prefix viewer run build
uv sync
uv run playwright install chromium
uv run bap-browser agent --demo --open
```

The last command opens the viewer in your browser, waits for it to connect, and runs the script at
one step a second. While it runs you can press Pause, Take over (then click and type in the picture:
it reaches the real page), Hand back, and Stop session. When the script is done, the viewer shows the
summary and stays open until you press Ctrl+C in the terminal.

| Option | Effect |
|---|---|
| `--demo` | The scripted sign-up. Needs no key. Without it the command says that no real model is connected yet |
| `--open` | Opens the viewer in your browser and starts once it has connected |
| `--wait-for-viewer` | Starts once a viewer has connected, without opening one |
| `--pace 0.5` | Seconds the script waits before each step. Default 1 |
| `--exit-when-done` | Ends when the script is finished, instead of keeping the viewer open |

The recorded viewer screens still work without the service: `npm --prefix viewer run dev`, then add
`?demo=signup` or `?state=<name>` to the address it prints.

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
| 4 | A refused token closes the connection with code 4401 and is not retried | Retrying would change nothing | A service that closes with another code is retried for ever |
| 5 | A live session's settings screen offers only colour mode and "show where the agent is acting" | The settings API is not built; the other settings would have done nothing | None |
| 6 | `agent.provider` accepts `anthropic` (the spec's default) and `scripted` | The spec's table is the authority | A configuration naming `anthropic` is accepted before that model exists |
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
| M11 | The cloud-metadata list lacks two providers' addresses and the NAT64 form |
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

1. **A real model.** You chose "scripted only for now". When you want one, say which provider and
   which environment variable holds the key.
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
6. **Try it with a real agent.** Adding the MCP server to your Claude Code changes your own
   configuration, so it was not done: `claude mcp add bap-browser -- uv run --directory "<this folder>" bap-browser mcp`.
7. **Three gotchas were added to the project `CLAUDE.md`** (shell heredocs and backslashes; the Windows
   connection fault; two pictures on their way). Say if you would rather review such additions first.

## Documents

| File | What it is |
|---|---|
| `docs/bap-browser-spec.md` | The spec, one file: the source of truth |
| `docs/bap-browser-spec.html` | The same, as a page |
| `docs/status.md` | This file |
| `docs/adr/0001-stack.md` | The stack decision |
| `docs/plans/2026-10-03-m1-stage-1-first-path.md` | The engine plan, stage 1 (11 tasks, done) |
| `docs/plans/2026-10-03-m1-viewer-experience.md` | The viewer plan (11 tasks, done) |
| `docs/plans/2026-10-03-m1-stage-2-live-loop.md` | The live loop plan (9 tasks, done) |
| `docs/research/` | Research reports: hermes, betterwright, performance, uiux, video, settings |
| `README.md`, `CLAUDE.md` | Install, run, test; project rules and gotchas |

## Next, in order

1. Act on the review of the live loop when it arrives: fix what is critical or important, list the rest.
2. The remaining 24 tools (frames, tabs, screenshots, forms, scrolling, files, waiting, finding).
3. Approvals for real: tools marked "confirm" wait for the person's answer in the viewer.
4. The settings API, so the settings screen acts on a live session.
5. The address policy at the network layer, so redirects and link clicks are checked too.
6. MCP over HTTP with the service (`bap-browser serve`), the micro VM image, the bench and the verify loop.
7. Then milestone 2 (take-over Chrome), milestone 3 (bundled Chromium), milestone 4 (the code tool).
