# Browser Agent (bap-browser)

![Python](https://img.shields.io/badge/Python_3.12-3776AB?style=flat&logo=python&logoColor=white) ![Playwright](https://img.shields.io/badge/Playwright-2EAD33?style=flat&logo=playwright&logoColor=white) ![MCP](https://img.shields.io/badge/MCP-000000?style=flat&logo=anthropic&logoColor=white) ![Starlette](https://img.shields.io/badge/Starlette-4B8BBE?style=flat&logo=python&logoColor=white) ![React](https://img.shields.io/badge/React_19-20232A?style=flat&logo=react&logoColor=61DAFB) ![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?style=flat&logo=typescript&logoColor=white) ![Vite](https://img.shields.io/badge/Vite-646CFF?style=flat&logo=vite&logoColor=white) ![Electron](https://img.shields.io/badge/Electron-47848F?style=flat&logo=electron&logoColor=white) ![Tailwind CSS](https://img.shields.io/badge/Tailwind-06B6D4?style=flat&logo=tailwindcss&logoColor=white) ![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat&logo=docker&logoColor=white)

## Overview

AI agents can drive a browser, but the person they work for usually can't see what they are doing or step in. A web page can also plant text that tricks an agent into paying, sending or deleting something nobody asked for.

bap-browser is a browser that AI agents use and that a person can watch and control. Agents call its tools over MCP (Model Context Protocol). A live viewer shows every step, and the person can pause the agent, take over the browser, hand it back or stop it. Safeguards check each step the agent asks for before it runs.

It is a Python service with a CLI, a React viewer, a browser extension, an Electron desktop app and a container image. The design is in [`docs/bap-browser-spec.md`](docs/bap-browser-spec.md).

## Key Features

- **Browser tools over MCP**: navigate, snapshot, find, click, type, fill forms, scroll, tabs, screenshots, downloads and more, over stdio or HTTP.
- **Live viewer** with a picture of the page, a timeline of steps, and Pause, Take over, Hand back and Stop.
- **Chat mode.** Give tasks one after another. The agent works in a window you watch, or in your browser's side panel.
- **Take-over mode.** The agent works in a tab of your own Chrome through an extension.
- **Always-on safeguards.** Paying, sending, deleting, giving access, or typing a password, card number or one-time code asks the person first.
- **Prompt-injection defence.** Page text reaches the agent between `<<page ...>>` marks. Text addressed to an AI is withheld and hidden text is dropped.
- **Cross-site guard.** Text read on one site is not sent to another without a yes, and a look-alike of a known site asks first.
- **Auto Mode** (off by default). A model decides the steps the rules are unsure of, judged against the task the agent declared. It never decides paying, sending, deleting or giving access.
- **Evaluations.** 159 tasks with a known right end, run on a practice site and checked by code.
- **Help from a person.** The agent can ask for a sign-in, a CAPTCHA or a code, and wait.

## How It Works

### Three ways in

1. **MCP over stdio**: an agent such as Claude Code starts `bap-browser mcp` as a process.
2. **MCP over HTTP**: `bap-browser serve` exposes the same tools on port 8765 with a bearer token, plus the viewer, for an agent running elsewhere.
3. **The built-in agent**: `bap-browser agent` runs a reference agent loop, either a scripted demo that needs no key or a hosted model.

### Every step is checked

When an agent calls a tool, the safeguards look at the action, the site and the text involved before the driver runs it. The step is allowed, put to the person, or denied. A task stops at 500 steps or 60 minutes, and a step repeated on a page that doesn't change is not run a sixth time. An MCP client states its task first with `browser_begin_task`, so Auto Mode can judge each step against it.

### Driving the browser

Playwright drives Chromium. The driver can also attach to a browser that is already running, or to your own Chrome through the extension and Chrome's debugger.

## Results / Highlights

- **159 evaluation tasks** that measure task completion, whether a person is asked before ordering, sending or deleting, and how often planted text hijacks the agent.
- A performance budget (`perf/budget.json`) timed by `bap-browser bench`.
- One gate script (`scripts/gate.py`) runs every check in order and stops at the first failure.
- The repo has no CI workflows, so the test suite under `tests/` is run locally through that gate script.

## Tech Stack

- **Language:** Python 3.12, TypeScript
- **Browser automation:** Playwright (Chromium)
- **Agent protocol:** MCP (stdio and HTTP)
- **Service:** Starlette, Uvicorn, WebSockets, Pydantic v2
- **Viewer:** React 19, Vite
- **Desktop app:** Electron, React, Tailwind CSS, shadcn/ui
- **Models:** OpenAI (`gpt-5.6-luna` by default)
- **Deployment:** Docker
- **Tooling:** uv, Ruff, Pyright, pytest, npm

## Getting Started

### Prerequisites

- Python 3.12 and [uv](https://docs.astral.sh/uv/)
- Node.js and npm (for the viewer and the desktop app)
- An OpenAI API key for real tasks (the demo needs none)

### Installation

```bash
git clone https://github.com/DCode-v05/Browser-Agent.git
cd Browser-Agent
uv sync
uv run playwright install chromium
npm --prefix viewer install
npm --prefix viewer run build
```

For real tasks, copy `.env.example` to `.env` and set `OPENAI_API_KEY`.

### Running

```bash
uv run bap-browser agent --demo --open    # a scripted agent signs up on the demo site; no key needed
uv run bap-browser studio --open          # one window, three browsers
uv run bap-browser doctor                 # check that everything needed is in place
```

## Usage

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

In a container:

```bash
docker build -f deploy/Dockerfile -t bap-browser .
docker run --rm -p 8765:8765 -e BAP_BROWSER_TOKEN=<a long random string> bap-browser
```

Run the checks:

```bash
uv run python scripts/gate.py
```

## Project Structure

```
Browser-Agent/
├── src/bap_browser/
│   ├── cli.py            # The bap-browser command
│   ├── tools/            # The browser tools agents call
│   ├── mcp/              # MCP server (stdio and HTTP)
│   ├── driver/           # Playwright browser driver
│   ├── agent/            # Reference agent loop
│   ├── safeguards/       # Step checks, approvals, injection defence
│   ├── policy/           # Address and action policies
│   ├── service/          # HTTP service behind the viewer
│   ├── extension/        # Browser extension (side panel, take-over)
│   ├── evals/            # Evaluation task sets
│   ├── demo_site/        # Practice site for the demo and evals
│   └── computer/         # Driver link and dock
├── viewer/               # React viewer
├── desktop/              # Electron desktop app
├── deploy/               # Dockerfiles and VM config
├── plugin/               # Claude Code plugin
├── scripts/              # gate.py, patterns.py and other checks
├── perf/                 # Performance budget
├── docs/                 # Spec, demo guide, systems guide, ADRs, research
├── tests/
└── pyproject.toml
```

---

## Contact

<table>
  <tr><td><b>Portfolio:</b> <a href="https://www.denistan.me">Denistan</a></td><td><b>LinkedIn:</b> <a href="https://www.linkedin.com/in/denistanb">denistanb</a></td></tr>
  <tr><td><b>GitHub:</b> <a href="https://github.com/DCode-v05">DCode-v05</a></td><td><b>LeetCode:</b> <a href="https://leetcode.com/u/Denistan_B">Denistan_B</a></td></tr>
  <tr><td colspan="2" align="center"><b>Email:</b> <a href="mailto:denistanb05@gmail.com">denistanb05@gmail.com</a></td></tr>
</table>

Made with ❤️ by **Denistan B**
