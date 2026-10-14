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
| 1 | CLI split (`--browser` / `--desktop`, merged pages) | Not started | | |
| 2 | Auth + `--dev` bypass | Not started | | |
| 3 | Take-over UX (background delivery default, working indicator, task queue) | Not started | | |
| 4 | Windows prerequisites / first-run permissions flow | Not started | | |
| 5 | Full visual redesign (all pages, settings named specifically) | Not started | | |
| 6 | VM direction 2 (VM drives Windows) | Not started | | |
| 7 | Full Windows computer-use evaluation via live UI | Not started | | |
| 8 | Final explanation doc | Not started | | |
| 9 | Merge every branch into main (incl. committing `worktree-computer-use-helpers`'s WIP first) | Not started | | |

## Decisions already made (do not re-ask)

- WIP on `worktree-computer-use-helpers`: commit as-is, then merge.
- UI scope: full visual redesign, not just polish.
- Take-over UX: the background-delivery + indicator + task-queue design above, approved.
- Shipping: one PR per piece.
