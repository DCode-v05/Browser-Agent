# Production UI/UX pass: progress log

This is a working log for one large, multi-part task, kept so the work survives a context
compaction. Re-read this file first after any gap. Update it after each piece finishes, fails, or
changes shape — not just at the end.

## The ask (verbatim intent, not the user's exact words)

1. CLI split: `--browser` (3 browser pages + Computer tab, merged into one page like production)
   and `--desktop` (desktop app shell + Computer tab, 2 pages merged). Both carry computer use.
2. Auth: real sign-in enforced; a `--dev` flag bypasses it for local development only.
3. Take-over UX: computer_use must not block the person's own use of their machine. Agreed
   design: background delivery stays the default on a person's own machine (already
   `computer.base.delivery=auto`); add a non-blocking "agent is working" indicator; let a person
   queue a new chat task instead of being refused one while a task runs.
4. Windows prerequisites: what permissions/software are needed, asked for up front (first run).
5. Full visual redesign of the viewer, every page, with the settings page named specifically.
6. VM work (`ssh team@13.201.94.97`, a headless Linux box, not Windows, shared with another
   project — see "VM facts" below): both directions of computer-use control between this Windows
   machine and that VM.
7. Full Windows computer-use evaluation, done through the live UI, not scripts, verified visually.
8. A final doc: what was done, what is left.
9. Ship: one PR per piece, merged as each is done; at the end, merge every other branch into main
   too (including `worktree-computer-use-helpers`, whose uncommitted WIP is to be committed as-is
   first, per the user's explicit answer).

## VM facts (established, do not re-derive)

- `ssh team@13.201.94.97` — Amazon Linux 2023, 32 cores, 61GB RAM, 30GB disk. No sudo password
  available. Key: `C:\Users\denis\.ssh\id_ed25519` (already authorized, no password needed).
- Shared box: `~/bap-browser-check` (a stale, non-git, Oct-8 packed snapshot, used by its own
  headless `box_check.sh`) and `~/kasukabe*`, `~/results`, `~/run*.log` (an unrelated project, real
  paid model spend already happened there) — never touched, never will be.
- My own isolated folder: `~/bap-browser-remote-agent` (rsync'd from this machine, excludes
  `.venv`, `node_modules`, `.git`, caches). Safe to rebuild/replace freely.
- Rootless Docker installed there (`curl -fsSL https://get.docker.com/rootless | SKIP_IPTABLES=1
  sh`; iptables needs root and was skipped). `export PATH=/home/team/bin:$PATH
  DOCKER_HOST=unix:///run/user/1001/docker.sock` before any docker/uv command over SSH.
- `bap-browser-desktop:latest` image built there from `deploy/desktop.Dockerfile`.
- Direction 1 (Windows watches/drives the VM's contained desktop) is **proven working**: studio
  runs on the VM (port 8798), reached from this Windows machine's Chrome via
  `ssh -L 8798:127.0.0.1:8798 team@13.201.94.97`. Verified visually: Computer tab live, "Ready".
- Found and fixed along the way (shipped as PR #67, merging now): `docker cp` into a running
  rootless container broke (`remount-ro ... operation not permitted`) whenever an app was
  disabled (the default: no terminal) — fixed by bind-mounting the driver in at the container's
  start instead of copying it in after. See `docs/status.md` → "The contained desktop under a
  rootless container program".
- Direction 2 (VM's agent drives this real Windows desktop) — **not started yet**. Plan: run
  `bap-browser computer helper --this-machine-alone` on Windows (driving this real screen via the
  already-installed, already-doctor-confirmed `cua-driver`); open a reverse SSH tunnel
  (`ssh -R 8796:127.0.0.1:8796 team@...`) so the VM-side engine, with `computer.runs=remote` and
  `helper_url=http://127.0.0.1:8796`, reaches it as if local (satisfies the helper's
  `THIS_MACHINE`-only trust check in `machine_helper.py` without Tailscale).
- The reverse-tunnel approach works because `machine_helper.refusal()` trusts a caller whose
  `caller.client.host` is `127.0.0.1`/`::1`/`localhost` with no `X-Forwarded-For` header — exactly
  what an SSH `-R` tunnel's far end looks like, with `--this-machine-alone` (`helper_tailnet` off).

## Piece-by-piece status

| # | Piece | Status | Branch / PR | Notes |
|---|---|---|---|---|
| 0 | Anthropic model provider (earlier in session) | **Shipped** | PR #66, merged | Unrelated to this bundle, done before it started |
| 0b | Contained-desktop rootless-Docker fix | **Shipped**, CI green, merging now | PR #67 `fix/contained-desktop-rootless-docker` | |
| 1 | CLI split (`--browser` / `--desktop`, merged pages) | Backend done, Electron side not started | PR #70, CI running | `built_in_config(keep_cdp=)`, `Studio(rooms_mode=)`. Desktop app itself still spawns the old single-session core; adding its Computer pane is its own remaining sub-piece |
| 2 | Auth + `--dev` bypass | In progress (parallel agent, worktree `feature/auth-dev-bypass`) | | Agent ID `a71d84e20f28aa9b9` |
| 3 | Take-over UX (background delivery default, working indicator, task queue) | In progress (parallel agent, worktree `feature/take-over-ux`) | | Agent ID `a771d48be4f2db121` |
| 4 | Windows prerequisites / first-run permissions flow | **Mostly already built** (found, not built this pass): `MachineSetup.tsx` already shows a worded reason, Install/Allow actions, and auto-retries via `computer.lacks()` + `machine_setup.until_ready()`, e2e-tested. One real, narrow gap found and left open: `computer.lacks()`'s automatic-retry check never probes the driver's runtime contract or doctor's live capability checks on Windows (only driver presence + macOS TCC) — a broken-but-installed driver gets no friendly message until a raw error surfaces later. Not fixed: changing `lacks()` affects every backend (`machine`/`remote`/`container`) with no test precedent, too risky to rush. | No PR (no code changed) | Agent `a7c3de48eccb159d6`. Follow-up: extend `lacks()` to call `cua_driver_runtime_contract_status` on non-macOS before returning `None`; add a test in `tests/unit/test_computer.py` |
| 5 | Full visual redesign (all pages, settings named specifically) | **Partial**: Systems/settings page spacing+hierarchy pass done (within existing tokens — judged the current token set coherent, not broken), a second real bug found+fixed (admin "users" view rendered nothing while policy was loading). Studio page and everything else: not started, out of budget. | PR #71 `feature/visual-redesign-pass`, CI pending | Agent `aa6b77ecea0bc2b56`. 624 viewer tests pass (had to use `--pool=threads`, a Windows-long-path env quirk in that worktree, not a real failure) |
| 6 | VM direction 1 (Windows drives VM) | **Done**, verified visually | shipped in PR #67 | |
| 6b | VM direction 2 (VM drives Windows) | Not started | | Plan: `computer helper --this-machine-alone` on Windows + reverse SSH tunnel, see "VM facts" above |
| 7 | Full Windows computer-use evaluation via live UI | Not started | | |
| 8 | Final explanation doc | Not started | | |
| 9 | Merge every branch into main (incl. committing `worktree-computer-use-helpers`'s WIP first) | 1 of several done | PR #67 merged; #70 pending | |

## Decisions already made (do not re-ask)

- WIP on `worktree-computer-use-helpers`: commit as-is, then merge.
- UI scope: full visual redesign, not just polish.
- Take-over UX: the background-delivery + indicator + task-queue design above, approved.
- Shipping: one PR per piece.
