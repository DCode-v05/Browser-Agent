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
- Show the configuration: `uv run bap-browser config show --sources`

## Rules
- Every tunable value lives in `src/bap_browser/config.py`. No tunable number anywhere else.
- No tool returns raw HTML, or an image that was not asked for. Every observation is capped.
- Typed text, form values, password values and tokens never reach a log, an event or a result.
- Tool results are short plain text written for a model. Failures are results, not crashes.
- Work on a branch; small commits with tests passing; nothing is pushed.

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
