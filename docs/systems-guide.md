# bap-browser: the Systems page

Written on 2026-10-06 and brought up to date on 2026-10-07: for the admin and the user, and then so
that each thing is in one place. It says what was added for the three browsers as **systems**: who
signs in, their configuration (what to enable, how to manage each), a user's own settings, and their
evaluations. The design is in
`docs/bap-browser-spec.md`, sections 4.11, 9.17 and 12.6; what else is built is in `docs/demo-guide.md`.

## In one paragraph

The window has three browsers the agent can work in: **Cloud browser**, **My Chrome** and
**Built-in browser**. Each is now a system of its own. It has its own settings, it can be turned on
and off and started and stopped by itself, it writes its own log file, and everything its tasks took
is recorded and shown for it alone.

**Each thing is in one place.** Nothing is set twice, and no screen opens over a page.

| What you want | Where it is |
|---|---|
| To work with one browser | Its tab, view **Browser and chat** |
| To set one browser up (admin) | Its tab, view **Configuration**. The settings button on the chat goes there too |
| To see what one browser's tasks took | Its tab, view **Evaluations** |
| To say what users may change and see, and the passwords (admin) | **Systems**, at the top right, view **Users** |
| To compare the three browsers (admin) | **Systems**, view **All systems** |
| Your own settings for one browser (user) | Its tab, view **Settings** |

| System | Name in files and addresses | What it is |
|---|---|---|
| Cloud browser | `cloud` | A browser of the service's own, with nothing kept from one session to the next |
| My Chrome | `chrome` | A tab of your own Chrome, through the extension |
| Built-in browser | `builtin` | The app's own browser, which keeps its sign-ins |

Every page begins with a heading and a line that say whose page it is and what it is for, such as
"Configuration of Cloud browser. For the admin. How this one browser is set up…". Every setting has
a line under its name saying what it does, and every control works: a change is saved as you make
it, and the row says "Saved". The view you choose under a browser's tab stays as it is when you go
to the next browser.

That is the window as **the admin** has it. A **user** signs in on a page of their own and has less:
Part 0 says who has what.

---

## Part 0. Who signs in: the admin and the user

### 0.1 Two pages, two passwords

| | The admin | A user |
|---|---|---|
| The page to open | `http://127.0.0.1:8765/admin` | `http://127.0.0.1:8765/` |
| Their part of the window | **Configuration**: sets the system up, and says what users are allowed | **Settings**: their own, inside what the admin allows |
| Under each browser's tab | Browser and chat, Configuration, Evaluations | Browser and chat, Settings, Evaluations |
| The **Systems** page | Yes | No |
| The browsers they have | All three | Those the admin lets users use |

The top right of the window says who is signed in, **Admin** or **User**, beside **Sign out**. Each
sign-in page has a link to the other.

### 0.2 The first time

1. Start the window: `uv run bap-browser studio --open`. The first time, it opens the admin's page
   with the link that creates the password.
2. **Create the admin password**: type it twice (8 characters or more) and press "Create the password
   and sign in". From then on the admin signs in at `/admin` with it.
3. Press **Systems**. In the view **Users**, under "Sign-in passwords", type the password users
   sign in with and press **Set it**.
4. A user opens `/` and signs in with that password.

If the admin's password is lost: start the service again and open the link it prints
(`…/admin#token=…`). With that link the admin is let in and changes the password on the Users card.

| Rule | As installed | In `config.json` |
|---|---|---|
| The shortest password | 8 characters | `auth.min_chars` |
| How long a sign-in lasts | 12 hours | `auth.session_hours` |
| Wrong passwords in a row before sign-in waits | 5, then 60 seconds | `auth.max_failures`, `auth.lock_s` |
| Where the passwords are kept | `.bap-browser/accounts.json`, as salted hashes, for you alone to read | `auth.file` |

A new password signs out everyone who used the old one; their open page goes back to its sign-in page.

### 0.3 What the admin allows users

Every line is a working switch, with a sentence under it saying what it lets a user do. A change
shows on the user's page within a few seconds, with no reload.

| Where | Switch | Off means |
|---|---|---|
| A browser's tab, **Configuration**, under "For users" | **Let users use this browser** | For a user that browser is not there at all: no tab, no address |
| **Systems**, Users, "What users may change" | One for each of: Ask before, Wait for my answer, Remember "Allow on this site", Blocked sites, Only allow these sites, Picture quality, Show where the agent is acting, Colour mode | Every user has your value for it, shown to them in words |
| **Systems**, Users, "What users may see" | Evaluations of the browsers they use | A user has no Evaluations view |
| | What the tasks cost | A user sees no tokens-to-dollars and no cost of a task |
| | The tasks and their traces | A user sees no list of tasks, no trace, and gives no Good or Bad |
| | Run the checklist | A user sees no checklist and cannot run one |
| | The log of the agent's steps (off as installed) | A user does not see the log |

Everything else in a browser's Configuration (Use this browser, Start, Stop, Restart, the model,
downloads, uploads, the log, scripts) is the admin's alone. A user never sees those controls.

On a browser's Configuration, a setting that users also have says so under its description: "Also on
the user's page. Users may set their own, never looser than yours.", or "…held at your value: users
cannot change it." A setting with no such line is yours alone.

The Users view also lists **Browsers users may use**, each with a button to that browser's
Configuration, where it is set.

### 0.4 A user's Settings

Under a browser's tab, **Settings** shows one card for that browser. The settings button on the chat
goes there too.

| On the card | What it does |
|---|---|
| **Preferred browser** | The browser your window opens on. Choose one and it opens at once, ready for a task. If it has stopped, it is started for you |
| **Approvals**: Ask before, Wait for my answer, Remember "Allow on this site" | When the agent must wait for you, for how long, and how long "Allow on this site" lasts |
| **Sites**: Blocked sites, Only allow these sites | Typed here, one site for each line |
| **Live view**: Picture quality, Show where the agent is acting | How sharp the live picture is, and whether the agent's pointer is drawn over it |
| **Appearance**: Colour mode | Light, dark, or the same as your device. It holds on every page of your window |
| A setting your admin holds | Shown in the same place in words, with its value and "Set by your admin". It has no control |

A user can make a setting stricter than the admin has it, never looser: where the admin asks before
every action, a user cannot go back to "Risky actions". The looser choice is shown, and cannot be taken.

### 0.5 Who sees which evaluations

| | The admin | A user |
|---|---|---|
| Each system's evaluations | All three | Those of the browsers they may use, if the admin lets users see evaluations |
| **Evaluations of all systems** (every system as one, with a row for each) | Yes: Systems, All systems | No |
| Cost, tasks and traces, the checklist | Yes | Each only where the admin's switch for it is on |

What a user may not see is not sent to their page at all.

---

## Part 1. Configuration

### 1.1 Turning a system on and off

| Control | What it does |
|---|---|
| **Use this browser** (a switch, at the top of a browser's Configuration) | On: the system runs and the agent can work in it. Off: its session ends, its tab says "Turned off", and nobody is connected to it. It stays off the next time the service starts |
| **Turn it on** (on the page of a system that is off) | The same switch, from the system's own page |

### 1.2 Managing a system

| Button | When it is there | What it does |
|---|---|---|
| **Start** | The system has no session | Starts a new browser and a new conversation |
| **Stop** | The system is running | Ends its session. The system stays turned on |
| **Restart** | The system is running | Ends its session and starts a new one |

The line under the buttons says what they do, and each says it when the pointer rests on it.

My Chrome has no Start button while it is not connected: it connects by itself, a moment after its
extension is loaded in Chrome. What cannot be done is answered with a sentence on the card, such as
"This browser is turned off. Turn it on first."

### 1.3 What to enable in a system

These are switches in a browser's Configuration, under **Files**, **Privacy** and **Advanced**. Each
is that system's alone: turning downloads off for the cloud browser leaves them on for the other two.

| Switch | What it does | As installed |
|---|---|---|
| Let the agent download files | Offers the tool that lists saved files | On |
| Let the agent upload files | Offers the upload tool. Each upload still asks you | On |
| Keep a log of the agent's steps | Writes that system's log file (section 1.6) | On |
| Let the agent run scripts in pages | Offers `browser_evaluate`. Each use still asks you | Off |
| Let the agent run scripts of several steps | Offers `browser_run`, the code tool | Off |

All five are the admin's to turn on and off. To take one out of the admin's hands, lock it in
`config.json`; it is then shown in words, with "Locked in config.json", and has no switch:

```json
{ "settings": { "locked": ["page_scripts", "code_tool"] } }
```

### 1.4 Every setting a system has of its own

All of them are in the browser's Configuration, by group, each with its line and its control.

| Setting | Choices (the first is as installed) | What it changes |
|---|---|---|
| Use this browser | On, Off | Section 1.1 |
| Model | The model in `config.json`, and any in `agent.offered_models` | The model that plans the agent's steps. A change holds from the next task |
| Ask before | Risky actions, Every action | When the agent must stop and wait for a person's approval before it acts |
| Wait for my answer | 3 minutes, 1, 5, 10 minutes | How long the agent waits for an answer. With none by then, the action is denied |
| Remember "Allow on this site" | Until the session ends, Never | After "Allow on this site", how long the agent may go on acting on that site without asking again |
| Blocked sites | A list, one site for each line | Sites the agent must never open. Added to those of `config.json` |
| Only allow these sites | A list | When it has entries, the agent may open only these |
| Let the agent download files | On, Off | Section 1.3 |
| Let the agent upload files | On, Off | Section 1.3 |
| Keep a log of the agent's steps | On, Off | Section 1.6 |
| Picture quality | Standard, Data saver, High | How sharp the live picture is. A sharper picture uses more data |
| Let the agent run scripts in pages | Off, On | Section 1.3 |
| Let the agent run scripts of several steps | Off, On | Section 1.3 |

**Which value holds.** A system's own value, where it has one. Otherwise the value you set for
every browser. Otherwise what `config.json` says. A user's own value, where the admin lets users
change the setting, is laid over that and may only be stricter.

**When a change takes hold.** At the agent's next step: the site lists, the tools on offer,
approvals, the log and the picture quality all follow at once. The model follows from the next task.

**What is one for the whole window, not a system's.** Colour mode; Show where the agent is acting;
Stay signed in to sites and Clear browsing data (both are about the cloud browser); About this
deployment. Changed in any browser's Configuration, these change everywhere, and each says "One
value for all three browsers." The colour mode holds on every page of the window.

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

At the bottom of a browser's Configuration, **Log file** shows where the file is, and **Show the log** shows its newest 20 lines,
newest first. Turning "Keep a log of the agent's steps" off for a system stops its file, and the
card then says "The log is turned off for this browser."

### 1.7 Where your choices are kept

In `.bap-browser/settings.json`, for you alone to read. What the admin set for every browser is at
the top; each system's own values are under `systems`; what the admin allows users is under `policy`;
and a user's own choices are under `user`, laid out the same way.

```json
{
  "colour_mode": "dark",
  "systems": {
    "cloud": { "allow_downloads": false, "ask_before": "every_action" },
    "builtin": { "system_enabled": false }
  },
  "policy": {
    "systems": { "cloud": false },
    "may_change": { "picture_quality": false },
    "sees": { "cost": false }
  },
  "user": {
    "preferred_browser": "builtin",
    "show_agent_pointer": false,
    "systems": { "builtin": { "ask_before": "every_action" } }
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
| `settings.locked` | `[]` | Settings nobody may change from the window, the admin included. Was there before; it holds for each system too |
| `auth.file` | `.bap-browser/accounts.json` | Where the two sign-in passwords are kept, as salted hashes |
| `auth.min_chars`, `auth.max_chars` | `8`, `200` | The shortest and the longest password that is taken |
| `auth.session_hours` | `12` | How long a sign-in lasts |
| `auth.max_failures`, `auth.lock_s` | `5`, `60` | Wrong passwords in a row before sign-in waits, and for how many seconds |

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

All but signing in need a token in an `Authorization: Bearer` header: the one a sign-in gave, or the
service's own, which speaks as the admin. `{name}` is `cloud`, `chrome` or `builtin`. A user is
answered 403 for what is the admin's, and 404 for a browser they may not use.

| Address | What it does |
|---|---|
| `GET /api/auth` | Whether there is a password to sign in with, and who the token speaks for |
| `POST /api/auth/sign-in` with `{"role": "admin", "password": "…"}` | Signs in: gives the token of the visit. `"user"` for a user |
| `POST /api/auth/password` with `{"role": "user", "password": "…"}` | Admin: sets a password |
| `POST /api/auth/sign-out` | Ends the visit |
| `GET /api/me` | Who you are, the browsers you may use, the one you prefer, what you may see |
| `PATCH /api/me` with `{"preferred": "{name}"}` | Choose the browser your window opens on |
| `GET /api/admin/policy` | Admin: what users may use, change and see |
| `PATCH /api/admin/policy` with `{"systems": {"cloud": false}}` | Admin: change it. Also `"may_change"` and `"sees"` |
| `GET /api/evals` | Admin: every system as one |
| `GET /api/systems` | Each system: where it stands, whether it is on, its model, where its log and records are |
| `POST /api/systems/{name}/start`, `/stop`, `/restart` | Manage it. A user may start one |
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

1. Start the window: `uv run bap-browser studio --open`. Sign in as the admin (the first time,
   create the password; section 0.2).
2. On the Cloud browser's page, give the agent a task in the chat, and let it finish.
3. Under the Cloud browser's tab, press **Configuration**: the page says whose it is, and every
   setting says what it does. Turn "Let the agent download files" off: the row says "Saved". Under
   the Built-in browser's tab it is still on.
4. Press **Show the log**, at the bottom: the steps of the task are there.
5. Under the Built-in browser's tab, turn **Use this browser** off: its tab says "Turned off". Turn
   it on again.
6. Under the Cloud browser's tab, press **Evaluations**: the task, with its model, time and tokens.
7. Press **Run the checklist**, and watch the lines turn to Passed.
8. Press **Show the trace** on the task, then **Good**.
9. Press **Systems**, then **All systems**: where each browser stands, and the tasks of all three as
   one. A button on a row takes you to that browser's Configuration or Evaluations.
10. The admin and the user, side by side. In **Systems**, **Users**, set the password users sign in
    with. In another window open `http://127.0.0.1:8765/` and sign in as a user: Browser and chat,
    **Settings**, Evaluations, and no Systems button.
11. As the admin, under the Cloud browser's tab, in Configuration, turn **Let users use this
    browser** off: within two seconds its tab is gone from the user's window.
12. As the user, under **Settings**, choose **Preferred browser**: Built-in browser. It opens at once.
    Give it a task.
13. As the admin, in **Systems**, **Users**, turn off "What users may change: Picture quality". On
    the user's Settings, Picture quality turns into words, "Set by your admin", with no reload.
14. As the admin, turn off "What users may see: What the tasks cost". The user's Evaluations show the
    task and its time, and no cost.

## What it does not do

| Not there | Note |
|---|---|
| An account for each person | There is one admin, and one password that every user signs in with. Users share their settings and their preferred browser |
| A judgement of an answer by another model | Outcome quality is how tasks ended, and your own Good and Bad |
| Cost without a price | Set the two prices in `config.json` (section 2.6) |
| Systems outside the three-browser window | The Systems page belongs to `bap-browser studio`. The commands that run one session (`agent`, `mcp`) have one log, `.bap-browser/events.jsonl`, and no evaluations |
| The checklist and the records, tried on My Chrome | They are the same code for the three systems. They were run on the Cloud and the Built-in browser; My Chrome was not connected when this was written |
