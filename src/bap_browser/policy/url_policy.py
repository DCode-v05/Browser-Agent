"""Which addresses the agent may open.

Order of checks: local files, scheme, cloud metadata, block list, allow list, private addresses
and names, then name resolution. The browser resolves names separately; a guard that connects to
the checked address is a later item.
"""

from __future__ import annotations

import asyncio
import ipaddress
import re
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from urllib.parse import urlsplit

from bap_browser.config import Safety

IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address
Resolver = Callable[[str], Awaitable[list[str]]]

METADATA_HOSTS = frozenset({"metadata.google.internal", "metadata.goog"})
METADATA_ADDRESSES = frozenset(
    ipaddress.ip_address(text)
    for text in ("169.254.169.254", "169.254.170.2", "100.100.100.200", "fd00:ec2::254")
)
PRIVATE_SUFFIXES = (".localhost", ".local", ".internal", ".lan", ".home.arpa")
SCHEMES_WITHOUT_A_HOST = frozenset({"about", "data", "blob"})
SCHEMES_WRITTEN_WITHOUT_SLASHES = ("about:", "data:", "blob:", "file:", "javascript:", "mailto:", "tel:")
HAS_SCHEME = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://")
IPV4_PART = re.compile(r"0[xX][0-9a-fA-F]*|[0-9]+")


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str = ""


ALLOWED = Decision(True)


def blocked(reason: str) -> Decision:
    return Decision(False, reason)


def parse_ip(host: str) -> IPAddress | None:
    """The address a browser would connect to for this host text, or None when it is a name."""
    try:
        ip: IPAddress | None = ipaddress.ip_address(host)
    except ValueError:
        ip = _legacy_ipv4(host)
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        return ip.ipv4_mapped
    return ip


def _legacy_ipv4(host: str) -> ipaddress.IPv4Address | None:
    """Browsers also accept 2130706433, 0x7f.1 and 0177.0.0.1 as IPv4 addresses."""
    parts = host.split(".")
    if not 1 <= len(parts) <= 4 or not all(IPV4_PART.fullmatch(part) for part in parts):
        return None
    numbers: list[int] = []
    for part in parts:
        if part[:2].lower() == "0x":
            numbers.append(int(part[2:] or "0", 16))
        elif len(part) > 1 and part.startswith("0"):
            if not part.isdecimal() or any(digit in "89" for digit in part):
                return None
            numbers.append(int(part, 8))
        else:
            numbers.append(int(part, 10))
    *leading, last = numbers
    if any(number > 255 for number in leading) or last >= 256 ** (4 - len(leading)):
        return None
    value = last
    for index, number in enumerate(leading):
        value += number << (8 * (3 - index))
    return ipaddress.IPv4Address(value)


def host_matches(host: str, pattern: str) -> bool:
    """`example.com` matches the host and its subdomains; `*.example.com` only subdomains."""
    pattern = pattern.lower().rstrip(".")
    if pattern.startswith("*."):
        return host.endswith(pattern[1:])
    return host == pattern or host.endswith("." + pattern)


async def _system_resolve(host: str) -> list[str]:
    infos = await asyncio.get_running_loop().getaddrinfo(host, None)
    return sorted({str(info[4][0]) for info in infos})


class UrlPolicy:
    def __init__(
        self,
        safety: Safety,
        *,
        resolve: Resolver | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._safety = safety
        self._resolve = resolve or _system_resolve
        self._clock = clock
        self._cache: dict[str, tuple[float, Decision]] = {}

    @staticmethod
    def normalise(url: str) -> str:
        """An address with no scheme gets https://."""
        url = url.strip()
        if HAS_SCHEME.match(url) or url.lower().startswith(SCHEMES_WRITTEN_WITHOUT_SLASHES):
            return url
        return "https://" + url

    async def check(self, url: str) -> Decision:
        safety = self._safety
        try:
            parts = urlsplit(url)
            host = (parts.hostname or "").rstrip(".").lower()
        except ValueError:
            return blocked("not a valid address")
        scheme = parts.scheme.lower()
        if scheme == "file":
            return (
                ALLOWED if safety.allow_file_urls else blocked("local files are off (safety.allow_file_urls)")
            )
        if scheme not in safety.allowed_schemes:
            return blocked(f"scheme '{scheme}' is not allowed (safety.allowed_schemes)")
        if scheme in SCHEMES_WITHOUT_A_HOST:
            return ALLOWED
        if not host:
            return blocked("the address has no host")

        now = self._clock()
        cached = self._cache.get(host)
        if cached is not None and cached[0] > now:
            return cached[1]
        decision = await self._check_host(host)
        self._cache = {name: entry for name, entry in self._cache.items() if entry[0] > now}
        self._cache[host] = (now + safety.policy_cache_s, decision)
        return decision

    async def _check_host(self, host: str) -> Decision:
        safety = self._safety
        ip = parse_ip(host)
        if safety.block_cloud_metadata and (host in METADATA_HOSTS or ip in METADATA_ADDRESSES):
            return blocked("cloud metadata address (safety.block_cloud_metadata)")
        if any(host_matches(host, pattern) for pattern in safety.blocked_domains):
            return blocked("blocked site (safety.blocked_domains)")
        if safety.allowed_domains and not any(host_matches(host, p) for p in safety.allowed_domains):
            return blocked("not in the allowed sites (safety.allowed_domains)")
        guard_private = safety.block_private_networks
        if ip is not None:
            if guard_private and not ip.is_global:
                return blocked("private address (safety.block_private_networks)")
            return ALLOWED
        if guard_private and (host == "localhost" or host.endswith(PRIVATE_SUFFIXES) or "." not in host):
            return blocked("private name (safety.block_private_networks)")
        if not (guard_private or safety.block_cloud_metadata):
            return ALLOWED
        try:
            addresses = await self._resolve(host)
        except OSError:
            if guard_private:
                return blocked(
                    "the name could not be resolved, so it cannot be checked (safety.block_private_networks)"
                )
            return ALLOWED
        for text in addresses:
            resolved = parse_ip(text)
            if safety.block_cloud_metadata and resolved in METADATA_ADDRESSES:
                return blocked("resolves to a cloud metadata address (safety.block_cloud_metadata)")
            if guard_private and (resolved is None or not resolved.is_global):
                return blocked("resolves to a private address (safety.block_private_networks)")
        return ALLOWED
