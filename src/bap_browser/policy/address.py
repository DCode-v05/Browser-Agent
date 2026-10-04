"""Reading an address the way a browser does, and writing it so that it can be read in one way only.

The policy judges this form and the browser is handed this form. Without it, a host that Python
and the browser read differently (a backslash, a percent-encoded digit, another spelling of an IP
address) would be judged as one site and opened as another.
"""

from __future__ import annotations

import ipaddress
import re
from urllib.parse import quote, unquote, urlsplit, urlunsplit

IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address

NOT_VALID = "not a valid address"
NO_HOST = "the address has no host"
BAD_SITE = (
    "write a site as a host name such as example.com or *.example.com, without a scheme, a port or a path"
)

SCHEMES_WRITTEN_WITHOUT_SLASHES = ("about:", "data:", "blob:", "file:", "javascript:", "mailto:", "tel:")
HAS_SCHEME = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://")
DEFAULT_PORTS = {"http": 80, "https": 443}
IPV4_PART = re.compile(r"0[xX][0-9a-fA-F]*|[0-9]+")
LABEL = r"[a-z0-9_](?:[a-z0-9_-]*[a-z0-9_])?"
HOST_NAME = re.compile(rf"{LABEL}(?:\.{LABEL})*")
# Characters that browsers and Python's own rules for international names turn into different
# names. Such a name has to be given in its xn-- form.
READ_DIFFERENTLY = frozenset("ßς‌‍")


def canonical_address(url: str) -> str:
    """The address a browser would open for this text. Raises ValueError when it would open none."""
    url = url.strip()
    if any(ord(character) < 0x20 or ord(character) == 0x7F for character in url):
        raise ValueError(NOT_VALID)
    if url.lower().startswith(SCHEMES_WRITTEN_WITHOUT_SLASHES):
        return url
    # A browser reads \ as / in a web address, up to the query.
    head = re.match(r"[^?#]*", url).group()  # type: ignore[union-attr]
    url = head.replace("\\", "/") + url[len(head) :]
    if not HAS_SCHEME.match(url):
        url = "https://" + url
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        raise ValueError(NOT_VALID) from None
    scheme = parts.scheme.lower()
    credentials, _, host_and_port = parts.netloc.rpartition("@")
    host = canonical_host(host_and_port if port is None else host_and_port.rsplit(":", 1)[0])
    netloc = host if port is None or port == DEFAULT_PORTS.get(scheme) else f"{host}:{port}"
    if credentials:
        name, colon, password = credentials.partition(":")
        netloc = f"{quote(unquote(name), safe='')}{colon}{quote(unquote(password), safe='')}@{netloc}"
    return urlunsplit((scheme, netloc, parts.path, parts.query, parts.fragment))


AUTHORITY = re.compile(r"^([a-zA-Z][a-zA-Z0-9+.-]*://)([^/?#]*)")


def without_credentials(url: str) -> str:
    """The address without the name and password it may carry. Those are never shown, sent or logged."""
    return AUTHORITY.sub(lambda found: found.group(1) + found.group(2).rpartition("@")[2], url, count=1)


def presentable_address(text: str) -> str | None:
    """An address as it may be logged or shown to a person: read the way a browser reads it, and without
    the name and password it may carry. None when no browser would open it; such text is shown nowhere."""
    try:
        return without_credentials(canonical_address(text))
    except ValueError:
        return None


def canonical_host(text: str) -> str:
    """One spelling for a host: lower case, an IP address in its usual form, an international name as xn--."""
    text = text.removesuffix(":")
    if not text:
        raise ValueError(NO_HOST)
    if text.startswith("["):
        try:
            # A zone such as %eth0 names an interface of this machine. A browser refuses it in an address.
            if "%" in text:
                raise ValueError
            ip = ipaddress.IPv6Address(text.removeprefix("[").removesuffix("]"))
        except ValueError:
            raise ValueError(NOT_VALID) from None
        if ip.ipv4_mapped is not None:
            # Written as browsers write it; Python's own spelling of these differs between versions.
            number = int(ip.ipv4_mapped)
            return f"[::ffff:{number >> 16:x}:{number & 0xFFFF:x}]"
        return f"[{ip}]"
    try:
        host = unquote(text, errors="strict")
        if READ_DIFFERENTLY.intersection(host):
            raise ValueError(NOT_VALID)
        if not host.isascii():
            host = host.encode("idna").decode("ascii")
    except UnicodeError:
        raise ValueError(NOT_VALID) from None
    host = host.lower().removesuffix(".")
    ip = legacy_ipv4(host)
    if ip is not None:
        return str(ip)
    # A browser reads a host that ends in a number as an IPv4 address or not at all.
    if not HOST_NAME.fullmatch(host) or IPV4_PART.fullmatch(host.rsplit(".", 1)[-1]):
        raise ValueError(NOT_VALID)
    return host


def parse_ip(host: str) -> IPAddress | None:
    """The address a browser would connect to for this host text, or None when it is a name."""
    try:
        ip: IPAddress | None = ipaddress.ip_address(host.removeprefix("[").removesuffix("]"))
    except ValueError:
        ip = legacy_ipv4(host)
    if isinstance(ip, ipaddress.IPv6Address):
        return _carried_ipv4(ip) or ip
    return ip


NAT64 = ipaddress.ip_network("64:ff9b::/96")
NAT64_LOCAL = ipaddress.ip_network("64:ff9b:1::/48")
IPV4_COMPATIBLE = ipaddress.ip_network("::/96")


def _carried_ipv4(ip: ipaddress.IPv6Address) -> ipaddress.IPv4Address | None:
    """The IPv4 address an IPv6 address stands for, when it is one of the forms that carry one. A
    gateway or the machine itself sends such traffic to that IPv4 address, so that is what is judged."""
    if ip.ipv4_mapped is not None:
        return ip.ipv4_mapped
    if ip.sixtofour is not None:
        return ip.sixtofour
    if ip.teredo is not None:
        return ip.teredo[1]
    number = int(ip)
    if ip in NAT64:
        return ipaddress.IPv4Address(number & 0xFFFFFFFF)
    if ip in NAT64_LOCAL:
        # RFC 6052 with a 48-bit prefix: 16 bits of the address, 8 unused bits, then the other 16.
        return ipaddress.IPv4Address((((number >> 64) & 0xFFFF) << 16) | ((number >> 40) & 0xFFFF))
    if ip in IPV4_COMPATIBLE and number > 1:
        return ipaddress.IPv4Address(number)
    return None


def legacy_ipv4(host: str) -> ipaddress.IPv4Address | None:
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


def site_identity(host: str) -> str:
    """What a site list is compared with: the address itself for every spelling of an IP address."""
    ip = parse_ip(host)
    return str(ip) if ip is not None else host


def site_pattern(entry: str) -> str:
    """An entry of a site list in the form hosts are compared in. Raises ValueError for one that could never match."""
    subdomains_only = entry.startswith("*.")
    name = entry.removeprefix("*.")
    try:
        try:
            host = str(ipaddress.ip_address(name))
        except ValueError:
            host = site_identity(canonical_host(name))
    except ValueError:
        raise ValueError(BAD_SITE) from None
    return f"*.{host}" if subdomains_only else host
