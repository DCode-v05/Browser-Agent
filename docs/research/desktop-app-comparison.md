# Our System, Hermes and the OpenAI Agents SDK, compared as a desktop app

Date: 2026-10-10 · Our System 0b4ae4f · Hermes dce1e9b · OpenAI Agents SDK 125efa0 · Read from the code, nothing installed or run

This page compares three systems as a person meets them through a desktop app. For Our System that is the Electron app in `desktop/` and the core it starts. For Hermes it is Hermes Desktop and the agent behind it. The OpenAI Agents SDK has no app, so its column says what the SDK gives a developer who builds one. Each row names the system that does the thing best, says why, and says what Our System could take from the others.

## 1. The three systems

| | Our System | Hermes | OpenAI Agents SDK |
|---|---|---|---|
| What it is | A browser that an AI agent drives and a person watches and controls | A general personal agent that runs commands, edits files, browses, sends messages, runs scheduled jobs and writes its own skills | A Python library for building agents: agents, tools, hand-offs, guardrails, sessions and tracing |
| Who makes it | September (this repository) | Nous Research | OpenAI |
| What "the desktop app" means here | The Electron app in `desktop/`, which shows the agent's browser and the chat in one window, and the core it starts with `uv run bap-browser agent --chat` | Hermes Desktop (`apps/desktop`) and the Hermes agent and gateway it starts or connects to | None. The SDK has no app. Its column says what it gives toward one |
| Repository | `DCode-v05/Browser-Agent` | `NousResearch/hermes-agent` | `openai/openai-agents-python` |
| Commit compared | `0b4ae4f`, 2026-10-10 | `dce1e9b375`, 2026-10-09 | `125efa02`, 2026-10-08 |

### How to read the tables

Sections 4 to 17 hold one table each. Every table has the same columns:

- **Row**: the row's id and the thing compared. The ids match the evidence list in section 20.
- **Our System**, **Hermes**, **OpenAI Agents SDK**: what each one has, in plain words. "None, you build it" means the SDK gives nothing for that row.
- **Best**: the verdict, one of the words below.
- **Why**: the reason for the verdict.
- **Gap or idea for Our System**: what Our System lacks, or could take from the others. "None" means nothing is worth doing now.

The verdict words:

- A system's name: that system does the thing best.
- **Tie**: two systems do it equally well, often in different ways.
- **Split**: each named system is best at a different half of the row.
- **None**: none of the three has it.
- **Not judged**: the row describes the systems and does not rank them.

## 2. The verdict

Hermes Desktop is the most complete desktop app of the three by a wide margin. It wins 58 of the 112 rows, mostly on breadth: an installer that is signed and updates itself, a full chat with sessions and search, 38 model providers, memory, skills, OS notifications and 21 messaging platforms. Hermes is fifteen months old and has 51,081 commits from 4,122 author names.

Our System wins 21 rows, and they sit where its purpose is. The person watches the agent's own browser in the same window as the chat (C2, E5). The core has its own driver with 30 browser tools (E1 to E4). Approvals know a payment from a click (G1, G2, H4), and Auto Mode has a floor in code that no model can lift (G7). Its web safeguards have no match in the other two: layers against instructions planted in pages, look-alike sites, checks on downloads, and limits that are on by default (H1, H8, H9, H15). Our System is one week old.

The OpenAI Agents SDK is not an app, so it wins 9 rows, all of them building blocks. It has the clearest agent loop, typed output on any agent, a paused run saved to disk and restored, guardrail hooks, tracing, lifecycle hooks, an importable API and two strict type checkers. Its defaults are the weakest on privacy: traces carry tool and model data to OpenAI unless the developer turns them off.

Most of what Our System lacks is packaging and chat polish, not design. Two gaps are deeper. The core sends the whole conversation to the model on every call, which a long browser task will outgrow (F11). The model key sits in a plain-text `.env` file (H6).

### Wins by area

| Area | Rows | Our System | Hermes | OpenAI SDK | Tie | Split | None or not judged |
|---|---|---|---|---|---|---|---|
| A. Identity and maturity | 6 | 0 | 2 | 0 | 1 | 0 | 3 |
| B. Install, packaging, updates | 6 | 0 | 6 | 0 | 0 | 0 | 0 |
| C. Window and layout | 10 | 1 | 8 | 0 | 0 | 1 | 0 |
| D. Chat and sessions | 9 | 1 | 7 | 0 | 1 | 0 | 0 |
| E. The agent's browser | 9 | 6 | 3 | 0 | 0 | 0 | 0 |
| F. Agent core | 15 | 1 | 11 | 2 | 1 | 0 | 0 |
| G. Human in the loop | 9 | 3 | 1 | 1 | 2 | 2 | 0 |
| H. Safety and security | 17 | 6 | 3 | 1 | 6 | 1 | 0 |
| I. Observability | 7 | 1 | 4 | 1 | 0 | 0 | 1 |
| J. Configuration | 6 | 1 | 3 | 0 | 2 | 0 | 0 |
| K. Extensibility | 6 | 0 | 2 | 3 | 0 | 1 | 0 |
| L. Engineering quality | 6 | 0 | 5 | 1 | 0 | 0 | 0 |
| M. Platforms | 2 | 0 | 2 | 0 | 0 | 0 | 0 |
| N. Performance | 4 | 1 | 1 | 0 | 1 | 0 | 1 |
| **Total** | **112** | **21** | **58** | **9** | **14** | **5** | **5** |

G5 repeats E6 (take-over) and G6 repeats D8 (stop), so those two verdicts count twice.

### What Our System should do next

The list runs from the most value for the least work to the largest jobs.

1. **Send an OS notification when an approval or a help request waits** (G9, C10). Hermes does this. Electron's `Notification` needs a few lines, and a person who looks away today misses the question until it runs out.
2. **Add a Content Security Policy and a deny-all permission handler to the desktop shell** (H11). Both are a few lines in `desktop/index.html` and `desktop/electron/main.cjs`.
3. **Add a licence and a `SECURITY.md`** (A2, H16). Without a licence nobody outside the team may use the code. Hermes' `SECURITY.md` is the model: it says which protections are rules, which are heuristics, and what neither stops.
4. **Ask for the model key in the app and keep it in the OS keychain** (B5, J4, H6). Electron's `safeStorage` does the encryption, as Hermes Desktop does for its gateway token.
5. **Trim old snapshots and tool output from the conversation** (F11). The SDK's `ToolOutputTrimmer` keeps recent turns whole and cuts older tool output. Hermes adds a cheap model that summarises the middle.
6. **Stream the model's answer into the chat** (D1). The SDK's stream events are a clean model for the protocol.
7. **Save a waiting question to disk** (G8), so a crash or a restart does not lose it. The SDK's `RunState` and Hermes' saved approvals both do this.
8. **Test, lint and gate the desktop app, and add a Windows runner to CI** (L2, L3, L5, L6). Today the desktop app has 5 tests on helper functions, no lint, no place in `scripts/gate.py`, and CI runs only on Linux.
9. **Package the desktop app**: an installer for Windows and macOS, signing, updates and a bundled core (B1 to B6). This is the largest job and the largest gap.
10. **Add a second model provider and a fallback model** (F2, F12).
11. **Keep a history of past tasks** with their answers and evidence (D5, D6).

## 3. Size and activity

These numbers come from the commands in section 19, run the same way on all three repositories. Line counts include blank lines and comments.

| Measure | Our System | Hermes | OpenAI Agents SDK |
|---|---|---|---|
| First commit | 2026-10-03 | 2025-07-22 | 2025-03-11 |
| Commits | 204 | 51,081 | 2,486 |
| Author names in `git shortlog` | 4 | 4,122 | 415 |
| Tags | 0 | 163 | 124 |
| Tracked files | 501 | 17,986 | 1,684 |
| Python lines (of them tests) | 45,187 (21,902) | 2,252,544 (1,330,230) | 484,556 (311,003) |
| TypeScript and JavaScript lines (of them tests) | 17,861 (5,587) | 1,048,028 (380,688) | 1,128 (66) |
| Desktop app lines of TypeScript, JavaScript and CSS (of them tests) | 1,835 (32) | 837,997 (332,435) | None |
| Python test functions | 1,072 | 45,676 | 8,311 |
| CI workflows | 1 | 51 | 10 |

## 4. Identity and maturity

| Row | Our System | Hermes | OpenAI Agents SDK | Best | Why | Gap or idea for Our System |
|---|---|---|---|---|---|---|
| **A1** What it is | A browser an AI agent drives and a person watches and controls. The desktop app shows the agent's browser on the left and the chat on the right, and starts the Python core beside it. | A general personal agent. Hermes Desktop is its full window app, one of several ways in, next to a terminal interface and chat platforms. | A library to build agents with. There is no app. | Not judged | They are three kinds of product. The rows below compare what each offers at each point. | Say in one line what Our System is for: the supervised browser that agents use. Hermes and the SDK could be its users as well as its rivals. |
| **A2** Licence | None. The repository has no `LICENSE` file and no licence field. | MIT. | MIT. | Tie: Hermes, OpenAI SDK | A stated licence tells others what they may do with the code. Without one, nobody outside the team may use it. | Choose a licence, or state that the code is proprietary, before it is shown outside September. |
| **A3** Languages and stack | Python 3.12 core with Playwright, Starlette and the MCP SDK. A React and Vite viewer. Electron 44 with React and shadcn/ui for the desktop app. | Python agent and gateway. Electron 40 with React 19, Vite and Tailwind for the desktop app. Docusaurus docs, and some Rust and native code. | Python 3.10 or later, on `openai`, `pydantic`, `mcp`, `httpx` and `websockets`, with optional extras for other models, stores and sandboxes. | Not judged | All three use common, well-supported tools. Our Electron is the newer of the two apps. | None. |
| **A4** Size | 45k lines of Python and 18k of TypeScript and JavaScript. The desktop app itself is 1.8k lines. | 2.25M lines of Python and 1.05M of TypeScript and JavaScript. Hermes Desktop alone is 838k lines. | 485k lines of Python, 135k of them in `src/agents`. | Not judged | Size is not quality. It shows how much each team has built and must maintain. | None. |
| **A5** Age and activity | One week old: 204 commits, 4 author names, no tags. | Fifteen months old: 51,081 commits, 4,122 author names, 163 tags, a release about every week. | Nineteen months old: 2,486 commits, 415 author names, 124 tags, version 0.23.1. | Hermes | It has the most contributors and ships about every week. The SDK is steady and versioned. | Tag a version before each demo, so the demo can be rebuilt exactly. |
| **A6** Documentation | One spec, a feature map that links each feature to its spec section, files and tests, a demo guide, status pages and an ADR. All are written for the team. There is no user guide. | A Docusaurus site of 452 pages, an 847-line guide to the desktop app, and build, design and engineering notes for the app. | An MkDocs site that covers every feature, a generated API reference, and copies in Japanese, Korean and Chinese. | Hermes | It has a guide written for the person who uses the desktop app. The SDK's docs are the best for a developer, who uses no desktop app. | Write a short user guide for the desktop app: install, a first task, approvals and take-over. |

## 5. Install, packaging and updates

| Row | Our System | Hermes | OpenAI Agents SDK | Best | Why | Gap or idea for Our System |
|---|---|---|---|---|---|---|
| **B1** How a person installs it | Clone the repository, run `uv sync`, install Playwright's Chromium, build the viewer, then run `npm --prefix desktop start`. | A one-line installer for each OS, a download of Hermes Desktop, or `hermes desktop` from the command line. | `pip install openai-agents`. That installs a library for a developer, not an app. | Hermes | A person installs Hermes Desktop without a terminal. Our System needs a developer's setup. | Build an installer. For a desktop app this is the largest gap. |
| **B2** Installers for each OS | None. `desktop/package.json` has no packaging tool, and the spec says the app runs from the repository. | DMG and ZIP for macOS and MSIX for Windows. An AppImage for Linux is configured, but the release workflow turns it off. | None. The SDK ships a wheel on PyPI. | Hermes | It is the only one with installers. | Add `electron-builder` with targets for Windows and macOS. |
| **B3** Code signing | None. | macOS builds are signed, notarized and use the hardened runtime. Windows builds are signed with Azure Trusted Signing when its keys are set. | Not an app. Releases reach PyPI by trusted publishing (OIDC), with no stored token. | Hermes | Signing stops the OS from warning about or blocking the app, and proves who built it. | Sign with the company's certificates once there is an installer. |
| **B4** Updates | None. | `electron-updater`, plus a channel file that carries its own SHA-256 and a signer name pinned inside the app rather than taken from the feed. The Microsoft Store updates Store builds. | The developer runs `pip install -U`. | Hermes | Hermes checks that an update comes from the expected signer before it installs it. | Add updates after the installer, with the signer pinned in the app as Hermes does. |
| **B5** First run | The app starts the core at once. If the model key is missing, the chat shows the core's error and a **Start again** button. The person sets the key by editing `.env` by hand. | A first-run screen asks whether to use a local or a remote agent. A guided tour follows, and a free-tier path serves a person with no account. | A quickstart page, and `run_demo_loop()`, a chat in the terminal for a developer. | Hermes | A new person reaches a first message without editing a file. | Ask for the model key in the app on first run, and keep it in the OS keychain (H6). |
| **B6** What a person must install first | Node, Python 3.12, `uv`, Playwright's Chromium and the whole repository. The app runs `uv run --project <repo> bap-browser agent --chat`. | Nothing, with the bundled build, which carries the agent inside the app. A build from source needs Python and the Hermes command line. | Python 3.10 or later. | Hermes | The bundled Hermes Desktop needs nothing else on the machine. | Bundle the core with the app, for example as a frozen Python build, so a person needs nothing else. |

## 6. Window and layout

| Row | Our System | Hermes | OpenAI Agents SDK | Best | Why | Gap or idea for Our System |
|---|---|---|---|---|---|---|
| **C1** The window | One window, 1440 by 900 at the start. The agent's browser is on the left and the chat on the right, in a split the person can drag (70 to 30 at the start). A sidebar folds away. Electron 44. | A chat with a session sidebar on the left and a right rail with files, a terminal, a code review and a preview. It also has command overlays and separate windows for sessions, checks and alerts. Electron 40. | None, you build it. | Hermes | Its window holds far more. Ours puts the browser first, which suits a browser product. | Keep the browser first. Add a right rail later for evidence, such as pictures and the files the agent downloaded. |
| **C2** The agent's browser in the window | The agent's real browser is a view inside the window. The core drives that very view over CDP, so the person sees each step on the page where it happens. | A preview pane shows pages and files, but it is a separate copy of a page, not the agent's own browser. The agent's browser runs headless, and on Windows it stays headless unless the person sets `AGENT_BROWSER_HEADED`. A live screen with take-over (Bot Screen) works only when the agent runs on Linux. | None, you build it. The computer-use example runs headless. | Our System | It is the only one that shows the browser the agent is driving, in the same window as the chat, on every OS. | Draw the agent's pointer and the working glow in the desktop view too. The spec lists them as missing there. |
| **C3** Previews of pages and files | None apart from the live browser. | The preview pane shows web pages, local files and tool output. It refuses files such as SSH keys, `.env` and cloud credentials, and caps the size it reads. | None, you build it. | Hermes | The person can look at what the agent made without leaving the app. | Show each downloaded file in the window, with the same refusal list for secret files. |
| **C4** File browser | None. | Yes, in the right rail, with open, reveal and rename. | None, you build it. | Hermes | It is the only one with a file browser. | Not needed for a browser product, apart from the downloads folder. |
| **C5** Terminal | None. | Yes: xterm.js on node-pty, and the person can take the terminal over from the agent. | None, you build it. | Hermes | It is the only one with a terminal. | Not needed. Our System gives the agent no shell, which keeps a whole class of risk out. |
| **C6** Themes | Light and dark follow the OS. Colours come from tokens, and a test checks the contrast of every pair of text and background in both themes. | Preset themes, skins, an accent colour and a theme for each profile. | None, you build it. | Hermes | It gives the person more choice. Our System is the only one that tests contrast. | A light and dark switch in the desktop app. |
| **C7** Languages | English only. Every string a person reads is in one file, `viewer/src/wording.ts`, so a translation is one more file of the same shape. | Nine languages (Arabic, German, English, Spanish, French, Japanese, Russian and two forms of Chinese), with a test that every string is translated. | Not an app. Only the docs are translated. | Hermes | It is the only one a person without English can use today. | Add a language when a customer needs one. The single wording file makes it cheap. |
| **C8** Accessibility | Labels on controls (108 `aria-` attributes in the viewer) and the contrast test above. No check with a screen reader. | It turns on Chromium's accessibility tree at start so that dictation tools work, after two bug reports. A setting turns it off. | Not an app. | Split: Our System for contrast, Hermes for assistive tools | Each covers a different half. Our System checks contrast in its tests. Hermes makes the app reachable by dictation and other assistive tools. | Turn on the accessibility tree as Hermes does, and take a screen reader through one task. |
| **C9** Shortcuts and command palette | One shortcut: Ctrl+B folds the sidebar. | A command palette on Ctrl+K and a screen to change every shortcut. | None, you build it. | Hermes | A person reaches every action from the keyboard. | Keys for the actions that matter under pressure: **Stop**, **Take over**, **Allow** and **Deny**. |
| **C10** Notifications, tray and windows | None. There is one window, and closing it ends the core. | OS notifications, a tray icon with "minimize to tray", and several windows. | None, you build it. | Hermes | Hermes tells the person when it needs them, even when its window is hidden. | An OS notification when an approval waits (G9). |

## 7. Chat and sessions

| Row | Our System | Hermes | OpenAI Agents SDK | Best | Why | Gap or idea for Our System |
|---|---|---|---|---|---|---|
| **D1** Streaming answers | The answer arrives whole when the model call ends. Steps appear live as they start and finish. | The answer streams in as the model writes it, with Markdown drawn as it arrives. | `Runner.run_streamed()` yields pieces of text and tool events as they happen. You draw them. | Hermes | The person sees the answer form instead of waiting for it. | Stream the model's text to the chat. The SDK's event types are a clean model for the protocol. |
| **D2** Tool activity | Each tool call is one step in a list, with a one-sentence summary, a box on the page where it acted, its duration and whether it failed. A click on a step opens its evidence: the picture and the result. | Tool calls are grouped in a feed, with a run summary, skill activity and the approvals that wait. | Typed events, `tool_call_item` and `tool_call_output_item`. You draw them. | Our System | Each step points at a place on the page and carries a picture, so a person can check the agent's work. | Group long runs of steps as Hermes does, so a 200-step task stays readable. |
| **D3** Rich text | Bold, inline code and links only. Raw HTML never renders. | Full Markdown with coloured code, maths and Mermaid diagrams. DOMPurify cleans any HTML. | None, you build it. | Hermes | Tables and code in an answer stay readable. | Lists and tables at least, since answers about web pages are often tables. |
| **D4** Attachments | None. | Images with a viewer, files and links, in the message box. | The input format takes text, images and files. You build the picker. | Hermes | It is the only one where a person can attach a file. | Let a person attach a file for the agent to upload to a page, since `browser_upload_file` exists. |
| **D5** Session list and search | None. **New session** starts over in the same place. | A session sidebar with filters, paging and full-text search (SQLite FTS5). | Session stores for SQLite, SQLAlchemy, Redis, MongoDB, Dapr and OpenAI's servers, and an encrypted wrapper. No interface. | Hermes | A person finds an earlier task and its result. | Keep a list of past tasks, with their answers and evidence. |
| **D6** Resume, branch and rewind | Pause and resume a live run only. An ended session cannot be reopened. | Sessions reopen, and a person can rewind, edit an earlier message, or branch. | `RunState` resumes a paused run, and `to_input_list()` carries a conversation into the next run. Branching is yours to build. | Hermes | It has all three in the app. | Reopen a finished task to ask a follow-up question. |
| **D7** Several sessions at once | One session. The studio window runs three browsers with a chat each, but the studio is outside the desktop app. | Tiled sessions, several agents and several gateways at once. Profiles in the background keep working. | None, you build it. | Hermes | A person can run more than one task. | Bring the studio's three browsers into the desktop app. |
| **D8** Stop | **Stop this task** ends the task and keeps the chat. **Stop** ends the session. Closing the window ends the core and every process it started. | Cancel in the chat. `/stop` ends background processes, and `/pause` holds all new work. | `cancel(mode="immediate")`, or `cancel(mode="after_turn")`, which lets the current turn finish and saves state first. | Tie: Our System, Hermes | Both give the person a stop that takes effect at once and leaves the app usable. | Offer "stop after this step", like the SDK's `after_turn`. |
| **D9** Voice | None. | Voice in and out, including a live spoken conversation. | A voice pipeline (speech to text, agent, text to speech), and realtime agents over WebSocket. No interface. | Hermes | It is the only one with voice a person can use today. The SDK's realtime agents are the best parts to build voice from. | Not needed now. |

## 8. The agent's browser

| Row | Our System | Hermes | OpenAI Agents SDK | Best | Why | Gap or idea for Our System |
|---|---|---|---|---|---|---|
| **E1** Engine and driver | Its own driver on Playwright and CDP. A page script runs in an isolated world that the page cannot see. In the desktop app the core attaches to the app's own Chromium. | No driver of its own. It hands the browser to outside engines: the `agent-browser` program, the `browser-harness` package, Camofox, or a cloud provider. | A `Computer` interface (click, type, scroll, screenshot) that you write against a driver of your choice. The example uses Playwright. | Our System | Owning the driver lets Our System check, cap and record every step in one place. | None. |
| **E2** What the model sees | A text snapshot: one line per element with a stable reference (`e12`, or `f2e7` inside a frame), capped in size. Hidden text is left out. A picture comes only when the agent asks for one. | An accessibility snapshot with references (`@e5`), cut to a size. By default the model writes Python against the page instead (E9). | Screenshots only. There is no text view of the page. | Our System | The text view costs few tokens, reaches into frames, and leaves out text a person cannot see, which also blocks one kind of planted instruction. | None. |
| **E3** Browser tools | 30 tools, 28 of them offered by default (`browser_evaluate` and `browser_run` are off). They navigate, read, find, click, type, fill a form, select, scroll, drag, answer dialogs, manage tabs, read the console and network, upload, download, take a screenshot and ask a person. | By default one tool, `browser_exec`, and five vault tools. The other mode has 10 tools, and 2 more for raw CDP and dialogs. | One `ComputerTool` with OpenAI's mouse and keyboard actions, and a hosted web search. | Our System | Each action is its own tool, so the safeguards can check each one before it runs. | Measure our token use against Hermes' code mode (N3). |
| **E4** Tabs, dialogs, downloads, uploads and frames | A tool for each of the first four: `browser_tabs`, `browser_handle_dialog`, `browser_downloads` and `browser_upload_file`. Frames appear in the snapshot. | Dialogs and frames work. Its docs list downloads as not supported, and there is no upload tool. | None, you build it. | Our System | It is the only one with all five. | None. |
| **E5** Live view | The person watches the agent's browser live in the window. The standalone viewer also shows the agent's pointer and a glow while it works. | A visible browser window when the person turns it on (not by default on Windows), recordings in WebM, and Bot Screen when the agent runs on Linux. | None, you build it. | Our System | The live view is the product, inside the app, on every OS. | Recordings a person can replay later (I3). |
| **E6** Take-over | **Take over** and **Hand back**. After hand-back the agent's next result starts with a note of the address before and after, and a reminder to take a new snapshot. | Bot Screen gives control as a lease, and the gateway drops input from anyone who does not hold it. It works when the agent runs on Linux. | None. | Our System | It works on every OS and tells the agent where the person left the browser. Hermes' lease is the stronger mechanism. | Treat a click by the person inside the desktop view as a take-over. The code does not show that it notices one today. |
| **E7** Signed-in sites | The desktop app keeps a browser profile of its own (`persist:agent`), apart from the person's browser. When a site needs a password, the agent hands the step to the person. | It can copy the person's real browser profile, so the agent is already signed in. A vault (encrypted on disk, or 1Password, or Bitwarden) has tools to fill a login and enter a code. | None, you build it. | Hermes | The agent can sign in without the person typing each time. | A vault that fills a field without the value reaching the model, which keeps our rule that the model never sees a password. |
| **E8** Stealth and cloud browsers | None. The "cloud browser" in the studio is our own headless Chromium. The spec lists cloud providers as later work. | Plug-ins for Browser Use cloud, Browserbase and Firecrawl, and the Camofox and Lightpanda engines. | None. | Hermes | Sites that block automation still work through a provider. | One adapter for a cloud provider, behind the same tools. |
| **E9** Code mode | `browser_run` runs a short script of several steps in one call. It stays off until the core runs in its micro VM. | `browser_exec` is the default: the model writes Python against helper functions. Hermes' own test reports 60 to 66 per cent fewer tokens than its one-step tools, at the same accuracy. | `ProgrammaticToolCallingTool` lets the model write JavaScript that calls other tools. It is not specific to browsers. | Hermes | It is the default, and it is measured. | Turn on `browser_run` inside the VM and run the same comparison on our task sets. |

## 9. Agent core

| Row | Our System | Hermes | OpenAI Agents SDK | Best | Why | Gap or idea for Our System |
|---|---|---|---|---|---|---|
| **F1** The agent loop | A small loop: call the model, run its tools, repeat. It is a reference agent. The main users are outside agents that drive the browser over MCP. | One `AIAgent` loop that every surface uses, with phases, retries, compression and budgets. | `Runner`, with each part of a turn in a module of its own: preparation, tool planning, tool calls, approvals, guardrails and saving. | OpenAI SDK | Its loop is the clearest, typed and documented, and it pauses for approvals and resumes. Hermes' loop does more, and the rows below score those features. | If Our System needs a fuller agent of its own, consider building it on the SDK rather than growing the reference loop. |
| **F2** Model providers | OpenAI only, over its Responses API. `scripted` runs the demo without a key. | 38 provider plug-ins, among them Anthropic, Gemini, Bedrock, Azure, OpenRouter and local models. | OpenAI natively, and over 100 others through LiteLLM or any-llm. | Hermes | It has the most providers, each with its own setup and health check. | Add Anthropic at least. The browser tools work with any model that calls tools. |
| **F3** Switching models | The person picks from `agent.offered_models` in the settings, all of them OpenAI's. | `/model` switches model and provider in a live chat. | Per agent or per run, in code. | Hermes | The person switches without a restart. | Follows from F2. |
| **F4** Structured output | Used inside the core, for the Auto Mode reviewer's answer only. | For side calls, and for the results of sub-agents (`output_schema`). | `output_type` on any agent, checked against a strict JSON schema. | OpenAI SDK | Any agent can return a typed object. | Let a task ask for its answer in a given shape, such as a table of prices. |
| **F5** Several agents | None. | Sub-agents (`delegate_task`) that run in parallel, each in its own git worktree, and a mixture of models whose answers are merged. | Hand-offs, where another agent takes over, agents as tools, where another agent answers and returns, and hosted sub-agents. | Tie: Hermes, OpenAI SDK | The SDK has the clearest model of how agents work together. Hermes runs them in a product. | Not needed. An outside agent with its own sub-agents can share one Our System. |
| **F6** Tools beyond the browser | None in the desktop app, by design. Computer use (a contained desktop, and a Mac through a helper) arrived in the studio window on 2026-10-09. | Terminal, files, code, web search, vision, image and video generation, speech, a kanban board, to-dos, memory and computer use. | Python functions as tools, and hosted tools: web search, file search, a code interpreter, image generation, shell, `apply_patch` and computer use. | Hermes | It has the widest set in a product. Our System chose to be a browser. | Bring computer use into the desktop app when it is ready. |
| **F7** MCP client | None. Our System serves MCP and calls no other MCP server. | A full client, settings for 68 ready-made servers, and a malware check (OSV) before it starts one. | A client for stdio, SSE and streamable HTTP, and hosted MCP. | Hermes | It is the most complete, and it checks a server before it runs it. | Not needed while outside agents bring their own tools. |
| **F8** MCP server | All 30 tools over stdio (`bap-browser mcp`) and HTTP (`bap-browser serve`). This sits outside the desktop window. | Only its messaging conversations, not its tools. | None. | Our System | It is the only one that offers its tools to other agents. | Let the desktop app show, and approve steps in, a session that an outside agent started over MCP. |
| **F9** Skills | None inside. Our System ships a skill that teaches Claude Code to use its tools. | 212 skills in the repository, a hub to install more, a scanner for each, and skills the agent writes from its own work. | Skills (`SKILL.md`) for sandbox agents, opened only when needed. | Hermes | It has the largest set, and the agent improves its own. | Saved recipes for sites ("how to check in with this airline") would be Our System's version. |
| **F10** Long-term memory | None. | `MEMORY.md` and `USER.md` that the agent curates, memory stores as plug-ins, and search over past sessions. | Conversation stores, but no curated memory. | Hermes | It is the only one that remembers the person across sessions. | Not needed now. If it comes, keep page text out of memory, since a page can plant instructions. |
| **F11** Context management | None. The core sends the whole conversation to the model on every call. | Several stages: old tool output is cut first, then a cheap model summarises the middle while the start and the end stay whole. | A hook to change the input before each call, a trimmer for old tool output, and compaction on OpenAI's servers. | Hermes | Long tasks keep running without hitting the model's limit. | High priority. A 500-step browser task will pass any model's context. Start as the SDK does: trim old snapshots and tool output. |
| **F12** Retries and a fallback model | Retries with growing, random waits, and a breaker that stops calling after repeated failures. No second model. | Retries, and a chain of fallback providers. | Retries with waits the developer sets. No second model. | Hermes | When one provider fails, the task goes on with another. | A fallback model, once there is a second provider. |
| **F13** Usage and cost | Cost in dollars from tokens and set prices. For each task: tokens, model, time and how it ended. | Usage by model, billing, account quotas, `/usage` in the chat and `hermes usage --json`. | Tokens per run, including cached and reasoning tokens. | Hermes | It is the most complete, with account quotas. | Show the running cost of a task in the chat. |
| **F14** Scheduling | None. | A full scheduler with job storage, locks, templates, and delivery to any messaging platform. | None. | Hermes | It is the only one. | Not needed now. |
| **F15** Messaging platforms | None. | 21 platforms, among them Slack, Teams, Telegram, WhatsApp, Discord, email and SMS. | None. | Hermes | It is the only one. | Not needed. The useful part would be a message to the person's phone when an approval waits. |

## 10. Human in the loop

| Row | Our System | Hermes | OpenAI Agents SDK | Best | Why | Gap or idea for Our System |
|---|---|---|---|---|---|---|
| **G1** Approval before actions | The core checks every step before it runs, in a fixed order. A step that pays, sends, deletes, grants access or shares data goes to the person every time, and no model can approve it. Three modes: every action, risky (the default) and Auto. | Shell commands and code go through about 15 rules that nothing can bypass and about 80 that ask the person. A plug-in can send any tool call to the same check. | `needs_approval` on each tool, off by default. A policy function that cannot read the arguments asks the person. | Split: Our System for web actions, Hermes for shell commands | Each checks the actions its own agent takes. The SDK checks nothing unless the developer asks it to. | None for the browser. |
| **G2** The approval card | It says why the person is asked, what text leaves and from which site, and the amount the page shows. In Auto Mode it adds the reviewer's sentence. **Allow**, **Allow on this site** or **Deny**, and the question expires. | A stack of cards the person swipes. **Reject**, **Run once**, and **Always allow**, which asks to confirm because it writes to the config file. | A list of `ToolApprovalItem` objects. The docs say to escape tool names and arguments before showing them. | Our System | The card shows what is at stake (money, text that leaves, the site), which is what a person needs to decide. | A queue, as Hermes has, for when several questions wait at once. |
| **G3** A tool for the agent to ask the person | `browser_request_human` hands the step to the person. The core nudges the agent to call it on a CAPTCHA or a sign-in form. | `clarify` asks up to five questions with up to four choices each, plus "Other", and marks a recommended choice. | None. There is only yes or no on a tool call. | Split: Hermes for questions, Our System for handing over a step | They do different jobs. Hermes asks the person for a decision, Our System asks for their hands. | Let `browser_request_human` offer choices, so the agent can ask "which flight?" without handing over the browser. |
| **G4** Pause and resume | **Pause** and **Resume** in the chat. The pause takes effect when the current step ends. | `/pause` holds all new work, and a long command can move to the background instead of ending. | A run pauses at each approval and resumes after it. There is no general pause. | Tie: Our System, Hermes | Both let the person pause a running task and resume it. | None. |
| **G5** Take-over | As in E6. | As in E6. | None. | Our System | As in E6. | As in E6. |
| **G6** Stop | As in D8. | As in D8. | As in D8. | Tie: Our System, Hermes | As in D8. | As in D8. |
| **G7** Autonomy levels and Auto Mode | **Every action**, **risky** and **Auto**. Auto is off until a deployment turns it on, and a deployment can forbid it. In Auto a reviewer model decides only the steps the rules are unsure of, and it can never approve a step that pays, sends, deletes, grants or shares. Auto pauses after 3 refusals in a row or 20 in a session. | **Manual**, **smart** and **off**. In smart mode a second model may approve or deny a flagged command, and stops after 3 denials in a row. **Off** skips every check except the hard rules. The `--yolo` flag is fixed when the process starts, so a skill cannot turn it on. | None. | Our System | Its floor is in code: the high-risk classes reach the person whatever the model says. Hermes' smart mode lets a model approve any command outside the hard rules. | At the end of a task, report how many steps the reviewer let through, so a person can audit Auto. |
| **G8** A paused run saved and resumed later | None. A session lives in memory, and a restart loses a question that waits. | Approvals and questions that wait are saved with the session and come back when it reopens. | `RunState.to_json()` and `from_json()` save a paused run and restore it, even in another process. The docs say to restore only from trusted storage. | OpenAI SDK | It is built for this, and it documents where trust ends. | Save a session's waiting question to disk, so a crash or a restart does not lose it. |
| **G9** Telling the person they are needed | Bars and notices in the chat: Auto paused, a limit reached, questions that ran out unanswered. No OS notification. | OS notifications. Approvals and questions alert the person even while they look at another session. | The app must check `result.interruptions` itself. | Hermes | It reaches a person who is not looking at the window. | An OS notification for each approval and each help request. Of all the gaps here, this one gives the most value for the least work. |

## 11. Safety and security

| Row | Our System | Hermes | OpenAI Agents SDK | Best | Why | Gap or idea for Our System |
|---|---|---|---|---|---|---|
| **H1** Instructions planted in content (prompt injection) | Five layers act on page text before the model reads it. Hidden text is left out, invisible characters are removed, address fragments are cut, page text sits between `<<page TOKEN>>` marks, and rules scan it with an optional model behind them. Text addressed to an AI agent is withheld, and the person is told. The rules are in English only. | Rules scan context files (`AGENTS.md`, `CLAUDE.md`, `.cursorrules`), skills and tool results. A project file that matches is dropped. Its security policy says the scan is not a security boundary. | None. Its security policy places prompt injection outside the SDK. | Our System | Web pages are where planted instructions come from, and Our System treats page text before the model sees it. | Rules for languages other than English. The Spanish attack page gets past the scan today. |
| **H2** Guardrails on input and output | The scan on what comes in, and the checks on what goes out. No general classifier. | The injection scan, redaction and a loop guard. No general classifier. | Four hooks (input, output, tool input and tool output) that can stop a run. None ships with a check inside. A rejected output is replaced before it is saved. | OpenAI SDK | It gives the cleanest place to plug in a check. | None. Our checks are already specific to a browser. |
| **H3** Dangerous actions | A classifier on the name of the control the agent presses: pays, sends, deletes, grants or commits. The word lists are in English. | About 15 hard rules and about 80 others for shell commands, covering Windows commands, SQL, hidden decoding, and commands that send credential files away. | None. When no handler is set, the computer-use safety checks from OpenAI's API go through without a person. | Split: Our System for web actions, Hermes for shell commands | Each covers what its agent can do. | Word lists in more languages. The spec's later layers do not rest on a control's name, which limits the harm meanwhile. |
| **H4** Sensitive actions and passwords | Pay, send, delete, grant and share go to the person every time. So do password, card and code fields, and their values never reach the model: the snapshot shows dots. | No classes for payment or sending. Writes to sensitive files (SSH keys, `.env`, shell start-up files) are checked. The vault fills logins. | None. | Our System | It is the only one that tells a payment from a click. | None. |
| **H5** Secrets kept out of logs, events and results | Patterns are redacted from every result. The event log never holds page text, typed text or task text. Password values never reach the model in the first place. | A redactor (1,360 lines), on by default, for logs, display, memory and approval cards. Child processes start without about 40 provider keys and tokens in their environment. | Logs leave out model and tool data by default. Traces include them by default and go to OpenAI. | Tie: Our System, Hermes | Our System keeps secrets from the model at the source. Hermes covers more places. | None now. Hermes' list of key names would make a good test list for our redaction. |
| **H6** Where keys are stored | The model key sits in `.env` as plain text. The desktop app makes a new service token for each run and keeps it in memory. | An encrypted vault by default (Fernet), or 1Password or Bitwarden. Files are written readable by the owner only (0600). The desktop keeps its gateway token in the OS keychain. | An environment variable. | Hermes | Keys are encrypted at rest. | Keep the model key in the OS keychain through Electron's `safeStorage`, entered in the app (B5). |
| **H7** Private addresses (server-side request forgery) | Before the browser goes to an address, a policy blocks cloud metadata addresses, private and local addresses (also after DNS), and private names such as `.local`, with allow and block lists. The browser then resolves the name again on its own, so a DNS answer that changes in between is not caught. | The same check before browser navigation. Its own HTTP clients check the address again when they connect, which closes DNS rebinding. Metadata addresses are always blocked. | None, apart from an allow list for hosted container shells and for web search. | Hermes | It closes DNS rebinding for its own requests. For the browser the two are equal. | Send the browser through a local proxy that checks the address it connects to. The code already names this as a later item. |
| **H8** Look-alike and malicious sites | Look-alikes of known sites by edit distance and lure words, mixed scripts in a name, and bare IP addresses. Lists from abuse.ch and RDAP are built but off. | None beyond the private-address check. | Not applicable: there is no browser. | Our System | It is the only one that checks for a fake site. | Turn the abuse.ch lists on once a key is set. |
| **H9** Downloads | Programs are deleted, found by name and by their first bytes. Archives, HTML and SVG need a yes. On the person's own machine every file needs a yes. | None. Downloads are not supported. | Not applicable. Archive inputs to sandboxes have size limits. | Our System | It is the only one that checks what arrives. | None. |
| **H10** Sandboxing | The agent has no shell. The code tool stays off until the micro VM is in use. The desktop app relies on Electron's sandbox. | Seven places to run commands: local (the default, with no isolation), Docker, Singularity, Modal, Daytona, SSH and Vercel Sandbox. | `SandboxAgent` with Docker or hosted providers. The local sandbox gives no OS isolation on Linux, and plain tools run in the host process. Most of the last 30 sandbox commits harden it. | Tie: Hermes, OpenAI SDK | Both offer real isolation, and neither turns it on by default. Our System avoids the risk by giving the agent no shell. | Run the core in the micro VM for the desktop app too, so that the browser itself is contained. |
| **H11** Electron hardening | Context isolation, the sandbox and no Node in all three views. The shell cannot navigate, new windows are refused, the agent's browser refuses every permission, and the main process checks the sender of each message. No Content Security Policy, and no permission handler on the default session. | The same three settings in all seven kinds of window, a new-window rule written against a published CVE, path checks on file messages, and a refusal list for secret files. No Content Security Policy for the main window. On some Windows machines it falls back to `--no-sandbox` after repeated crashes. | Not applicable. | Tie: Our System, Hermes | Both set the core protections. Hermes defends a much larger app, and Our System never turns its sandbox off. | Add a Content Security Policy and a deny-all permission handler on the default session. Both are a few lines. |
| **H12** The local service | Bound to 127.0.0.1, with a new random token each run, compared in constant time. The service checks the Origin on `/mcp` and on the WebSocket, and the Host header. The token travels in the address fragment, which no server receives, and never touches the disk. | Bound to the loopback address, with a session token. The app checks the token the backend actually serves and notices a process it did not start. Remote gateways use a new one-time ticket for each connection. | Not applicable. | Tie: Our System, Hermes | Both protect the local channel well. Hermes also secures remote connections, which the Our System desktop app does not offer. | None now. |
| **H13** Supply chain | Lock files for Python, the viewer and the desktop app. No scan of dependencies, and no signed builds. | Lock files, an OSV scan in CI, a malware check before an MCP server starts, a scanner for skills and plug-ins, and signed builds. A desktop plug-in installs from any Git address, with only a warning for `http` and `file`. | A lock file, CI actions pinned to commits, a check that a release matches its tag, trusted publishing and CodeQL. | Tie: Hermes, OpenAI SDK | Hermes guards more parts. The SDK has the cleanest release path. | Add `osv-scanner`, or `pip-audit` and `npm audit`, to CI. |
| **H14** Telemetry and privacy | Nothing is sent. There is no privacy page. The event log is kept for 30 days. | Off by default. Collection and sending are two separate switches, and the telemetry of a third-party driver is forced off. | Tracing is on by default and sends spans, with tool and model data, to `api.openai.com`. | Tie: Our System, Hermes | Neither sends anything unless the person agrees. | A one-page privacy note: what is stored, where, and for how long. |
| **H15** Limits | For each task: 500 steps, 60 minutes and 120 calls a minute, and a spending cap that is off by default. A step repeated on a page that does not change is noted at the third time and refused at the sixth. | No turn limit for the main agent by default (`agent.max_turns: None`). Sub-agents stop at 250. Guards stop repeated text and repeated tool calls. A price warning, but no spending cap. | 10 turns by default and a timeout for each tool. No time limit, cost cap or loop guard. | Our System | Every limit is on by default, and the loop guard looks at whether the page changed. | Turn the spending cap on by default, at a modest figure. |
| **H16** Security policy | None. There is no `SECURITY.md`. | A 335-line `SECURITY.md` with private reporting, 90-day disclosure, and a frank trust model: the approval gate, redaction and the skill scanner are not security boundaries, and only OS isolation is. | A `SECURITY.md` with private reporting, its scope, and the rules its reviewers check. | Hermes | It tells users plainly which protections they can rely on. | Write a `SECURITY.md` as frank as Hermes': which safeguards are rules, which use a model, and what neither stops. |
| **H17** Audit record | One JSON line for each tool call with what the check decided: stage, outcome, findings and risk. Never page text or typed text. Kept for 30 days. A question that timed out leaves no line, and lines are not signed. | The session store holds messages, tool calls and approvals. A separate log records sign-ins to the dashboard. Neither is tamper-evident. | Every item of a run is in the result object in memory, and in the traces. Nothing is saved by default. | Our System | It is the only record written for audit: what was decided and why, without the content. | Write a line for the question that timed out (an open finding), and chain each line's hash to the line before it. |

## 12. Observability

| Row | Our System | Hermes | OpenAI Agents SDK | Best | Why | Gap or idea for Our System |
|---|---|---|---|---|---|---|
| **I1** Logging | Logs go to standard error at a level the person sets, and `events.jsonl` holds one redacted line per step. | Four log files that rotate, written through one queue, with every line passed through the redactor. | Python `logging` under the name `openai.agents`. Model and tool data are left out by default. | Hermes | A person can send the rotating files with a bug report. | Write the core's log to a rotating file when the desktop app starts the core. |
| **I2** Tracing | None. | OpenTelemetry export and a Langfuse plug-in, both off by default. | Built-in traces and spans, with processors and exporters, on by default. | OpenAI SDK | It is the most complete, and it is built into every run. | Spans for each step (the model call, the check and the tool call) would explain a slow task. |
| **I3** Record and replay | For each task, a list of steps with their timing in the Evaluations page. No replay player. The spec lists one as next work. | Trajectories saved for evaluation and training, and session rewind. No replay player. | A saved run state, and scripted models for repeatable tests. | None | None of the three can replay a past session for a person. | A replay of the browser's pictures in step with the timeline would put Our System ahead of both. |
| **I4** Usage and cost views | For each task: time split into model, tool and waiting, the steps, tokens, cost, and how the task ended. | Usage by model, billing and quotas. | Token counts in the result. | Hermes | It is the most complete. Our split of time into model, tool and waiting is something the others lack. | None. |
| **I5** Diagnostics | `bap-browser doctor` checks Python, which browsers start, and whether a key is set, without reading the key. | `hermes doctor` runs seven groups of checks, and `--fix` repairs what it can. | None. | Hermes | It repairs as well as reports. | Run `doctor` from the desktop app when the core fails to start. |
| **I6** Evaluations and benchmarks | 50 tasks with known answers on a practice site, graded by code, runnable with the agent or with reference solutions. 26 attack pages and 4 harmless pages for the safeguards. An Evaluations page shows the results. | 147 evaluation files, side-by-side runs of a change against its base, and the browser benchmark. | Scripted models for tests. No evaluation suite. | Hermes | It is larger, and it compares two versions directly. | Run each change side by side with its base on our task sets. Keep the attack pages: neither of the others has them. |
| **I7** Performance budget | `perf/budget.json` gives a target and a fail time for about 39 tool cases, and `bap-browser bench` measures them. | One gate: the dashboard answers within one second at the 99th percentile under load. Elsewhere it counts operations rather than time. | None. | Our System | Every tool has a time budget that a command checks. | Run `bench` in CI. |

## 13. Configuration

| Row | Our System | Hermes | OpenAI Agents SDK | Best | Why | Gap or idea for Our System |
|---|---|---|---|---|---|---|
| **J1** Config files | Every default sits in one typed file (`config.py`). `config.json` overrides it, then environment variables, then options for one session. | One `config.yaml` with a version number, and migrations that `hermes update` applies. The example file is 127 KB. | None. Configuration is Python code. | Tie: Our System, Hermes | Our System has one typed source for every value. Hermes migrates a person's file when the app updates, which an installed app needs. | Give `config.json` a version and migrate it, once there are installed copies. |
| **J2** Environment variables | Every setting can be set as `BAP_BROWSER__SECTION__KEY`. | A `.env` file for secrets, with a 28 KB example. | Many `OPENAI_*` variables. | Our System | One rule reaches every setting. | None. |
| **J3** Settings screen | 23 settings drawn from one catalogue, each changed live. | More than 20 pages, among them appearance, models, providers, keys, keyboard, plug-ins and notifications, and a config page drawn from the backend's schema, with search. | None, you build it. | Hermes | Far more can be changed without editing a file. | Add the model key and the desktop app's folders. |
| **J4** Providers and keys in the app | None. The key lives in `.env`. | A **Providers** page and a **Keys** page. Values stay hidden until the person asks to see them. | None, you build it. | Hermes | A person sets keys without editing a file. | See B5 and H6. |
| **J5** Profiles | None. There is one browser profile, and roles for admin and user. | Profiles, each a separate Hermes home, in one app. | None. | Hermes | It is the only one. | Not needed now. |
| **J6** Settings a deployment locks | An admin locks what users may change or see, through `/api/admin/policy` and a separate admin sign-in. | A switch that locks all of the config, and a managed scope that locks single keys through file permissions. | None. | Tie: Our System, Hermes | Both let an organisation fix settings. Our System does it with roles in the service, Hermes with files that an IT team pushes. | None. |

## 14. Extensibility

| Row | Our System | Hermes | OpenAI Agents SDK | Best | Why | Gap or idea for Our System |
|---|---|---|---|---|---|---|
| **K1** Plug-ins | None. Our System ships a plug-in for Claude Code instead. | 18 kinds of plug-in (browsers, models, memory, platforms and more), under a rule that a plug-in never touches core files, and a catalogue of 523 entries. | Optional extras inside the package. | Hermes | It has the only real plug-in system. | Not needed now. |
| **K2** Skills | As in F9. | As in F9. | As in F9. | Hermes | As in F9. | As in F9. |
| **K3** Hooks | None. | Gateway hooks on start, on session start and end, on each agent step and on each command. | `RunHooks` and `AgentHooks` at each stage: agent start and end, tool start and end, and hand-off. | OpenAI SDK | It has typed hooks at every point of a run. | A hook after each step would let a deployment add its own check. |
| **K4** Custom tools | None. The list of tools is fixed. | `registry.register()`, with a clear contract for handlers. | `@function_tool` turns a typed Python function into a tool, schema included. | OpenAI SDK | Adding a tool takes the least work. | Not needed. The fixed list is what lets the safeguards know every action. |
| **K5** MCP | A server. | A full client and a narrow server. | A client. | Split: Our System serves, Hermes consumes | They face opposite ways. See F7 and F8. | None. |
| **K6** An API for embedding | `Toolkit(session).call(name, arguments)` calls any tool from Python. Other programs use MCP. | `AIAgent`, from a checkout of the repository only. `setup.py` refuses to build a wheel outside Nix. | The whole package is the API, on PyPI. | OpenAI SDK | It is built to be imported. | Publish the core as a package, so another program can use the tools without the repository. |

## 15. Engineering quality

| Row | Our System | Hermes | OpenAI Agents SDK | Best | Why | Gap or idea for Our System |
|---|---|---|---|---|---|---|
| **L1** Tests | 1,072 Python test functions, which pytest expands to 2,072 tests. 456 viewer test cases. 5 desktop tests. | 45,676 Python test functions, 1,536 desktop test files and 57 desktop end-to-end specs. | 8,311 test functions and 125 integration tests. | Hermes | It has by far the most. Our System has about as many lines of tests as of source (21.9k against 22.5k). | Test the desktop app itself (L2). |
| **L2** Kinds of tests | Unit, service, end-to-end in a real browser, and the viewer in a real browser. The desktop app's tests cover four helper functions only. | Unit, integration, live canaries against real providers, end-to-end, desktop end-to-end with Playwright, and install tests on each OS. | Unit tests and about 15 integration profiles, among them providers, voice, sandboxes and security. | Hermes | It tests the installed app on each OS. | A Playwright test that starts the Electron app, runs the demo task and approves a step. |
| **L3** CI | One workflow, on Ubuntu. | 51 workflows, including installs on Windows and macOS. | 10 workflows, including CodeQL. | Hermes | It runs on the operating systems people use. | Add a Windows runner. The team builds on Windows and macOS, but CI checks only Linux. |
| **L4** Type checking | Pyright, and `tsc` for the viewer and the desktop app. | `ty` on the changed code, and `tsc` on four desktop projects. | mypy in strict mode and Pyright, both on the whole tree. | OpenAI SDK | Two strict checkers run on every file. | None. |
| **L5** Lint and format | Ruff for Python and ESLint for the viewer. The desktop app has no lint script and no ESLint config. | Ruff with a strict config, ESLint and Prettier, and a hook before each commit. | Ruff. | Hermes | Every part is linted, before each commit. | Lint the desktop app. |
| **L6** Code rules and gates | `scripts/gate.py` runs every check in one order, and `scripts/patterns.py` enforces the rules in `docs/bad-patterns.md`. The gate leaves the desktop app out. | A code-health check that compares each change with its base and lets it only get better, 8 narrow checkers (Windows pitfalls, `/tmp` paths and others), and ESLint rules against bugs the team has had. | `make check`, and a coverage floor of 85 per cent. | Hermes | It has the most rules, and a limit that only tightens. | Add the desktop app's checks to `scripts/gate.py`. |

## 16. Platforms

| Row | Our System | Hermes | OpenAI Agents SDK | Best | Why | Gap or idea for Our System |
|---|---|---|---|---|---|---|
| **M1** Operating systems | Runs from source on Windows and macOS, where the team works. CI runs on Linux only. No installers. | macOS (Apple Silicon first) and Windows 10 and 11 (the MSIX needs Windows 11 22H2). Linux and WSL2 for the command line, with Linux desktop builds off in releases. Android through Termux, command line only. | Anywhere Python runs. The local sandbox needs macOS or Linux. | Hermes | Its installs are tested on each OS. | See B2 and L3. |
| **M2** Windows care | Short paths against the long-path limit, quoting for spaces, an end to each HTTP connection after its answer, and `taskkill /T /F` to end the core's whole process tree. | Recovery from two kinds of Chromium crash, a fix for Git Bash variables, a fix for a cookie-folder bug, and the same process-tree kill. | Docker for the sandbox on Windows. | Hermes | It has found and fixed more Windows cases, though one of its fixes turns the sandbox off. | None. |

## 17. Performance

| Row | Our System | Hermes | OpenAI Agents SDK | Best | Why | Gap or idea for Our System |
|---|---|---|---|---|---|---|
| **N1** Start time | Not measured. | Not measured. A watchdog restarts a gateway that hangs at start. | Not measured. | None | None of the three states a start time. | Measure the time from opening the app to a ready chat. |
| **N2** Latency budgets | A target and a fail time for about 39 tool cases (I7). | The dashboard's one-second gate (I7). | None. | Our System | Every tool has a budget. | None. |
| **N3** Token use | The 30 tool definitions measure 2,759 tokens, counted as characters divided by 4, against a budget of 3,750 (measured at `0b4ae4f`). Pages go to the model as text, not pictures. | Code mode saves 60 to 66 per cent by its own test, and an offline probe measures the size of the prompt. | A trimmer for old tool output, compaction and prompt caching. No measured figure. | Hermes | It measured a large saving. | Measure tokens per task on our task sets, and compare with `browser_run`. |
| **N4** Measured results in the repository | Tool speeds stated for 2026-10-06 on macOS: open a small page 11 ms, read a page 1.1 ms, fill a field 1.8 ms, take a screenshot 17 ms. | The browser benchmark, side-by-side runs of tool changes, and a benchmark of how easy the code is to navigate. | None. | Tie: Our System, Hermes | Our System measures each tool's speed. Hermes measures whole agent runs. | Measure whole tasks too: time, steps and tokens. |

## 18. What Our System has outside the desktop window

The comparison counts only what a person reaches from the desktop app. Our System has more, which the window does not reach yet:

| What | Where |
|---|---|
| The MCP server for outside agents, over stdio and HTTP | `src/bap_browser/mcp/server.py`, `src/bap_browser/service/server.py` |
| The studio window: the cloud browser, the person's own Chrome and the built-in browser as pages, each with its session and chat | `uv run bap-browser studio`, `src/bap_browser/agent/studio.py`, `viewer/src/Studio.tsx` |
| Computer use: a contained desktop as the fourth page of the studio, a desktop served from the micro VM, and a person's own Mac through a helper they run there (added 2026-10-09 and 2026-10-10) | `src/bap_browser/driver/desktop_driver.py`, `src/bap_browser/driver/mac_driver.py`, `src/bap_browser/service/mac_helper.py` |
| Take-over of the person's own Chrome through the extension, with the chat in Chrome's side panel | `src/bap_browser/service/bridge.py`, `src/bap_browser/extension/manifest.json` |
| The admin console, the policy lock and the user sign-in | `src/bap_browser/service/accounts.py`, `/api/admin/policy` in `src/bap_browser/service/app.py` |
| The Evaluations page and the task sets: 50 browser tasks, and desktop sets including an attack set | `src/bap_browser/evals/`, `src/bap_browser/evals/sets/` |
| `bap-browser doctor` and `bap-browser bench` | `src/bap_browser/doctor.py`, `src/bap_browser/bench/runner.py` |
| A Claude Code plug-in and skill for the browser tools | `plugin/.claude-plugin/plugin.json`, `plugin/skills/browse/SKILL.md` |
| The code tool `browser_run`, off by default | `src/bap_browser/code/runner.py` |
| A container image for the service and one for the desktop of computer use | `deploy/Dockerfile`, `deploy/desktop.Dockerfile` |

## 19. Method and limits

**What was read.** Both other repositories were cloned on 2026-10-10 into a folder outside this repository: Hermes at `dce1e9b375` (2026-10-09) and the OpenAI Agents SDK at `125efa02` (2026-10-08). Seven research agents each read one part (our app, our safeguards, Hermes Desktop, the Hermes core, Hermes' safeguards, the SDK's core and the SDK's safeguards) against one shared checklist of rows. Each claim in their notes carries a `path:line` they opened. Nothing was installed, started or called over the network. Our rows were read at `6f075fb`. `main` then moved to `0b4ae4f`. The 26 commits in between add computer use, a Mac helper and repository rules, and they do not change `desktop/`, so the desktop rows hold. The numbers in section 3 were measured again at `0b4ae4f`.

**What I checked by hand.** These facts decide verdicts, so I opened each one myself:

- This repository has no `LICENSE` file.
- `desktop/index.html` sets no Content Security Policy, and `desktop/electron/main.cjs:118-135` sets the three isolation settings on every view.
- The SDK includes sensitive data in traces by default (`src/agents/run_config.py:53-56`) and sends traces to `api.openai.com` (`src/agents/tracing/processors.py:46`).
- The SDK runs a computer-use action without a person when no safety handler is set (`src/agents/run_internal/tool_execution.py:2513-2522`).
- Hermes has no turn limit for the main agent and a limit of 250 for a sub-agent (`hermes_cli/config_defaults.py:78` and `:1361`).
- Bot Screen runs only on a Linux host (`tools/bot_desktop/runtime.py:80`).
- Hermes' preview pane is a separate render, not the agent's browser (`apps/desktop/electron/preview-reach.ts:1-21`).
- Hermes' browser calls the private-address check (`tools/browser_tool.py:88`).

**A correction to the agents' notes.** One agent wrote that Hermes stops the main agent after 500 turns and a sub-agent after 50. The config says otherwise: no limit for the main agent and 250 for a sub-agent. The 500 and 50 come from an out-of-date comment in `agent/iteration_budget.py:4`. H15 uses the config.

**How the numbers were measured.**

- Commits, authors, tags and files: `git rev-list --count HEAD`, `git shortlog -sn HEAD | wc -l`, `git tag | wc -l`, `git ls-files | wc -l`, and the first commit from `git log --reverse --format=%cd --date=short | head -1`.
- Lines: a short Python script counts the newline characters in every tracked file with a given extension, leaving out lock files. Python is `.py`. TypeScript and JavaScript are `.ts`, `.tsx`, `.js`, `.cjs`, `.mjs` and `.jsx`. A file counts as a test when a folder in its path is `tests`, `test`, `e2e`, `tests-js` or `integration_tests`, or when its name starts with `test_` or holds `.test.` or `.spec.`. Blank lines and comments count.
- Python test functions: `grep -rE "^\s*(async\s+)?def test_" tests --include=*.py | wc -l` in each repository. This counts functions, not the cases that parametrisation adds. For Our System, `uv run pytest --collect-only -q` collects 2,072 cases from its 1,072 functions.
- Viewer test cases: the count of `it(` and `test(` calls in `viewer/src/**/*.test.ts(x)`.
- Hermes counts (providers, platforms, skills, MCP settings, plug-in catalogue, workflows): `ls <folder> | wc -l` or `find ... -iname SKILL.md | wc -l`, as the evidence list names them.

**Limits.**

- The verdicts judge the code at the commits above. Hermes and the SDK change every day.
- Code was read, not run. A feature that exists in code may still fail in use. Our own open findings are in `docs/auto-mode-safeguards-status.md`.
- Line counts include blank lines and comments, so they overstate the code of all three alike.
- Three points are not confirmed from code. The first is whether Our System notices a person who clicks into the desktop view without pressing **Take over** (E6). The second is whether Hermes' main chat turn supports structured output (F4). The third is the absence of an ask-the-person tool and of action classes in the SDK, which rests on targeted searches rather than a full reading (G3, H4).
- The research notes behind this page were kept outside the repository and are not part of it.

## 20. Evidence by row

Paths for Hermes are relative to the `hermes-agent` repository, and paths for the SDK to `openai-agents-python`. "Absent" means a search found nothing.

| Row | Our System | Hermes | OpenAI Agents SDK |
|---|---|---|---|
| **A1** | `README.md:1-3` | `README.md:19-26`, `apps/desktop/package.json:6` | `pyproject.toml:2-6`, `README.md:3` |
| **A2** | Absent: `ls LICENSE*` | `LICENSE:1-3` | `LICENSE:1-3` |
| **A3** | `pyproject.toml:4-13`, `desktop/package.json:14-35` | `apps/desktop/package.json:186` | `pyproject.toml:8-23` |
| **A4, A5** | Section 19 | Section 19 | Section 19 |
| **A6** | `docs/feature-map.json`, `docs/demo-guide.md` | `website/docs/` (452 files), `website/docs/user-guide/desktop.md` | `mkdocs.yml:51-200` |
| **B1** | `README.md:8-13`, `desktop/electron/main.cjs:74` | `README.md:28-31`, `hermes_cli/main_desktop.py:1` | `README.md:29-48` |
| **B2** | `desktop/package.json:8-13`, `docs/bap-browser-spec.md:2944-2945` | `apps/desktop/electron-builder.config.cjs:180,236,285`, `website/docs/getting-started/platform-support.md:48-49` | `.github/workflows/publish.yml` |
| **B3** | Absent | `apps/desktop/electron-builder.config.cjs:126,181-195,338-350` | `.github/workflows/publish.yml:116-122` |
| **B4** | Absent | `apps/desktop/electron-builder.config.cjs:89-102`, `apps/desktop/electron/updater/channel.ts:18-41` | `README.md:29-48` |
| **B5** | `desktop/electron/main.cjs:87-107`, `desktop/src/App.tsx:170-178` | `apps/desktop/electron/first-run-setup-gate.ts:9-25`, `apps/desktop/src/components/onboarding-chat/intro.ts:1-39` | `src/agents/repl.py:16-34` |
| **B6** | `desktop/electron/main.cjs:74-76` | `apps/desktop/electron/backend-child.ts:1-21`, `apps/desktop/package.json:36-37` | `pyproject.toml:6` |
| **C1** | `desktop/electron/main.cjs:110-139`, `desktop/src/App.tsx:161-186` | `apps/desktop/src/app/right-sidebar/`, `apps/desktop/electron/session-windows.ts:52-55` | Absent |
| **C2** | `desktop/electron/main.cjs:16-25,66-99,134` | `apps/desktop/electron/preview-reach.ts:1-21`, `tools/browser_tool_session.py:67-83`, `tools/bot_desktop/runtime.py:80` | `examples/tools/computer_use.py:33` |
| **C3** | Absent | `apps/desktop/electron/hardening.ts:285-333,531-578` | Absent |
| **C4** | Absent | `apps/desktop/src/app/right-sidebar/files/`, `apps/desktop/src/app/right-sidebar/file-actions.tsx` | Absent |
| **C5** | Absent | `apps/desktop/package.json:108-113,136`, `apps/desktop/electron/terminal-ipc.ts` | Absent |
| **C6** | `desktop/src/main.tsx:9`, `viewer/src/tokens.test.ts:72-76` | `apps/desktop/src/themes/presets.ts`, `apps/desktop/src/themes/skin.ts` | Absent |
| **C7** | `viewer/src/wording.ts` | `apps/desktop/src/i18n/`, `apps/desktop/src/i18n/catalog-completeness.test.ts` | `docs/ja`, `docs/ko`, `docs/zh` |
| **C8** | `aria-` attributes in `viewer/src`, `viewer/src/tokens.test.ts:72-76` | `apps/desktop/electron/renderer-accessibility.ts:1-40` | Absent |
| **C9** | `desktop/src/components/ui/sidebar.tsx:30,97` | `apps/desktop/src/app/command-palette/index.tsx:1-30`, `apps/desktop/src/app/settings/keybind-settings.tsx` | Absent |
| **C10** | `desktop/electron/main.cjs:197` | `apps/desktop/electron/notification-registry.ts:1-14`, `apps/desktop/electron/tray-host.ts:1-24` | Absent |
| **D1** | `viewer/src/protocol.ts:44-97` | `apps/desktop/package.json:81-83,150` | `src/agents/stream_events.py:11-60` |
| **D2** | `viewer/src/protocol.ts:61-62`, `docs/demo-guide.md:113-115` | `apps/desktop/src/components/assistant-ui/tool/` | `src/agents/stream_events.py:24-50` |
| **D3** | `viewer/src/components/richText.tsx:1-37` | `apps/desktop/package.json:86-150` (shiki, katex, mermaid, dompurify) | Absent |
| **D4** | Absent | `apps/desktop/src/app/chat/composer/attachments.tsx:5-122` | `src/agents/items.py` |
| **D5** | `viewer/src/protocol.ts:152` | `apps/desktop/src/app/chat/sidebar/use-server-session-search.ts` | `src/agents/memory/session.py:53-96`, `src/agents/extensions/memory/` |
| **D6** | `viewer/src/protocol.ts:138-139` | `apps/desktop/src/app/session/hooks/use-prompt-actions/rewind.ts:1-9` | `src/agents/run_state.py`, `src/agents/repl.py:76` |
| **D7** | `README.md:17` | `apps/desktop/src/app/chat/sidebar/fleet-rail.ts`, `apps/desktop/ENGINEERING.md:74-76` | Absent |
| **D8** | `viewer/src/protocol.ts:140,151`, `desktop/electron/main.cjs:53-64` | `hermes_cli/commands.py:124-126`, `apps/desktop/src/app/session/hooks/use-prompt-actions/rewind.ts:1-6` | `src/agents/result.py:933-958` |
| **D9** | Absent | `apps/desktop/src/app/chat/composer/hooks/use-voice-live-conversation.ts` | `src/agents/voice/`, `src/agents/realtime/` |
| **E1** | `src/bap_browser/driver/playwright_driver.py:1-10` | `tools/browser_tool_session.py:331-362`, `tools/browser_use_cli.py:234-241` | `src/agents/computer.py:8-66` |
| **E2** | `src/bap_browser/driver/snapshot.py` | `tools/browser_tool.py:817-848`, `tools/browser_tool_snapshot.py:69-108` | `src/agents/computer.py:27-29` |
| **E3** | `src/bap_browser/tools/offered.py`, `src/bap_browser/config.py:173` | `tools/browser_tool.py:1308-1370`, `tools/browser_use_cli.py:829`, `tools/browser_vault_tool.py` | `src/agents/tool.py:836,891` |
| **E4** | `docs/feature-map.json` ("tools") | `tools/browser_supervisor_dialogs.py`, `tools/browser_supervisor_frames.py`, `website/docs/user-guide/features/browser.md` | `src/agents/computer.py:8-66` |
| **E5** | `docs/demo-guide.md:93-95` | `tools/browser_tool_session.py:67-83`, `apps/desktop/src/plugins/hermes-bots/screen-pane.tsx:1-12` | `examples/tools/computer_use.py:33` |
| **E6** | `src/bap_browser/service/session.py:209,220-221,500` | `apps/desktop/src/plugins/hermes-bots/screen-pane.tsx:1-12`, `tools/bot_desktop/runtime.py:80` | `src/agents/tool.py:890-898` |
| **E7** | `desktop/electron/main.cjs:130-131` | `tools/browser_tool_real_profile.py`, `agent/vault_backends/` | `src/agents/computer.py` |
| **E8** | `src/bap_browser/config.py` (`Backend.kind`), `docs/bap-browser-spec.md:2984` | `plugins/browser/browser_use/provider.py`, `plugins/browser/browserbase/provider.py`, `plugins/browser/firecrawl/provider.py` | `src/agents/extensions/sandbox/` |
| **E9** | `docs/feature-map.json` ("code-tool") | `tools/browser_use_cli.py:234-241,829`, `evals/browser_use/README.md:52-65` | `src/agents/tool.py:1641-1646` |
| **F1** | `src/bap_browser/agent/loop.py:1-5` | `run_agent.py:214`, `agent/conversation_loop.py:1381-1709` | `src/agents/run.py`, `src/agents/run_internal/` |
| **F2** | `src/bap_browser/config.py:405-407` | `plugins/model-providers/` (38) | `src/agents/extensions/models/` |
| **F3** | `src/bap_browser/config.py:408-411` | `hermes_cli/cli_model_switch_mixin.py:829,928` | `src/agents/models/default_models.py:103` |
| **F4** | `src/bap_browser/safeguards/model.py:132` | `agent/auxiliary_structured_output.py:1-20`, `tools/delegation_output_schema.py:1-15` | `src/agents/agent_output.py:22-39` |
| **F5** | Absent | `tools/delegate_tool.py:1-12,60`, `hermes_cli/moa_config.py:1-15` | `src/agents/agent.py:354-355,606-646` |
| **F6** | `docs/feature-map.json` ("computer-use") | `tools/` (281 files) | `src/agents/tool.py:454-1646` |
| **F7** | Absent | `tools/mcp_tool.py`, `optional-mcps/` (68), `tools/osv_check.py:1-20` | `docs/mcp.md:20-25` |
| **F8** | `src/bap_browser/mcp/server.py` | `mcp_serve.py:1-8` | Absent |
| **F9** | `plugin/skills/browse/SKILL.md` | `tools/skills_tool.py:1-4`, `skills/` and `optional-skills/` (212 `SKILL.md`) | `src/agents/sandbox/capabilities/skills.py:29-85` |
| **F10** | Absent | `tools/memory_tool.py:1-7`, `plugins/memory/` | `src/agents/memory/` |
| **F11** | `src/bap_browser/agent/openai_model.py:1-5` | `agent/context_compressor.py:1-2`, `agent/conversation_compression.py:1-8` | `src/agents/extensions/tool_output_trimmer.py:1-24`, `src/agents/run_config.py:455` |
| **F12** | `src/bap_browser/safeguards/model.py:85-108` | `agent/agent_init_fallback.py:11-18` | `src/agents/retry.py:16-30` |
| **F13** | `src/bap_browser/safeguards/model.py:31-36`, `src/bap_browser/evals/summary.py:14-25` | `hermes_state_usage.py`, `agent/account_usage.py`, `hermes_cli/subcommands/usage.py:1-5` | `src/agents/usage.py`, `docs/usage.md:3-18` |
| **F14** | Absent | `cron/jobs.py:2-3` | Absent |
| **F15** | Absent | `plugins/platforms/` (21) | Absent |
| **G1** | `src/bap_browser/safeguards/check.py:185-221`, `src/bap_browser/safeguards/reviewer.py:146-164` | `tools/approval.py:945-1016`, `tools/approval_detection.py:107-140,228-482` | `src/agents/tool.py:499-511`, `docs/human_in_the_loop.md:15` |
| **G2** | `src/bap_browser/driver/session.py:26-30` | `apps/desktop/src/components/assistant-ui/tool/approval.tsx:190-423` | `src/agents/run_internal/approvals.py:46-48`, `docs/human_in_the_loop.md:199` |
| **G3** | `src/bap_browser/tools/browser_tools.py:338`, `src/bap_browser/tools/human_checks.py:1-39` | `tools/clarify_tool.py:1-80` | Absent |
| **G4** | `src/bap_browser/service/session.py:207,218` | `hermes_cli/commands.py:126`, `tools/interrupt.py:74-99` | `src/agents/run_state.py:1366-1413` |
| **G5** | As E6 | As E6 | As E6 |
| **G6** | As D8 | As D8 | As D8 |
| **G7** | `src/bap_browser/config_safeguards.py:14-20`, `src/bap_browser/safeguards/reviewer.py:146-164`, `src/bap_browser/safeguards/check.py:382-391` | `apps/desktop/src/store/approval-mode.ts:3`, `tools/approval.py:46,94-112,741-770` | Absent |
| **G8** | `src/bap_browser/service/session.py:45` | `gateway/session_state.py:236`, `apps/desktop/src/app/session/hooks/use-session-actions/restore-pending-approval.ts:1-28` | `src/agents/run_state.py:1885,2247,2305,2318-2323,2393` |
| **G9** | `docs/bap-browser-spec.md:4540-4542,4571` | `apps/desktop/src/store/native-notifications.ts:25-39` | `docs/human_in_the_loop.md:53` |
| **H1** | `docs/bap-browser-spec.md:4086-4221`, `src/bap_browser/safeguards/scan.py` | `tools/threat_patterns.py:1-60`, `agent/context_file_sources.py:52-58`, `SECURITY.md:150-158` | `SECURITY.md:38` |
| **H2** | `src/bap_browser/safeguards/scan.py` | `agent/tool_guardrails.py:1-60` | `src/agents/guardrail.py:71-185`, `src/agents/tool_guardrails.py:40-117`, `docs/guardrails.md:56` |
| **H3** | `src/bap_browser/safeguards/actions.py` | `tools/approval_detection.py:107-140,228-482` | `src/agents/run_internal/tool_execution.py:2513-2522` |
| **H4** | `src/bap_browser/safeguards/reviewer.py:29,146-150`, `docs/bap-browser-spec.md:4240-4257` | `tools/approval_detection.py:17-39` | `src/agents/tool.py:499-511` |
| **H5** | `src/bap_browser/policy/redaction.py:13-27`, `docs/bap-browser-spec.md:4493-4496` | `agent/redact.py:97,887-951`, `tools/environments/local_env_policy.py:1-50` | `src/agents/_debug.py:12-28`, `src/agents/run_config.py:53-56` |
| **H6** | `desktop/electron/main.cjs:80`, `src/bap_browser/config.py:419-422` | `agent/vault_backends/local.py:1-20`, `hermes_cli/auth.py:793-797`, `apps/desktop/electron/hardening.ts:156-236` | `src/agents/_config.py:13-17` |
| **H7** | `src/bap_browser/policy/url_policy.py:7-8,27-30,112-144` | `tools/url_safety.py:96-137,339-429`, `tools/browser_tool.py:88` | `src/agents/tool.py:1332-1374` |
| **H8** | `src/bap_browser/safeguards/lookalikes.py`, `docs/auto-mode-safeguards-status.md:50` | `tools/url_safety.py:70-93` | Absent |
| **H9** | `docs/bap-browser-spec.md:4302-4317` | `website/docs/user-guide/features/browser.md` | `src/agents/run_config.py:48-50` |
| **H10** | `docs/feature-map.json` ("code-tool") | `SECURITY.md:48-75`, `agent/terminal_env_registry.py:27` | `docs/sandbox/guide.md:67-73`, `git log --oneline -30 -- src/agents/sandbox` |
| **H11** | `desktop/electron/main.cjs:118-168`, `desktop/index.html:1-13` | `apps/desktop/electron/window-open-policy.ts:1-94`, `apps/desktop/electron/main.ts:13581-13588`, `apps/desktop/electron/windows-sandbox-fallback.ts:1-20`, `apps/desktop/index.html` | Not applicable |
| **H12** | `src/bap_browser/service/app.py:77,563-567,683`, `src/bap_browser/service/wrapping.py:32-43`, `src/bap_browser/config.py:317`, `desktop/electron/core-line.cjs:21-24` | `apps/desktop/electron/backend-discovery.ts:23,42,152`, `apps/desktop/electron/dashboard-token.ts:1-101` | Not applicable |
| **H13** | `uv.lock`, `viewer/package-lock.json`, `desktop/package-lock.json` | `tools/osv_check.py:1-20`, `tools/skills_guard.py:21-33`, `tools/plugin_guard.py:1-9`, `.github/workflows/osv-scanner.yml`, `apps/desktop/electron/desktop-plugin-install.ts:355-364` | `.github/workflows/publish.yml:40-44,116-122`, `.github/workflows/codeql.yml:1-24` |
| **H14** | Absent: no telemetry code in `src`, `desktop` or `viewer/src`, `docs/bap-browser-spec.md:4498-4500` | `hermes_cli/config_defaults.py:2329-2342,2545-2547` | `src/agents/tracing/processors.py:46`, `src/agents/run_config.py:53-56` |
| **H15** | `src/bap_browser/config_safeguards.py:458-471`, `src/bap_browser/safeguards/limits.py:56-170` | `hermes_cli/config_defaults.py:78,1361`, `agent/repetition_guard.py:16-57`, `agent/tool_guardrails.py:36-45`, `hermes_cli/model_cost_guard.py:12-13` | `src/agents/run_config.py:45`, `src/agents/tool.py:514-519` |
| **H16** | Absent: no `SECURITY.md` | `SECURITY.md:1-20,76-100,320-335` | `SECURITY.md:1-44` |
| **H17** | `docs/bap-browser-spec.md:4483-4500`, `docs/auto-mode-safeguards-status.md:68` | `hermes_state_timeline.py`, `hermes_cli/dashboard_auth/audit.py:1-33` | `src/agents/result.py:369,374` |
| **I1** | `src/bap_browser/tools/event_log.py:1-35`, `src/bap_browser/cli.py:245` | `hermes_logging.py:1-17` | `src/agents/_debug.py:12-28` |
| **I2** | Absent | `agent/monitoring/otlp_exporter.py:1-7`, `plugins/observability/langfuse/__init__.py:1-7` | `src/agents/tracing/processors.py:28-903` |
| **I3** | `src/bap_browser/evals/record.py:1-7`, `docs/bap-browser-spec.md:2980` | `mini_swe_runner.py:1-9`, `batch_runner.py:2-6` | `docs/testing.md:3-6` |
| **I4** | `src/bap_browser/evals/summary.py:14-29` | `hermes_cli/subcommands/usage.py:1-5` | `docs/usage.md:3-27` |
| **I5** | `src/bap_browser/doctor.py:1-23` | `hermes_cli/doctor.py:1-4` | Absent |
| **I6** | `src/bap_browser/evals/sets/`, `tests/site/attacks/` (26) | `evals/` (147 Python files), `evals/toolperf_abeval/ab_eval.py:1-15` | `docs/testing.md:1-20` |
| **I7** | `perf/budget.json`, `src/bap_browser/bench/runner.py:1-20` | `scripts/iso-certify.py:1-32`, `tests/perf_guards/test_pattern_b_scaling.py:1-8` | Absent |
| **J1** | `src/bap_browser/config.py:1-35` | `hermes_cli/config.py:436-438`, `cli-config.yaml.example:1-9` | `src/agents/_config.py:13-54` |
| **J2** | `src/bap_browser/config.py:25-27` | `.env.example:1-18` | `src/agents/_debug.py:5-28` |
| **J3** | `src/bap_browser/settings/catalogue.py` | `apps/desktop/src/app/settings/`, `apps/desktop/src/app/settings/config-settings.tsx:10` | Absent |
| **J4** | `src/bap_browser/config.py:419-422` | `apps/desktop/src/app/settings/keys-settings.tsx`, `apps/desktop/src/app/settings/env-credentials.tsx:1-20` | `src/agents/_config.py:13-19` |
| **J5** | `src/bap_browser/config.py:198-202` | `hermes_cli/profiles.py:1` | Absent |
| **J6** | `src/bap_browser/service/app.py:273-300,656-657` | `hermes_cli/managed_scope.py:1-7`, `hermes_cli/config.py:235` | Absent |
| **K1** | `plugin/.claude-plugin/plugin.json` | `plugins/AGENTS.md:1-15`, `plugin-catalog/` (523) | `src/agents/extensions/` |
| **K2** | As F9 | As F9 | As F9 |
| **K3** | Absent | `gateway/hooks.py:1-8` | `src/agents/lifecycle.py` |
| **K4** | `src/bap_browser/tools/offered.py` | `website/docs/developer-guide/adding-tools.md:96-119` | `src/agents/decorators.py`, `src/agents/tool.py:454` |
| **K5** | As F7 and F8 | As F7 and F8 | As F7 and F8 |
| **K6** | `docs/feature-map.json` ("tools") | `run_agent.py:1-6`, `setup.py:1-18` | `README.md:58-69` |
| **L1** | Section 19 | Section 19, `apps/desktop/e2e/` | Section 19, `integration_tests/` |
| **L2** | `desktop/electron/core-line.test.cjs` | `pyproject.toml:841-849`, `apps/desktop/package.json:65-78` | `Makefile` |
| **L3** | `.github/workflows/ci.yml` | `.github/workflows/` (51) | `.github/workflows/` (10) |
| **L4** | `.github/workflows/ci.yml:16-30` | `.github/workflows/lint.yml:1,51-84`, `apps/desktop/package.json:60` | `pyproject.toml:193-194`, `Makefile` |
| **L5** | `desktop/package.json:8-13` | `ruff.strict.toml`, `lefthook.yml:1-4`, `apps/desktop/package.json:61-64` | `pyproject.toml:157-172` |
| **L6** | `scripts/gate.py:38-48`, `scripts/patterns.py` | `scripts/check:1-16`, `scripts/code_health/`, `apps/desktop/eslint.config.mjs:17-67` | `Makefile` (`check`, `coverage`) |
| **M1** | `.github/workflows/ci.yml:8` | `website/docs/getting-started/platform-support.md:17-49` | `pyproject.toml:30`, `README.md:77` |
| **M2** | `CLAUDE.md` ("Gotchas"), `desktop/electron/main.cjs:57-63` | `apps/desktop/electron/windows-sandbox-fallback.ts`, `apps/desktop/electron/windows-stack-cookie-fallback.ts`, `apps/desktop/electron/backend-child.ts:1-15` | `README.md:77` |
| **N1** | Absent | `hermes_startup_watchdog.py:1-9` | Absent |
| **N2** | As I7 | As I7 | Absent |
| **N3** | `tests/unit/test_registry.py:96-104`, run on `TOOLS` from `src/bap_browser/tools/offered.py` | `evals/browser_use/README.md`, `evals/prompt_footprint/property_guidance.py:1-2` | `src/agents/extensions/tool_output_trimmer.py:1-24` |
| **N4** | `docs/demo-guide.md:214-217` | `evals/browser_use/`, `evals/toolperf_abeval/`, `evals/codebase_navigability/` | Absent |
