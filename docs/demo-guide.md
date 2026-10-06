# bap-browser: what is built, and how to show it

Written on 2026-10-06 for `main`. The longer record, with every decision and finding, is
`docs/status.md`; the design is `docs/bap-browser-spec.md`.

## In one paragraph

bap-browser is a browser that an AI agent uses and that a person watches and controls. The agent
reads a page as short text with an id for each element, and acts by id: it is not sent the page's
HTML or a picture on every turn, which is what keeps it cheap. A person sees the browser live,
talks to the agent in a chat, and can pause it, take the browser over, hand it back and stop it.
The agent asks the person when it meets a sign-in, a CAPTCHA or a payment.

## What is built

| Part | What it does |
|---|---|
| The engine | Drives a real Chromium, Chrome or Edge. Reads a page as text with refs such as `e12`, also inside frames (`f2e7`) |
| 28 tools | Open and go back, read, find, click, hover, drag, type, fill a form, choose, check, press keys, scroll, wait, screenshots and zoom, tabs, dialogs, the console and network logs, uploads and downloads, a script in the page (off unless turned on), and asking a person |
| The viewer | A web page with the live browser, the agent's pointer and click marks, a glow while it works, the steps it took, and the controls: Pause, Take over, Hand back, Stop |
| The chat | Give tasks one after another, read the answers, stop a task without ending the session |
| Help from a person | The agent asks for a sign-in, a CAPTCHA or a code and waits; the person takes over, does it, and answers Done |
| Approvals | A tool can be allowed, asked about or denied; an action that pays, sends or deletes is asked about every time |
| Safety | An address policy checked for every page the browser loads, also after a redirect, a link or inside a frame; the cloud metadata address is always refused; typed text and passwords never reach a log |
| Three ways for an agent to use it | The built-in agent loop (OpenAI `gpt-5.6-luna`, or a scripted demo with no key); MCP over stdio; MCP over HTTP with the viewer |
| Three places for the browser | A headless browser with a live picture; a browser window on your screen with the chat beside it; a tab of your own Chrome through the extension |
| The Chrome extension | The chat in Chrome's side panel; for your own Chrome it is the bridge: it pairs with a one-time token, reconnects by itself, asks you site by site what the agent may do, and has its own Stop |
| A desktop app, first cut | Electron: the agent's browser and the chat in one window |
| `doctor` and `bench` | Which browsers launch on this machine; how fast each tool is against the budget |
| Configuration | Every setting has a default in one file and is changed in `config.json` |

## Before you show it

Do this once, and again after pulling new code.

```bash
uv sync
uv run playwright install chromium
npm --prefix viewer install
npm --prefix viewer run build
uv run bap-browser doctor
```

`doctor` should end with "Everything bap-browser needs is in place." For the parts with a real
model, the key is in `.env` in this folder (`OPENAI_API_KEY=...`). The scripted demo needs no key.

Close every earlier run first (Ctrl+C in its terminal). Each command below opens its own viewer.

## The show, in order

About ten minutes. Each part stands by itself, so any can be left out.

### 1. The scripted demo: no key, nothing can go wrong (2 minutes)

```bash
uv run bap-browser agent --demo --open --pace 2
```

A viewer opens in your browser. A scripted agent signs up on a demo site that ships with
bap-browser.

| Point at | Say |
|---|---|
| The live picture with the purple edge | "This is a real browser. The edge glows while the agent works." |
| The pointer, the outline and the ring on a click | "You always see where it is about to act, and where it clicked." |
| The steps on the right | "Every action is one sentence a person can read. What it typed is shown as a count, never the text." |
| Press **Pause**, then **Resume** | "It stops between two actions, and goes on." |
| Press **Take over**, type in the page, then **Hand back** | "I drive now. The agent waits, and is told the page may have changed." |

### 2. The chat with a real model (3 minutes)

```bash
uv run bap-browser agent --chat --open
```

Type these one after another in the chat:

1. `Open example.com and tell me its heading.`
2. `Go to huggingface.co/models, choose the Image Classification filter, and tell me one model with a link.`
3. `Take a screenshot and tell me what the top of the page shows.`

| Point at | Say |
|---|---|
| The chip that goes Working, then Ready | "It says in one word what the agent is doing." |
| The steps under Activity | "Every step is listed as it happens. Press one to see its picture and its result." |
| The answer, with its bold name and its link | "It answers in the chat, and the session stays open for the next task." |
| "Stop this task", the button beside the box while a task runs | "This stops the task, not the session." |

### 3. A person in the loop (2 minutes)

In the same chat:

```
Open https://www.google.com/recaptcha/api2/demo and submit the form. It has a CAPTCHA.
```

The agent asks for help instead of trying. A card says "Verification needed". Press **Take
over**, tick the box in the picture, press **Done**. The agent goes on and submits.

Say: "It never tries a human check itself. It asks, waits, and continues when you say so."

### 4. Safety, shown live (1 minute)

In the same chat:

```
Open http://169.254.169.254/latest/meta-data/ and tell me what it says.
```

The agent is refused, and the viewer shows "Blocked". Say: "That is the address cloud machines
keep their secrets at. It is refused whichever way a page tries to reach it: directly, by a
redirect, by a link or inside a frame."

Then show the log: `.bap-browser/events.jsonl`. One line per action, and where the agent typed,
only a count.

### 5. The browser on your screen, and your own Chrome (2 minutes, optional)

The agent in a browser window you can see, with the chat beside it:

```bash
uv run bap-browser agent --chat --show-browser --open
```

The agent in a tab of your own Chrome. The command names a folder; load it once at
`chrome://extensions` (Developer mode, Load unpacked), then open the side panel with the BAP icon:

```bash
uv run bap-browser agent --chat --takeover
```

The first time the agent touches a site, the extension asks you: Allow once, Always allow on this
site, Don't allow. Its own "Stop the agent" takes the agent off the tab at once.

Try this part once before you show it: loading an extension by hand is the step most likely to
take time in front of people.

### 6. For a technical audience (1 minute, optional)

```bash
uv run bap-browser doctor       # which browsers launch here
uv run bap-browser bench        # how fast each tool is, against the budget
uv run bap-browser serve --open # the same tools over MCP on HTTP, for any agent
```

Any MCP agent can use the browser. For Claude Code:
`claude mcp add bap-browser -- uv run bap-browser mcp`

## If something goes wrong while you show it

| What you see | What to do |
|---|---|
| "The viewer is not built" | `npm --prefix viewer run build` |
| "Executable doesn't exist" | `uv run playwright install chromium` |
| "OPENAI_API_KEY is not set" | Put the key in `.env`, or show part 1, which needs none |
| The viewer says "Connection lost" | The command was stopped. Start it again; a new viewer opens |
| A real site behaves differently that day | Go back to the demo site: `--demo`, or ask the agent to open the address the command printed with `/demo-site/start.html` |
| The model is slow | Say so and wait: each step is a call to the model. The scripted demo is instant |

## What it does not do yet

Say these plainly if asked.

| Not built | Note |
|---|---|
| Settings changed from the viewer on a live session | Only colour mode and the agent's pointer. The rest is changed in `config.json` |
| More than one agent tab in your own Chrome | One tab, in its own tab group |
| A core that runs in the cloud with your Chrome at home | The pieces are there (pairing, reconnecting); it has only been run on one machine |
| An installer for the desktop app | It runs from this folder |
| The micro VM image | Written, never built or started |
| The code tool `browser_run` | Planned last |
| Four tools slower than their target | A click by point, a key press and choosing an option take about 33 ms against 5 to 10. See `docs/status.md` |

## Numbers you can quote

Measured on 2026-10-06, on macOS with Python 3.12.5. Take them from here, not from memory.

| What | Number |
|---|---|
| Tools | 28 (27 offered by default; a script in the page is off unless turned on) |
| Size of all 28 tool definitions sent to a model | 2,518 tokens, counted as characters / 4, against a budget of 3,500 |
| Python tests | 958 passed, none failed (`uv run pytest -q`, 209 s) |
| Viewer tests | 400 passed |
| Browsers that launch on this machine | Chromium 153, Chrome 154, Edge 154 |
| Speed, on Chromium | Open a small page 11 ms; read a page 1.1 ms; fill one field 1.8 ms; a screenshot 17 ms |
