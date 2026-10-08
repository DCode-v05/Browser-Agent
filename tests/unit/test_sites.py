import time

import pytest

from bap_browser.policy.sites import (
    is_ip_address,
    origin_of,
    registrable_name,
    same_site,
    site_of,
    to_latin,
    writing_systems,
)

REGISTRABLE_NAME: list[tuple[str, str]] = [
    ("a.shop.co.uk", "shop.co.uk"),
    ("victim.github.io", "victim.github.io"),
    ("www.example.com", "example.com"),
    ("example.com", "example.com"),
    ("localhost", "localhost"),
    # A host that is itself a public suffix is its own site.
    ("co.uk", "co.uk"),
    ("github.io", "github.io"),
    # The real list's *.ck wildcard rule and its !www.ck exception.
    ("www.ck", "www.ck"),
    ("foo.bar.ck", "foo.bar.ck"),
    ("foo.www.ck", "www.ck"),
    ("ck", "ck"),
    # Trailing dots and upper case are ignored.
    ("www.example.com.", "example.com"),
    ("WWW.EXAMPLE.COM", "example.com"),
    # An IDN host and its xn-- form are the same site; registrable_name keeps the spelling given.
    ("bücher.example", "bücher.example"),
    ("xn--bcher-kva.example", "xn--bcher-kva.example"),
    # Garbage still gets an answer, never an exception.
    ("", ""),
    ("not a hostname at all!!", "not a hostname at all!!"),
]

GARBAGE = ["...", "a..b", "-" * 80, "\x00\x01", "\U0001f642.example", "a" * 500, "[not an ip", "xn--"]


@pytest.mark.parametrize(("host", "name"), REGISTRABLE_NAME)
def test_registrable_name(host: str, name: str) -> None:
    assert registrable_name(host) == name


def test_shop_and_evil_on_a_shared_suffix_are_different_sites() -> None:
    assert not same_site("shop.co.kr", "evil.co.kr")


def test_victim_and_attacker_on_github_io_are_different_sites() -> None:
    assert not same_site("victim.github.io", "attacker.github.io")


def test_an_idn_host_and_its_xn_form_are_the_same_site() -> None:
    assert same_site("bücher.example", "xn--bcher-kva.example")


def test_an_ip_address_is_a_site_by_itself() -> None:
    assert same_site("8.8.8.8", "8.8.8.8")
    assert not same_site("8.8.8.8", "8.8.4.4")


IP_ADDRESSES: list[tuple[str, bool]] = [
    ("8.8.8.8", True),
    ("127.0.0.1", True),
    ("::1", True),
    ("[::1]", True),
    ("2001:4860:4860::8888", True),
    ("example.com", False),
    ("localhost", False),
    ("", False),
    ("999.999.999.999", False),
]


@pytest.mark.parametrize(("host", "expected"), IP_ADDRESSES)
def test_is_ip_address(host: str, expected: bool) -> None:
    assert is_ip_address(host) is expected


def test_registrable_name_of_an_ip_address_is_the_address_itself() -> None:
    assert registrable_name("8.8.8.8") == "8.8.8.8"
    assert registrable_name("[::1]") == "::1"


SITE_OF: list[tuple[str, str]] = [
    ("https://www.example.com/path", "example.com"),
    ("http://a.shop.co.uk:8080/x", "shop.co.uk"),
    # A port does not change the site.
    ("https://example.com:8443/", "example.com"),
    # Neither does a user and a password.
    ("https://user:pass@example.com/", "example.com"),
    # The site of a blob: address is the site of the address it was made from.
    ("blob:https://shop.example/9b1f3e2a-uuid", "shop.example"),
    # These have no host at all.
    ("about:blank", ""),
    ("data:text/html,hello", ""),
    ("file:///C:/pages/a.html", ""),
    ("not an address", ""),
    ("", ""),
]


@pytest.mark.parametrize(("address", "site"), SITE_OF)
def test_site_of(address: str, site: str) -> None:
    assert site_of(address) == site


ORIGIN_OF: list[tuple[str, str]] = [
    ("http://127.0.0.1:8765/path", "http://127.0.0.1:8765"),
    # The usual port is written out even when the address does not give it.
    ("https://example.com/path", "https://example.com:443"),
    ("http://example.com/path", "http://example.com:80"),
    # A user and a password are not part of the origin.
    ("https://user:pass@example.com:8443/x", "https://example.com:8443"),
    ("http://[::1]:9000/", "http://[::1]:9000"),
    ("about:blank", ""),
    ("not an address", ""),
]


@pytest.mark.parametrize(("address", "origin"), ORIGIN_OF)
def test_origin_of(address: str, origin: str) -> None:
    assert origin_of(address) == origin


TO_LATIN: list[tuple[str, str]] = [
    ("paypal", "paypal"),
    ("PayPal", "paypal"),
    # Five Cyrillic letters and the palochka letter, read as the Latin letters they look like.
    ("\u0440\u0430\u0443\u0440\u0430\u04cf", "paypal"),
    ("123-abc", "123-abc"),
]


@pytest.mark.parametrize(("label", "latin"), TO_LATIN)
def test_to_latin(label: str, latin: str) -> None:
    assert to_latin(label) == latin


def test_writing_systems_of_a_latin_word() -> None:
    assert writing_systems("paypal") == {"Latin"}


def test_writing_systems_of_a_cyrillic_word() -> None:
    assert writing_systems("\u0440\u0430\u0443\u0440\u0430\u04cf") == {"Cyrillic"}


def test_writing_systems_of_a_greek_word() -> None:
    assert writing_systems("\u03b1\u03b2\u03b3") == {"Greek"}


def test_writing_systems_mixing_latin_and_cyrillic() -> None:
    assert writing_systems("p\u0430ypal") == {"Latin", "Cyrillic"}


def test_digits_and_hyphens_belong_to_no_writing_system() -> None:
    assert writing_systems("123-456") == set()


@pytest.mark.parametrize("garbage", GARBAGE)
def test_garbage_never_raises(garbage: str) -> None:
    assert isinstance(registrable_name(garbage), str)
    assert isinstance(site_of(garbage), str)
    assert isinstance(origin_of(garbage), str)
    assert isinstance(is_ip_address(garbage), bool)
    assert isinstance(to_latin(garbage), str)
    assert isinstance(writing_systems(garbage), set)


def test_10_000_lookups_are_fast() -> None:
    hosts = ["a.shop.co.uk", "victim.github.io", "www.example.com", "localhost", "8.8.8.8"] * 2000
    start = time.perf_counter()
    for host in hosts:
        registrable_name(host)
    assert time.perf_counter() - start < 1.0
