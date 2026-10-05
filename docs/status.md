# bap-browser: Status

Date: 2026-10-04 · Branch `prototype/base` · 49 commits on the branch · nothing pushed

## Where things stand

One command runs an agent in a real browser while a person watches it in the viewer and can pause it,
take over the browser, hand it back and stop it.

Three things are new since the last version of this page:

1. **A real model is connected.** Without `--demo`, the agent loop calls OpenAI's `gpt-5.6-luna`. The
   key is read from `OPENAI_API_KEY` in a file named `.env`. **It has not been run against the real
   service**: there is no key on this side, so it was tested against a stand-in server built from
   OpenAI's published reference. Your first run with your key is the first real one.
2. **The second review was acted on.** A fresh reviewer read the live loop and found 4 critical and 3
   important faults. All seven are fixed, each with a test that failed first.
3. **The viewer has the BAP product's look**: its colours, its typeface (Hanken Grotesk) and its
   shapes, taken from the product's own code. It is not a copy of the product's screens.

| Part | State | Proof (measured on 2026-10-04 at commit `bfa2148`) |
|---|---|---|
| Whole Python suite | Passing | `uv run pytest -q`: 696 passed, exit code 0. 495 unit, 74 in a real browser against the engine, 35 against the real service and commands, 92 of the built viewer in a real browser |
| Python checks | Clean | `uv run ruff format --check .`, `uv run ruff check .`, `uv run pyright`: no findings |
| Viewer unit tests | Passing | `npm --prefix viewer run test`: 347 passed |
| Viewer checks | Clean | `npm --prefix viewer run typecheck`, `run lint`: no findings. `run build`: builds |
| Accessibility | No findings | The axe scanner runs on every state, light and dark, desktop and phone, inside the 92 viewer tests |
| The whole path | Proven | `tests/viewer/test_live_session.py`: a real agent browser, the real service and the real viewer in a second browser |
| The command, run by hand | Works | `bap-browser agent --demo --wait-for-viewer --pace 3`, watched in a browser: steps and pictures arrive live; a Stop pressed right after a Pause ended the session in 74 ms; the browser's console stayed empty |
| The hosted model | Built, not run for real | 13 tests against a stand-in server. With no key the command says: "OPENAI_API_KEY is not set. Put a line OPENAI_API_KEY=... in a file named .env in this folder…" and ends with code 2 |
| Review of stage 1 | Done, all fixed | 1 critical and 9 important findings fixed. 20 minor findings deferred (listed below) |
| Review of the live loop | Done, all fixed | 4 critical and 3 important findings fixed. Of 12 minor findings, 5 fixed and 7 deferred (listed below) |
| Review of those fixes and of the new look | Not done | A third reviewer was started on commits `68722d1..bfa2148` and was cut off by a usage limit before it reported anything |

## Try it

```bash
npm --prefix viewer install
npm --prefix viewer run build
uv sync
uv run playwright install chromium
uv run bap-browser agent --demo --open                      # the scripted sign-up, no key needed
uv run bap-browser agent "What is on example.com?" --open   # a real task, done by GPT-5.6 Luna
```

For a real task, copy `.env.example` to `.env` and put your key after `OPENAI_API_KEY=`. The file is
never committed. `--open` opens the viewer in your browser, waits for it to connect, and then starts.
While the agent works you can press Pause, Take over (then click and type in the picture: it reaches
the real page), Hand back, and Stop session. When the task is done the answer is printed in the
terminal, the viewer shows the summary, and the viewer stays open until you press Ctrl+C.

| Option | Effect |
|---|---|
| `--demo` | The scripted sign-up on the demo site. Needs no key |
| `--open` | Opens the viewer in your browser and starts once it has connected |
| `--wait-for-viewer` | Starts once a viewer has connected, without opening one |
| `--pace 0.5` | Seconds the demonstration waits before each step. Default 1 |
| `--exit-when-done` | Ends when the task is finished, instead of keeping the viewer open |

The command ends with 0 when the task was answered, 1 when the model failed or the task was not
finished (the step limit, or a person stopped the session), 2 when the command or the configuration
was wrong.

The recorded viewer screens still work without the service: `npm --prefix viewer run dev`, then add
`?demo=signup` or `?state=<name>` to the address it prints (add `&theme=dark` for the dark theme).

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

1. Your test through the viewer with a real key, and whatever it shows.
2. The remaining 24 tools (frames, tabs, screenshots, forms, scrolling, files, waiting, finding).
3. Approvals for real: tools marked "confirm" wait for the person's answer in the viewer.
4. The settings API, so the settings screen acts on a live session.
5. The address policy at the network layer, so redirects and link clicks are checked too.
6. MCP over HTTP with the service (`bap-browser serve`), the micro VM image, the bench and the verify loop.
7. Then milestone 2 (take-over Chrome), milestone 3 (bundled Chromium), milestone 4 (the code tool).
