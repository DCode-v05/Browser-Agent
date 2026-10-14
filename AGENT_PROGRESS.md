# Visual redesign pass — progress

Budget: 20 minutes. Priority order: Systems (settings) page, then Studio, then anything else.

## Done: Systems page (`viewer/src/systems/`)

Read `viewer/src/systems/SystemsPage.tsx`, `parts.tsx`, `viewer/src/tokens.css`, `viewer/src/styles/app.css`
(lines ~1920-2150) first. Loaded the `frontend-design` skill.

Judgment call: the existing token set (warm neutrals, hairlines, pills, Hanken Grotesk) is coherent
and not broken — this is a spacing/hierarchy pass within it, not a rebrand, per the brief.

Changes, all token-only (`viewer/src/styles/app.css`):
- `.systems` page padding/gap: `--space-4` → `--space-5`. The page breathed too tightly against the
  window edge and between the header and the grid.
- `.system-card` padding: `--space-4` → `--space-5`; added `box-shadow: var(--shadow-float)` so the
  card reads as a raised surface (the token already existed, unused here) instead of a flat outline —
  gives the settings card clearer separation from the page background.
- `.system-section` (the uppercase section dividers: "This browser", "For users", "Log", "Records"):
  `margin-top`/`padding-top` `--space-2`/`--space-3` → `--space-5`/`--space-4`. This was the main
  hierarchy problem — sections inside one card ran together with barely more gap than a row has from
  its own label. Now each section reads as a distinct group.
- `.system-head` icon-to-name gap: `--space-2` → `--space-3`, matching the heavier `--icon-large` icon
  used there.

Markup (`viewer/src/systems/SystemsPage.tsx`):
- Added a `.systems-empty` class (dashed border, `--surface-2` fill, centered, `min-height`) and wrapped
  every bare "Loading…" / "Can't reach it" `<p>` in it — in `SystemPanel` (single-browser tab) and in
  `SystemsPage` (admin overview). Previously these were a stray line of muted text with no visual
  weight; now they hold the place the content will fill.
- Found and fixed a second gap while there: in `SystemsPage`, the "users" view rendered nothing at all
  while `policy` was still null (no loading state existed for it). Added the same `.systems-empty`
  placeholder there.

No new wording: `W.systems.loading` / `W.systems.unreachable` already existed in `wording.ts` and are reused.

## Not done (next pass, in priority order)

1. Studio page (`viewer/src/Studio.tsx`) — tabs, chat panel, live-picture area. Not started; ran out of
   budget after the Systems page checks + PR. This is priority 2 in the brief.
2. Any other page.
3. Screenshots not taken (no time to boot `npm run dev` + capture both themes/surfaces on top of the
   checks below) — before/after is diff-visible only (padding/shadow/section-gap values).

## Checks run

- `npm --prefix viewer install` — needed first, `node_modules` was not present in this worktree.
- `npm --prefix viewer run typecheck` — pass, no errors.
- `npm --prefix viewer run lint` — pass, no errors.
- `npm --prefix viewer run test` — the default `forks` pool times out spawning workers on this long
  Windows path (`[vitest-pool-runner]: Timeout waiting for worker to respond`), an environment issue
  unrelated to this change; 5 of 24 files ran that way. Re-ran with `npx vitest run --pool=threads`:
  **24 files, 624 tests, all passed.**
- `npm --prefix viewer run build` — pass, `vite build` succeeds, viewer_dist written.
- `uv run pytest tests/viewer -q` — not run (time budget spent on the above plus the PR).

Updated `docs/status.md` with a short entry before "## Documents".
Committed, pushed, PR opened. See the PR description for the before/after summary.
