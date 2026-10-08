"""What a site is: the registrable name a host belongs to, and the writing of a host that lets two
spellings of the same look-alike name be compared (spec 18.2, 18.7).

The registrable name follows the Public Suffix List algorithm: the longest matching rule wins, an
exception rule beats a longer wildcard match at the same depth, and a host with no matching rule is
its own suffix (the implicit `*` rule). Both the ICANN and the private section of the list are rules
to this algorithm; the file only splits them apart for its own licensing and upkeep.
"""

from __future__ import annotations

import functools
import ipaddress
import unicodedata
from pathlib import Path
from urllib.parse import urlsplit

PSL_FILE = Path(__file__).with_name("public_suffix_list.dat")
CONFUSABLES_FILE = Path(__file__).with_name("confusables.txt")

IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address
DEFAULT_PORTS = {"http": 80, "https": 443}


@functools.cache
def _rules() -> tuple[frozenset[str], frozenset[str]]:
    """The list's rules and its exceptions, each in the ASCII form hosts are matched in. Read once."""
    rules: set[str] = set()
    exceptions: set[str] = set()
    for line in PSL_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("//"):
            continue
        if line.startswith("!"):
            exceptions.add(_ascii_form(line[1:]))
        else:
            rules.add(_ascii_form(line))
    return frozenset(rules), frozenset(exceptions)


def _ascii_form(text: str) -> str:
    """`text`, lower case and in its xn-- form when it holds a character outside ASCII. Falls back to
    the lower-cased text when it cannot be converted: a lookup that cannot match any rule still runs."""
    text = text.lower()
    if text.isascii():
        return text
    try:
        return text.encode("idna").decode("ascii")
    except UnicodeError:
        return text


def parsed_ip(host: str) -> IPAddress | None:
    text = host.strip()
    if text.startswith("[") and text.endswith("]"):
        text = text[1:-1]
    try:
        return ipaddress.ip_address(text)
    except ValueError:
        return None


def is_ip_address(host: str) -> bool:
    """Whether `host` is an IP address: IPv4, or IPv6 with or without its brackets."""
    return parsed_ip(host) is not None


def registrable_name(host: str) -> str:
    """The site a host belongs to: its public suffix and the one label before it. A host that is
    itself a public suffix, or an IP address, is its own site. Never raises."""
    host = host.strip().lower().removesuffix(".")
    ip = parsed_ip(host)
    if ip is not None:
        return str(ip)
    labels = host.split(".")
    ascii_labels = [_ascii_form(label) for label in labels]
    rules, exceptions = _rules()
    suffix_start = len(labels) - 1  # the implicit `*` rule: the last label, when nothing else matches
    for i in range(len(labels)):
        candidate = ".".join(ascii_labels[i:])
        if candidate in exceptions:
            suffix_start = i + 1
            break
        if candidate in rules:
            suffix_start = i
            break
        if i + 1 < len(labels) and "*." + ".".join(ascii_labels[i + 1 :]) in rules:
            suffix_start = i
            break
    name_start = max(suffix_start - 1, 0)
    return ".".join(labels[name_start:])


def site_of(address: str) -> str:
    """The site of a web address. Empty for an address with no host (`about:`, `data:`, `file:`,
    garbage). The site of the address a `blob:` address was made from."""
    address = address.strip()
    if address.lower().startswith("blob:"):
        address = address[len("blob:") :]
    try:
        host = urlsplit(address).hostname
    except ValueError:
        return ""
    return registrable_name(host) if host else ""


def same_site(one: str, other: str) -> bool:
    """Whether two hosts belong to the same site. registrable_name keeps the spelling it is given
    (a decoded label is wanted elsewhere, for to_latin), so the comparison is in the xn-- form."""
    return _ascii_form(registrable_name(one)) == _ascii_form(registrable_name(other))


def _bracketed(host: str) -> str:
    return f"[{host}]" if ":" in host else host


def origin_of(address: str) -> str:
    """Scheme, host and port of an address, the port always written out. Empty when the address has
    no host."""
    try:
        parts = urlsplit(address.strip())
        port = parts.port
    except ValueError:
        return ""
    host = parts.hostname
    if not host:
        return ""
    scheme = parts.scheme.lower()
    port = port if port is not None else DEFAULT_PORTS.get(scheme)
    origin = f"{scheme}://{_bracketed(host.lower())}"
    return f"{origin}:{port}" if port is not None else origin


@functools.cache
def _confusable_map() -> dict[str, str]:
    """Each look-alike character, mapped to the lower-case Latin letter or digit it stands for. The
    data also maps a few plain ASCII characters to one another (a digit 1 to a letter l, and so
    on); those are not look-alikes of a Latin letter, they already are one, so they are left out."""
    mapping: dict[str, str] = {}
    for line in CONFUSABLES_FILE.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        source_hex, target_hex, _rest = line.split(";", 2)
        source = chr(int(source_hex.strip(), 16))
        if source.isascii():
            continue
        target = chr(int(target_hex.strip(), 16)).lower()
        mapping[source.lower()] = target
    return mapping


def to_latin(label: str) -> str:
    """`label`, in small letters, with every look-alike character read as the Latin letter or digit
    it looks like."""
    mapping = _confusable_map()
    return "".join(mapping.get(character, character) for character in label.lower())


def writing_systems(label: str) -> set[str]:
    """The writing systems the letters of `label` come from: 'Latin', 'Cyrillic', 'Greek', and so on.
    Digits and hyphens belong to none. The standard library has no script property for a character,
    so this reads the first word of its Unicode name, which names the script for a letter."""
    systems: set[str] = set()
    for character in label:
        if character.isdigit() or character == "-":
            continue
        try:
            name = unicodedata.name(character)
        except ValueError:
            continue
        systems.add(name.split(" ", 1)[0].capitalize())
    return systems
