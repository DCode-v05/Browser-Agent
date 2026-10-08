"""The bad patterns of this codebase (docs/bad-patterns.md): none is new, and each rule finds what
it is for. The first test is the one that holds the rules in CI."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]


def _the_checker() -> ModuleType:
    spec = importlib.util.spec_from_file_location("patterns", REPOSITORY / "scripts" / "patterns.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Its dataclasses look their own module up by name.
    sys.modules["patterns"] = module
    spec.loader.exec_module(module)
    return module


patterns = _the_checker()


def test_no_bad_pattern_is_new_and_the_baseline_allows_nothing_that_is_gone() -> None:
    new, stale = patterns.judge(patterns.scan(), patterns.read_baseline())
    assert new == [], "\n\n".join(new)
    assert stale == [], "Lower the baseline: uv run python scripts/patterns.py --lower\n" + "\n".join(stale)


def test_every_rule_is_explained_and_the_baseline_names_only_rules_and_files_that_exist() -> None:
    explained = (REPOSITORY / "docs" / "bad-patterns.md").read_text(encoding="utf-8")
    for rule in patterns.RULES:
        assert f"`{rule}`" in explained, f"docs/bad-patterns.md does not explain the rule {rule}"
    for rule, paths in patterns.read_baseline().items():
        assert rule in patterns.RULES, rule
        for path in paths:
            assert (REPOSITORY / path).is_file(), f"the baseline names {path}, which is gone"


def a_repository(folder: Path, files: dict[str, str]) -> Path:
    for name, text in files.items():
        path = folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return folder


def found_in(folder: Path, files: dict[str, str]) -> list[tuple[str, str, int]]:
    return [(one.rule, one.path, one.line) for one in patterns.scan(a_repository(folder, files))]


CLEAN = {
    "src/bap_browser/config.py": "LIMIT = 40\n",
    "src/bap_browser/driver/page.py": '"""Reads a page."""\n\nfrom bap_browser.config import LIMIT\n\n# Why the limit: a page can be endless.\nNAME = "page"\n',
    "tests/unit/test_page.py": "from bap_browser.driver.page import NAME\n\n\ndef test_name() -> None:\n    assert NAME\n",
    "viewer/src/options.ts": "export const TICK_MS = 1000;\n",
    "viewer/src/Page.tsx": "// What a person sees of a page.\nexport const title = 'Page';\n",
}


def test_code_that_follows_the_rules_is_found_clean(tmp_path: Path) -> None:
    assert found_in(tmp_path, CLEAN) == []


@pytest.mark.parametrize(
    ("rule", "path", "text"),
    [
        ("suppression", "src/bap_browser/driver/a.py", "x = f()  # type: ignore[arg-type]\n"),
        ("suppression", "src/bap_browser/driver/a.py", "x = y._z  # pyright: ignore[reportPrivateUsage]\n"),
        ("suppression", "src/bap_browser/driver/a.py", "f = lambda: 1  # noqa: E731\n"),
        (
            "suppression",
            "viewer/src/A.tsx",
            "useEffect(run, []); // eslint-disable-line react-hooks/exhaustive-deps\n",
        ),
        ("suppression", "viewer/src/A.tsx", "// @ts-expect-error the type is wrong\nconst a = b;\n"),
        (
            "workaround-comment",
            "src/bap_browser/driver/a.py",
            "x = 1 + 1  # a workaround until the driver is fixed\n",
        ),
        ("workaround-comment", "src/bap_browser/driver/a.py", "# TODO: handle frames\nx = None\n"),
        (
            "workaround-comment",
            "tests/unit/test_a.py",
            "# Temporary: remove when the service is faster.\nx = None\n",
        ),
        (
            "workaround-comment",
            "viewer/src/A.tsx",
            "// HACK: the socket closes twice\nexport const a = null;\n",
        ),
        ("private-import", "src/bap_browser/tools/a.py", "from bap_browser.driver.page import _hidden\n"),
        ("private-import", "tests/unit/test_a.py", "from bap_browser.driver.page import _hidden\n"),
        ("layer", "src/bap_browser/driver/a.py", "from bap_browser.tools.registry import Tool\n"),
        ("layer", "src/bap_browser/tools/a.py", "from bap_browser.service.session import ServiceSession\n"),
        ("layer", "src/bap_browser/service/a.py", "from bap_browser.agent.loop import run_agent\n"),
        ("tunable-outside-config", "src/bap_browser/driver/a.py", "RETRIES = 3\n"),
        ("tunable-outside-config", "viewer/src/A.tsx", "const POLL_MS = 1500;\n"),
        (
            "broad-except",
            "src/bap_browser/driver/a.py",
            "try:\n    x = None\nexcept Exception:\n    x = None\n",
        ),
        ("broad-except", "src/bap_browser/driver/a.py", "try:\n    x = None\nexcept:\n    x = None\n"),
        (
            "skipped-test",
            "tests/unit/test_a.py",
            "import pytest\n\n\n@pytest.mark.skip\ndef test_a() -> None: ...\n",
        ),
        ("skipped-test", "viewer/src/A.test.tsx", "it.only('a', () => undefined);\n"),
        (
            "fixed-wait-in-test",
            "tests/unit/test_a.py",
            "import asyncio\n\n\nasync def test_a() -> None:\n    await asyncio.sleep(2)\n",
        ),
        ("literal-in-viewer", "viewer/src/A.tsx", 'export const a = <div aria-label="Steps" />;\n'),
        ("literal-in-viewer", "viewer/src/A.tsx", "export const a = <span>Elapsed</span>;\n"),
        (
            "fixed-wait-in-test",
            "tests/viewer/test_a.py",
            "async def test_a(page):\n    await page.wait_for_timeout(500)\n",
        ),
        ("large-file", "src/bap_browser/driver/a.py", "x = None\n" * 701),
        ("large-file", "viewer/src/A.tsx", "export const a = null;\n" * 501),
    ],
)
def test_a_rule_finds_what_it_is_for(tmp_path: Path, rule: str, path: str, text: str) -> None:
    found = found_in(tmp_path, {**CLEAN, path: text})
    assert [(one[0], one[1]) for one in found] == [(rule, path)], found


@pytest.mark.parametrize(
    ("path", "text"),
    [
        # A string that holds the sign of a comment is not a comment.
        ("src/bap_browser/driver/a.py", 'COLOUR = "#todo"\n'),
        # Words that only look like an excuse.
        ("src/bap_browser/driver/a.py", "# The methodology and the hackathon are named here.\nx = None\n"),
        # A higher layer may use a lower one, and a part may use itself.
        (
            "src/bap_browser/agent/a.py",
            "from bap_browser.service.session import ServiceSession\nfrom bap_browser.agent.loop import run_agent\n",
        ),
        # The package's own top is anyone's to read.
        ("src/bap_browser/driver/a.py", "from bap_browser import __version__\n"),
        # The expected errors, by name.
        ("src/bap_browser/driver/a.py", "try:\n    x = None\nexcept (OSError, ValueError):\n    x = None\n"),
        # A tunable where tunables live; and a name in capitals that is not a number.
        ("src/bap_browser/config.py", "LIMIT = 40\nRETRIES = 3\n"),
        ("src/bap_browser/driver/a.py", 'NAME = "page"\nON = True\n'),
        # A test may wait in a loop for a thing to become true.
        (
            "tests/unit/test_a.py",
            "import asyncio\n\n\nasync def test_a() -> None:\n    await asyncio.sleep(0.1)\n",
        ),
        # A test's own suppression is the test's business.
        ("tests/unit/test_a.py", "x = f()  # type: ignore[arg-type]\n"),
        # A test that cannot run on some system says where, before it starts.
        (
            "tests/unit/test_a.py",
            'import pytest\n\n\n@pytest.mark.skipif(False, reason="no links here")\ndef test_a() -> None: ...\n',
        ),
        # A string from the list of strings, and a name that is not for a person to read.
        (
            "viewer/src/A.tsx",
            'export const a = <div aria-label={W.parts.steps} className="rows" role="log" />;\n',
        ),
        # The list of every string a person reads is long by its nature.
        ("viewer/src/wording.ts", "export const a = null;\n" * 501),
    ],
)
def test_a_rule_leaves_alone_what_it_is_not_for(tmp_path: Path, path: str, text: str) -> None:
    assert found_in(tmp_path, {**CLEAN, path: text}) == []


def test_what_is_in_the_baseline_passes_more_fails_and_less_asks_for_the_baseline_to_be_lowered(
    tmp_path: Path,
) -> None:
    files = {**CLEAN, "src/bap_browser/driver/a.py": "A = 1\nB = 2\n"}
    found = patterns.scan(a_repository(tmp_path, files))
    path = "src/bap_browser/driver/a.py"
    assert patterns.judge(found, {"tunable-outside-config": {path: 2}}) == ([], [])
    new, stale = patterns.judge(found, {"tunable-outside-config": {path: 1}})
    assert (
        len(new) == 1 and "has 2, the baseline allows 1" in new[0] and f"{path}:2" in new[0] and stale == []
    )
    new, stale = patterns.judge(found, {"tunable-outside-config": {path: 3}})
    assert new == [] and stale == [f"tunable-outside-config: {path} has 2, the baseline still allows 3"]
    # A file that was cleaned up altogether, and a rule nothing breaks any more.
    assert patterns.judge([], {"broad-except": {"src/bap_browser/gone.py": 1}})[1] == [
        "broad-except: src/bap_browser/gone.py has 0, the baseline still allows 1"
    ]


def test_except_exception_is_right_only_in_a_function_named_as_a_boundary(tmp_path: Path) -> None:
    broad = "def {name}() -> None:\n    try:\n        x = None\n    except Exception:\n        x = None\n"
    path = "src/bap_browser/tools/toolkit.py"
    assert found_in(tmp_path / "a", {**CLEAN, path: broad.format(name="_outcome")}) == []
    assert found_in(tmp_path / "b", {**CLEAN, path: broad.format(name="call")}) == [("broad-except", path, 4)]
    for (file, _), why in patterns.BOUNDARIES.items():
        assert (REPOSITORY / file).is_file() and why, file


def test_the_same_function_in_two_files_is_found_and_one_that_differs_is_not(tmp_path: Path) -> None:
    body = "    path.mkdir()\n    text = path.read_text()\n    return text.strip()\n"
    files = {
        **CLEAN,
        "src/bap_browser/driver/a.py": "def read(path):\n" + body,
        "src/bap_browser/tools/b.py": 'def _read(path):\n    """Reads it."""\n' + body,
        "src/bap_browser/service/c.py": "def read(path):\n" + body.replace("strip", "lower"),
    }
    assert found_in(tmp_path, files) == [("duplicate-code", "src/bap_browser/tools/b.py", 1)]


def test_a_long_file_is_over_the_size_or_not_whatever_its_length(tmp_path: Path) -> None:
    files = {**CLEAN, "src/bap_browser/driver/a.py": "x = None\n" * 900}
    found = patterns.scan(a_repository(tmp_path, files))
    assert patterns.counted(found) == {"large-file": {"src/bap_browser/driver/a.py": 1}}


def test_the_layers_name_every_part_of_the_engine() -> None:
    parts = {
        path.name if path.is_dir() else path.stem
        for path in (REPOSITORY / "src" / "bap_browser").iterdir()
        if (path.is_dir() and any(path.glob("*.py"))) or (path.suffix == ".py" and path.stem != "__init__")
    }
    assert parts - set(patterns.RANK) == set(), (
        "a part of the engine has no place in LAYERS of scripts/patterns.py"
    )
