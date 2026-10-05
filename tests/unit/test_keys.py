import pytest

from bap_browser import keys
from bap_browser.errors import BadInput


@pytest.mark.parametrize(
    ("written", "normal"),
    [
        ("Enter", "Enter"),
        ("return", "Enter"),
        ("esc", "Escape"),
        ("ctrl+a", "Control+a"),
        ("Control+A", "Control+a"),
        ("cmd+shift+t", "Shift+Meta+t"),
        ("shift+ctrl+alt+Delete", "Control+Alt+Shift+Delete"),
        ("ctrl+ctrl+c", "Control+c"),
        (" Shift + Tab ", "Shift+Tab"),
        ("left", "ArrowLeft"),
        ("ArrowDown", "ArrowDown"),
        ("pagedown", "PageDown"),
        ("f5", "F5"),
        ("space", "Space"),
        ("a", "a"),
        ("A", "A"),
        ("+", "+"),
        ("ctrl++", "Control++"),
        ("ctrl+plus", "Control++"),
        ("mod+s", "ControlOrMeta+s"),
        ("shift", "Shift"),
    ],
)
def test_key_names_in_any_dialect_become_one_form(written: str, normal: str) -> None:
    assert keys.normalise(written) == normal


@pytest.mark.parametrize("written", ["", "  ", "ctrl+", "+a", "hunter2", "ctrl+hunter2", "banana+a", "f99"])
def test_what_is_not_a_key_is_refused_without_being_repeated(written: str) -> None:
    with pytest.raises(BadInput) as refused:
        keys.normalise(written)
    # What was given may be text an agent meant to type. The message goes to the log.
    assert "hunter2" not in str(refused.value) and "banana" not in str(refused.value)


@pytest.mark.parametrize(
    ("written", "typed"),
    [
        ("a", True),
        ("7", True),
        ("Shift+a", True),
        ("+", True),
        ("hunter2", True),
        ("Enter", False),
        ("Control+a", False),
        ("ctrl++", False),
        ("ArrowDown", False),
        ("F5", False),
    ],
)
def test_a_key_that_types_a_character_is_typed_text(written: str, typed: bool) -> None:
    assert keys.is_typed_text(written) is typed
