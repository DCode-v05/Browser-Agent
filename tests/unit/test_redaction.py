import pytest

from bap_browser.errors import ConfigError
from bap_browser.policy.redaction import Redactor


def test_no_patterns_changes_nothing() -> None:
    assert Redactor([])("card 4111 1111 1111 1111") == "card 4111 1111 1111 1111"


def test_every_match_of_every_pattern_is_replaced() -> None:
    redact = Redactor([r"\b\d{4} \d{4} \d{4} \d{4}\b", r"sk-[A-Za-z0-9]+"])
    text = "card 4111 1111 1111 1111 and key sk-abc123, again sk-zzz"
    assert redact(text) == "card [REDACTED] and key [REDACTED], again [REDACTED]"


def test_a_match_across_lines_is_replaced() -> None:
    assert Redactor([r"BEGIN.*?END"])("x BEGIN\nsecret\nEND y") == "x BEGIN\nsecret\nEND y"
    assert Redactor([r"(?s)BEGIN.*?END"])("x BEGIN\nsecret\nEND y") == "x [REDACTED] y"


def test_a_bad_pattern_stops_start_up_and_is_named() -> None:
    with pytest.raises(ConfigError, match=r"safety.redact_patterns: '\(\[' is not a valid pattern"):
        Redactor(["(["])
