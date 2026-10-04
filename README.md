# bap-browser

A browser that AI agents can use and that a person can watch and control.
Agents call its tools over MCP. The full description is in `docs/bap-browser-spec.md`.

## Install

```bash
uv sync
uv run playwright install chromium
npm --prefix viewer install
npm --prefix viewer run build      # the viewer, which the service serves
```

## Run

```bash
uv run bap-browser agent --demo --open    # watch a scripted agent sign up on the built-in demo site
uv run bap-browser mcp                    # an MCP server over stdio, for an agent to start
uv run bap-browser config show --sources  # the effective configuration
uv run bap-browser config init            # write a starter config.json
```

Connect Claude Code: `claude mcp add bap-browser -- uv run bap-browser mcp`

`bap-browser agent --demo` needs no model key. It starts a browser, the service and the viewer,
prints the viewer's address, and runs a fixed script through the same tools a real agent uses.
In the viewer you can pause it, take over the browser, hand it back, and stop it. `--open` opens
the viewer in your browser and waits for it; `--exit-when-done` ends the process after the run;
`--pace 0.5` changes how long each step waits.

## Test

```bash
uv run pytest                                      # needs the built viewer
uv run ruff format --check . && uv run ruff check .
uv run pyright
npm --prefix viewer run typecheck && npm --prefix viewer run lint && npm --prefix viewer run test
```
