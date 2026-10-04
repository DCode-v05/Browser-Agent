"""Which addresses the agent may open.

Every address is first rewritten the way a browser reads it (see address.py); that form is what
is judged and what the browser is handed.

Order of checks: local files, scheme, cloud metadata, block list, allow list, private addresses
and names, then name resolution. The browser resolves names separately; a guard that connects to
the checked address is a later item.
"""

from __future__ import annotations

import asyncio
import ipaddress
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from urllib.parse import urlsplit

from bap_browser.config import Safety
from bap_browser.policy.address import NOT_VALID, canonical_address, parse_ip, site_identity, site_pattern

Resolver = Callable[[str], Awaitable[list[str]]]

METADATA_HOSTS = frozenset({"metadata.google.internal", "metadata.goog"})
METADATA_ADDRESSES = frozenset(
    ipaddress.ip_address(text)
    for text in ("169.254.169.254", "169.254.170.2", "100.100.100.200", "fd00:ec2::254")
)
PRIVATE_SUFFIXES = (".localhost", ".local", ".internal", ".lan", ".home.arpa")
SCHEMES_WITHOUT_A_HOST = frozenset({"about", "data", "blob"})


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str = ""
    url: str = ""
    """The address as the browser will read it. This, and nothing else, is what may be opened."""


ALLOWED = Decision(True)


def blocked(reason: str) -> Decision:
    return Decision(False, reason)


def host_matches(host: str, pattern: str) -> bool:
    """`example.com` matches the host and its subdomains; `*.example.com` only subdomains."""
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
        self._blocked = [site_pattern(entry) for entry in safety.blocked_domains]
        self._allowed = [site_pattern(entry) for entry in safety.allowed_domains]
        self._resolve = resolve or _system_resolve
        self._clock = clock
        self._cache: dict[str, tuple[float, Decision]] = {}

    @staticmethod
    def normalise(url: str) -> str:
        """The address as a browser reads it; with no scheme it gets https://. Raises ValueError."""
        return canonical_address(url)

    async def check(self, url: str) -> Decision:
        """Whether the address may be opened. The decision carries the address to hand to the browser."""
        try:
            url = canonical_address(url)
            parts = urlsplit(url)
        except ValueError as exc:
            return replace(blocked(str(exc) or NOT_VALID), url=url)
        return replace(await self._judge(parts.scheme, parts.netloc.rpartition("@")[2]), url=url)

    async def _judge(self, scheme: str, host_and_port: str) -> Decision:
        safety = self._safety
        if scheme == "file":
            return (
                ALLOWED if safety.allow_file_urls else blocked("local files are off (safety.allow_file_urls)")
            )
        if scheme not in safety.allowed_schemes:
            return blocked(f"scheme '{scheme}' is not allowed (safety.allowed_schemes)")
        if scheme in SCHEMES_WITHOUT_A_HOST:
            return ALLOWED
        host = urlsplit(f"//{host_and_port}").hostname or ""

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
        site = site_identity(host)
        if any(host_matches(site, pattern) for pattern in self._blocked):
            return blocked("blocked site (safety.blocked_domains)")
        if self._allowed and not any(host_matches(site, pattern) for pattern in self._allowed):
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
