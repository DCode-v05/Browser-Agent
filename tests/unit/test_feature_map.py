"""The feature map (docs/feature-map.json) is kept in step with the code: every file it names is
there, and every tool and every address of the service is in it. A map that is out of date sends
its reader to the wrong place, which is worse than no map."""

import json
import re
from pathlib import Path
from typing import Any

from bap_browser.config import Config
from bap_browser.evals.suite import SETS
from bap_browser.tools.browser_tools import TOOLS

REPOSITORY = Path(__file__).resolve().parents[2]
MAP = REPOSITORY / "docs" / "feature-map.json"
AN_ADDRESS = re.compile(r'(?:Route|WebSocketRoute|Mount)\("([^"]+)"')


def features() -> list[dict[str, Any]]:
    return json.loads(MAP.read_text(encoding="utf-8"))["features"]


def test_every_feature_says_where_it_is_and_how_to_reach_it() -> None:
    ids = [feature["id"] for feature in features()]
    assert len(set(ids)) == len(ids), "two features have one id"
    for feature in features():
        for field in ("title", "spec", "source", "tests", "reach"):
            assert feature[field], f"{feature['id']} has no {field}"


def test_every_file_the_map_names_is_there() -> None:
    for feature in features():
        for path in feature["source"] + feature["tests"]:
            assert (REPOSITORY / path).is_file(), f"{feature['id']} names {path}, which is not there"


def test_every_tool_is_in_the_map_and_the_map_names_no_tool_that_is_gone() -> None:
    mapped = [tool for feature in features() for tool in feature["tools"]]
    assert sorted(mapped) == sorted(tool.name for tool in TOOLS)


def test_every_address_of_the_service_is_in_the_map() -> None:
    app = (REPOSITORY / "src" / "bap_browser" / "service" / "app.py").read_text(encoding="utf-8")
    served = {*AN_ADDRESS.findall(app), Config().mcp.http_path}
    mapped = {address for feature in features() for address in feature["addresses"]}
    assert served - mapped == set(), "addresses of the service that no feature of the map names"
    assert mapped - served == set(), "the map names addresses the service does not have"


def test_every_task_set_is_named_by_the_feature_that_is_about_them() -> None:
    sets = next(feature for feature in features() if feature["id"] == "task-sets")
    for name in SETS:
        assert f"src/bap_browser/evals/sets/{name}.json" in sets["source"], name


def test_every_spec_section_the_map_names_is_in_the_spec() -> None:
    spec = (REPOSITORY / "docs" / "bap-browser-spec.md").read_text(encoding="utf-8")
    headings = set(re.findall(r"^#{2,3} (\d+(?:\.\d+)?)\.? ", spec, re.MULTILINE))
    for feature in features():
        for section in feature["spec"].split(", "):
            assert section in headings, (
                f"{feature['id']} names section {section}, which the spec does not have"
            )
