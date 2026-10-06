import json
from typing import Any

from bap_browser.config import Browser, Code, Config
from bap_browser.tools import TOOLS, tools_for


def by_name() -> dict[str, dict]:
    return {tool.name: tool.input_schema for tool in TOOLS}


def test_the_tools_of_this_stage() -> None:
    assert [tool.name for tool in TOOLS] == [
        "browser_navigate",
        "browser_go_back",
        "browser_go_forward",
        "browser_reload",
        "browser_snapshot",
        "browser_get_text",
        "browser_find",
        "browser_screenshot",
        "browser_zoom",
        "browser_click",
        "browser_hover",
        "browser_drag",
        "browser_type",
        "browser_fill_form",
        "browser_select_option",
        "browser_set_checked",
        "browser_press_key",
        "browser_scroll",
        "browser_scroll_to",
        "browser_wait",
        "browser_handle_dialog",
        "browser_tabs",
        "browser_console",
        "browser_network",
        "browser_evaluate",
        "browser_upload_file",
        "browser_downloads",
        "browser_request_human",
        "browser_run",
    ]


def test_four_tools_exist_only_where_their_feature_is_on() -> None:
    def offered(**browser: Any) -> set[str]:
        return {tool.name for tool in tools_for(Config(browser=Browser(**browser)))}

    everything = {tool.name for tool in TOOLS}
    assert len(everything) == 29
    # A script in the page, and a script of the agent's own, are off unless a deployment turns them on.
    assert everything - offered() == {"browser_evaluate", "browser_run"}
    assert "browser_run" in {tool.name for tool in tools_for(Config(code=Code(enabled=True)))}
    assert "browser_evaluate" in offered(javascript={"allow_evaluate": True})
    assert "browser_downloads" not in offered(downloads={"enabled": False})
    assert "browser_upload_file" not in offered(uploads={"enabled": False})
    # With no folder to upload from, no upload could ever be allowed.
    assert "browser_upload_file" not in offered(uploads={"allowed_dirs": []})


def test_schemas_reject_unknown_arguments_and_carry_no_titles() -> None:
    for schema in by_name().values():
        assert schema["type"] == "object"
        assert schema["additionalProperties"] is False
        assert "title" not in json.dumps(schema)


def test_the_click_schema() -> None:
    assert by_name()["browser_click"] == {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "ref": {"type": "string", "pattern": "^(f\\d+)?e\\d+$"},
            "x": {"type": "number", "minimum": 0},
            "y": {"type": "number", "minimum": 0},
            "button": {"type": "string", "enum": ["left", "right", "middle"], "default": "left"},
            "click_count": {"type": "integer", "minimum": 1, "maximum": 3, "default": 1},
            "modifiers": {
                "type": "array",
                "items": {"type": "string", "enum": ["Alt", "Control", "Meta", "Shift"]},
                "default": [],
            },
        },
    }


def test_optional_arguments_are_plain_types() -> None:
    properties = by_name()["browser_snapshot"]["properties"]
    assert properties["ref"] == {"type": "string", "pattern": "^(f\\d+)?e\\d+$"}
    assert properties["mode"] == {"type": "string", "enum": ["interactive", "all"]}
    assert properties["max_chars"] == {"type": "integer", "minimum": 1}


def test_the_definitions_stay_small() -> None:
    """The budget is 3,500 tokens for 28 tools (spec 11.6), counted as characters / 4: 125 a tool."""
    sent = json.dumps(
        [{"name": t.name, "description": t.description, "inputSchema": t.input_schema} for t in TOOLS],
        separators=(",", ":"),
    )
    assert len(sent) / 4 <= 3500 / 28 * len(TOOLS)
