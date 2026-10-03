import json

from bap_browser.tools import TOOLS


def by_name() -> dict[str, dict]:
    return {tool.name: tool.input_schema for tool in TOOLS}


def test_the_four_tools_of_this_stage() -> None:
    assert [tool.name for tool in TOOLS] == [
        "browser_navigate",
        "browser_snapshot",
        "browser_click",
        "browser_type",
    ]


def test_schemas_reject_unknown_arguments_and_carry_no_titles() -> None:
    for schema in by_name().values():
        assert schema["type"] == "object"
        assert schema["additionalProperties"] is False
        assert "title" not in json.dumps(schema)


def test_the_click_schema() -> None:
    assert by_name()["browser_click"] == {
        "type": "object",
        "additionalProperties": False,
        "required": ["ref"],
        "properties": {
            "ref": {"type": "string", "pattern": "^(f\\d+)?e\\d+$"},
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
    """The budget is 3,500 tokens for 28 tools (spec 11.6), counted as characters / 4: 500 per four tools."""
    sent = json.dumps(
        [{"name": t.name, "description": t.description, "inputSchema": t.input_schema} for t in TOOLS],
        separators=(",", ":"),
    )
    assert len(sent) / 4 <= 500
