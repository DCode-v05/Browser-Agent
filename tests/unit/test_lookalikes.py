import pytest

from bap_browser.safeguards.lookalikes import is_bare_public_ip, lookalike_of, mixed_script_of

PROTECTED = ["paypal.com", "amazon.com", "skylark-air.example", "apple.com"]
LURE_WORDS = ["login", "secure", "signin", "verify", "account"]
COMMON_WORDS = ["apply"]

# Six Cyrillic letters, each a known look-alike of a Latin letter, that together look like "paypal".
CYRILLIC_PAYPAL = "\u0440\u0430\u0443\u0440\u0430\u04cf"
CYRILLIC_PAYPAL_XN = "xn--80aa0cbo65f"
MIXED_LATIN_CYRILLIC_XN = "xn--pypal-4ve"  # a Latin "p", a Cyrillic look-alike of "a", then "ypal"
HONEST_CYRILLIC_XN = "xn--b1agh1afp"  # a Cyrillic word meaning "hello", looks like no protected name


def lookalike(host: str) -> str | None:
    return lookalike_of(host, PROTECTED, lure_words=LURE_WORDS, common_words=COMMON_WORDS)


NOT_A_LOOKALIKE = [
    "paypal.com",
    "www.paypal.com",
    "paypal.org",  # same label, plain Latin, another suffix: too many honest sites share this
    "paypal.reviews.example",
    "mypaypalstory.example",
    "apply.com",  # close to "apple", but a common word
    "unrelated.example",
]


@pytest.mark.parametrize("host", NOT_A_LOOKALIKE)
def test_not_a_lookalike(host: str) -> None:
    assert lookalike(host) is None


CLOSE_LOOKALIKES = [
    ("paypa1.com", "paypal.com"),  # a digit standing in for a letter
    ("paypaI.com", "paypal.com"),  # a capital I standing in for a lower-case l
    ("paypall.com", "paypal.com"),  # one letter added
    ("payapl.com", "paypal.com"),  # two neighbouring letters swapped
    ("amazom.com", "amazon.com"),  # one letter substituted
    ("skylark-alr.example", "skylark-air.example"),  # one letter substituted, in a longer label
]


@pytest.mark.parametrize(("host", "protected"), CLOSE_LOOKALIKES)
def test_close_lookalikes(host: str, protected: str) -> None:
    assert lookalike(host) == protected


LURED_LOOKALIKES = [
    "paypal.secure-login.example",
    "paypal-login.example",
    "login.paypal.example",
]


@pytest.mark.parametrize("host", LURED_LOOKALIKES)
def test_lured_lookalikes(host: str) -> None:
    assert lookalike(host) == "paypal.com"


def test_a_protected_label_under_5_letters_is_never_measured_for_closeness() -> None:
    # "lebay" is one letter from "ebay", but "ebay" is only 4 letters: under the floor.
    assert lookalike_of("lebay.example", ["ebay.com"], lure_words=[], common_words=[]) is None


def test_a_host_label_under_5_letters_is_never_measured_for_closeness() -> None:
    # "aple" is one letter from "apple", but "aple" itself is only 4 letters: under the floor.
    assert lookalike("aple.example") is None


def test_a_4_letter_protected_label_is_still_measured_for_the_lure_rule() -> None:
    # Too short for (a) (under 5 letters), but (b) only skips labels under 4.
    assert lookalike_of("ebay-login.example", ["ebay.com"], lure_words=LURE_WORDS, common_words=[]) == (
        "ebay.com"
    )


def test_a_protected_label_under_4_letters_is_skipped_for_the_lure_rule() -> None:
    assert lookalike_of("ok-login.example", ["ok.com"], lure_words=LURE_WORDS, common_words=[]) is None


def test_the_cyrillic_lookalike_is_allowed_to_be_found_here_too() -> None:
    # Spec: this one belongs to mixed_script_of, but lookalike_of may return it too.
    assert lookalike(f"{CYRILLIC_PAYPAL}.com") == "paypal.com"


def mixed_script(host: str) -> str | None:
    return mixed_script_of(host, PROTECTED)


def test_none_for_a_host_with_no_xn_label() -> None:
    assert mixed_script("paypal.com") is None
    assert mixed_script(CYRILLIC_PAYPAL + ".com") is None  # not punycode: no xn-- label


def test_an_international_name_that_decodes_to_a_protected_name() -> None:
    assert mixed_script(f"{CYRILLIC_PAYPAL_XN}.com") == "paypal.com"


def test_a_label_mixing_writing_systems_gives_the_host_itself() -> None:
    host = f"{MIXED_LATIN_CYRILLIC_XN}.example"
    assert mixed_script(host) == host


def test_an_honest_international_name_matches_nothing() -> None:
    assert mixed_script(f"{HONEST_CYRILLIC_XN}.example") is None


def test_a_protected_sites_own_subdomain_is_not_flagged() -> None:
    # The registrable name is paypal.com itself; whatever its subdomain looks like is not judged.
    assert mixed_script(f"{CYRILLIC_PAYPAL_XN}.paypal.com") is None


BARE_PUBLIC_IP = [
    ("8.8.8.8", True),
    ("127.0.0.1", False),
    ("10.0.0.5", False),
    ("192.168.1.1", False),
    ("[::1]", False),
    ("169.254.1.1", False),  # link-local
    ("example.com", False),  # not an IP at all
    ("", False),
]


@pytest.mark.parametrize(("host", "expected"), BARE_PUBLIC_IP)
def test_is_bare_public_ip(host: str, expected: bool) -> None:
    assert is_bare_public_ip(host) is expected
