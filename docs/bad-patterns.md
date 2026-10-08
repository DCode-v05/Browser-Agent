# Bad patterns: the rules of this codebase

An agent copies what it finds. A workaround that is in the repository today is how things are done
here tomorrow, in every file the next agent touches. So the repository must always be in a state we
are happy to see copied.

This page lists the patterns that must not spread, as points. Each was found by reading this
codebase on 2026-10-08, not taken from a list. Each says where it is held: by the code, by a check,
or only by these words.

The idea, and the order of the layers, are from Lauren Tan's talk "here's how i shipped 2,500 PRs
last month to production" (September 2026). The talk is a video; this page rests on four written
accounts of it, named at the end.

## Where a correction goes

When an agent, or a person, gets something wrong, the correction is put at the highest layer that
can hold it. A lower layer is used only when a higher one cannot.

| Layer | What it is here | How long it holds |
|---|---|---|
| 1. The code | A shape that makes the mistake impossible: one place for tunables, one file of strings, an import graph with one direction | Until someone changes the shape |
| 2. A check | `scripts/patterns.py`, `ruff`, `pyright`, `eslint`, and tests that hold a rule, such as the one for style tokens | Every run of the gate and of CI |
| 3. Rules and skills | This page, `CLAUDE.md`, `.claude/skills/` | Only when they are read |
| 4. Review | A person reading a pull request | Only when they notice |

A rule that lives only at layer 3 or 4 is a debt: the next step is to move it up. A review comment
made twice is a missing check.

## The rules

Rules 1 to 10 are held by `scripts/patterns.py`. What was in the code when a rule was written is
counted in `scripts/patterns_baseline.json`. That count may go down and may never go up: a new case
fails the gate, and a cleaned-up case must be taken out of the baseline. This is "stop the bleeding
first, then clean up".

| # | Rule (`id` in the checker) | Why | In the code on 2026-10-08 |
|---|---|---|---|
| 1 | **No silenced check** (`suppression`). No `# pyright: ignore`, `# type: ignore`, `# noqa`, `eslint-disable`, `@ts-ignore` in product code | A silenced check is copied with its line. The next agent learns that the check is optional | 17 found, 9 fixed the same day, 8 left |
| 2 | **No comment that excuses a workaround** (`workaround-comment`). No "hack", "workaround", "temporary", "for now", "TODO", "FIXME" in a comment | An agent uses such a comment as leave not to fix the cause, and the next one copies it as precedent | None. Held at zero |
| 3 | **No private name across modules** (`private-import`). A name that begins with `_` is not imported from another module | It says "not for you" and is used anyway: the boundary means nothing after the first time | 11 found, 6 fixed by making the names public, 5 left in tests |
| 4 | **Imports go one way** (`layer`). `errors, results` < `config` < `policy` < `driver, code, settings` < `tools` < `service` < `evals` < `agent` < `mcp, bench, doctor` < `cli` | A lower part that reaches up cannot be understood, tested or reused by itself. This is the boundary the talk holds with the import graph | 3 left: `config` imports `policy`; `evals/record.py` imports `agent` twice |
| 5 | **Tunables live in one place** (`tunable-outside-config`). A number in capitals belongs in `config.py`, or in `options.ts` for the viewer | A tunable beside its use is found by nobody, and the next one is put beside it | 22 left in 12 files. Some are codes of a protocol, not tunables; they are still to be sorted |
| 6 | **No `except Exception`** (`broad-except`) | It catches the error nobody thought of and hides it | 4 left, each a last line of defence with a comment saying so |
| 7 | **No skipped test** (`skipped-test`). No `skip`, `xfail`, `.only` | A test that does not run proves nothing and looks as if it did | 1 left: a test of links on a system that cannot make them |
| 8 | **No fixed wait in a test** (`fixed-wait-in-test`). No `wait_for_timeout`, no `time.sleep` | It is slow when the thing is fast and fails when the thing is slow. Wait for the thing | 3 left in 2 files |
| 9 | **No file too long to hold** (`large-file`). 700 lines of Python, 500 of the viewer | A reader with little context, person or agent, reads part of it and guesses the rest | 5 left. The longest is `playwright_driver.py`, 1,923 lines |
| 10 | **No symbolic link in the repository** (`tracked-link`) | It points at one machine's folders. On 2026-10-08 one replaced the viewer's packages on another checkout | None. Held at zero |

Rules that other checks already hold:

| # | Rule | Held by |
|---|---|---|
| 11 | **No colour, size, duration or font outside `viewer/src/tokens.css`** | `viewer/src/tokens.test.ts` |
| 12 | **Every string a person reads is in `viewer/src/wording.ts`** | Review only. To be moved up |
| 13 | **Tests fail on any warning** | `filterwarnings = error` in `pyproject.toml` |
| 14 | **Typed text, passwords and tokens never reach a log, an event or a result** | Tests of the event log and of each tool |
| 15 | **No tool returns raw HTML, and every observation is capped** | Tests of each tool |

Rules that are words only, for now the weakest kind:

| # | Rule | Why it is not a check yet |
|---|---|---|
| 16 | **One helper for one job.** `_read` and `_write` of a JSON file are written three times (`evals/record.py`, `service/accounts.py`, `settings/store.py`); `ref_of` is in the engine and again in two tests | Finding two functions that do the same thing needs judgement. A check on equal names would be a start |
| 17 | **A report says what was seen.** "Built" means its output was read; "live" means the page was looked at | On 2026-10-08 a build that failed silently was reported as live. The gate now prints each stage's result |
| 18 | **A second working folder installs its own packages.** No link to another checkout's `node_modules` | Held in part by rule 10 |

## When you find a new bad pattern

1. Fix the case in front of you at layer 1 if you can: change the shape so that it cannot recur.
2. If it can recur, add a rule to `scripts/patterns.py` and a test of it in
   `tests/unit/test_patterns.py`, and a row to the table above.
3. Run `uv run python scripts/patterns.py --list` to see how far it has spread already. Fix what is
   quick; the rest goes into the baseline, to be cleaned up.
4. Only if no check can hold it, write it here as words, and say why.

The skill `.claude/skills/garden/` walks through these steps.

## Sources

The talk: Lauren Tan (@poteto), <https://x.com/poteto/status/2102050467505430555>. It is a video of
38 minutes, which was not watched for this page. The accounts read:

- <https://redreamality.com/blog/lauren-tan-poteto-trust-before-parallel/>
- <https://github.com/Wladefant/super-board/issues/227>
- Matt Pocock's summary, <https://x.com/mattpocockuk/status/2103431302527508886>
- <https://ratstack.sh/lore/poteto-lauren-tan-2500-prs-dune>

The accounts differ on where "skills" and "review" sit among the lower layers. They agree on the
top two: the code first, then static checks. One thing the talk does that this page does not: it
bans comments altogether. Here a comment that says why stays; one that excuses a workaround does not.
