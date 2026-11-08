# Browser Agent (bap-browser)

bap-browser is a browser that AI agents drive through MCP tools and that a person can watch and control. A live viewer shows each step, and the person can pause the agent, take the browser over, hand it back or stop it.

I built it because an agent working in a browser is usually a black box, and a web page can plant text that talks the agent into paying, sending or deleting something nobody asked for. Here every step the agent asks for passes through safeguards before it runs.

## How it works

There are three ways in:

1. MCP over stdio: an agent such as Claude Code starts `bap-browser mcp` as a process.
2. MCP over HTTP: `bap-browser serve` exposes the same tools on port 8765 with a bearer token, plus the viewer.
3. The built-in agent: `bap-browser agent` runs a reference loop, either a scripted demo that needs no key or a hosted model.

When an agent calls a tool, the safeguards look at the action, the site and the text involved before the driver runs it. The step is allowed, put to the person, or denied. A task stops at 500 steps or 60 minutes, and a step repeated on a page that does not change is not run a sixth time. An MCP client states its task first with `browser_begin_task`, so Auto Mode can judge each step against it.

Playwright drives Chromium. The driver can also attach to a browser that is already running, or to your own Chrome through the extension and Chrome's debugger.

What the safeguards do:

- Paying, sending, deleting, giving access, or typing a password, card number or one-time code asks the person first.
- Page text reaches the agent between `<<page ...>>` marks. Text addressed to an AI is withheld and hidden text is dropped.
- Text read on one site is not sent to another without a yes, and a look-alike of a known site asks first.
- Auto Mode is off by default. A model decides the steps the rules are unsure of, judged against the declared task, but never paying, sending, deleting or giving access.
- The agent can ask the person for a sign-in, a CAPTCHA or a code, and wait.

Other modes: chat mode takes tasks one after another in a window you watch or in the browser's side panel, and take-over mode works in a tab of your own Chrome through the extension.

The repo also has 159 evaluation tasks with a known right end, run on a practice site and checked by code. They measure task completion, whether a person is asked before ordering, sending or deleting, and how often planted text hijacks the agent. A performance budget in `perf/budget.json` is timed by `bap-browser bench`.

## Tech stack

- Python 3.12, TypeScript
- Playwright (Chromium), MCP (stdio and HTTP)
- Starlette, Uvicorn, WebSockets, Pydantic v2
- Viewer: React 19, Vite
- Desktop app: Electron, React, Tailwind CSS, shadcn/ui
- Models: OpenAI (`gpt-5.6-luna` by default)
- Docker for deployment
- Tooling: uv, Ruff, Pyright, pytest, npm

## Setup

You need Python 3.12 with [uv](https://docs.astral.sh/uv/), Node.js with npm, and an OpenAI API key for real tasks (the demo needs none).

```bash
git clone https://github.com/DCode-v05/Browser-Agent.git
cd Browser-Agent
uv sync
uv run playwright install chromium
npm --prefix viewer install
npm --prefix viewer run build
```

For real tasks, copy `.env.example` to `.env` and set `OPENAI_API_KEY`.

## Running

```bash
uv run bap-browser agent --demo --open    # a scripted agent signs up on the demo site; no key needed
uv run bap-browser studio --open          # one window, three browsers
uv run bap-browser doctor                 # check that everything needed is in place
```

```bash
uv run bap-browser agent "Find the price of ..." --open    # a real task
uv run bap-browser agent --chat --show-browser --open      # chat while you watch the browser
uv run bap-browser agent --chat --extension                # chat in the browser's side panel
uv run bap-browser agent --chat --takeover                 # the agent works in your own Chrome
uv run bap-browser mcp                                     # MCP server over stdio
uv run bap-browser serve                                   # MCP over HTTP (port 8765) with the viewer
uv run bap-browser bench                                   # time the performance budget
uv run bap-browser config show --sources                   # show the effective configuration
```

Connect Claude Code:

```bash
claude mcp add bap-browser -- uv run bap-browser mcp
```

Desktop app:

```bash
npm --prefix desktop install
npm --prefix desktop start
```

Container:

```bash
docker build -f deploy/Dockerfile -t bap-browser .
docker run --rm -p 8765:8765 -e BAP_BROWSER_TOKEN=<a long random string> bap-browser
```

Run every check, stopping at the first failure:

```bash
uv run python scripts/gate.py
```

## Project structure

```
Browser-Agent/
├── src/bap_browser/
│   ├── cli.py            # the bap-browser command
│   ├── tools/            # browser tools agents call
│   ├── mcp/              # MCP server (stdio and HTTP)
│   ├── driver/           # Playwright driver
│   ├── agent/            # reference agent loop
│   ├── safeguards/       # step checks, approvals, injection defence
│   ├── policy/           # address and action policies
│   ├── service/          # HTTP service behind the viewer
│   ├── extension/        # browser extension (side panel, take-over)
│   ├── evals/            # evaluation task sets
│   ├── demo_site/        # practice site for the demo and evals
│   └── computer/         # driver link and dock
├── viewer/               # React viewer
├── desktop/              # Electron desktop app
├── deploy/               # Dockerfiles and VM config
├── plugin/               # Claude Code plugin
├── scripts/              # gate.py, patterns.py and other checks
├── perf/                 # performance budget
├── docs/                 # spec, ADRs, research, guides
├── tests/
└── pyproject.toml
```

The design is in [`docs/bap-browser-spec.md`](docs/bap-browser-spec.md).

---

## Contact

<table>
  <tr><td><b>Portfolio:</b> <a href="https://www.denistan.me">Denistan</a></td><td><b>LinkedIn:</b> <a href="https://www.linkedin.com/in/denistanb">denistanb</a></td></tr>
  <tr><td><b>GitHub:</b> <a href="https://github.com/DCode-v05">DCode-v05</a></td><td><b>LeetCode:</b> <a href="https://leetcode.com/u/Denistan_B">Denistan_B</a></td></tr>
  <tr><td colspan="2" align="center"><b>Email:</b> <a href="mailto:denistanb05@gmail.com">denistanb05@gmail.com</a></td></tr>
</table>
