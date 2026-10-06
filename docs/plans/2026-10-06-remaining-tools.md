# The ten remaining tools: plan and state

Written on 2026-10-06, when the work was stopped part-way, and finished the same day. Branch
`wip/remaining-tools`: `uv run pytest -q` gives 902 passed. Steps 1 to 8 below are done; step 9, onto
`main`, is a pull request.

The tools: `browser_screenshot`, `browser_zoom`, `browser_drag`, `browser_handle_dialog`,
`browser_tabs`, `browser_console`, `browser_network`, `browser_evaluate`, `browser_upload_file`,
`browser_downloads`. With them there are 28 tools. Three exist only when their feature is on:
`browser_evaluate` (off by default), `browser_upload_file`, `browser_downloads`.

## How it is built

| Part | Where | How |
|---|---|---|
| Tabs | `driver/playwright_driver.py` | Every page is a `_Tab` with its own DevTools session, page script, counters, console and network logs. An action works on the tab that was active when it began. Tab ids and refs are never used twice, in any tab |
| Pop-ups | same | A window that one of the agent's tabs opens becomes a tab (`_adopt`). The page says when it opens one (`Page.windowOpen`), so an action waits for the new tab and its own result already shows it. A window opened by anyone else in the same browser is left alone |
| Dialogs | same, and `tools/toolkit.py` | The driver keeps an open dialog until it is answered or its time runs out. The toolkit runs each tool against "a dialog opened": when one does, the call returns with the dialog and the action is kept, to be finished after `browser_handle_dialog`. Time limits do not count the time a dialog is open (`_within`) |
| What happened by itself | `driver/base.py` (`Happened`), `driver/session.py` | The driver tells the session; the session keeps it for the agent's next result (`[events]`) and passes it on to the viewer (`dialog_opened`, `dialog_closed`, `download_saved`) |
| Pictures | `results.py` (`Picture`), `tools/registry.py` (`Shown`) | A tool may return a picture with its text. Over MCP it is an image; the reference loop sends the model the newest picture only |
| Uploads | `policy/files.py` | A file must be inside `browser.uploads.allowed_dirs`. The element is clicked and the file chooser that opens is given the files |
| Downloads | `driver/playwright_driver.py` (`_save`) | Saved in `browser.downloads.dir` under a name of their own; a name the page suggests is never used as a path |

Two new settings: `browser.capture.read_limit` (50) and `browser.capture.max_state_events` (20).

## State of each tool

| Tool | State |
|---|---|
| `browser_tabs`, pop-ups | Works. `tests/e2e/test_tabs.py`: 7 pass |
| `browser_handle_dialog` | Works. `tests/e2e/test_dialogs.py`: 9 pass |
| `browser_console`, `browser_network`, `browser_evaluate` | Work. 3 tests pass in `tests/e2e/test_files_and_logs.py` |
| `browser_screenshot`, `browser_zoom` | A real fault, below. `tests/e2e/test_pictures.py`: 7 pass, 2 fail |
| `browser_upload_file` | The files reach the page. One test fails: it reads the page before the page has read the file |
| `browser_downloads` | Works. One test fails: it refuses a saved name with ".." in it (`_.._escape.txt`), which is inside the folder and harmless |
| `browser_drag` | Not seen working yet. Its test stops at the wording of the result |

## What is left, in order

- [x] **1. Pictures: take them the way the browser's own driver does.** A capture with a clip and a
  scale asked for on our own DevTools session makes the browser reset the screen that Playwright
  emulates (device scale, viewport): seen with `browser.device_scale_factor: 2`, where the picture
  came out half size. The cure, designed and not applied:
  - `_capture` calls `tab.page.screenshot(type=..., full_page=..., clip=..., scale="css" or "device")`
    instead of `Page.captureScreenshot` on `tab.cdp`. `scale="css"` gives one picture pixel per page
    pixel on any screen; `"device"` gives every pixel, for `browser_zoom`. With `full_page=True` a
    `clip` is in page coordinates.
  - The true size of a picture is read from its first bytes: `driver/screenshots.py` (`size_of`,
    already on this branch, not yet used).
  - A picture whose longest side is over `browser.screenshot.max_dimension` is made smaller by the
    browser itself, in the page script: a new operation `shrink` (`atob`, `createImageBitmap` with
    `resizeWidth` and `resizeHeight`, an `OffscreenCanvas`, `convertToBlob`, back as base64). No
    image library is needed. `_fitted(tab, picture)` returns the picture and how much smaller it is.
  - `screenshot()` then keeps `_Taken(x, y, scale, width, height)` from the true size, and
    `tab.pixel = 1 / scale` for a picture of what the browser shows.
  - Add to the dense-screen test: after the picture, `devicePixelRatio`, `innerWidth` and
    `innerHeight` are what they were.
- [x] **2. The five failing new tests.**
  - `test_a_region_of_the_last_screenshot_at_full_resolution`: sizes within 2 pixels, not exact.
  - `test_on_a_dense_screen_...`: passes once step 1 is done.
  - `test_files_are_given_...`: wait for the text with `browser_wait` before reading the page.
  - `test_a_download_is_kept_...`: check that three files are in the folder and none is outside it.
  - `test_dragging`: the result names a bare element by its tag: `(div "Knob")`, and a point on a
    plain element as `(255, 270) (div)`. Then see whether the knob and the card really moved.
- [x] **3. The nine tests that pass on `main` and fail here.**
  - Six describe 18 tools: `test_registry.py` (1), `test_mcp.py` (2), `test_serve.py` (1),
    `test_agent_loop.py` (1), `test_toolkit.py` (1). The tools offered now come from
    `tools_for(config)` in `tools/toolkit.py`.
  - Two in `test_driver_options.py`: the context options now hold `accept_downloads`.
  - One fault: `test_a_browser_that_went_away_...` in `test_toolkit_in_process.py`. When the browser
    goes away, the result ends with "[events] tab t1 closed". A browser that closed should not also
    report its tabs as closed.
- [x] **4. Tests not written yet.** With the stand-in driver (`tests/support/fakes.py`, already
  extended): the dialog rule in the toolkit; the `[events]` line and its cap; the timeline sentences
  of the ten tools; what a viewer is told (`dialog_opened`, `dialog_closed`, `download_saved`, a
  tab's `attention`, `select_tab` while a person drives); a picture over MCP; the newest picture
  only to the model; `policy/files.py`; `driver/screenshots.py` for PNG and JPEG.
- [x] **5. The spec, which should have come first.** Sections 5.3, 5.5, 5.7, 5.8, 5.9, 6.1, 6.2, 9.7,
  10.3 and 16.5, then the page again. To say there: how pictures are taken and made smaller; the
  sentence for an open dialog begins with a capital; the two new settings; a download's size is
  checked when it has arrived, not while it arrives; a window a page opens in take-over Chrome
  cannot be reached, and the agent is told so; the address policy is not applied to a window a
  page opens.
- [x] **6. `uv run ruff format src tests`** (8 files), then `ruff check` and `pyright`, which pass now.
- [x] **7. The viewer.** See that the new tool names read well in the timeline and the chat; rebuild.
- [x] **8. README and `CLAUDE.md`.** Propose a gotcha: a screenshot with a clip on our own DevTools
  session resets what Playwright emulates.
- [ ] **9. Onto `main`** when `uv run pytest` passes, then `/verify` over the whole build.

## Check

```bash
uv run pytest tests/e2e/test_tabs.py tests/e2e/test_dialogs.py tests/e2e/test_pictures.py tests/e2e/test_files_and_logs.py -q
uv run pytest -q
```
