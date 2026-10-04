from typing import Any

import pytest

from bap_browser.config import Safety
from bap_browser.policy.address import parse_ip
from bap_browser.policy.url_policy import UrlPolicy, host_matches

PUBLIC = "93.184.216.34"


def policy(resolves_to: list[str] | None = None, **safety: Any) -> UrlPolicy:
    async def resolve(host: str) -> list[str]:
        return [PUBLIC] if resolves_to is None else resolves_to

    return UrlPolicy(Safety(**safety), resolve=resolve)


ALLOWED: list[tuple[str, dict[str, Any]]] = [
    ("https://example.com/", {}),
    ("http://example.com:8080/path?q=1", {}),
    ("about:blank", {}),
    ("data:text/html,hello", {}),
    ("http://127.0.0.1:8000/", {}),
    ("http://localhost:3000/", {}),
    ("https://sub.example.com/x", {"allowed_domains": ["*.example.com"]}),
    ("https://sub.example.com/", {"allowed_domains": ["example.com"]}),
    ("https://example.com/", {"allowed_domains": ["example.com"]}),
    ("file:///C:/pages/a.html", {"allow_file_urls": True}),
    ("https://example.com/", {"block_private_networks": True}),
    ("https://8.8.8.8/", {"block_private_networks": True}),
]

BLOCKED: list[tuple[str, dict[str, Any], str]] = [
    ("file:///etc/passwd", {}, "local files are off (safety.allow_file_urls)"),
    ("ftp://example.com/", {}, "scheme 'ftp' is not allowed (safety.allowed_schemes)"),
    ("javascript:alert(1)", {}, "scheme 'javascript' is not allowed"),
    ("https:///nothing", {}, "the address has no host"),
    ("http://[::1", {}, "not a valid address"),
    ("http://169.254.169.254/latest/meta-data/", {}, "cloud metadata address"),
    ("http://2852039166/", {}, "cloud metadata address"),
    ("http://0xa9.0xfe.0xa9.0xfe/", {}, "cloud metadata address"),
    ("http://[::ffff:169.254.169.254]/", {}, "cloud metadata address"),
    ("http://metadata.google.internal/computeMetadata/", {}, "cloud metadata address"),
    ("https://ads.example.com/", {"blocked_domains": ["example.com"]}, "blocked site"),
    ("https://EXAMPLE.com./", {"blocked_domains": ["example.com"]}, "blocked site"),
    (
        "https://example.com/",
        {"blocked_domains": ["example.com"], "allowed_domains": ["example.com"]},
        "blocked site",
    ),
    ("https://example.org/", {"allowed_domains": ["example.com"]}, "not in the allowed sites"),
    ("https://example.com.evil.org/", {"allowed_domains": ["example.com"]}, "not in the allowed sites"),
    ("https://notexample.com/", {"allowed_domains": ["example.com"]}, "not in the allowed sites"),
    ("https://example.com/", {"allowed_domains": ["*.example.com"]}, "not in the allowed sites"),
    ("https://example.com@10.0.0.5/", {"block_private_networks": True}, "private address"),
    ("http://127.0.0.1:8000/", {"block_private_networks": True}, "private address"),
    ("http://0x7f.1/", {"block_private_networks": True}, "private address"),
    ("http://017700000001/", {"block_private_networks": True}, "private address"),
    ("http://[::1]/", {"block_private_networks": True}, "private address"),
    ("http://192.168.1.10/", {"block_private_networks": True}, "private address"),
    ("http://100.64.0.1/", {"block_private_networks": True}, "private address"),
    ("http://localhost/", {"block_private_networks": True}, "private name"),
    ("http://printer/", {"block_private_networks": True}, "private name"),
    ("http://db.internal/", {"block_private_networks": True}, "private name"),
    ("http://app.localhost:3000/", {"block_private_networks": True}, "private name"),
    # A browser reads \ as /, so the host here is 127.0.0.1 and example.com is part of the path.
    ("http://127.0.0.1:8000\\@example.com/../admin", {"block_private_networks": True}, "private address"),
    (
        "http://127.0.0.1:8000\\@example.com/",
        {"allowed_domains": ["example.com"]},
        "not in the allowed sites",
    ),
    ("http://169.254.169.254\\@example.com/../latest/meta-data/", {}, "cloud metadata address"),
    # A browser decodes %31 in a host.
    ("http://%31%36%39.254.169.254/latest/meta-data/", {}, "cloud metadata address"),
    ("http://%31%32%37.0.0.1/", {"block_private_networks": True}, "private address"),
    # Every spelling of an address is the same site to a list.
    ("http://2130706433:8000/", {"blocked_domains": ["127.0.0.1"]}, "blocked site"),
    ("http://0x7f.1/", {"blocked_domains": ["127.0.0.1"]}, "blocked site"),
    ("http://１２７.0.0.1/", {"blocked_domains": ["127.0.0.1"]}, "blocked site"),
    ("http://127。0。0。1/", {"blocked_domains": ["127.0.0.1"]}, "blocked site"),
    ("http://%31%32%37.0.0.1/", {"blocked_domains": ["127.0.0.1"]}, "blocked site"),
    ("http://[::ffff:127.0.0.1]/", {"blocked_domains": ["127.0.0.1"]}, "blocked site"),
    ("http://[0:0:0:0:0:0:0:1]/", {"blocked_domains": ["::1"]}, "blocked site"),
    ("http://ｌｏｃａｌｈｏｓｔ/", {"blocked_domains": ["localhost"]}, "blocked site"),
    ("http://%6cocalhost/", {"blocked_domains": ["localhost"]}, "blocked site"),
    ("https://xn--bcher-kva.example/", {"blocked_domains": ["bücher.example"]}, "blocked site"),
    ("https://bücher.example/", {"blocked_domains": ["xn--bcher-kva.example"]}, "blocked site"),
    ("https://BÜCHER.example/", {"blocked_domains": ["*.Bücher.example", "bücher.example"]}, "blocked site"),
    ("http://2130706433/", {"allowed_domains": ["example.com"]}, "not in the allowed sites"),
    # An IPv4 address carried inside an IPv6 one is judged as that IPv4 address.
    ("http://[64:ff9b::a9fe:a9fe]/latest/meta-data/", {}, "cloud metadata address"),
    ("http://[::169.254.169.254]/", {}, "cloud metadata address"),
    ("http://[64:ff9b:1:a9fe:a9:fe00::]/", {}, "cloud metadata address"),
    ("http://[2002:a9fe:a9fe::]/", {}, "cloud metadata address"),
    ("http://[64:ff9b::7f00:1]/", {"block_private_networks": True}, "private address"),
    ("http://[::127.0.0.1]/", {"block_private_networks": True}, "private address"),
    ("http://[2002:c0a8:0101::1]/", {"block_private_networks": True}, "private address"),
    ("http://[2001:0:4136:e378:8000:63bf:3fff:fdd2]/", {"block_private_networks": True}, "private address"),
    ("http://[64:ff9b::7f00:1]/", {"blocked_domains": ["127.0.0.1"]}, "blocked site"),
    # What a browser would not open at all.
    ("http://256.0.0.1/", {}, "not a valid address"),
    ("http://1.2.3.4.5/", {}, "not a valid address"),
    ("http://exa mple.com/", {}, "not a valid address"),
    ("http://exa%2Fmple.com/", {}, "not a valid address"),
    ("http://example.com:99999/", {}, "not a valid address"),
    ("http://exam\tple.com/", {}, "not a valid address"),
    ("http://[::1%25eth0]/", {}, "not a valid address"),
    ("https://faß.example/", {}, "not a valid address"),
]


@pytest.mark.parametrize(("url", "safety"), ALLOWED)
async def test_allowed(url: str, safety: dict[str, Any]) -> None:
    decision = await policy(**safety).check(url)
    assert decision.allowed, decision.reason


@pytest.mark.parametrize(("url", "safety", "reason"), BLOCKED)
async def test_blocked(url: str, safety: dict[str, Any], reason: str) -> None:
    decision = await policy(**safety).check(url)
    assert not decision.allowed
    assert reason in decision.reason


async def test_a_name_that_resolves_to_a_private_address_is_blocked() -> None:
    decision = await policy(resolves_to=["10.1.2.3"], block_private_networks=True).check(
        "https://intranet.example.com/"
    )
    assert not decision.allowed
    assert "resolves to a private address (safety.block_private_networks)" in decision.reason


async def test_a_name_that_resolves_to_a_private_address_is_allowed_locally() -> None:
    assert (await policy(resolves_to=["10.1.2.3"]).check("https://intranet.example.com/")).allowed


async def test_a_name_that_resolves_to_the_metadata_address_is_always_blocked() -> None:
    decision = await policy(resolves_to=["169.254.169.254"]).check("https://innocent.example.com/")
    assert not decision.allowed
    assert "cloud metadata address" in decision.reason


async def test_one_private_address_among_several_is_enough() -> None:
    decision = await policy(resolves_to=[PUBLIC, "127.0.0.1"], block_private_networks=True).check(
        "https://a.example.com/"
    )
    assert not decision.allowed


async def test_a_name_that_cannot_be_resolved_is_blocked_only_when_private_networks_are() -> None:
    async def fails(host: str) -> list[str]:
        raise OSError("no such host")

    guarded = UrlPolicy(Safety(block_private_networks=True), resolve=fails)
    decision = await guarded.check("https://nowhere.example.com/")
    assert not decision.allowed
    assert "could not be resolved" in decision.reason
    assert (await UrlPolicy(Safety(), resolve=fails).check("https://nowhere.example.com/")).allowed


async def test_a_decision_is_reused_for_policy_cache_s() -> None:
    now = [100.0]
    calls: list[str] = []

    async def resolve(host: str) -> list[str]:
        calls.append(host)
        return [PUBLIC]

    checker = UrlPolicy(Safety(policy_cache_s=5), resolve=resolve, clock=lambda: now[0])
    await checker.check("https://example.com/a")
    await checker.check("https://example.com/b")
    assert calls == ["example.com"]
    now[0] += 6
    await checker.check("https://example.com/c")
    assert calls == ["example.com", "example.com"]


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        ("example.com", "https://example.com"),
        ("  example.com/path  ", "https://example.com/path"),
        ("localhost:3000/a", "https://localhost:3000/a"),
        ("http://example.com", "http://example.com"),
        ("HTTPS://Example.COM./a?b=C#d", "https://example.com/a?b=C#d"),
        ("http://example.com:80/", "http://example.com/"),
        ("https://example.com:8443/", "https://example.com:8443/"),
        ("http://127.0.0.1:8000\\@example.com/../admin", "http://127.0.0.1:8000/@example.com/../admin"),
        ("http:\\\\example.com\\a?q=\\b", "http://example.com/a?q=\\b"),
        ("http://%31%32%37.0.0.1/p", "http://127.0.0.1/p"),
        ("http://2130706433/", "http://127.0.0.1/"),
        ("http://0x7f.1/", "http://127.0.0.1/"),
        ("http://１２７.0.0.1/", "http://127.0.0.1/"),
        ("http://127。0。0。1/", "http://127.0.0.1/"),
        ("http://ｌｏｃａｌｈｏｓｔ:3000/", "http://localhost:3000/"),
        ("https://bücher.example/", "https://xn--bcher-kva.example/"),
        ("http://[::FFFF:127.0.0.1]/", "http://[::ffff:7f00:1]/"),
        ("https://user:p%40ss@example.com/", "https://user:p%40ss@example.com/"),
        ("https://a@b@example.com/", "https://a%40b@example.com/"),
        ("https://my_site.example.com/", "https://my_site.example.com/"),
        ("about:blank", "about:blank"),
        ("data:text/html,hi", "data:text/html,hi"),
        ("file:///C:/a.html", "file:///C:/a.html"),
    ],
)
def test_normalise(given: str, expected: str) -> None:
    assert UrlPolicy.normalise(given) == expected


@pytest.mark.parametrize(
    ("host", "expected"),
    [
        ("127.0.0.1", "127.0.0.1"),
        ("2130706433", "127.0.0.1"),
        ("0x7f.0.0.1", "127.0.0.1"),
        ("0177.0.0.1", "127.0.0.1"),
        ("127.1", "127.0.0.1"),
        ("::ffff:10.0.0.1", "10.0.0.1"),
        ("64:ff9b::a9fe:a9fe", "169.254.169.254"),
        ("::10.0.0.1", "10.0.0.1"),
        ("2002:0a00:0001::", "10.0.0.1"),
        ("64:ff9b:1:a9fe:a9:fe00::", "169.254.169.254"),
        ("2606:4700:4700::1111", "2606:4700:4700::1111"),
        ("::1", "::1"),
        ("example.com", None),
        ("1_0.0.0.1", None),
        ("256.0.0.1", None),
        ("1.2.3.4.5", None),
        ("", None),
    ],
)
def test_parse_ip(host: str, expected: str | None) -> None:
    parsed = parse_ip(host)
    assert (str(parsed) if parsed is not None else None) == expected


def test_host_matches() -> None:
    assert host_matches("example.com", "example.com")
    assert host_matches("a.b.example.com", "example.com")
    assert host_matches("a.example.com", "*.example.com")
    assert not host_matches("example.com", "*.example.com")
    assert not host_matches("notexample.com", "example.com")


@pytest.mark.parametrize(
    "given",
    [
        "http://256.0.0.1/",
        "http://exa mple.com/",
        "http://exa%2Fmple.com/",
        "http://example.com:port/",
        "http://[::1",
        "https:///nothing",
        "http://a..b/",
        "https://faß.example/",
        "http://exam\nple.com/",
    ],
)
def test_an_address_a_browser_would_not_open_cannot_be_normalised(given: str) -> None:
    with pytest.raises(ValueError, match=r"not a valid address|the address has no host"):
        UrlPolicy.normalise(given)


async def test_the_decision_carries_the_address_to_open() -> None:
    decision = await policy().check("HTTPS://Example.COM/a")
    assert decision.allowed and decision.url == "https://example.com/a"
    refused = await policy(block_private_networks=True).check("http://2130706433/x")
    assert not refused.allowed and refused.url == "http://127.0.0.1/x"


async def test_one_spelling_of_a_host_is_judged_once() -> None:
    calls: list[str] = []

    async def resolve(host: str) -> list[str]:
        calls.append(host)
        return [PUBLIC]

    checker = UrlPolicy(Safety(), resolve=resolve)
    await checker.check("https://Example.com/a")
    await checker.check("https://example.com./b")
    await checker.check("https://ｅｘａｍｐｌｅ.com/c")
    assert calls == ["example.com"]
