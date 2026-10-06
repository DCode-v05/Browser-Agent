"""The check a script passes before it runs, and the worker's own part of running it (spec 7.2, 7.4).

The check is defence in depth, not a boundary: these tests hold the ways out that are known."""

from typing import Any

import pytest

from bap_browser.code.worker import Rejected, check, run


def refusal(code: str) -> str | None:
    try:
        check(code)
    except Rejected as no:
        return str(no)
    return None


@pytest.mark.parametrize(
    ("code", "why"),
    [
        ("import os", "cannot import"),
        ("from os import system", "cannot import"),
        ("x = ().__class__", "the attribute '__class__'"),
        ("().__class__.__base__.__subclasses__()", "the attribute"),
        ("open('/etc/passwd')", "the name 'open' is not available"),
        ("eval('1')", "the name 'eval' is not available"),
        ("exec('x = 1')", "the name 'exec' is not available"),
        ("getattr(browser, 'x')", "the name 'getattr' is not available"),
        ("type(browser)", "the name 'type' is not available"),
        ("globals()", "the name 'globals' is not available"),
        ("__import__('os')", "begins with an underscore"),
        ("_x = 1", "begins with an underscore"),
        ("def f(_a):\n    return 1", "begins with an underscore"),
        ("def _f():\n    return 1", "begins with an underscore"),
        ("f = lambda __x: 1", "begins with an underscore"),
        ("try:\n    x = 1\nexcept Exception as _e:\n    x = 2", "begins with an underscore"),
        ("print(x=1, __y=2)", "begins with an underscore"),
        # Reading an attribute by a name held in a string.
        ("print('{0.__class__}'.format(1))", "the attribute 'format'"),
        ("'{a.__class__}'.format_map({'a': 1})", "the attribute 'format_map'"),
        # The frames and the code behind a value lead to the worker's own modules.
        ("g = (i for i in [1])\ng.gi_frame", "the attribute 'gi_frame'"),
        ("c = browser.snapshot()\nc.cr_frame", "the attribute 'cr_frame'"),
        ("def f():\n    return 1\nf.f_globals", "the attribute 'f_globals'"),
        ("str.mro()", "the attribute 'mro'"),
        ("class A:\n    x = 1", "cannot define a class"),
        ("def f():\n    global x\n    x = 1", "cannot use 'global'"),
        ("with x:\n    y = 1", "cannot use 'with'"),
        ("match 1:\n    case int(real=r):\n        x = r", "cannot use 'match'"),
        ("@print\ndef f():\n    return 1", "cannot use a decorator"),
        ("x = (", "line 1"),
    ],
)
def test_a_script_that_reaches_outside_is_not_run(code: str, why: str) -> None:
    said = refusal(code)
    assert said is not None and why in said
    assert said.startswith("line ")


@pytest.mark.parametrize(
    "code",
    [
        "x = 1\nx + 1",
        "rows = [m for m in re.findall(r'INV-\\d+', 'INV-1 INV-22')]\nlen(rows)",
        "async def read():\n    return await browser.snapshot(mode='all')\nawait read()",
        "try:\n    await browser.click(find='Next')\nexcept StepError as failed:\n    print(failed)",
        "state['seen'] = sorted({1, 2})\nprint(f'{state[\"seen\"]!r:>10}')",
        "total = sum(int(n) for n in json.loads('[1, 2]'))\nmath.sqrt(total)",
        "def twice(n=2, *rest, **more):\n    return n * 2\ntwice(3)",
        "for i, (a, b) in enumerate(zip([1], [2])):\n    print(i, a, b)\nelse:\n    print('done')",
        "",
    ],
)
def test_an_ordinary_script_is_taken(code: str) -> None:
    assert refusal(code) is None


class Core:
    """Stands in for the core: it answers the steps a script asks for."""

    def __init__(self) -> None:
        self.asked: list[dict[str, Any]] = []

    def __call__(self, message: dict[str, Any]) -> dict[str, Any]:
        self.asked.append(message)
        if message["call"] == "click":
            return {"failed": True, "text": "Could not click: nothing there\n[tabs] t1* about:blank"}
        return {"failed": False, "text": 'Page\n- cell "INV-1"\n- cell "INV-22"'}


JOB: dict[str, Any] = {"max_output_chars": 100, "methods": {"snapshot": ["mode", "ref"], "click": ["ref"]}}


def ran(code: str, state: dict[str, Any] | None = None, core: Core | None = None) -> dict[str, Any]:
    return run({**JOB, "code": code}, {} if state is None else state, core or Core())


def test_a_script_does_steps_keeps_state_prints_and_has_a_value() -> None:
    core, state = Core(), {}
    done = ran(
        "snap = await browser.snapshot('all')\n"
        "rows = re.findall(r'INV-\\d+', snap)\n"
        "state['rows'] = len(rows)\n"
        "print(len(rows), 'invoices')\n"
        "rows",
        state,
        core,
    )
    assert done == {
        "value": '["INV-1", "INV-22"]',
        "value_cut": False,
        "printed": "2 invoices\n",
        "printed_cut": False,
    }
    # Values given without a name go to the tool's arguments in their order.
    assert core.asked == [{"call": "snapshot", "args": {"mode": "all"}}]
    # What a script keeps is there for the next one.
    assert ran("state['rows'] + 1", state)["value"] == "3"


def test_a_step_that_fails_stops_the_script_unless_it_is_caught() -> None:
    done = ran("x = 1\nawait browser.click('e1')\nprint('not reached')")
    assert done["step_failed"].startswith("Could not click: nothing there") and done["line"] == 2
    assert done["printed"] == ""
    caught = ran("try:\n    await browser.click(ref='e1')\nexcept StepError:\n    print('went on')\n'ok'")
    assert caught["printed"] == "went on\n" and caught["value"] == '"ok"' and "step_failed" not in caught


def test_an_error_in_the_script_is_reported_with_its_line() -> None:
    assert ran("x = [1]\nx[5]") == {
        "error": "IndexError: list index out of range",
        "line": 2,
        "printed": "",
        "printed_cut": False,
    }
    # The modules a script has are a few functions of them, not the modules themselves.
    assert "has no attribute 'codecs'" in ran("json.codecs.open('x')")["error"]
    assert "has no attribute 'sys'" in ran("re.sys")["error"]
    assert ran("def f(n):\n    return f(n + 1)\nf(0)")["error"].startswith("RecursionError")
    assert ran("import os") == {
        "rejected": "line 1: a script cannot import; re, json and math are there already"
    }


def test_what_a_script_prints_and_its_value_are_cut_to_the_limit() -> None:
    done = ran("print('a' * 500)\n'b' * 500")
    assert done["printed"] == "a" * 100 and done["printed_cut"] is True
    assert len(done["value"]) == 100 and done["value_cut"] is True


def test_a_step_takes_only_what_can_be_sent() -> None:
    assert "takes text, numbers, lists and dictionaries" in ran("await browser.click({1, 2})")["error"]
    assert "takes at most 1 values" in ran("await browser.click('e1', 'e2')")["error"]
    assert "given 'ref' twice" in ran("await browser.click('e1', ref='e2')")["error"]
    assert "has no attribute 'evaluate'" in ran("await browser.evaluate('1')")["error"]


def test_a_script_cannot_reach_what_it_was_not_given() -> None:
    # Names the worker itself uses are not names of the script.
    for name in ("sys", "os", "ast", "asyncio", "builtins", "run", "check", "open", "compile", "vars", "dir"):
        assert refusal(f"{name}") is not None, name
    # A value that is not None is returned as JSON; one that cannot be is shown as Python shows it.
    assert ran("browser")["value"].startswith('"<')
