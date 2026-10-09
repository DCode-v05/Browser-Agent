---
name: develop
description: Make a change to bap-browser by the one pathway of this repository. Use for any feature, fix or refactor here, before writing code.
---

# Make a change by the pathway

`docs/agent-pathway.md` is the source of this skill. Follow its ten steps in order. Do not skip one
because the change looks small; say so in your report if a step did not apply, and why.

1. **Read.** Find the feature in `docs/feature-map.json`: it names the spec section, the source
   files and the tests. Read those, and `docs/bad-patterns.md`. Then say in one line which files
   will change and which tests hold them.
2. **Spec first.** If what the system must do changes, edit `docs/bap-browser-spec.md` first, then
   run `uv run --no-project --with markdown python docs/spec_to_html.py`.
3. **Branch.** `git switch -c <kind>/<what-it-does>` from an up-to-date `main`. In a second working
   folder run `uv sync` and `npm --prefix viewer ci`. Never link `node_modules` from another folder.
4. **Test first.** Write the test. Run it and read the failure: it must fail because the thing is
   missing, not because of a typo.
5. **Build.** The smallest change that passes the test. Put each thing in its one place: the table
   "The paved road" in `docs/agent-pathway.md`. If you are about to silence a check, write a
   comment that excuses a workaround, or import a name that begins with `_`, stop and fix the cause.
6. **Gate.** `uv run python scripts/gate.py --quick` while you work; `uv run python scripts/gate.py`
   before step 9. Read the line it prints for each stage. Do not go on until it prints
   "The gate is passed".
7. **Evidence.** See the change work where a person would: the table "Evidence" in
   `docs/agent-pathway.md`. Quote what you saw. A passing test is not evidence that a page shows
   the right thing.
8. **Record.** `docs/status.md`: what was built, what was not, what it found. Add or change the
   feature's entry in `docs/feature-map.json`.
9. **Ship.** Before committing, read `git status --short` and name every file: nothing goes in that
   you did not mean. One short imperative subject. Push, open a pull request, wait for CI, merge,
   then `git switch main && git pull --ff-only`.
10. **Garden.** For each thing that went wrong on the way, use the skill `garden`.

## pstack on the way

Apply the eight pstack skills that `CLAUDE.md` lists: `tdd` at step 4, `principle-laziness-protocol`
and `principle-type-system-discipline` at step 5, `principle-test-behavior-not-implementation` to every
test, `principle-sequence-verifiable-units` to the order of the work, `principle-prove-it-works` at
step 7, and `unslop` with `technical-writing` to every word written at step 8 and in the report.

## What to report

- The gate's last line.
- The evidence, quoted.
- What is not built, and what you did not check. Say it plainly; a gap named is worth more than a
  claim that turns out wrong.
