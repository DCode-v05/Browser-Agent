"""What goes out (spec 18.6): copied text, short secrets, amounts of money, sensitive fields, files."""

import base64
import random
import string
import time
from decimal import Decimal

import pytest

from bap_browser.config import ArrivingFiles, Outgoing
from bap_browser.safeguards.outgoing import (
    Amount,
    CopyMemory,
    agrees,
    amounts,
    is_consent_address,
    is_long_address,
    judged_file,
    largest,
    says_grant_access,
    sensitive_kind,
    short_secrets,
    unpacked,
)

LETTER = "Dear Ada. Your booking reference is confirmed and the gate closes at a quarter to seven sharp."
WORDS = Outgoing().sensitive_words
FILES = ArrivingFiles()


def memory(**settings: object) -> CopyMemory:
    chosen = Outgoing(**settings)  # type: ignore[arg-type]
    return CopyMemory(lambda: chosen)


def read_on_mail() -> CopyMemory:
    kept = memory()
    kept.remember("mail.test", LETTER)
    return kept


# Text carried from one site to another.


def test_text_read_on_one_site_and_sent_to_another_is_a_copy() -> None:
    copy = read_on_mail().copied("the gate closes at a quarter to seven", "evil.test")
    assert copy is not None
    assert (copy.site, copy.how, copy.sample) == (
        "mail.test",
        "text",
        "the gate closes at a quarter to seven",
    )
    assert copy.chars == len("the gate closes at a quarter to seven")


def test_the_same_text_sent_back_where_it_was_read_is_none() -> None:
    assert read_on_mail().copied("the gate closes at a quarter to seven", "mail.test") is None


def test_white_space_and_capitals_do_not_hide_a_copy() -> None:
    assert read_on_mail().copied("THE GATE   closes at\na quarter to seven", "evil.test") is not None


def test_a_copy_is_twenty_four_characters_or_more() -> None:
    kept = read_on_mail()
    assert kept.copied("the gate closes at a qu", "evil.test") is None  # 23
    assert kept.copied("the gate closes at a qua", "evil.test") is not None  # 24


def test_a_copy_inside_other_text_is_found_and_only_it_is_reported() -> None:
    copy = read_on_mail().copied(
        "note to self: the gate closes at a quarter to seven sharp. zzz", "evil.test"
    )
    assert copy is not None and copy.sample == "the gate closes at a quarter to seven sharp."


def test_what_the_person_said_themselves_is_no_copy() -> None:
    kept = read_on_mail()
    task = "Tell Bob that the gate closes at a quarter to seven sharp."
    assert kept.copied("the gate closes at a quarter to seven sharp.", "evil.test", known=[task]) is None


def test_text_that_both_sites_show_is_no_copy() -> None:
    kept = read_on_mail()
    kept.remember("evil.test", "We use cookies. " + LETTER)
    assert kept.copied("the gate closes at a quarter to seven", "evil.test") is None


def test_text_that_was_never_read_is_not_taken_for_a_copy() -> None:
    kept = memory()
    words = random.Random(7)
    kept.remember(
        "mail.test", " ".join("".join(words.choices(string.ascii_lowercase, k=7)) for _ in range(30000))
    )
    strangers = ["".join(words.choices(string.ascii_lowercase + " ", k=40)) for _ in range(2000)]
    assert [text for text in strangers if kept.copied(text, "evil.test")] == []


@pytest.mark.parametrize(
    "packing",
    [
        lambda secret: f"/collect?d={secret}",
        lambda secret: "/collect?d=" + "".join(f"%{ord(letter):02X}" for letter in secret),
        lambda secret: "/c?d=" + base64.b64encode(secret.encode()).decode(),
        lambda secret: "/c?d=" + base64.urlsafe_b64encode(secret.encode()).decode().rstrip("="),
        lambda secret: "/c?d=" + secret.encode().hex(),
    ],
    ids=["plain", "percent", "base64", "base64-url", "hex"],
)
@pytest.mark.parametrize("secret", ["A7K29QX1B4ZP", "481516", "ada.lovelace@example.com", "+91 98765 43210"])
def test_a_short_secret_is_found_however_it_is_packed(secret: str, packing) -> None:
    kept = memory()
    kept.remember("shop.test", f"Your order: {secret}. Thank you for shopping with us.")
    copy = kept.copied(packing(secret), "evil.test")
    # An email address of twenty-four characters is long enough to be found as copied text too.
    assert copy is not None and copy.site == "shop.test"
    assert copy.how == "secret" or len(secret) >= 24
    assert kept.copied(packing(secret), "shop.test") is None


def test_the_short_secrets_of_a_text() -> None:
    text = (
        "Order A7K29QX1B4ZP, code 481516, card 4111 1111 1111 1111, call +91-98765-43210, "
        "write to Ada.Lovelace@Example.com before 2026-10-07 or 07.10.2026. Room 12, version 3.11."
    )
    assert sorted(short_secrets(text)) == sorted(
        ["a7k29qx1b4zp", "481516", "4111111111111111", "919876543210", "ada.lovelace@example.com"]
    )


def test_a_sites_memory_begins_again_when_it_is_full_and_the_oldest_site_is_dropped() -> None:
    kept = memory(remember_chars_per_site=200, remember_sites=2)
    kept.remember("mail.test", LETTER)
    kept.remember("mail.test", "x" * 150)
    assert kept.copied("the gate closes at a quarter to seven", "evil.test") is None, "it began again"
    kept.remember("a.test", LETTER)
    kept.remember("b.test", "Nothing of note is written on this page at all.")
    kept.remember("c.test", "Nor on this one, which is the third site read.")
    assert kept.copied("the gate closes at a quarter to seven", "evil.test") is None, "a.test was dropped"


def test_the_memory_of_a_session_stays_under_two_megabytes_and_keeps_no_text() -> None:
    kept = memory()
    for number in range(20):
        kept.remember(f"site{number}.test", LETTER * 50)
    assert kept.size_bytes <= 2 * 1024 * 1024 + 16 * 2000 * 8
    assert not any(isinstance(value, str) for read in kept._sites.values() for value in vars(read).values())


def test_a_page_is_taken_in_quickly() -> None:
    kept = memory()
    page = (LETTER + " ") * 210  # about 20,000 characters
    began = time.perf_counter()
    kept.remember("mail.test", page)
    assert time.perf_counter() - began < 0.2


def test_unpacking_never_fails_on_what_is_not_packed() -> None:
    assert unpacked("plain words", 8) == ["plain words"]
    assert unpacked("%E0%A4%A", 12)[0] == "%E0%A4%A"
    assert "hello world!!" in unpacked(base64.b64encode(b"hello world!!").decode(), 12)


# Money.


@pytest.mark.parametrize(
    ("text", "value", "currency", "shown"),
    [
        ("Total $84.00.", "84.00", "USD", "$84.00"),
        ("Pay ₹ 1,23,456 now", "123456", "INR", "₹ 1,23,456"),
        ("1.234,50 € incl. VAT", "1234.50", "EUR", "1.234,50 €"),
        ("USD 1,000", "1000", "USD", "USD 1,000"),
        ("Rs. 499 only", "499", "INR", "Rs. 499"),
        ("$1,234", "1234", "USD", "$1,234"),
        ("€1.234", "1234", "EUR", "€1.234"),
        ("12,34,567.89 INR", "1234567.89", "INR", "12,34,567.89 INR"),
        ("1 234 567,89 €", "1234567.89", "EUR", "1 234 567,89 €"),
        ("£0.5", "0.5", "GBP", "£0.5"),
    ],
)
def test_an_amount_is_read_however_it_is_grouped(text: str, value: str, currency: str, shown: str) -> None:
    assert amounts(text) == [Amount(Decimal(value), currency, shown)]


@pytest.mark.parametrize("text", ["84.00", "Room 404", "5 stars", "Users: 1,234", "", "Rs", "$"])
def test_a_number_with_no_currency_is_no_amount(text: str) -> None:
    assert amounts(text) == []


def test_the_largest_amount_and_the_largest_in_one_currency() -> None:
    found = amounts("Shirt $20.00, shipping $4.50, total $24.50 (about €22,40)")
    assert largest(found) == Amount(Decimal("24.50"), "USD", "$24.50")
    assert largest(found, "eur") == Amount(Decimal("22.40"), "EUR", "€22,40")
    assert largest(found, "INR") is None and largest([]) is None


# Fields.


@pytest.mark.parametrize(
    ("texts", "attributes", "kind"),
    [
        (["Password"], [], "password"),
        (["Card number"], [], "card"),
        (["CVV"], [], "card"),
        (["Enter the OTP"], [], "code"),
        (["Your PIN"], [], "code"),
        (["UPI PIN"], [], "code"),
        (["Aadhaar number"], [], "identity"),
        ([""], ["cardNumber"], "card"),
        ([""], ["otp_code"], "code"),
        ([""], ["user-password2"], "password"),
        ([""], ["acct", "accountNumber"], "identity"),
    ],
)
def test_a_field_is_sensitive_by_the_words_of_its_name_or_its_attributes(
    texts: list[str], attributes: list[str], kind: str
) -> None:
    assert sensitive_kind(WORDS, texts=texts, attributes=attributes) == kind


@pytest.mark.parametrize(
    ("texts", "attributes"),
    [
        (["PIN code"], []),
        (["Postal PIN"], []),
        (["Area pin code"], ["pincode"]),
        (["Shipping address"], ["shipping"]),
        (["Your opinion"], ["opinion", "spinner"]),
        (["Passport expiry"], []),
        (["Email"], ["email"]),
        ([""], ["zip_pin"]),
    ],
)
def test_a_word_counts_only_whole_and_a_pin_code_is_a_postal_code(
    texts: list[str], attributes: list[str]
) -> None:
    assert sensitive_kind(WORDS, texts=texts, attributes=attributes) is None


# Files.


@pytest.mark.parametrize(
    ("name", "first", "own", "what"),
    [
        ("setup.exe", b"MZ\x90", False, "risky"),
        ("invoice.pdf.exe", b"", False, "risky"),
        ("report.pdf", b"MZ\x90\x00", False, "risky"),
        ("report.pdf", b"\x7fELF\x02", False, "risky"),
        ("run.txt", b"#!/bin/sh\n", False, "risky"),
        ("photo.scr. ", b"", False, "risky"),
        ("REPORT.PDF", b"%PDF-1.7", False, "keep"),
        ("report.pdf", b"%PDF-1.7", True, "ask"),
        ("archive.zip", b"PK\x03\x04", False, "ask"),
        ("page.html", b"<!doctype html>", False, "ask"),
        ("drawing.SVG", b"<svg", False, "ask"),
        ("notes", b"plain", False, "keep"),
    ],
)
def test_a_file_that_arrived_is_never_kept_asked_about_or_kept(
    name: str, first: bytes, own: bool, what: str
) -> None:
    assert judged_file(name, first, FILES, own_machine=own) == what


def test_a_deployment_can_ask_about_every_file_or_about_none() -> None:
    always, never = ArrivingFiles(ask="always"), ArrivingFiles(ask="never")
    assert judged_file("report.pdf", b"%PDF", always, own_machine=False) == "ask"
    assert judged_file("archive.zip", b"PK", never, own_machine=True) == "keep"
    assert judged_file("setup.exe", b"MZ", never, own_machine=True) == "risky", "what can run is never kept"


# Addresses and screens.


def test_a_long_address_is_told_by_its_path_its_query_and_its_fragment() -> None:
    assert not is_long_address("https://" + "a" * 300 + ".example/", 200)
    assert is_long_address("https://x.example/" + "p" * 201, 200)
    assert is_long_address("https://x.example/p?" + "q" * 100 + "#" + "f" * 100, 200)
    assert not is_long_address("https://x.example/p?q=1#top", 200)
    assert not is_long_address("http://[bad", 200)


CONSENT = Outgoing().consent_addresses


@pytest.mark.parametrize(
    ("address", "is_one"),
    [
        ("https://accounts.google.com/o/oauth2/v2/auth?client_id=abc", True),
        ("https://acme.okta.com/oauth2/v1/authorize?client_id=x", True),
        ("https://GitHub.com/login/oauth/authorize", True),
        ("https://login.microsoftonline.com/common/oauth2/v2.0/authorize", True),
        ("https://accounts.google.com/signin/v2/identifier", False),
        ("https://github.com/torvalds/linux", False),
        ("https://evil.example/accounts.google.com/o/oauth2/auth", False),
        ("not an address", False),
    ],
)
def test_the_known_screens_on_which_an_app_is_given_access(address: str, is_one: bool) -> None:
    assert is_consent_address(address, CONSENT) is is_one


def test_a_page_that_says_an_app_asks_for_access() -> None:
    assert says_grant_access(["Mailtidy wants to access your Google Account"])
    assert says_grant_access(["Sign in", "Authorize Mailtidy"])
    assert says_grant_access(["Calendar Pro is requesting access to your mail"])
    assert not says_grant_access(["Sign in", "Authorize"])
    assert not says_grant_access(["We value your privacy", "Accept all cookies"])


@pytest.mark.parametrize("name", ["Allow", "Authorize app", "Yes, continue", "I agree", "Accept", "GRANT"])
def test_a_control_that_agrees(name: str) -> None:
    assert agrees(name)


@pytest.mark.parametrize("name", ["Cancel", "Deny", "Allowance", "Disagree", "Discontinued", ""])
def test_a_control_that_does_not(name: str) -> None:
    assert not agrees(name)
