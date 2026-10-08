# bap-browser

A browser that AI agents can use and that a person can watch and control.
Agents call its tools over MCP. The full description is in `docs/bap-browser-spec.md`.
What is built and how to show it: `docs/demo-guide.md`.

## Install

```bash
uv sync
uv run playwright install chromium
npm --prefix viewer install
npm --prefix viewer run build      # the viewer, which the service serves
```

## Run

```bash
uv run bap-browser studio --open          # one window, three browsers: the cloud browser, your own Chrome, the built-in browser
uv run bap-browser agent --demo --open    # watch a scripted agent sign up on the built-in demo site
uv run bap-browser agent "Find the price of ..." --open   # a real task, done by GPT-5.6 Luna
uv run bap-browser agent --chat --show-browser --open     # the agent works in a browser window you watch; you talk to it in the chat
uv run bap-browser agent --chat --extension               # the same, with the chat in the browser's own side panel
uv run bap-browser agent --chat --takeover                # the agent works in a tab of your own Chrome (load the extension it names, once)
uv run bap-browser mcp                    # an MCP server over stdio, for an agent to start
uv run bap-browser serve                  # the same tools over MCP on HTTP (port 8765), with the viewer, for an agent elsewhere
uv run bap-browser doctor                 # which browsers launch here, and whether everything needed is in place
uv run bap-browser bench                  # time each line of the performance budget (perf/budget.json)
uv run bap-browser config show --sources  # the effective configuration
uv run bap-browser config init            # write a starter config.json
```

Connect Claude Code: `claude mcp add bap-browser -- uv run bap-browser mcp`

`bap-browser agent --demo` needs no model key. It starts a browser, the service and the viewer,
prints the viewer's address, and runs a fixed script through the same tools a real agent uses.
In the viewer you can pause it, take over the browser, hand it back, and stop it. `--open` opens
the viewer in your browser and waits for it; `--exit-when-done` ends the process after the run;
`--pace 0.5` changes how long each step waits.

A real task needs a model key. Copy `.env.example` to `.env` and put your key on the
`OPENAI_API_KEY=` line; `.env` is never committed. The model is `gpt-5.6-luna` unless
`agent.model` in `config.json` says otherwise. The answer is printed when the task is done.

## Safeguards and Auto Mode

Every step an agent asks for is checked before it runs (spec section 18). The checks are always on:

- A step that pays, sends, deletes or gives an app access, and typing a password, a card number or a
  one-time code, asks the person first.
- What a page wrote reaches the agent between `<<page …>>` marks. Text addressed to an AI agent is
  withheld, text no person can see is left out, and the person is told about the page.
- Text read on one site is not typed or sent to another without a yes. A look-alike of a known site
  asks first.
- A program that arrives as a download is never kept. An archive is kept only with a yes.
- A task stops at 500 steps or 60 minutes (`limits`), and a step repeated on a page that does not
  change is not run a sixth time.

**Auto Mode** lets a model decide the steps the rules are unsure of, so the person is asked less. It
is off until a deployment turns it on:

```json
{ "safety": { "auto_mode": { "offered": true }, "ask_before": "auto" } }
```

With `offered` alone, a person chooses "Auto" in the settings screen. Paying, sending, deleting and
giving access never run on a model's word. It uses the model key of `.env`.

**An agent that connects over MCP** states its task first, once: `browser_begin_task` with the task
in the person's words and the sites it needs. Auto Mode judges each step against that task; without
one, a step it is unsure of asks the person. A client can pin the tools it was offered:
`GET /api/tools` on the service, or `uv run bap-browser config show --tools`, give one value that
changes when any tool's name, description or arguments change.

What is built and what is not: `docs/auto-mode-safeguards-status.md`.

## Desktop app

```bash
npm --prefix desktop install
npm --prefix desktop start      # one window: the agent's browser on the left, the chat on the right
```

The app is Electron with a shadcn/ui shell. Its own Chromium is the agent's browser; it starts the
agent's core itself, so the model's key must be in `.env`. Checks: `npm --prefix desktop run typecheck`,
`run test`, `run build`.

## In a container

```bash
docker build -f deploy/Dockerfile -t bap-browser .
docker run --rm -p 8765:8765 -e BAP_BROWSER_TOKEN=<a long random string> bap-browser
```

The container runs `bap-browser serve` as an unprivileged user with `deploy/config.vm.json`: the
viewer is at `http://127.0.0.1:8765/#token=<the token>` and the tools over MCP at
`http://127.0.0.1:8765/mcp`. For a machine others reach, set `BAP_BROWSER__SERVER__PUBLIC_URL` to the
address they use.

## Test

```bash
uv run pytest                                      # needs the built viewer
uv run ruff format --check . && uv run ruff check .
uv run pyright
npm --prefix viewer run typecheck && npm --prefix viewer run lint && npm --prefix viewer run test
```
