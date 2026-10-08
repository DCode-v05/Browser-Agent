---
name: garden
description: Turn a mistake or a bad pattern found in bap-browser into a rule that holds. Use after a correction from a person, a review comment made twice, a bug caused by copying existing code, or when asked to look for bad patterns.
---

# Turn a mistake into a rule

An agent copies what is in the repository. One workaround left in becomes the way things are done.
The gardener's work is to stop a pattern before it spreads, and then to clean it up.

`docs/bad-patterns.md` has the rules as they stand and the layers a correction can go to.

## When a mistake was made

1. **Name the pattern, not the instance.** "A tunable number was written beside its use", not
   "the poll time in Suite.tsx".
2. **Count it.** `uv run python scripts/patterns.py --list` shows what the present rules match. For
   a pattern with no rule yet, search for it and note how many places and which files.
3. **Choose the highest layer that can hold it.**
   - Layer 1, the code: can the shape change so that the mistake cannot be made? One place for the
     thing, a type that does not allow it, an import that cannot go that way.
   - Layer 2, a check: add a rule to `scripts/patterns.py` (a regular expression, or a walk of the
     syntax tree), or a lint rule, or a test that holds it.
   - Layer 3, words: a row in `docs/bad-patterns.md`. Only when no check can hold it, and the row
     says why not.
4. **Add the rule with its test.** In `tests/unit/test_patterns.py`: one case the rule must find,
   and one near it that it must leave alone.
5. **Stop the bleeding.** Fix the cases that are quick. Put the rest in the baseline:
   they are counted, and the count can only go down. Do not raise a count to let a new case in.
6. **Write the row.** In `docs/bad-patterns.md`: the rule, why it is one, how many were found.

## When asked to look for bad patterns

1. Run `uv run python scripts/patterns.py --list` and read the baseline: what is left to clean up.
2. Read the three largest files and the three most recently changed. Look for: a thing done two
   ways; a helper written twice; a check silenced; a boundary crossed; a value that should be a
   setting; a test that proves less than its name says.
3. For each, do the six steps above. Report them as points: the pattern, where, how many, and the
   layer you put the correction at.

## When cleaning up

Take one rule and one file. Fix it at layer 1. Run `uv run python scripts/patterns.py --lower` to
write the lower count, then the gate. One clean-up to a pull request: it is easy to review and
easy to undo.
