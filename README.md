# bap-browser

A browser that AI agents can use and that a person can watch and control.
Agents call its tools over MCP. The full description is in `docs/bap-browser-spec.md`.

## Install

```bash
uv sync
uv run playwright install chromium
```

## Run

```bash
uv run bap-browser mcp                    # an MCP server over stdio, for an agent to start
uv run bap-browser config show --sources  # the effective configuration
uv run bap-browser config init            # write a starter config.json
```

Connect Claude Code: `claude mcp add bap-browser -- uv run bap-browser mcp`

## Test

```bash
uv run pytest
uv run ruff format --check . && uv run ruff check .
uv run pyright
```
