# bap-browser: Status

Date: 2026-10-03 · Branch `prototype/base` · 13 commits · nothing pushed

## Where things stand

The spec is written for the three-backend design. The first engine stage is built and passing: an
agent can drive a real Chromium through four tools, in the same process or over MCP. The viewer's
experience is built on recorded sessions: every state, the controls, the cards, the timeline and the
settings screen. The engine and the viewer are not connected to each other yet; that is the next slice.

| Part | State | Proof (measured on 2026-10-03) |
|---|---|---|
| Spec and documents | Done for this stage | Files listed below |
| Engine, stage 1 (slices 0, 2, 3) | Done: 11 of 11 tasks | `uv run pytest -q`: 291 passed. `ruff format --check`, `ruff check`, `pyright`: clean |
| Viewer experience (slice 1) | 10 of 11 tasks done | `npm --prefix viewer run test`: 276 passed. `tsc --noEmit`, `eslint`: clean. `vite build`: builds |
| Viewer checks in a real browser | In progress | 12 states looked at by hand: no sideways scroll, no console errors. The automated suite is not written yet |
| Engine and viewer connected (slice 4) | Not started | |
| Final review of the engine branch by a fresh reviewer | Not done yet | |

## Documents

| File | What it is |
|---|---|
| `docs/bap-browser-spec.md` | The spec, one file, 18 sections: the source of truth |
| `docs/bap-browser-spec.html` | The same, as a page |
| `docs/status.md` | This file |
| `docs/adr/0001-stack.md` | The stack decision |
| `docs/plans/2026-10-03-m1-stage-1-first-path.md` | The engine plan, stage 1 (11 tasks, all done) |
| `docs/plans/2026-10-03-m1-viewer-experience.md` | The viewer plan (11 tasks, 10 done) |
| `docs/research/` | Six research reports: hermes, betterwright, performance, uiux, video, settings |
| `docs/browser-agent-perception.html` | How agents see pages |
| `README.md`, `CLAUDE.md` | Install, run, test; project rules and gotchas |

## Engine: what is built

| Task | Delivers | Commit |
|---|---|---|
| 1 | Repository, `pyproject.toml`, ruff, pyright, pytest, CI workflow, README, CLAUDE.md, ADR | `fa4389e` |
| 2 | `config.py` with every milestone 1 key and its default; file, environment and session layers; unknown keys refused | `362060b` |
| 3 | `bap-browser config show`, `init`, `doc` | `5811525` |
| 4 | Address policy: schemes, allowed and blocked sites, cloud metadata, private-network guard, cached decisions | `d8a0299` |
| 5 | Redaction patterns | `62c7560` |
| 6 | Local test site (10 pages) and test fixtures | `239eaa4` |
| 7 | Driver interface; page script in an isolated world; launch and navigation | `f6674c9` |
| 8 | Page snapshot: stable refs, output cap, hidden text left out, passwords masked | `31958bf` |
| 9 | Click and type by ref, with readiness checks and navigation settling | `a17fd27` |
| 10 | Tool layer with four tools, in-process API, event log with typed text masked | `808ee4d` |
| 11 | MCP server over stdio; `bap-browser mcp` | `64c4587` |

What works today:

- `uv run bap-browser mcp` starts an MCP server. An agent gets `browser_navigate`, `browser_snapshot`, `browser_click` and `browser_type`.
- A test drives the real command over the real transport: it opens the test form, types a name and an email, ticks a box, submits, and reads the next page.
- The same four tools work from Python in one process (`open_session`, `Toolkit`).
- A blocked address is refused before the browser starts. Typed text never reaches the log.
- The snapshot of the 9-control test form is under the 700-character budget, and its roles and names agree with Playwright's own accessibility snapshot.

Not built yet in the engine: the other 24 tools, frames inside the snapshot, tabs and pop-ups, the
address policy at the network layer, Chrome and Edge, screenshots, the session service, control
states and approvals, the settings catalogue, MCP over HTTP, the micro VM image, the bench.

## Viewer: what is built

| Task | Delivers | State |
|---|---|---|
| 1 | Scaffold: Vite, React, TypeScript, Vitest, ESLint | Done |
| 2 | Design tokens in light and dark; every string in one file | Done. 65 contrast checks pass in both themes |
| 3 | Protocol, the event reducer, what each state looks like | Done |
| 4 | Timeline rows: sentence per step, collapsed reads, idle dividers | Done |
| 5 | Recorded sessions and the player that answers commands | Done. 15 recordings: one full run and one per state |
| 6 | Shell, tabs, address bar, live picture, border and label, target outline | Done |
| 7 | Controls, approval card, help card, dialog card, takeover bar, toasts, summary | Done |
| 8 | Timeline panel and step drawer | Done |
| 9 | Settings screen for web, mobile and desktop | Done |
| 10 | Keyboard map, announcements, themes, reduced motion | Done in code; reduced motion is checked in task 11 |
| 11 | Checks of the built viewer in a real browser: every state, both themes, phone width, accessibility scan | In progress |

How to see it:

```bash
npm --prefix viewer install
npm --prefix viewer run dev
```

Then open the address it prints, with one of these on the end:

| Address ending | Shows |
|---|---|
| `?demo=signup` | The full run at real pace. You answer the approval and the request for help |
| `?state=agent` | The agent working, with its target outlined |
| `?state=waiting_approval` | An approval waiting |
| `?state=person_requested` | The agent asking for help |
| `?state=person` | You in control, full width |
| `?state=paused`, `blocked`, `dialog`, `ended`, `disconnected`, `stale`, `no_agent`, `empty`, `denied`, `person_unasked`, `own_browser` | Each of those states |
| add `&theme=dark` | The dark theme |
| add `&surface=mobile` or `&surface=desktop` | That surface's settings set |
| add `&embed` | As shown inside a client, without the product name |

Settings sets in the viewer: web 16, mobile 13 (what milestone 1 builds), desktop 22 (its whole design,
so it can be reviewed).

## Decisions taken while building

Each was needed to keep going. Say if any should go the other way.

| # | Decision | Why | Cost if wrong |
|---|---|---|---|
| 1 | The viewer is built first, on recorded sessions; the engine was built alongside by a second worker | "Much more focus on UI and UX" | Only the order of work |
| 2 | One commit on `main`, then all work on `prototype/base`, no separate worktree | As chosen earlier | The branch can be moved |
| 3 | `README.md` is written before the first install | The build reads it | None |
| 4 | Ruff does not format `docs/` | It rewrote the code examples inside the spec | Examples in docs are not auto-formatted |
| 5 | After a navigation the page script forgets the old document | The plan kept a dead context, and its own test failed | One extra round trip after a navigation |
| 6 | A navigation right after a failed one waits for Chromium's error page to settle | Otherwise it fails with "interrupted by another navigation" | A navigation that fails with no error page reports up to 3 s later |
| 7 | The "never stops moving" test waits until the animation runs | A browser that has just started draws no frame for about 1.5 s; the click is correct then | The test no longer covers a click before the first frame |
| 8 | An element whose box has not changed counts as still, even with no frame drawn | A page that is not painted (a background tab) must stay clickable | On a machine starved of CPU, a moving element can be judged still |
| 9 | Missing argument is reported before unknown argument | Pydantic 2.13.5 lists them in that order | A later Pydantic could change the order and fail one test |
| 10 | The picture is called stale only when the service stops confirming it (`picture_current` event) | A page that is simply still would otherwise look broken after 5 s | One small event every few seconds |
| 11 | In the "person" state, Done and Couldn't do it appear only when answering a request for help; otherwise Hand back | Done has nothing to answer when the person took over unasked | The spec table lists all four buttons together; it will be updated |
| 12 | What happened before the viewer opened is not popped up again as toasts | A reload would replay old "Allowed once" messages | None |
| 13 | A site list keeps what was typed when it is refused | So it can be corrected instead of retyped | The spec says a refused change puts the control back; it will be updated |
| 14 | The target outline is a layer over the picture, not a second canvas | It follows the theme and needs no drawing code | None |

Four smaller ones were lint or type fixes with no change in behaviour (raw strings in tests, one
joined condition, one typed local, one default written as `Field(default=[])`).

## Open points for you

1. **Try it with a real agent?** Adding the server to your Claude Code changes your own configuration, so it was not done. The command is `claude mcp add bap-browser -- uv run --directory "<this folder>" bap-browser mcp`.
2. **Two fixed values outside `config.py`:** two animation frames to settle after an action, and eight dots for a password. I see them as fixed parts of the method, not settings. Say if they should be configurable.
3. **Line endings.** The repository has no `.gitattributes`. A fresh checkout on Windows would turn the test pages and the page script into CRLF. I plan to add one that keeps them LF.
4. **The page script has no time limit of its own.** A page with a stuck main thread could hang a tool call. Not tested yet; it belongs to the next engine stage.

## Next, in order

1. Finish viewer task 11: the automated checks of the built viewer (every state, both themes, phone width, accessibility scan, keyboard walk-through), and fix what they find.
2. Bring the spec up to date with decisions 10 to 14 and the protocol details the viewer needed, and regenerate the HTML page.
3. A fresh-context review of the whole branch against the spec, then one fix pass.
4. The plan for slice 4, "watch it live": the session service, the event stream and live pictures feeding this viewer.
5. Then the remaining tools, control, settings on the server side, the micro VM image and the verify loop.
