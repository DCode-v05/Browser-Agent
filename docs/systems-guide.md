# bap-browser: the Systems page

Written on 2026-10-06 for `main`. It says what was added for the three browsers as **systems**:
their configuration (what to enable, how to manage each) and their evaluations. The design is in
`docs/bap-browser-spec.md`, sections 9.17 and 12.6; what else is built is in `docs/demo-guide.md`.

## In one paragraph

The window has three browsers the agent can work in: **Cloud browser**, **My Chrome** and
**Built-in browser**. Each is now a system of its own. It has its own settings, it can be turned on
and off and started and stopped by itself, it writes its own log file, and everything its tasks took
is recorded and shown for it alone.

It is shown in two places:

| Where | What you see |
|---|---|
| Under each browser's own tab | Three views of that browser: **Browser and chat**, **Configuration** and **Evaluations** |
| **Systems**, at the top right of the window | The three browsers side by side, to compare them |

| System | Name in files and addresses | What it is |
|---|---|---|
| Cloud browser | `cloud` | A browser of the service's own, with nothing kept from one session to the next |
| My Chrome | `chrome` | A tab of your own Chrome, through the extension |
| Built-in browser | `builtin` | The app's own browser, which keeps its sign-ins |

The Systems page has the same two views, **Configuration** and **Evaluations**, with one card for
each system. The card is the same in both places. The view you choose under a browser's tab stays
as it is when you go to the next browser.

---

## Part 1. Configuration

### 1.1 Turning a system on and off

| Control | What it does |
|---|---|
| **Use this browser** (a switch, on each card) | On: the system runs and the agent can work in it. Off: its session ends, its tab says "Turned off", and nobody is connected to it. It stays off the next time the service starts |
| **Turn it on** (on the page of a system that is off) | The same switch, from the system's own page |

### 1.2 Managing a system

| Button | When it is there | What it does |
|---|---|---|
| **Start** | The system has no session | Starts a new browser and a new conversation |
| **Stop** | The system is running | Ends its session. The system stays turned on |
| **Restart** | The system is running | Ends its session and starts a new one |
| **All settings** | Always | Opens the whole settings screen of that system |

My Chrome has no Start button while it is not connected: it connects by itself, a moment after its
extension is loaded in Chrome. What cannot be done is answered with a sentence on the card, such as
"This browser is turned off. Turn it on first."

### 1.3 What to enable in a system

These are switches on each card, under **What the agent may do here**. Each is that system's alone:
turning downloads off for the cloud browser leaves them on for the other two.

| Switch | What it does | As installed |
|---|---|---|
| Let the agent download files | Offers the tool that lists saved files | On |
| Let the agent upload files | Offers the upload tool. Each upload still asks you | On |
| Keep a log of the agent's steps | Writes that system's log file (section 1.6) | On |
| Let the agent run scripts in pages | Offers `browser_evaluate`. Each use still asks you | Off, and locked |
| Let the agent run scripts of several steps | Offers `browser_run`, the code tool | Off, and locked |

**Locked** means the switch is shown, off, with "Set by your organisation", and cannot be turned on
from the window. The rule is the same everywhere in the settings: in the window a person can make
things stricter than `config.json` says, never looser. To be able to turn these two on, allow them
in `config.json` first:

```json
{
  "browser": { "javascript": { "allow_evaluate": true } },
  "code": { "enabled": true }
}
```

After that each system has the switch, and you turn it off for the systems that should not have it.

### 1.4 Every setting a system has of its own

Shown on the card under **How it is set up**, and changed in **All settings** (or from the settings
button on that browser's page).

| Setting | Choices (the first is as installed) | What it changes |
|---|---|---|
| Use this browser | On, Off | Section 1.1 |
| Model | The model in `config.json`, and any in `agent.offered_models` | The model that plans the agent's steps. A change holds from the next task |
| Ask before | Risky actions, Every action | When the agent must wait for your approval |
| Wait for my answer | 3 minutes, 1, 5, 10 minutes | How long an approval waits before it is denied |
| Remember "Allow on this site" | Until the session ends, Never | How long that answer lasts |
| Blocked sites | A list, one site for each line | Sites the agent must never open. Added to those of `config.json` |
| Only allow these sites | A list | When it has entries, the agent may open only these |
| Let the agent download files | On, Off | Section 1.3 |
| Let the agent upload files | On, Off | Section 1.3 |
| Keep a log of the agent's steps | On, Off | Section 1.6 |
| Picture quality | Standard, Data saver, High | How much data the live picture uses |
| Let the agent run scripts in pages | Off, On | Section 1.3 |
| Let the agent run scripts of several steps | Off, On | Section 1.3 |

**Which value holds.** A system's own value, where it has one. Otherwise the value you set for
every browser. Otherwise what `config.json` says.

**When a change takes hold.** At the agent's next step: the site lists, the tools on offer,
approvals, the log and the picture quality all follow at once. The model follows from the next task.

**What is one for the whole window, not a system's.** Colour mode; Show where the agent is acting;
Stay signed in to sites and Clear browsing data (both are about the cloud browser); About this
deployment. Changed on any system's screen, these change everywhere.

### 1.5 To choose the model for each system

Name the other models in `config.json`. Each system then has a **Model** setting.

```json
{ "agent": { "model": "gpt-5.6-luna", "offered_models": ["another-model-name"] } }
```

### 1.6 The log file of each system

Each system writes its own file. Nothing goes to one shared log.

| System | File |
|---|---|
| Cloud browser | `.bap-browser/logs/cloud.jsonl` |
| My Chrome | `.bap-browser/logs/chrome.jsonl` |
| Built-in browser | `.bap-browser/logs/builtin.jsonl` |

One line for each step the agent took:

```json
{"ts": 1791302741.076, "tool": "browser_snapshot", "args": {"mode": "all"}, "ok": true, "ms": 3.3, "chars": 1367, "result": "Page: BAP Browser"}
```

| Field | What it is |
|---|---|
| `ts` | When, in seconds since 1970 |
| `tool` | The tool that was called |
| `args` | What it was given. Typed text is written as its length only, never the text |
| `ok` | Whether it worked |
| `ms` | How long it took |
| `chars` | How many characters went back to the agent |
| `result` | The first line of the result: what was done |

On the card, **Log file** shows where the file is, and **Show the log** shows its newest 20 lines,
newest first. Turning "Keep a log of the agent's steps" off for a system stops its file, and the
card then says "The log is turned off for this browser."

### 1.7 Where your choices are kept

In `.bap-browser/settings.json`, for you alone to read. What you set for every browser is at the
top; each system's own values are under `systems`.

```json
{
  "colour_mode": "dark",
  "systems": {
    "cloud": { "allow_downloads": false, "ask_before": "every_action" },
    "builtin": { "system_enabled": false }
  }
}
```

### 1.8 What was added to `config.json`

| Key | As installed | What it is |
|---|---|---|
| `agent.offered_models` | `[]` | Other models a person may choose for a system |
| `agent.input_price_per_million` | `0.0` | What a million tokens sent to the model cost, in US dollars. 0 means not known |
| `agent.output_price_per_million` | `0.0` | What a million tokens the model wrote cost |
| `logging.systems_dir` | `.bap-browser/logs` | Where each system writes its log |
| `logging.shown_lines` | `200` | The most lines of a log the service hands the window |
| `evals.enabled` | `true` | Keep a record of each task (Part 2) |
| `evals.dir` | `.bap-browser/evals` | Where those records are kept |
| `evals.max_task_chars` | `200` | How much of a task's words, and of its answer, a record keeps |
| `evals.recent_tasks` | `20` | The tasks listed for a system |
| `evals.max_tasks_read` | `2000` | The newest records a summary is made from |
| `evals.step_budget_ms` | `2000` | The checklist's limit for one step |
| `settings.locked` | `[]` | Settings nobody may change from the window. Was there before; it holds for each system too |

---

## Part 2. Evaluations

### 2.1 What is recorded

Every task you give a system in its chat is recorded when it ends: one line in
`.bap-browser/evals/<system>/tasks.jsonl`, for you alone to read.

| Recorded | What it is |
|---|---|
| How it ended | Answered; the model failed; stopped by you; ran out of steps; the session ended |
| Time | The whole task, and its three parts: the model's replies, the steps in the browser, and waiting for you |
| Steps | How many, and how many failed |
| Model | Which model, and how many replies it gave |
| Tokens and cost | Tokens in and out as the provider counted them, and what they cost |
| The task and the answer | In their own words, cut to 200 characters |
| The trace | Every reply of the model and every step, in order: when it began, how long it took, whether it worked |

Two things are never recorded. What the agent types into a page: a step is kept by its tool's
name only. And, where the log is turned off for a system, the words of the task and the answer:
only the numbers are kept then.

### 2.2 What the Evaluations view shows, for each system

| Shown | What it says | Example, from a real task on the cloud browser |
|---|---|---|
| **Model** | The model the system uses now | `gpt-5.6-luna` |
| **Tasks** | How many tasks and steps; how many failed, were stopped, ran out of steps | 1 task, 1 step |
| **Outcome quality** | The share of tasks answered; steps that failed; your own Good and Bad | 100% answered (1 of 1) |
| **Latency** | A step in the browser, and a reply of the model: the typical one and the slow one | A step: 4 ms. A reply: 2.3 to 3.8 s |
| **Time** | A task, typical and slow; and where the time went: the model, the browser, waiting for you | 6.1 s, nearly all of it the model |
| **Cost** | Tokens in and out; dollars in all and for a task | 4,730 tokens in, 34 out |
| **Performance by tool** | For each tool: calls, typical time, slow time, failures. The most used comes first | snapshot: 1 call, 4 ms |
| **Checklist** | Section 2.4 | 10 passed, 1 skipped |
| **Recent tasks and their traces** | The newest 20 tasks, each with Good, Bad and Show the trace | |

"Typical" is the median: half are faster. "Slow" is the 95th percentile: 95 in 100 are faster.
What a step waited for you (an approval, a sign-in) is taken out of that step's time, so a system
is not shown as slow because you were away.

### 2.3 The trace of a task

**Show the trace** on a task draws it as bars, one for each reply of the model and each step in the
browser: where in the task it began, and how long it was. A step that failed is marked. A step that
waited for you says how much of its time was that wait. A reply of the model says its tokens.

The task above, as its trace:

| | Took |
|---|---|
| The model | 3.8 s |
| snapshot | 4 ms |
| The model | 2.3 s |

### 2.4 The checklist

**Run the checklist** does eleven checks as real steps on the demo site, in that system's own
browser, in a few seconds. You see the steps on the system's page like any others, and they are
written to its log. What it types is made up ("Ada Lovelace"). When it has finished, the browser
goes back to where it was.

| Check | Passes when |
|---|---|
| The browser answers | It lists its tabs |
| Opens a page | The demo site's start page opens |
| Reads the page | The page's words come back |
| Finds an element by its words | "create an account" is found |
| Clicks, and the page follows | Clicking it opens the sign-up page |
| Types into a field | Typing into the first field works |
| Takes a picture | A screenshot comes back |
| Refuses the cloud metadata address | Opening `169.254.169.254` is refused |
| Every step within 2000 ms | The slowest step of the run is within the limit |
| Writes its log | The system's log file grew. Skipped where its log is off |
| A person can be asked | Someone is watching the system's page. Skipped when no one is |

Each line says Passed, Failed or Skipped, with how long it took, and why when it did not pass. The
result is kept and shown until the next run. The checklist runs only on a system the agent is
driving and that is doing nothing; otherwise the card says why, for example "This browser is busy.
Run the checklist when its task is finished."

### 2.5 Your word on an answer

**Good** and **Bad** on a task record what you thought of the answer. It counts in Outcome quality
("You rated 3 good and 1 bad"). Pressed again, it is taken back.

### 2.6 To see cost in dollars

Tokens are always counted. Dollars are shown once you say what your model costs. No cost is made up
without a price.

```json
{ "agent": { "input_price_per_million": 2.0, "output_price_per_million": 10.0 } }
```

Those two numbers are an example. Put in your provider's own prices.

### 2.7 The files

| File | What it holds |
|---|---|
| `.bap-browser/evals/<system>/tasks.jsonl` | One line for each task, with its trace |
| `.bap-browser/evals/<system>/ratings.json` | Your Good and Bad, by task |
| `.bap-browser/evals/<system>/checks.json` | The checklist as it was last run |

---

## Part 3. For a program: the addresses

All need the service's token in an `Authorization: Bearer` header. `{name}` is `cloud`, `chrome` or
`builtin`.

| Address | What it does |
|---|---|
| `GET /api/systems` | Each system: where it stands, whether it is on, its model, where its log and records are |
| `POST /api/systems/{name}/start`, `/stop`, `/restart` | Manage it |
| `GET /api/systems/{name}/log` | Where the log is, and its newest lines |
| `GET /api/settings?surface=web&system={name}` | That system's settings |
| `PATCH /api/settings` with `{"surface": "web", "system": "{name}", "changes": {…}}` | Change them |
| `GET /api/systems/{name}/evals` | Everything of section 2.2 |
| `GET /api/systems/{name}/evals/{task}` | One task with its trace |
| `POST /api/systems/{name}/evals/{task}/rating` with `{"rating": "good"}` | Your word on an answer. `"bad"`, or `null` to take it back |
| `POST /api/systems/{name}/checks` | Run the checklist |

A request that cannot be done answers 409 with `{"error": "…"}`, a sentence for a person.

---

## Part 4. To show it

1. Start the window: `uv run bap-browser studio --open`.
2. On the Cloud browser's page, give the agent a task in the chat, and let it finish.
3. Under the Cloud browser's tab, press **Configuration**, then **Evaluations**: that browser's own
   set-up, and what the task took.
4. Press **Systems** to see the three side by side. In **Configuration**, turn "Let the agent
   download files" off for the Cloud browser: the other two cards keep it on.
5. Press **Show the log** on the Cloud browser's card: the steps of the task are there.
6. Turn **Use this browser** off for the Built-in browser: its tab says "Turned off". Turn it on again.
7. Go to **Evaluations**. The Cloud browser's card shows the task: model, time, tokens.
8. Press **Run the checklist** on a card, and watch the lines turn to Passed.
9. Press **Show the trace** on the task, then **Good**.

## What it does not do

| Not there | Note |
|---|---|
| A judgement of an answer by another model | Outcome quality is how tasks ended, and your own Good and Bad |
| Cost without a price | Set the two prices in `config.json` (section 2.6) |
| Systems outside the three-browser window | The Systems page belongs to `bap-browser studio`. The commands that run one session (`agent`, `mcp`) have one log, `.bap-browser/events.jsonl`, and no evaluations |
| The checklist and the records, tried on My Chrome | They are the same code for the three systems. They were run on the Cloud and the Built-in browser; My Chrome was not connected when this was written |
