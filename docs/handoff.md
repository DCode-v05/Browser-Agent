# Handoff: bap-browser

## Task

This session only ran the handoff skill to checkpoint state; no new work was asked for or done here.
The surrounding work (visible in the tree) is: compare bap-browser against Hermes and the OpenAI
Agents SDK, and design and start building cross-platform computer-use helpers (Windows, Linux) plus
reaching a helper over a Tailscale tailnet.

## Done

- **Desktop-app and computer-use comparisons against Hermes and the OpenAI Agents SDK**, written and
  rendered: `docs/research/desktop-app-comparison.md`/`.html`, `docs/research/computer-use-comparison.md`/`.html`.
  Both are read-from-the-code comparisons, commit-pinned (Our System `0b4ae4f`, Hermes `dce1e9b`,
  OpenAI Agents SDK `125efa0`), not yet committed.
- **`docs/spec_to_html.py` generalised** to render any Markdown/HTML page pair, not just the main
  spec (`CONTENTS_OPEN` is now a regex matching any page name, and the script takes `<markdown>
  <page>` arguments). This is what rendered the two comparison pages above. Not yet committed.
- **Spec sections 21.1, 21.10, 21.12, 21.14, 21.15, 21.16 written**, designing Windows and Linux
  (X11) helpers and a helper reached over a tailnet, alongside the Mac helper already built.
  `docs/bap-browser-spec.md` and the regenerated `docs/bap-browser-spec.html` carry this. Not yet
  committed on the main checkout.
- **A build plan for that design**, `docs/plans/2026-10-10-helpers-and-tailnet.md` (26 numbered
  steps across 7 parts): prove the tailnet for real, a shared refactor, add Pillow, Windows helper,
  Linux helper, settings/viewer, reach a helper over the tailnet. Untracked on the main checkout.
- **A worktree at `.claude/worktrees/computer-use-helpers`** (branch `worktree-computer-use-helpers`)
  has started that plan for real, well past the main checkout:
  - Checkpoint commit `57fca57` ("WIP: computer-use helper refactor and Windows helper") does plan
    steps 6-13: `MacLink` extracted to `driver/helper_link.py` as `HelperLink`; `driver/mac_driver.py`
    renamed `driver/helper_driver.py`; `service/mac_helper.py` renamed `service/helper_service.py`;
    `computer.mac_any_app` renamed `computer.helper_any_app`; `computer.runs` widened to include
    `"windows"` and `"linux"`; Pillow added to `pyproject.toml`; and a full `driver/windows_hands.py`
    (`WindowsHands`, `WINDOWS_APPS`, `ctypes` calls into `user32.dll`/`gdi32.dll`).
  - On top of that, uncommitted work (staged and unstaged) adds `tests/support/hands_stand_in.py`,
    `tests/unit/test_windows_hands.py`, `tests/unit/test_windows_helper.py`, trims
    `tests/unit/test_mac_helper.py`, and has started `src/bap_browser/driver/linux_hands.py`
    (untracked, no stand-in for it committed yet).
  - Verified in this session: `uv run pytest tests/unit/test_windows_hands.py
    tests/unit/test_windows_helper.py tests/unit/test_mac_helper.py -q` in that worktree gives
    **37 passed, 3 failed**. The 3 failures are pre-existing and unrelated to this work: they assert
    POSIX file permission bits (`0o600`, `0o700`) on files written on Windows, which does not support
    `chmod` that way — see Gotchas.

## State

- **Main checkout**, branch `docs/desktop-app-comparison`, last commit `0b4ae4f` (merge of PR #46,
  "Keep every file that holds a key, token or password out of the repository"). Working tree is
  **not clean**:
  - Modified, uncommitted: `docs/bap-browser-spec.html`, `docs/bap-browser-spec.md`, `docs/spec_to_html.py`
  - Untracked: `docs/plans/2026-10-10-helpers-and-tailnet.md`, `docs/research/computer-use-comparison.{md,html}`,
    `docs/research/desktop-app-comparison.{md,html}`, `.claude/worktrees/` (the worktree below)
- **Worktree** `.claude/worktrees/computer-use-helpers`, branch `worktree-computer-use-helpers`, on
  top of checkpoint commit `57fca57`. Working tree there is also **not clean**: staged changes to
  `docs/bap-browser-spec.html`, `docs/bap-browser-spec.md`, `docs/feature-map.json`, `docs/status.md`,
  `src/bap_browser/driver/windows_hands.py`, `tests/support/hands_stand_in.py` (new),
  `tests/unit/test_mac_helper.py`, `tests/unit/test_windows_hands.py` (new),
  `tests/unit/test_windows_helper.py` (new); plus unstaged changes to `src/bap_browser/agent/loop.py`,
  `src/bap_browser/keys.py`, `tests/unit/test_windows_helper.py`; plus an untracked
  `src/bap_browser/driver/linux_hands.py`.

## Next

1. On the `docs/desktop-app-comparison` branch: review the two new research pages and the spec/plan
   changes, then commit them (they read as finished prose, not drafts) before anything else touches
   those files, since the worktree below has a divergent copy of the same spec sections.
2. In `.claude/worktrees/computer-use-helpers`: decide whether the uncommitted staged/unstaged work
   is a checkpoint to commit now or still mid-edit, then continue the plan at
   `docs/plans/2026-10-10-helpers-and-tailnet.md` from around step 13 (wiring the Windows driver into
   `cli.py`'s `_helper`) — steps 11-12 (Windows hands + tests) look materially done per the test run
   above.
3. Reconcile the two spec copies: the main checkout's `docs/bap-browser-spec.md` and the worktree's
   version both edit sections 21.1/21.10/21.12/21.14-21.16; merging the worktree branch later will
   conflict there unless one is rebased onto the other first.
4. `docs/plans/2026-10-10-helpers-and-tailnet.md` step 0 (confirm SSH/Docker on the woken cloud VM)
   and step 1 (a real Tailscale key) are still unstarted and block part 1's live proof; they need the
   user's own cloud host and Tailscale admin console, not something an agent can do alone.

## Open questions

- Whether the worktree's uncommitted changes are ready to land as a commit, or are mid-edit and
  should be left alone until the user says to continue there.
- Whether `.claude/worktrees/` should be gitignored (it is currently untracked and showing in
  `git status` on the main checkout).

## Decisions made

- The Windows and Linux helpers are designed (spec 21.14, 21.15) before being built, following this
  project's practice of writing the spec section first.
- Windows before Linux, because this machine can prove Windows live without extra hardware, while
  Linux needs `scrot`/`xdotool` installed first and has desktop-environment-dependent app names
  (stated directly in the plan's "Order and why" section).
- `docs/spec_to_html.py` was generalised to take any markdown/page pair rather than writing a
  separate script per comparison page, since the frame-rewrite logic was already page-name-agnostic
  except for one hardcoded string.

## Files

- `docs/bap-browser-spec.md` / `.html` — the spec; sections 21.1-21.16 cover computer-use arrangements
- `docs/plans/2026-10-10-helpers-and-tailnet.md` — the 26-step build plan for this work
- `docs/research/desktop-app-comparison.md` / `.html` — Our System vs Hermes vs OpenAI Agents SDK, as a desktop app
- `docs/research/computer-use-comparison.md` / `.html` — the same three, on computer use only
- `docs/spec_to_html.py` — now renders any markdown/page pair, used for both the spec and the research pages
- `.claude/worktrees/computer-use-helpers/` — the in-progress Windows/Linux helper build, branch `worktree-computer-use-helpers`
- `src/bap_browser/driver/windows_hands.py`, `driver/helper_link.py`, `driver/helper_driver.py`, `service/helper_service.py` — worktree-only so far (renamed/new from the Mac-only originals)

## Gotchas

- `tests/unit/test_mac_helper.py`'s file-permission assertions (`0o600` on the pairing file, `0o700`
  on `start-helper.command`) fail when run on Windows: Windows does not honour POSIX `chmod` bits the
  way the test expects. This is a pre-existing gap in running Mac-helper tests on a Windows machine,
  not something introduced by the Windows-helper work; do not treat it as a regression caused by this
  session's changes.
- The worktree's `git status` shows renames as separate add+modify entries in places (e.g.
  `driver/mac_driver.py` -> `driver/helper_driver.py`) rather than clean renames, because the content
  changed enough in the move that git did not detect it as a rename; this is cosmetic, not a problem.
- Two copies of the same spec sections (21.1, 21.10, 21.12, 21.14-21.16) are being edited in parallel
  on the main checkout and in the worktree. They are not identical; do not assume one is a stale copy
  of the other without diffing them directly.
