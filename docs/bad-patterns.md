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

Rules 1 to 12, and 19, are held by `scripts/patterns.py`. What was in the code when a rule was written is
counted in `scripts/patterns_baseline.json`. That count may go down and may never go up: a new case
fails the gate, and a cleaned-up case must be taken out of the baseline. This is "stop the bleeding
first, then clean up".

The audit of 2026-10-08 found 51 cases. Fifty were cleaned up the same day, each at the highest
layer that holds it. The last column says what is left.

| # | Rule (`id` in the checker) | Why | Found, and left |
|---|---|---|---|
| 1 | **No silenced check** (`suppression`). No `# pyright: ignore`, `# type: ignore`, `# noqa`, `eslint-disable`, `@ts-ignore` in product code | A silenced check is copied with its line. The next agent learns that the check is optional | 17 found. None left |
| 2 | **No comment that excuses a workaround** (`workaround-comment`). No "hack", "workaround", "temporary", "for now", "TODO", "FIXME" in a comment | An agent uses such a comment as leave not to fix the cause, and the next one copies it as precedent | None found. Held at zero |
| 3 | **No private name across modules** (`private-import`). A name that begins with `_` is not imported from another module | It says "not for you" and is used anyway: the boundary means nothing after the first time | 11 found. None left: the names another module or a test uses were made public |
| 4 | **Imports go one way** (`layer`). `errors, results, address, private_file, config_base` < `config_safeguards` < `config` < `policy` < `driver, code, settings` < `safeguards` < `tools` < `service` < `evals` < `agent` < `mcp, bench, doctor` < `cli` | A lower part that reaches up cannot be understood, tested or reused by itself. This is the boundary the talk holds with the import graph | 3 found. None left: the address module moved below the configuration, and the record of a task no longer knows the agent |
| 5 | **Tunables live in one place** (`tunable-outside-config`). A number in capitals belongs in `config.py` (the settings of Auto Mode and the safeguards are its sections in `config_safeguards.py`), or in `options.ts` for the viewer | A tunable beside its use is found by nobody, and the next one is put beside it | 22 found. None left: 11 became settings, 4 codes became a named set, the viewer's went to `options.ts` |
| 6 | **No `except Exception`** (`broad-except`), but at a named boundary | It catches the error nobody thought of and hides it. At four places that is the point: an agent's call, an agent's script, a browser that will not launch, an address that cannot be judged. Those are named in `BOUNDARIES`, each with its reason | 4 found. All four are boundaries. A fifth anywhere else fails |
| 7 | **No skipped test** (`skipped-test`). No `skip`, `xfail`, `.only`. A test that cannot run on some system says where, with `skipif` | A test that does not run proves nothing and looks as if it did | 1 found. None left |
| 8 | **No fixed wait in a test** (`fixed-wait-in-test`). No `wait_for_timeout`, no sleep of a second or more written as a number | It is slow when the thing is fast and fails when the thing is slow. Wait for the thing. A short sleep in a loop that looks again is how that is done | 3 found. 1 left, in `tests/viewer/test_takeover.py`: it says the extension does not dial in again by waiting and looking |
| 9 | **No file too long to hold** (`large-file`). 700 lines of Python, 500 of the viewer | A reader with little context, person or agent, reads part of it and guesses the rest | 5 found. None left. The driver, 1,923 lines, is four files of at most 601 |
| 10 | **No symbolic link in the repository** (`tracked-link`) | It points at one machine's folders. On 2026-10-08 one replaced the viewer's packages on another checkout | None. Held at zero |
| 11 | **One helper for one job** (`duplicate-code`). A function is not written again in a second file | The copy is changed and the first is not, and both are copied on | The check finds a function that is the same statement for statement: none. Three that differed by one argument were found by reading, and are one helper now (`private_file.py`) |
| 12 | **Every string a person reads is in `viewer/src/wording.ts`** (`literal-in-viewer`) | A string in a component is not found when the wording changes, and is written again in the next component | 7 found. None left. The check finds what is read or heard of an element (`aria-label`, `title`, `alt`, `placeholder`) and plain text between tags; a string built in code is still held by review only |
| 19 | **No character nobody can see, written as itself** (`invisible-character`). A joiner, a mark of direction, a no-break space or a control is written by its name or its number: `"\N{ZERO WIDTH JOINER}"`, `"\u200d"` | It is not seen in a review, in a diff or in an editor, and a tool on the way (a shell, an editor) can put one in, or turn its name into the character, with nobody noticing. On 2026-10-08 a script written through a shell did exactly that to a joiner | 3 found, in `address.py` and a test. None left |

Rules that other checks already hold:

| # | Rule | Held by |
|---|---|---|
| 13 | **No colour, size, duration or font outside `viewer/src/tokens.css`** | `viewer/src/tokens.test.ts` |
| 14 | **Tests fail on any warning** | `filterwarnings = error` in `pyproject.toml` |
| 15 | **Typed text, passwords and tokens never reach a log, an event or a result** | Tests of the event log and of each tool |
| 16 | **No tool returns raw HTML, and every observation is capped** | Tests of each tool |
| 17 | **A second working folder installs its own packages.** No link to another checkout's `node_modules` | Rule 10, and `.gitignore`, which keeps a link of that name out |

A rule that is words only, because no check can hold it:

| # | Rule | Why it is not a check |
|---|---|---|
| 18 | **A report says what was seen.** "Built" means its output was read; "live" means the page was looked at | It is about what is said, not about the code. The gate helps: it prints each stage's own result line, and a stage that printed nothing has not passed. On 2026-10-08 a build that failed silently was reported as live |

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
