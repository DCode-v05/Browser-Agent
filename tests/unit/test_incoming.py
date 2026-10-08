"""What comes in: planted instructions, rules 2 to 4 (spec 18.5)."""

import time

import pytest

from bap_browser.config_safeguards import Incoming
from bap_browser.safeguards import incoming

# -- without_invisible ------------------------------------------------------------------------


def test_plain_ascii_text_is_returned_untouched_by_the_fast_path() -> None:
    text = "Hello, world! Line one.\nLine two.\tTabbed."
    assert incoming.without_invisible(text) == (text, 0)


def test_200_000_ascii_characters_are_handled_in_well_under_50ms() -> None:
    text = ("The quick brown fox jumps over the lazy dog. " * 5000)[:200_000]
    start = time.perf_counter()
    cleaned, count = incoming.without_invisible(text)
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert cleaned == text
    assert count == 0
    assert elapsed_ms < 50, f"took {elapsed_ms:.1f}ms"


def test_tag_characters_are_removed_and_counted() -> None:
    # U+E0041 is a tag character (part of the tag block used to spell hidden ASCII).
    text = "abc\U000e0041def"
    assert incoming.without_invisible(text) == ("abcdef", 1)


def test_supplement_variation_selectors_are_removed_and_counted() -> None:
    text = "a\U000e0100b\U000e0101c"
    assert incoming.without_invisible(text) == ("abc", 2)


def test_a_direction_override_is_removed_but_not_counted() -> None:
    # U+202E RIGHT-TO-LEFT OVERRIDE.
    assert incoming.without_invisible("a\U0000202eb") == ("ab", 0)


def test_the_soft_hyphen_is_removed() -> None:
    # U+00AD SOFT HYPHEN.
    assert incoming.without_invisible("soft\U000000adhyphen") == ("softhyphen", 0)


def test_the_escape_character_is_removed() -> None:
    assert incoming.without_invisible("a\x1bb") == ("ab", 0)


@pytest.mark.parametrize(
    "filler",
    [
        "\U0000115f",  # HANGUL CHOSEONG FILLER
        "\U00001160",  # HANGUL JUNGSEONG FILLER
        "\U00003164",  # HANGUL FILLER
        "\U0000ffa0",  # HALFWIDTH HANGUL FILLER
        "\U00002800",  # BRAILLE PATTERN BLANK
        "\U0000034f",  # COMBINING GRAPHEME JOINER
        "\U000017b4",  # KHMER VOWEL INHERENT AQ
        "\U000017b5",  # KHMER VOWEL INHERENT AA
    ],
)
def test_fillers_that_draw_nothing_are_removed(filler: str) -> None:
    assert incoming.without_invisible(f"a{filler}b") == ("ab", 0)


@pytest.mark.parametrize(
    "kept",
    [
        "\U00000600",  # ARABIC NUMBER SIGN
        "\U00000601",  # ARABIC SIGN SANAH
        "\U00000605",  # ARABIC NUMBER MARK ABOVE
        "\U000006dd",  # ARABIC END OF AYAH
        "\U0000070f",  # SYRIAC ABBREVIATION MARK
        "\U000008e2",  # ARABIC DISPUTED END OF AYAH
        "\U000110bd",  # KAITHI NUMBER SIGN
    ],
)
def test_format_characters_that_are_drawn_are_always_kept(kept: str) -> None:
    text = f"a{kept}b"
    assert incoming.without_invisible(text) == (text, 0)


def test_zwj_between_two_latin_letters_is_removed() -> None:
    assert incoming.without_invisible("a\U0000200db") == ("ab", 0)


def test_zwnj_between_devanagari_letters_is_kept() -> None:
    # KA, ZWNJ, RA: the joiner is needed by the script and must survive.
    text = "\U00000915\U0000200c\U00000930"
    assert incoming.without_invisible(text) == (text, 0)


def test_zwnj_between_latin_letters_is_removed_even_though_it_is_kept_for_arabic() -> None:
    assert incoming.without_invisible("a\U0000200cb") == ("ab", 0)


def test_zwj_between_two_emoji_is_kept() -> None:
    # MAN, ZWJ, WOMAN: a family sequence that must stay joined.
    text = "\U0001f468\U0000200d\U0001f469"
    assert incoming.without_invisible(text) == (text, 0)


def test_zwj_right_after_a_variation_selector_on_an_emoji_is_kept() -> None:
    # HEAVY BLACK HEART, VS16, ZWJ, FIRE: VS16 right before the joiner counts as emoji.
    text = "\U00002764\U0000fe0f\U0000200d\U0001f525"
    assert incoming.without_invisible(text) == (text, 0)


def test_a_variation_selector_is_kept_straight_after_a_drawn_character() -> None:
    text = "a\U0000fe0fb"
    assert incoming.without_invisible(text) == (text, 0)


def test_a_variation_selector_at_the_start_of_the_text_is_removed() -> None:
    assert incoming.without_invisible("\U0000fe0fab") == ("ab", 0)


def test_a_second_stacked_variation_selector_is_removed() -> None:
    text = "a\U0000fe0f\U0000fe01b"
    assert incoming.without_invisible(text) == ("a\U0000fe0fb", 0)


def test_crlf_becomes_a_single_line_break() -> None:
    assert incoming.without_invisible("a\r\nb") == ("a\nb", 0)


def test_a_lone_cr_becomes_a_line_break() -> None:
    assert incoming.without_invisible("a\rb") == ("a\nb", 0)


def test_ordinary_non_ascii_text_with_nothing_invisible_is_unchanged() -> None:
    text = "caf\U000000e9 d\U000000e9j\U000000e0 vu"
    assert incoming.without_invisible(text) == (text, 0)


# -- carries_hidden_characters ------------------------------------------------------------------


def test_a_tag_character_alone_carries_hidden_characters_however_high_the_threshold() -> None:
    assert incoming.carries_hidden_characters("x\U000e0041y", hidden_message_chars=100)


def test_a_direction_override_alone_carries_hidden_characters() -> None:
    assert incoming.carries_hidden_characters("x\U0000202ey", hidden_message_chars=100)


def test_enough_invisible_characters_in_all_carries_hidden_characters() -> None:
    text = "x" + "\U000000ad" * 8 + "y"
    assert incoming.carries_hidden_characters(text, hidden_message_chars=8)
    assert not incoming.carries_hidden_characters(text, hidden_message_chars=9)


def test_ordinary_text_does_not_carry_hidden_characters() -> None:
    assert not incoming.carries_hidden_characters("nothing hidden here", hidden_message_chars=1)


# -- shown_address ----------------------------------------------------------------------------


def _settings(**overrides: object) -> Incoming:
    return Incoming(**overrides)  # type: ignore[arg-type]


def test_a_short_plain_fragment_is_shown() -> None:
    address = "https://example.com/page#section-2"
    assert incoming.shown_address(address, _settings()) == address


def test_a_long_fragment_is_hidden() -> None:
    address = f"https://example.com/page#{'a' * 100}"
    assert incoming.shown_address(address, _settings(fragment_max_chars=64)) == "https://example.com/page#…"


def test_a_fragment_with_a_space_is_hidden() -> None:
    address = "https://example.com/page#has space"
    assert incoming.shown_address(address, _settings()) == "https://example.com/page#…"


def test_a_fragment_with_a_percent_is_hidden() -> None:
    address = "https://example.com/page#a%20b"
    assert incoming.shown_address(address, _settings()) == "https://example.com/page#…"


def test_a_fragment_that_points_at_text_is_hidden() -> None:
    address = "https://example.com/page#:~:text=hello"
    assert incoming.shown_address(address, _settings()) == "https://example.com/page#…"


def test_no_fragment_shows_nothing() -> None:
    address = "https://example.com/page"
    assert incoming.shown_address(address, _settings()) == address


def test_a_long_query_value_is_cut_and_short_ones_are_not() -> None:
    address = "https://example.com/search?q=" + "x" * 20 + "&page=1"
    shown = incoming.shown_address(address, _settings(query_value_max_chars=10))
    assert shown == f"https://example.com/search?q={'x' * 10}…&page=1"


def test_shown_address_never_raises_on_garbage() -> None:
    assert incoming.shown_address("http://[::1", _settings()) == "http://[::1"


# -- address_words ------------------------------------------------------------------------------


def test_address_words_reads_the_fixed_separators_as_spaces() -> None:
    words = incoming.address_words("https://example.com/ignore-previous-instructions")
    assert words.split() == ["ignore", "previous", "instructions"]


def test_address_words_reads_percent_20_as_a_space_too() -> None:
    words = incoming.address_words("https://example.com/a%20b+c.d_e")
    assert words.split() == ["a", "b", "c", "d", "e"]


def test_address_words_does_not_touch_the_scheme_or_the_host() -> None:
    words = incoming.address_words("https://ignore.example.com/plain")
    assert "ignore" not in words


# -- new_token --------------------------------------------------------------------------------


def test_new_token_is_six_small_letters_and_digits() -> None:
    import re

    assert re.fullmatch(r"[a-z0-9]{6}", incoming.new_token(""))


def test_new_token_is_never_one_that_occurs_in_inside(monkeypatch: pytest.MonkeyPatch) -> None:
    scripted = iter(list("aaaaaa") + list("bbbbbb"))
    monkeypatch.setattr(incoming.secrets, "choice", lambda alphabet: next(scripted))
    assert incoming.new_token("before aaaaaa after") == "bbbbbb"


# -- marked -------------------------------------------------------------------------------------


def test_marked_wraps_the_page_text_with_the_token_and_the_note() -> None:
    wrapped, found = incoming.marked("Page: Your basket\nURL: https://shop.example/basket", "k7q2mz")
    assert wrapped == (
        "<<page k7q2mz>>\n"
        "Page: Your basket\nURL: https://shop.example/basket\n"
        "<<end page k7q2mz>>\n"
        f"{incoming.PAGE_NOTE}"
    )
    assert found is False


@pytest.mark.parametrize(
    ("raw", "defanged"),
    [
        ("[tabs] open", "[ tabs] open"),
        ("said [events] here", "said [ events] here"),
        ("[notice] be careful", "[ notice] be careful"),
        ("[withheld] gone", "[ withheld] gone"),
        ("[What is between the marks here]", "[ What is between the marks here]"),
        ("<<page abc>>", "< <page abc>>"),
        ("<<end page abc>>", "< <end page abc>>"),
        ("<<end abc>>", "< <end abc>>"),
        ("<<data abc>>", "< <data abc>>"),
        ("<<passage abc 1>>", "< <passage abc 1>>"),
        ("[TABS] loud", "[ TABS] loud"),
        ("<<PAGE abc>>", "< <PAGE abc>>"),
    ],
)
def test_marked_defangs_the_engines_own_words_anywhere_in_the_line(raw: str, defanged: str) -> None:
    wrapped, found = incoming.marked(raw, "qqqqqq")
    assert found is True
    assert defanged in wrapped


def test_unseen_colon_is_defanged_only_at_the_start_of_a_line() -> None:
    wrapped, found = incoming.marked("Unseen: 3 passages\nShe said Unseen: nothing", "qqqqqq")
    assert found is True
    lines = wrapped.splitlines()
    assert "Unseen : 3 passages" in lines
    assert "She said Unseen: nothing" in lines


def test_marked_reports_no_fake_engine_words_when_there_are_none() -> None:
    _, found = incoming.marked("Just ordinary text about tabs and events.", "qqqqqq")
    assert found is False


# -- quoted_name --------------------------------------------------------------------------------


def test_quoted_name_removes_its_own_double_quotes() -> None:
    assert incoming.quoted_name('Say "hi" there', 80) == '"Say hi there"'


def test_quoted_name_takes_out_line_breaks_rather_than_replacing_them_with_a_space() -> None:
    assert incoming.quoted_name("line one\nline two", 80) == '"line oneline two"'


def test_quoted_name_is_cut_with_an_ellipsis() -> None:
    assert incoming.quoted_name("a" * 200, 10) == '"{}…"'.format("a" * 9)


def test_quoted_name_short_enough_is_not_cut() -> None:
    assert incoming.quoted_name("Pay now", 80) == '"Pay now"'
