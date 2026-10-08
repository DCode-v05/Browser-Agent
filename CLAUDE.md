# bap-browser

A browser that AI agents use through MCP tools and that a person watches and controls.
The spec is the source of truth: `docs/bap-browser-spec.md`. Update it first when requirements
change, then regenerate `docs/bap-browser-spec.html`. Plans are in `docs/plans/`.

## Commands
- Install: `uv sync`, then `uv run playwright install chromium`
- Test: `uv run pytest` (one file: `uv run pytest tests/unit/test_config.py -v`)
- Format: `uv run ruff format .`; check: `uv run ruff format --check .` and `uv run ruff check .`
- Types: `uv run pyright`
- Run as an MCP server: `uv run bap-browser mcp`
- Run the whole path with no model key: `uv run bap-browser agent --demo --open` (the viewer must be built)
- Show the configuration: `uv run bap-browser config show --sources`
- Every check in one order, stopping at the first that fails: `uv run python scripts/gate.py` (`--quick` leaves out the tests that start a browser)
- The bad patterns, read from the code: `uv run python scripts/patterns.py` (`--list` shows every place a rule matches)
- Viewer install: `npm --prefix viewer install`
- Viewer checks: `npm --prefix viewer run typecheck`, `run lint`, `run test`, `run build`
- Viewer in a real browser: build it, then `uv run pytest tests/viewer -q` (screenshots land in `.bap-browser/viewer-shots/`)
- Viewer by hand: `npm --prefix viewer run dev`, then open `?demo=signup` or `?state=<name>` (add `&theme=dark`, `&surface=mobile`)
- Record the demo pictures again: `uv run python viewer/scripts/record_demo.py`

## Rules
- Every tunable value lives in `src/bap_browser/config.py`. No tunable number anywhere else.
- No tool returns raw HTML, or an image that was not asked for. Every observation is capped.
- Typed text, form values, password values and tokens never reach a log, an event or a result.
- Tool results are short plain text written for a model. Failures are results, not crashes.
- Work on a branch; small commits with tests passing; nothing is pushed.
- A change is made by the one pathway in `docs/agent-pathway.md`. The rules of the code are in `docs/bad-patterns.md`; a new case of one fails the gate.
- `docs/feature-map.json` says where each feature is: its spec section, its files, its tests.

## Gotchas
- Windows long paths are off and this workspace path is long. If `uv sync` fails with "os error 3",
  set `UV_PROJECT_ENVIRONMENT` to a short folder (for example `C:/venvs/bap-browser`) and run it again.
- The workspace path contains spaces. Quote paths in shell commands.
- The page script (`driver/snapshot_page.js`) runs in an isolated world of the page through a CDP
  session. `page.evaluate` cannot reach it, and it cannot see the page's own variables.
- The standard output of `bap-browser mcp` carries the protocol. Log to the error stream only.
- Tests fail on any warning (`filterwarnings = error`). Fix the cause; for a warning raised inside a
  dependency, add an ignore for that exact message in `pyproject.toml` with a comment saying why.
- `README.md` must exist before `uv sync`: the build reads it.
- `uv run pytest` needs the built viewer (`npm --prefix viewer run build`); `tests/viewer` fails with that message otherwise.
- Test files cannot import each other (pytest runs with `--import-mode=importlib`). Share through fixtures in `conftest.py`, or through a module in `tests/support/`, which is on the tests' import path.
- Viewer styles use tokens only: no colour, pixel size, duration or font outside `viewer/src/tokens.css` (a test enforces it).
- Every string a person reads is in `viewer/src/wording.ts`.
- The viewer's settings screen is drawn from the settings answer; it holds no list of settings of its own.
- Write Python that holds backslash escapes (`\r\n`, regular expressions) with the Write tool, not
  through a shell heredoc: the heredoc turns the escapes into real characters.
- On Windows, Python's asyncio does not release a connection that the other side cut (a browser that
  was closed). The service therefore ends each HTTP connection after its answer and stops waiting
  after `server.shutdown_wait_s`. A test that closes a browser page while it is connected leaves a
  socket open and fails the run on its warning: stop the service first.
- A browser keeps up to two live pictures on their way. A test of the picture rate must allow for them.
- Run `ruff format` on `src tests viewer/scripts`, never on `docs/` (it is excluded: the formatter rewrites code examples in Markdown).
