# The pathway: how a change is made here

There is one way to make a change in this repository. A person follows it, and so does an agent
working for a person. It is a line, not a menu: each step has one command or one file, and one
thing that must be true before the next step.

One road is the point. An agent takes the shortest path it can see; when the shortest path is the
right one, it does the right thing with little context. Two ways to do a thing are two things to
copy, and the worse one spreads as fast as the better.

## The line

| # | Step | What you do | You go on when |
|---|---|---|---|
| 1 | **Read** | The spec section for the thing (`docs/bap-browser-spec.md`), its entry in `docs/feature-map.json`, and `docs/bad-patterns.md` | You can say which files change and which tests hold them |
| 2 | **Spec first** | If what the system must do changes, change the spec, then `uv run --no-project --with markdown python docs/spec_to_html.py` | The spec says the new behaviour |
| 3 | **Branch** | `git switch -c <kind>/<what-it-does>` from an up-to-date `main`. In a second working folder: `uv sync` and `npm --prefix viewer ci`, never a link | `git status --short` shows nothing of yours |
| 4 | **Test first** | Write the test that fails for the right reason | It fails, and its message names what is missing |
| 5 | **Build** | The smallest change that passes it, on the paved road below | The new test passes |
| 6 | **Gate** | `uv run python scripts/gate.py` | It prints "The gate is passed" |
| 7 | **Evidence** | See the change work where a person would: the table below | You have seen the output yourself, and can quote it |
| 8 | **Record** | `docs/status.md`: what was built, what was not, what it found. Add the feature to `docs/feature-map.json` | The status page would not surprise the next reader |
| 9 | **Ship** | Commit (one short imperative subject), push, pull request, wait for CI, merge, `git switch main && git pull --ff-only` | CI is green and `main` holds the change |
| 10 | **Garden** | For each thing that went wrong on the way: put the correction at the highest layer that holds it (`docs/bad-patterns.md`) | No correction lives only in a chat |

Step 6 is the same checks CI runs. While you build, `uv run python scripts/gate.py --quick` leaves
out the tests that start a browser; the whole gate is run before step 9.

## The paved road

Where a thing goes. If you are about to put it somewhere else, stop.

| The thing | Its one place |
|---|---|
| A tunable value | `src/bap_browser/config.py`; for the viewer, `viewer/src/options.ts` |
| A string a person reads | `viewer/src/wording.ts` |
| A colour, a size, a duration, a font | `viewer/src/tokens.css` |
| A tool an agent calls | `src/bap_browser/tools/browser_tools.py`, added to `TOOLS` |
| An address of the service | `src/bap_browser/service/app.py`, and a row in `docs/feature-map.json` |
| A setting a person can change | `src/bap_browser/settings/catalogue.py`. The settings screen draws itself from it |
| An event to the viewer | Published by `service/session.py`, typed in `viewer/src/protocol.ts`, applied in `viewer/src/state/reducer.ts` |
| A test double | `tests/support/`. Test files do not import each other |
| A task with a known right end | `src/bap_browser/evals/sets/` |
| A rule about the code | `scripts/patterns.py`, with a row in `docs/bad-patterns.md` |

Which part of the engine may use which is in `scripts/patterns.py` (`LAYERS`): imports go one way,
and the gate refuses one that goes the other.

## Evidence

A test that passes says the code does what the test says. Evidence is seeing the change do what the
person wanted. Which evidence fits which change:

| The change touches | The evidence |
|---|---|
| A tool, the driver, the page script | The task sets by their reference solutions: Evaluations, "Run the reference solutions", or `POST /api/systems/{name}/suite` with `"mode": "reference"` |
| What the agent does with its model | A task set run with the agent, read task by task |
| The viewer | The page in a real browser: every new control pressed, in each role, with no console error |
| Speed | `uv run bap-browser bench` against `perf/budget.json` |
| A browser of the window | Its checklist: Evaluations, "Run the checklist" |
| The build | The stage's own last line, such as `✓ built in 467ms`. No line is not a pass |

## What an agent is given

| File | What it is for |
|---|---|
| `CLAUDE.md` | The commands and the gotchas |
| `docs/agent-pathway.md` | This page: the one line |
| `docs/bad-patterns.md` | The rules, as points, and where each is held |
| `docs/feature-map.json` | Every feature: its spec section, its files, its tests, and how to reach it on screen |
| `.claude/skills/develop/` | The line as steps an agent runs |
| `.claude/skills/garden/` | How to turn a mistake into a rule |
| `scripts/gate.py`, `scripts/patterns.py` | The checks themselves |

## Where this comes from

Lauren Tan's talk on shipping about 2,500 pull requests in a month with agents (September 2026),
read through four written accounts (named in `docs/bad-patterns.md`). What is taken from it:

- Trust comes before speed. More agents on a codebase that is not locked down make more bad pull
  requests, not more good ones.
- The codebase is the agent's memory. What is in it is copied.
- Make the shortcut the correct path: one paved road.
- A correction goes to the strongest layer that can hold it.
- Stop a bad pattern from spreading before cleaning it up.
- An agent's work is trusted on evidence it produced, not on its word.
- A map of the features, kept in step with the code, lets an agent find its way from a vague report.

What is not taken, because it is not built here: a framework that makes these impossible by
construction, agents started by alerts, and a ban on every comment.
