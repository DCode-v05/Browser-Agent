# bap-browser on a remote machine: status report

Date: 8 October 2026 · Machine: the team box · Two runs on this day

| Run | Time (UTC) | Code |
|---|---|---|
| First | 12:33 to 12:50 | `main` at `f933e91` |
| Second, this update | 13:01 to 13:11 | `main` at `81a9438`: the same code with the corrected picture test (pull request 31, merged) |

## Summary

The second run started from a fresh copy of the code on the box and ran more than the first: every
test the project has, not only the real-browser tests of the tools. All 1,318 tests pass there, and
nothing fails in the speed check. The service started and answered through the tunnel. **The real
task with the model and the live view were not repeated in the second run**: the newly started
service refused the sign-in link the laptop had kept from the first run, and the new one was not
copied over. Their results below are from the first run. Nothing was added to the box's shared
environment, and no key or password was copied to it.

## What was checked in the second run

| Check | Result |
|---|---|
| A browser launches on the box | Yes: Chromium 153 |
| `bap-browser doctor` | Everything needed is in place. Only the model key is absent, by design |
| The bad-pattern check (`scripts/patterns.py`) | No new bad pattern; the 1 known case in the baseline |
| Scripted sign-up on the demo site, with no model | Passed: "Welcome, Ada" with 3 open invoices |
| Unit and service tests (`tests/unit`, `tests/service`) | 1,021 of 1,021 pass, in 51 s. New in this run |
| Real-browser tests of the tools (`tests/e2e`) | 172 of 172 pass at the first try, in 1 min 50 s. In the first run 171 |
| The viewer in a real browser (`tests/viewer`) | 125 of 125 pass, in 2 min 32 s, after one missing file was copied (see below). New in this run |
| Speed against the budget (`bap-browser bench`) | 23 OK, 9 warnings, 0 failures, 8 not measured |
| The service (`bap-browser serve`) | Started; answered on the box and through the tunnel |
| A real task with the model | **Not repeated.** First run: passed, 10 steps, 1 min 34 s |
| Live view from the laptop | **Not repeated.** First run: working, with no console error |

**The viewer tests needed one file.** At the first try 28 passed, 2 failed and 95 stopped with an
error, all for one reason: the tests read the accessibility checker from
`viewer/node_modules/axe-core/axe.min.js`, and the copy sent to the box holds no `node_modules`.
The box has no Node, so the packages cannot be installed there. That one file was copied from the
laptop, and all 125 passed. This was a gap in what was copied, not a fault in the viewer.

## The machine

| | |
|---|---|
| System | Amazon Linux 2023, kernel 6.18, x86_64 |
| Size | 32 CPUs, 61 GB of memory, no GPU |
| Access | SSH as the shared user `team`, with a key registered on the box's start page |
| Limits | No `sudo`. It turns off after 15 idle minutes, after 4 hours, or when the team's shared budget is spent |
| Browser build | Playwright says this system is not officially supported and uses its build for Ubuntu 24.04. That build launches here |

## How it was set up

Two arrangements were used. Both keep the model key off the box.

**1. Everything on the box, for the checks.** The code and the built viewer were copied to the box
as one archive of 2.1 MB. It was unpacked into a folder of its own and given an environment of its
own with `uv sync`. `doctor`, the scripted run, the tests and the bench ran there with no model.

**2. The browser on the box, the agent on the laptop, for the real task.**

```
laptop                                        team box
------                                        --------
agent loop + model + key                      bap-browser serve (127.0.0.1:8795 only)
        |                                        |-- the browser (headless Chromium)
        |--- MCP over HTTP ---- SSH tunnel ----> |-- the 27 tools
viewer in a browser tab <------ SSH tunnel ----- |-- the viewer and the live picture
```

- On the box, `bap-browser serve` listens on the box itself only. It is not reachable from the
  internet.
- An SSH tunnel carries one port from the laptop to the box. The viewer and the tool calls both go
  through it.
- The agent's model call is made from the laptop. Only tool calls and their results cross to the
  box.

## The real task (first run)

The agent was asked to check in for booking SK4821, choose a window seat, and report what the
boarding pass says. It did so in the browser on the box:

| Step | What it did |
|---|---|
| 1 | Opened the demo site's start page |
| 2 | Clicked "Skylark Air: check in online" |
| 3 | Read the page |
| 4 | Filled the booking reference and the last name |
| 5 | Clicked "Find booking" |
| 6 | Read the page |
| 7 | Chose "14A, window" |
| 8 | Ticked "I am not carrying any dangerous goods" |
| 9 | Clicked "Check in" |
| 10 | Read the boarding pass |

Its answer: seat 14A, flight SK 214 from Chennai to Singapore on 12 October, boarding 08:55, gate
B7, departure 09:40, standard meal. This matches the page. In the viewer, the live picture, the
address and all ten steps were shown, and Pause, Take over and Stop session were on offer.

## The test that failed, and what it was

`tests/e2e/test_pictures.py::test_the_labels_of_a_marked_picture_do_not_stay_in_the_page`

The test takes a plain picture of a page, then one with numbered labels drawn on it, then a plain
one again. It expected the two plain pictures to be the same to the byte. On the box they were not,
every time.

| What was measured on the box | Result |
|---|---|
| An empty layer put over the page and taken off again | The picture is the same to the byte |
| The labels drawn and taken off again | 3 pixels differ |
| By how much | One shade of grey out of 255: 213 became 212 |
| Where | The rounded corners of a list box the browser draws itself, at its right edge |
| Elements in the page before and after | The same number: the labels were removed |
| A second later, and with the pointer moved away | The same 3 pixels |

**Cause.** The labels are removed, as the test's name asks. Once something has been drawn over a
native control, the browser on this machine draws three pixels of that control's rounded corners one
shade apart. Nobody could see it. The test asked for more than it meant: the same bytes, where it
meant the same picture.

**Fix.** The test now compares the two pictures as a person sees them: no colour of any pixel may be
more than 2 shades out of 255 apart. A label left on the page is 183 shades from the page under it,
so the test still catches what it is for. The comparison is in `tests/support/pictures.py`, with six
tests of its own. No code of the product was changed: there was no fault in it.

**After the fix, on the box.** In the first run the corrected test passed three times out of three.
In the second run, from a fresh copy of the code, the whole suite passed at the first try: 172 of
172. The fix is merged into `main`.

## The speed warnings: six are the frame waits, three are lines close to their target

Nine lines of the bench are in the warning band in each run on the box, but not the same nine. The
laptop's figures are from the same day. All times are the median, in milliseconds.

| Line | Box, first run | Box, second run | Laptop | Target | Fail limit |
|---|---|---|---|---|---|
| Click by ref, small page | 66.7 | 66.7 | 66.8 | 50 | 100 |
| Click by ref, big page | 66.6 | 66.6 | 66.9 | 50 | 100 |
| Hover by ref | 83.3 | 83.3 | 83.6 | 50 | 100 |
| Set a checkbox | 66.7 | 66.6 | 66.6 | 50 | 100 |
| Press a key, big page | 16.7 | 16.7 | 16.7 | 10 | 30 |
| Scroll one step | 66.7 | 66.6 | 66.5 | 60 | 120 |
| Click at a point | 10.0 | 8.7 | 16.7, **over the limit** | 5 | 15 |
| Press a key, small page | 6.5 | 7.4 | 1.7 | 5 | 15 |
| Find an element, small page | 5.3 | 3.9, OK | 1.3 | 5 | 15 |
| Read the network log | 1.7, OK | 2.3 | not compared | 2 | 10 |

**Six lines are the same in both runs and on both machines.** A click, a hover, a checkbox, a
scroll and a key on a big page wait for the page to hold still for some frames, and a frame is
16.7 ms. One frame is 16.7 ms, four are 66.7 ms and five are 83.3 ms, which is what is measured
every time, against targets of 10, 50 and 60.

**Three lines sit close to their target and move from run to run.** Finding an element went from
5.3 to 3.9 and is inside its target of 5 in the second run. Reading the network log went from 1.7
to 2.3 and is just over its target of 2. Pressing a key on a small page was 6.5 and then 7.4. These
are work the processor does, with no waiting; on the laptop the same work takes about a quarter of
the time, so a core of the box is slower than a core of the laptop. Nothing in the code makes the
difference, and nothing was changed for it.

**A click at a point** takes one frame on the laptop, 16.7 ms, which is over that line's limit of
15; on the box it took 10.0 and then 8.7.

The frame waits are a choice between two things the project wants, and it was left for its owner:

- Wait fewer frames (`browser.timeouts.settle_frames`, 2 now). Faster; the risk is acting on a page
  that is still moving, or missing a page change that an action started.
- Or set the targets of these lines to what the waits cost, in `perf/budget.json` and spec
  section 11.

Eight lines were not measured because no scenario is written for them yet: drag, slow typing,
answering a dialog, running a script, upload, download by click, and the two for asking a person.

## What was left on the box

| What | Where | Size |
|---|---|---|
| The code and its own environment (the fresh copy of the second run; the first run's copy was removed) | `~/bap-browser-check` | 273 MB |
| The logs of both runs (`check-20261008-123339.log`, `check-after-fix.log`, `check-20261008-130130.log`, `viewer-tests-second.log`), the first run's service log and event log | `~/results/bap-browser/` | 32 KB |
| Chromium | `~/.cache/ms-playwright`, already there from an earlier setup | 658 MB, not added by this check |

- Nothing was installed into the shared environment (`/opt/venv`).
- Nothing in `~/work`, `~/chromelibs` or any other folder on the box was changed.
- No model key, password or `.env` file was copied to the box.
- One file of a test tool, `axe.min.js`, was copied into `~/bap-browser-check/viewer/node_modules/`.
- At 13:11 UTC every tmux session of this check was ended, no process of it was left running, and
  the tunnel was closed. The box turns itself off when nobody else is using it.

## What was not checked

- In the second run: the real task with the model, and the live view from the laptop (see the
  Summary). To repeat them, the new sign-in link that `serve` prints has to be taken to the laptop.
- The person's own Chrome through the extension: the box has no screen.
- The three-browser window (`bap-browser studio`) on the box: it needs a model key there, and none
  was put there.
- The task sets of the Evaluations view on the box: they are run from that window.
- More than one session at a time, and how many browsers the box can hold.
- Reaching the box without a tunnel. The service was kept on the box's own address on purpose.

## To do it again

The box's address changes each time it starts; take it from the start page.

```bash
# On the laptop: copy the code with the built viewer, then connect. For the viewer tests, send
# viewer/node_modules/axe-core/axe.min.js as well: the box has no Node.
scp bap-browser-check.tar.gz team@ADDRESS:/tmp/
ssh team@ADDRESS

# On the box, inside tmux:
tar -xzf /tmp/bap-browser-check.tar.gz -C ~ && cd ~/bap-browser-check
uv sync && uv run playwright install chromium
uv run pytest tests/unit tests/service tests/e2e tests/viewer -q -p no:cacheprovider
uv run bap-browser bench                         # set BAP_BROWSER__BROWSER__CHROMIUM_SANDBOX=false first
uv run bap-browser doctor
uv run bap-browser serve --config serve.json     # serve.json sets the port to 8795

# On the laptop, in a second terminal: the tunnel, then the viewer's address that `serve` printed.
ssh -N -L 8795:127.0.0.1:8795 team@ADDRESS
```

When done, end the tmux session on the box. An open one counts as work and keeps the box on.
