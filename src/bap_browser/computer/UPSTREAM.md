# What is taken from Hermes, and how

Computer use here is built on Hermes' (spec 22). This page says what was taken, what was changed,
and how to take a later Hermes in.

| | |
|---|---|
| Source | [NousResearch/hermes-agent](https://github.com/nousresearch/hermes-agent), MIT, Copyright (c) 2025 Nous Research |
| Commit | `3569e846` (12 October 2026) |
| Taken | `tools/computer_use/` to `hermes/computer_use/`, `tools/bot_desktop/` to `hermes/bot_desktop/`: 25 files |
| Record | `hermes/TAKEN.json`: for each file, the SHA-256 of Hermes' and of ours |
| Licence | `hermes/LICENSE`, and a two-line notice at the head of each Python file |

## The one rule

Nothing under `hermes/` or `tests/hermes/test_*.py` is edited by hand. `scripts/take_hermes.py`
writes every file there, and `tests/unit/test_hermes_base.py` fails when one no longer matches
`TAKEN.json`. A change we need is made in a seam, or in the script.

## What the script changes

Only three kinds of text, listed in full in `scripts/take_hermes.py`:

| Change | Why | Example |
|---|---|---|
| The names of Hermes' modules | The copied code asks Hermes for settings, a home folder, approval, the driver and a clean environment. Our seams answer | `hermes_cli.config` becomes `bap_browser.computer.seams.settings` |
| Nine names that begin with `_` | Our rule: no private name is imported across modules | `_sanitize_subprocess_env` becomes `sanitize_subprocess_env` |
| Two words a person reads | The command and the variable are ours | `hermes computer-use` becomes `bap-browser computer` |

## The seams

Each module of `seams/` stands where a part of Hermes stood.

| Seam | In Hermes | What ours does |
|---|---|---|
| `settings` | `hermes_cli.config` | Answers Hermes' two settings blocks from `Config.computer.base` |
| `home` | `hermes_constants`, `hermes_cli.profiles` | One folder for computer use, given by the engine. One profile |
| `process` | `tools.environments.local`, `hermes_cli._subprocess_compat`, `agent.async_utils` | An environment with every key and token taken out; no console window on Windows |
| `approval` | `tools.approval` | Asks whoever the engine named. With nobody to ask, refuses. Never told to ask nobody |
| `driver_package` | `pm` | Finds the installed driver. Installs nothing |
| `provider` | `plugins.computer_use`, `agent.provider_base` | One driver: `cua-driver`, or a stand-in a test names |
| `vision` | `agent.auxiliary_client`, `tools.vision_tools` | A screenshot goes to the model as it is |
| `sandbox` | `tools.terminal_tool`, `tools.environments` | No terminal sandbox: the desktop is on the engine's own machine |
| `manifest_file` | `hermes_yaml` | Reads the driver's permission file, which we write as JSON |

## Hermes' own tests

`src/bap_browser/computer/hermes_tests.txt` names the test files taken: 42, and one file they
read. On macOS 273 of their tests pass against our seams and 31 are for Linux or Windows and run
there. 94 are left out, each named in `tests/hermes/not_here.json` with its reason: they test
what was not taken (Hermes' package manager, its settings file, its second model for pictures,
its terminal sandbox). Five test files were not taken at all for the same reason.

## Taking a later Hermes

1. Check out hermes-agent at the commit to take.
2. `uv run python scripts/take_hermes.py /path/to/hermes-agent`
3. `uv run pytest tests/hermes tests/unit/test_hermes_base.py`. A new import of Hermes shows as an
   import error: add it to `STAND_INS` in the script and answer it in a seam.
4. Change the commit in this page, and run the gate.

## Not yet changed

Some results the model reads still say "Hermes" (for example "Hermes did not replay it"). They are
Hermes' sentences and are correct; they are reworded when the tool is put behind the session.
