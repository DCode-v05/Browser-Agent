"""Takes Hermes' computer use into this repository (spec 22.2, 22.3).

Hermes (NousResearch/hermes-agent, MIT) is the base of computer use here. Its two modules are copied
as they are; the only changes are the ones this script makes, so a later Hermes can be taken in by
running it again:

    uv run python scripts/take_hermes.py /path/to/a/checkout/of/hermes-agent

It rewrites the names of the Hermes modules the copied code imports to our seams
(`src/bap_browser/computer/seams/`), the names of the commands a message tells a person to run, and
nothing else. It writes `TAKEN.json` beside the copy: the commit, and for each file the SHA-256 of
what Hermes had and of what is here. A test fails when a copied file no longer matches, so the copy
is never edited by hand.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = "NousResearch/hermes-agent"
INTO = ROOT / "src/bap_browser/computer/hermes"
TESTS_INTO = ROOT / "tests/hermes"
OURS = "bap_browser.computer.hermes"
SEAMS = "bap_browser.computer.seams"

# Hermes' folder, and the folder it becomes under `INTO`.
MODULES = {
    "tools/computer_use": "computer_use",
    "tools/bot_desktop": "bot_desktop",
    # The manual Hermes gives a model for the tool. It is outside the two modules, and the tool is
    # used poorly without it.
    "skills/autonomous-ai-agents/computer-use": "skill",
}
# A module of Hermes, and the module of ours that stands in its place. Longest names first.
STAND_INS = (
    ("tools.computer_use", f"{OURS}.computer_use"),
    ("tools.bot_desktop", f"{OURS}.bot_desktop"),
    ("tools.environments.local", f"{SEAMS}.process"),
    ("tools.approval_context", f"{SEAMS}.approval"),
    ("tools.approval", f"{SEAMS}.approval"),
    ("tools.vision_tools", f"{SEAMS}.vision"),
    ("tools.terminal_tool", f"{SEAMS}.sandbox"),
    ("tools.browser_tool_session", f"{SEAMS}.sandbox"),
    ("tools.environments", f"{SEAMS}.sandbox"),
    ("hermes_cli._subprocess_compat", f"{SEAMS}.process"),
    ("hermes_cli.browser_runtime", f"{SEAMS}.sandbox"),
    ("hermes_cli.sandbox_image_switch", f"{SEAMS}.sandbox"),
    ("hermes_cli.profiles", f"{SEAMS}.home"),
    ("hermes_cli.config", f"{SEAMS}.settings"),
    ("hermes_platform.host.runtime", f"{SEAMS}.home"),
    ("hermes_constants", f"{SEAMS}.home"),
    ("plugins.computer_use", f"{SEAMS}.provider"),
    ("agent.provider_base", f"{SEAMS}.provider"),
    ("agent.auxiliary_client", f"{SEAMS}.vision"),
    ("agent.async_utils", f"{SEAMS}.process"),
    ("model_tools", f"{SEAMS}.vision"),
)
# Whole statements that are written again.
STATEMENTS = (
    ("import hermes_yaml as yaml", f"from {SEAMS} import manifest_file as yaml"),
    ("from pm import", f"from {SEAMS}.driver_package import"),
    ("from tools import terminal_tool as tt", f"from {SEAMS} import sandbox as tt"),
)
# Names that begin with an underscore in Hermes and are public in our seams.
PUBLIC = (
    "_sanitize_subprocess_env",
    "_run_approval_gate",
    "_secure_dir",
    "_get_env_config",
    "_read_main_model",
    "_read_main_provider",
    "_native_tool_result_images",
    "_run_async",
    "_needs_chromium_sandbox_bypass",
    # Used by our installer, which does on macOS what Hermes' installer does (spec 22.2.2).
    "_resolve_cua_driver_app_path",
    "_validate_cua_driver_app_signature",
    # Started by the helper, which holds an engine elsewhere to the allowed apps (spec 22.7).
    "_EmbeddedCuaDaemon",
)
# What a message tells a person to run, and the variable that names another driver.
WORDS = (
    ("hermes computer-use", "bap-browser computer"),
    ("HERMES_CUA_DRIVER_CMD", "BAP_BROWSER_CUA_DRIVER_CMD"),
)


def rewritten(text: str) -> str:
    for theirs, ours in STATEMENTS:
        text = text.replace(theirs, ours)
    for theirs, ours in STAND_INS:
        text = re.sub(rf"(?<![\w.]){re.escape(theirs)}(?![\w])", ours, text)
    for name in PUBLIC:
        text = re.sub(rf"(?<![\w]){name}(?![\w])", name.lstrip("_"), text)
    for theirs, ours in WORDS:
        text = text.replace(theirs, ours)
    return text


def notice(commit: str, path: str) -> str:
    return (
        f"# Taken from {SOURCE} at {commit}: {path}\n"
        "# MIT License, Copyright (c) 2025 Nous Research. Changed only by scripts/take_hermes.py.\n"
    )


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def take(checkout: Path, tests: list[str]) -> dict[str, object]:
    commit = subprocess.run(
        ["git", "-C", str(checkout), "rev-parse", "--short=8", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    files: dict[str, dict[str, str]] = {}
    for theirs, ours in MODULES.items():
        for path in sorted((checkout / theirs).iterdir()):
            if not path.is_file():
                continue
            original = path.read_bytes()
            relative = f"{theirs}/{path.name}"
            if path.suffix == ".py":
                data = (notice(commit, relative) + rewritten(original.decode("utf-8"))).encode("utf-8")
            else:
                data = original
            target = INTO / ours / path.name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            files[f"{ours}/{path.name}"] = {
                "from": relative,
                "theirs": digest(original),
                "sha256": digest(data),
            }
    (INTO / "LICENSE").write_bytes((checkout / "LICENSE").read_bytes())
    taken_tests: dict[str, str] = {}
    TESTS_INTO.mkdir(parents=True, exist_ok=True)
    for relative in tests:
        original = (checkout / relative).read_bytes()
        if relative.endswith(".py"):
            data = (notice(commit, relative) + rewritten(original.decode("utf-8"))).encode("utf-8")
            (TESTS_INTO / Path(relative).name).write_bytes(data)
        else:
            # A file a test reads, such as what a driver answered. It stays where the test looks for it.
            (ROOT / relative).parent.mkdir(parents=True, exist_ok=True)
            (ROOT / relative).write_bytes(original)
        taken_tests[Path(relative).name] = relative
    record = {"source": SOURCE, "commit": commit, "files": files, "tests": taken_tests}
    (INTO / "TAKEN.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return record


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("checkout", type=Path, help="a checkout of hermes-agent at the commit to take")
    asked = parser.parse_args(arguments)
    kept = ROOT / "src/bap_browser/computer/hermes_tests.txt"
    tests = [line.strip() for line in kept.read_text(encoding="utf-8").splitlines() if line.strip()]
    record = take(asked.checkout.resolve(), tests)
    files = record["files"]
    assert isinstance(files, dict)
    print(f"Took {len(files)} files and {len(tests)} tests of {SOURCE} at {record['commit']}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
