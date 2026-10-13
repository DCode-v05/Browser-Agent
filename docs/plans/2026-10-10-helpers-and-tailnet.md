# Windows and Linux helpers, and a helper reached over the tailnet: plan

> **Where this plan stands, 13 October 2026.** After it was written, spec section 22 replaced its
> design: Windows, macOS and Linux are driven by Hermes' driver, and no input code of our own is
> written for any of them. The plan's goals are met by that route, but for the live proofs.
>
> | Part of this plan | Steps | What became of it |
> |---|---|---|
> | Prove arrangement 3 on a real tailnet | 0 to 5 | Not done. It needs your cloud host and a Tailscale key, as the plan says. The VM's image is now built, and its start with a refused key is tested in a real container |
> | The shared refactor of the Mac helper | 6 to 9 | Dropped. The Mac helper is removed: "This Mac" goes through Hermes' driver (status 1ai) |
> | Add Pillow | 10 | Dropped. The driver makes and sizes the pictures |
> | The Windows helper | 11 to 15 | Met another way. `bap-browser computer helper` is one program for all three systems, and on Windows it was proven with the real driver: field found by number, typed into, confirmed by Notepad (status 1af) |
> | The Linux (X11) helper | 16 to 20 | Met another way, the same: proven on Ubuntu, and in the contained desktop's container (status 1af, 1aj) |
> | Settings and the viewer | 21 to 23 | Met. "This machine" and "A machine elsewhere" are in the settings, and the Computer tab has a setup page (status 1ag). One choice covers all three systems, in place of "This PC" and "This Linux machine" |
> | Reach a helper over the tailnet | 24 to 26 | Built differently, and not proven live. The helper listens on its own machine only and `tailscale serve` shows it to the tailnet, in place of binding to the tailnet's address with `--host`. It checks a pairing code and who Tailscale says the caller is |
>
> The branch `worktree-computer-use-helpers` holds steps 6 to 13 as they were first built. It is not
> merged and cannot be: it extends the helper that was removed.

Written on 2026-10-10. Spec sections 21.1, 21.10, 21.12, 21.14, 21.15 and 21.16 already say what
this builds; this is the order to build it in. Three things, asked for together:

1. Arrangement 3 (section 21.12), proven for real: a real Tailscale key, the micro VM on your own
   cloud host joining your tailnet, its viewer reached over it, a private service reached through it.
2. Two new helpers, Windows and Linux (X11), at the same safety bar as the Mac helper already built.
3. Arrangement 4 reached over the tailnet (section 21.16): any of the three helpers, reached by the
   engine on the micro VM instead of only on `127.0.0.1`.

Not in this plan: Wayland (section 21.10), reading apps through their accessibility tree, a desktop
of macOS or Windows itself (as opposed to a helper on one).

## Before any code: confirm the host

Your cloud VM is woken by a Lambda URL you hold. That URL is a secret-equivalent (public, no
authentication, starts a billable resource): it goes in your own shell or a local, gitignored file,
never in `config.json`, never in a commit, never pasted into an issue or a log. This plan does not
write it anywhere in the repository.

- [ ] **0. Confirm SSH and Docker on the woken VM.** Wake it, SSH in, run `docker --version`. If
  Docker is missing, install it before anything else (the exact step depends on the VM's own image,
  which is not yet known). No test; this is a one-time check of the machine, not of the code.

## 1. Prove arrangement 3 for real (no code changes expected)

- [ ] **1. A real key.** In the Tailscale admin console, make a reusable, ephemeral, tagged key
  (`tag:bap-browser`), and an ACL rule granting that tag only what it needs (reaching the private
  service you intend to test with, and nothing else). Keep the key out of the repository the same
  way as the Lambda URL.
- [ ] **2. Build and run the image on the VM.**
  ```bash
  docker build --build-arg TAILSCALE=true --build-arg DESKTOP=true -f deploy/Dockerfile -t bap-browser-computer .
  docker run --rm -p 8765:8765 -e BAP_BROWSER_TOKEN=<a long random string> -e TS_AUTHKEY=<the real key> \
    bap-browser-computer uv run --project /app --no-sync bap-browser serve --desktop
  ```
  Confirm in the container's own log: it joins the tailnet, `tailscale serve` starts, and
  `BAP_BROWSER__SERVER__PUBLIC_URL` is set to the tailnet's own HTTPS address (`deploy/vm-start.sh`
  prints it).
- [ ] **3. Reach it.** From a second machine on the same tailnet (or your own, if it's a tailnet
  member), open the printed `https://<name>.<tailnet>.ts.net` address and see the viewer; drive a
  task on the VM's own contained desktop through it.
- [ ] **4. Reach a private service through it.** Point the agent (or `browser_navigate`, if you build
  the browser image instead of `DESKTOP=true`) at an address private to your tailnet, and confirm it
  loads, through `BAP_BROWSER__BROWSER__PROXY__SERVER`'s local proxy.
- [ ] **5. Write down what you found** in `docs/status.md`, the way sections 1u to 1w already do:
  what ran, on what, and what (if anything) in `deploy/vm-start.sh` or `deploy/Dockerfile` needed a
  change to work on your actual host. Fix those before step 2 of this plan, not after.

## 2. The shared refactor (small, before either new helper)

One commit, no behaviour change for the Mac helper; `uv run pytest` must still pass exactly as before.

- [ ] **6. Extract `HelperLink`.** Move `MacLink` out of `driver/mac_driver.py` into a new
  `driver/helper_link.py`, renamed `HelperLink`. It has nothing Mac-specific in it today (`url`,
  `token`, HTTP calls); moving it changes no behaviour. `MacDriver` imports it from there.
- [ ] **7. Take the app map out of `Helper`.** In `service/mac_helper.py`, `Helper.app_names` and
  `act()`'s `open` case use `MAC_APPS` directly. Give `Helper.__init__` an `apps_by_name: dict[str,
  str]` parameter instead, and pass `MAC_APPS` for it from `cli.py`'s `_helper`. No test changes if
  done right: `tests/unit/test_mac_helper.py` passes unchanged.
- [ ] **8. Rename the shared setting.** `config_computer.py`: `mac_any_app` → `helper_any_app`,
  docstring generalised. Update its three call sites (`driver/mac_driver.py`, `safeguards/check.py`,
  `tools/computer_tools.py`) and `settings/catalogue.py`'s `computer_mac_any_app` →
  `computer_helper_any_app` (id, title, key). `uv run pytest -q` passes; `grep -rn mac_any_app src`
  finds nothing.
- [ ] **9. Widen `computer.runs`.** `Literal["container", "here", "mac"]` →
  `Literal["container", "here", "mac", "windows", "linux"]`. `desktop_driver_for` (`driver/mac_driver.py`,
  soon to be the shared dispatch point) grows the two new branches once the drivers below exist; for
  now it is a no-op change plus the type.
- [ ] **Check:** `uv run pytest -q`, `uv run ruff check .`, `uv run pyright`. Nothing about the Mac
  helper's behaviour changes; this step is purely the seam the next two need.

## 3. Add Pillow

- [ ] **10. `pyproject.toml`**: add `pillow` to `dependencies` (check its current version against
  PyPI before pinning a range, per the version actually resolved). `uv sync`. No test of its own;
  it is exercised by steps 11 and 14.

## 4. The Windows helper (spec 21.14)

- [ ] **11. `driver/windows_hands.py`.** A `WindowsHands` class implementing the `Hands` Protocol
  (`driver/mac_hands.py` has the protocol to match exactly): `screen()` via
  `GetSystemMetrics(SM_CXSCREEN/SM_CYSCREEN)`; `pointer_at()` via `GetCursorPos`; `click`/`move`/
  `press`/`drag`/`scroll` via `SendInput` with `MOUSEINPUT` (absolute coordinates, normalised to
  0–65535); `type_text`/`key` via `SendInput` with `KEYEVENTF_UNICODE` and a virtual-key table (the
  Windows equivalent of `NAMED_CODES`/`CHARACTER_CODES`); `picture()` via `BitBlt` from the desktop
  device context into a memory bitmap, then Pillow to resize and JPEG-encode; `allowed()` always
  `(True, True)` and `ask_for_access()` a no-op (section 21.14's note: Windows has no Mac-like gate);
  `open_app`/`running`/`front`/`quit_app` via `EnumWindows`, `GetForegroundWindow`,
  `GetWindowThreadProcessId`, and `subprocess` for launching `notepad.exe`, `explorer.exe`, a
  calculator and a terminal by name. A `WINDOWS_APPS` map, the shape of `MAC_APPS`.
- [ ] **12. Tests first.** `tests/unit/test_windows_hands.py`: the virtual-key table covers every
  name `bap_browser.keys.normalise` can produce (mirror `test_mac_hands.py`'s coverage, if that file
  exists, or write the equivalent cases fresh); a point built from `SendInput`'s struct layout is
  checked against known byte offsets without needing a real Windows session, the way CoreGraphics's
  structs are checked today.
- [ ] **13. Wire it into the helper.** `cli.py`'s `_helper`: branch on `sys.platform` (`darwin` →
  `MacHands`/`MAC_APPS`, `win32` → `WindowsHands`/`WINDOWS_APPS`) instead of refusing every platform
  but Mac. `driver/mac_driver.py`'s `desktop_driver_for` (or wherever it lands after step 9) picks
  the matching driver for `computer.runs == "windows"`.
- [ ] **14. `tests/unit/test_windows_helper.py`**, mirroring `test_mac_helper.py` exactly: the token,
  a missing app refused, the stop corner, `any_app`. Uses a stand-in `Hands`, not a real Windows API
  call, so this test runs on any OS, including CI.
- [ ] **15. Live proof, by hand, on this machine** (it is Windows): `uv run bap-browser helper
  --allow text_editor,calculator`, then a task through the built-in desktop choosing "This PC",
  opening the calculator and typing into Notepad. Write what happened into `docs/status.md`.
- [ ] **Check:** `uv run pytest tests/unit/test_windows_hands.py tests/unit/test_windows_helper.py -q`,
  then `uv run pytest -q` for the whole suite, `ruff check`, `pyright`.

## 5. The Linux (X11) helper (spec 21.15)

- [ ] **16. `driver/linux_hands.py`.** A `LinuxHands` class: `picture()` shells out to `scrot` (or
  `maim` if `scrot` is not on the path — check both with `shutil.which`) for the raw capture, then
  Pillow for resize/encode; `click`/`move`/`press`/`drag`/`scroll`/`type_text`/`key` shell out to
  `xdotool`; `screen()` via `xdotool getdisplaygeometry`; `open_app` tries an ordered candidate list
  per app id (text editor: `gedit`, `kate`, `mousepad`; files: `nautilus`, `dolphin`, `pcmanfm`;
  calculator: `gnome-calculator`, `kcalc`, `galculator`; terminal: `gnome-terminal`, `konsole`,
  `xterm`), resolved with `shutil.which` at helper start, not per call; `allowed()` always
  `(True, True)`. A refusal at start (not at every call) if neither `scrot`/`maim` nor `xdotool` is
  found, naming which is missing and that it must be installed by hand (section 21.15).
- [ ] **17. `tests/unit/test_linux_hands.py`**: the candidate-list resolution (a stand-in `which`
  that reports only some programs present, confirm the first found wins); the refusal when neither
  capture tool is on the path.
- [ ] **18. Wire it in**, the same shape as step 13: `sys.platform == "linux"` → `LinuxHands`.
- [ ] **19. `tests/unit/test_linux_helper.py`**, mirroring `test_mac_helper.py` and
  `test_windows_helper.py`.
- [ ] **20. Live proof, by hand, on a Linux machine you have** (or a disposable cloud one, confirmed
  to have `scrot`/`xdotool` installed, or install them first): the same task as step 15. Write the
  result into `docs/status.md`, naming the desktop environment it was run on.
- [ ] **Check:** `uv run pytest tests/unit/test_linux_hands.py tests/unit/test_linux_helper.py -q`,
  then the whole suite, `ruff check`, `pyright`.

## 6. Settings and the viewer

- [ ] **21. `settings/catalogue.py`**: add `Option("windows", "This PC", ...)` and
  `Option("linux", "This Linux machine", ...)` to the `computer_runs` `Choice`; generalise its title
  and description off "this Mac itself" to name all three.
- [ ] **22. The viewer.** `viewer/src/Studio.tsx`, `viewer/src/systems/SystemsPage.tsx`,
  `viewer/src/studio/rooms.ts`: wherever `room.runs === 'mac'` picks Mac-only wording or a Mac-only
  "start the helper" button, widen it to the other two `runs` values. `viewer/src/wording.ts` gains
  whatever new strings this needs (every string a person reads lives there, per this project's
  rule). `npm --prefix viewer run typecheck`, `run lint`, `run test`, `run build`. Also update
  `docs/feature-map.json`'s `computer-use` entry with the new files and tests of parts 4 and 5, so
  the test that checks the map against the code still passes.
- [ ] **23. `cli.py`'s `_helper` help text and `start_helper_in_terminal`-equivalent**, if a
  per-platform "start it for me" button is wanted on Windows/Linux the way it exists for the Mac
  (`start-helper.command`). This is the one open design question this plan defers: decide, when
  reached, whether a Windows `.bat`/`.ps1` and a Linux `.sh` equivalent are worth building now or
  left as "start it from a terminal yourself" for this first round.

## 7. Reach a helper over the tailnet (spec 21.16)

Needs step 1 (a real tailnet) and at least one of the Windows/Linux work above (or the existing Mac
helper) done first.

- [ ] **24. `cli.py`'s `helper` command**: confirm `--host <tailscale-ip>` already works for binding
  to a specific address (it does today, per `--host`'s existing argument) — no code change expected,
  only a docs one.
- [ ] **25. Documentation**: `docs/bap-browser-spec.md` section 21.16 already says the design;
  extend `README.md` or `docs/systems-guide.md` with the concrete steps: find the machine's
  Tailscale address (`tailscale ip -4`), start the helper with `--host` set to it, set
  `computer.helper_url` and `BAP_BROWSER_HELPER_TOKEN` on the engine side to match.
- [ ] **26. Live proof.** The micro VM from part 1, on your tailnet; this machine (or whichever
  platform's helper is built and reachable), on the same tailnet; the engine on the VM given the
  helper's Tailscale address; a task run from the VM's own viewer that ends up acting on this
  machine, its screenshots streamed back through the VM's viewer. Write the result into
  `docs/status.md`: this is the point where all three arrangements (2, 3, 4) are proven together,
  which the spec has never claimed before.

## Order and why

Part 1 before part 4/5: proving the tailnet first means part 7's live proof has a VM to reach from,
and surfaces any `deploy/vm-start.sh` problems early, on the actual host, before more code depends on
it. Part 2 before parts 4 and 5: the refactor must land, proven behaviour-neutral for the Mac helper,
before either new helper is built on top of it — building on the old shape and refactoring after
would touch the new code twice. Windows before Linux, per your own call: it is what this machine can
prove live without extra hardware; Linux's extra prerequisite (installing `scrot`/`xdotool`) and its
app-name uncertainty make it the better second, not first.

## Check, start to finish

```bash
uv run pytest -q
uv run ruff format --check . && uv run ruff check .
uv run pyright
uv run python scripts/gate.py
npm --prefix viewer run typecheck && npm --prefix viewer run lint && npm --prefix viewer run test && npm --prefix viewer run build
```
