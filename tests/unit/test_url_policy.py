from typing import Any

import pytest

from bap_browser.config import Safety
from bap_browser.policy.url_policy import UrlPolicy, host_matches, parse_ip

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
        ("HTTPS://Example.com", "HTTPS://Example.com"),
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
    assert host_matches("example.com", "Example.COM")
