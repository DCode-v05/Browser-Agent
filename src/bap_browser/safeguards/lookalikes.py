"""Look-alike checks on a host (spec 18.7, part 1): a name close to one the task or the deployment
protects, a protected name hidden beside a lure word, an international name that reads as a Latin
one, and a bare public IP address used as a host.
"""

from __future__ import annotations

import ipaddress
from collections.abc import Sequence

from bap_browser.policy import sites

IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address
# A protected name under this length is never measured for (b): too many short, ordinary words.
SHORTEST_LURED_LABEL = 4
# A label under this length is never measured for (a), on either side of the comparison.
SHORTEST_MEASURED_LABEL = 5
# (a) allows one edit for a protected label of this length, two for anything longer.
LONGEST_LABEL_FOR_ONE_EDIT = 8


def lookalike_of(
    host: str,
    protected: Sequence[str],
    *,
    lure_words: Sequence[str],
    common_words: Sequence[str],
) -> str | None:
    """The protected name this host looks like and is not, or None. Never raises."""
    host = host.strip().lower().removesuffix(".")
    protected_sites = {sites.registrable_name(name) for name in protected}
    host_site = sites.registrable_name(host)
    if host_site in protected_sites:
        return None  # a protected site, named by itself or a subdomain, is never a look-alike
    host_label = host_site.split(".")[0]
    host_latin = sites.to_latin(host_label)
    close_measured = host_latin not in {word.lower() for word in common_words}
    lure_set = {word.lower() for word in lure_words}
    host_labels = host.split(".")
    for name in protected:
        protected_label = sites.registrable_name(name).split(".")[0]
        if close_measured and _close(host_label, host_latin, protected_label):
            return name
        if _stands_with_lure(host_labels, protected_label, lure_set):
            return name
    return None


def mixed_script_of(host: str, protected: Sequence[str]) -> str | None:
    """For an international name: the protected name it becomes when its look-alike letters are read
    as Latin ones, or the host itself when one of its labels mixes writing systems. None otherwise,
    including for a host with no `xn--` label. Never raises."""
    host = host.strip().lower().removesuffix(".")
    if "xn--" not in host:
        return None
    host_site = sites.registrable_name(host)
    if host_site in {sites.registrable_name(name) for name in protected}:
        return None
    for label in host.split("."):
        if len(sites.writing_systems(_decoded(label))) > 1:
            return host
    first_label = _decoded(host_site.split(".")[0])
    latin_first = sites.to_latin(first_label)
    for name in protected:
        if latin_first == sites.registrable_name(name).split(".")[0]:
            return name
    return None


def is_bare_public_ip(host: str) -> bool:
    """Whether `host` is a public IP address: not a private, loopback or link-local one. Never
    raises."""
    ip = _parse_ip(host)
    return ip is not None and not (ip.is_private or ip.is_loopback or ip.is_link_local)


def _parse_ip(host: str) -> IPAddress | None:
    text = host.strip()
    if text.startswith("[") and text.endswith("]"):
        text = text[1:-1]
    try:
        return ipaddress.ip_address(text)
    except ValueError:
        return None


def _decoded(label: str) -> str:
    """`label` read back from its xn-- punycode form; itself when it is not one, or cannot be read."""
    if not label.startswith("xn--"):
        return label
    try:
        return label.encode("ascii").decode("idna")
    except UnicodeError:
        return label


def _close(host_label: str, host_latin: str, protected_label: str) -> bool:
    """Rule (a): the host's label is close to the protected label, after look-alike letters are read
    as Latin ones. A label that came out equal only because of that reading counts; one that was
    already equal in plain Latin does not (too many honest sites share a first label across suffixes)."""
    protected_latin = sites.to_latin(protected_label)
    if len(protected_latin) < SHORTEST_MEASURED_LABEL or len(host_latin) < SHORTEST_MEASURED_LABEL:
        return False
    distance = _edit_distance(host_latin, protected_latin)
    if distance == 0:
        return host_latin != host_label
    threshold = 1 if len(protected_latin) <= LONGEST_LABEL_FOR_ONE_EDIT else 2
    return distance <= threshold


def _stands_with_lure(host_labels: list[str], protected_label: str, lure_words: set[str]) -> bool:
    """Rule (b): the protected label stands in the host as a whole label or a hyphen-part of one, with
    a lure word beside it: another hyphen-part of the same label, or any part of another label."""
    if len(protected_label) < SHORTEST_LURED_LABEL:
        return False
    for index, label in enumerate(host_labels):
        parts = label.split("-")
        if protected_label not in parts:
            continue
        beside = [part for part in parts if part != protected_label]
        for other_index, other_label in enumerate(host_labels):
            if other_index != index:
                beside.extend(other_label.split("-"))
        if any(word in lure_words for word in beside):
            return True
    return False


def _edit_distance(one: str, other: str) -> int:
    """Damerau-Levenshtein distance: an insertion, a deletion, a substitution or a swap of two
    neighbouring letters, each counting 1."""
    rows, columns = len(one) + 1, len(other) + 1
    distance = [[0] * columns for _ in range(rows)]
    for i in range(rows):
        distance[i][0] = i
    for j in range(columns):
        distance[0][j] = j
    for i in range(1, rows):
        for j in range(1, columns):
            cost = 0 if one[i - 1] == other[j - 1] else 1
            distance[i][j] = min(
                distance[i - 1][j] + 1,
                distance[i][j - 1] + 1,
                distance[i - 1][j - 1] + cost,
            )
            if i > 1 and j > 1 and one[i - 1] == other[j - 2] and one[i - 2] == other[j - 1]:
                distance[i][j] = min(distance[i][j], distance[i - 2][j - 2] + 1)
    return distance[rows - 1][columns - 1]
