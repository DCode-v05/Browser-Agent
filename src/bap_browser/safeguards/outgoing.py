"""What goes out (spec 18.6): the rules that notice data leaving through the browser.

Text that was read on one site and is about to be typed or sent on another; the fields that
take a password, a card or a code; the amounts of money a page shows; the files that arrive;
and the screens on which an app is given access to an account.
"""

from __future__ import annotations

import base64
import binascii
import fnmatch
import re
import secrets
from collections import OrderedDict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal
from urllib.parse import unquote, urlsplit

from bap_browser.config import ArrivingFiles, Outgoing

# How the first bytes of a program look: Windows, Linux, macOS, and a script that names its interpreter.
PROGRAM_BEGINNINGS = (
    b"MZ",
    b"\x7fELF",
    b"\xfe\xed\xfa\xce",
    b"\xfe\xed\xfa\xcf",
    b"\xce\xfa\xed\xfe",
    b"\xcf\xfa\xed\xfe",
    b"\xca\xfe\xba\xbe",
    b"#!",
)
# How much of a file is read to tell a program from what its name says it is.
FIRST_BYTES = max(len(beginning) for beginning in PROGRAM_BEGINNINGS)
SIGNS = {
    "$": "USD",
    "€": "EUR",
    "£": "GBP",
    "₹": "INR",
    "¥": "JPY",
    "₩": "KRW",
    "₽": "RUB",
    "₺": "TRY",
    "₫": "VND",
    "₦": "NGN",
    "₱": "PHP",
    "฿": "THB",
}
CODES = ("INR", "USD", "EUR", "GBP", "JPY", "AUD", "CAD", "SGD", "AED", "CHF", "CNY")
_MARK = "[" + "".join(map(re.escape, SIGNS)) + "]|(?<![A-Za-z])(?:" + "|".join(CODES) + r"|Rs\.?)(?![A-Za-z])"
# Digits with their grouping marks: 1,234,567.89 and 12,34,567.89 and 1.234.567,89 and 1 234 567,89.
_NUMBER = r"\d+(?:[.,]\d+|[ \xa0]\d{3}(?!\d))*"
_AMOUNT = re.compile(
    rf"(?P<before>{_MARK})\s?(?P<after_mark>{_NUMBER})|(?P<before_mark>{_NUMBER})\s?(?P<after>{_MARK})",
    re.IGNORECASE,
)
_EMAIL = re.compile(r"[a-z0-9._%+-]{1,64}@[a-z0-9-]{1,63}(?:\.[a-z0-9-]{1,63})+", re.IGNORECASE)
_DIGITS = re.compile(r"\d{6,}")
_GROUPED = re.compile(r"(?<![\d.-])\d{1,6}(?:[ .-]\d{1,6}){1,7}(?![\d.-]?\d)")
_A_DATE = re.compile(r"\d{4}[ .-]\d{1,2}[ .-]\d{1,2}|\d{1,2}[ .-]\d{1,2}[ .-]\d{4}")
_A_WORD = re.compile(r"[A-Za-z0-9_-]{8,}")
# A phone or card number is told from other grouped digits by how many it has.
DIGITS_OF_A_LONG_NUMBER = 10
_POSTAL_PIN = re.compile(r"\b(?:postal|zip|area|code)\W+pin\b|\bpin\W+(?:code|postal|zip|area)\b")
_GRANTS = re.compile(
    r"wants to access your|is requesting access|would like to access|grant access|authori[sz]e\s+\w",
    re.IGNORECASE,
)
_AGREES = re.compile(
    r"\b(?:allow|authorize|authorise|accept|approve|grant|agree|continue|yes)\b", re.IGNORECASE
)


@dataclass(frozen=True)
class Copy:
    """Text that was read on one site and is about to go to another."""

    site: str
    """Where it was read."""
    chars: int
    sample: str
    """The copied text as it stands in what goes out. The caller cuts it."""
    how: Literal["text", "secret"]


@dataclass
class _Read:
    """What is kept of one site: nothing that can be read back."""

    bits: bytearray | None = None
    taken: int = 0
    secrets: dict[int, None] = field(default_factory=dict[int, None])


def _normal(text: str) -> str:
    """Text as it is compared: white space made single, letters made small."""
    return " ".join(text.split()).lower()


class CopyMemory:
    """What the agent was given to read, site by site, kept so that nothing can be read back.

    Every run of a few characters marks a few bits of a filter for its site. Text that goes out
    is a copy when a long row of its runs is all marked for one other site: a chance hit on one
    run is common, on a row of them it is not. Short secrets (a code, an order number, an email
    address) are kept as hashes of their own, because they are shorter than any row.
    """

    def __init__(self, settings: Callable[[], Outgoing]) -> None:
        self._settings = settings
        # The built-in hash is keyed for this process. This keeps two memories apart as well.
        self._salt = secrets.randbits(63)
        self._sites: OrderedDict[str, _Read] = OrderedDict()

    @property
    def size_bytes(self) -> int:
        """What the memory holds now."""
        return sum(len(read.bits or b"") + 8 * len(read.secrets) for read in self._sites.values())

    def remember(self, site: str, text: str) -> None:
        """Takes in page text that was given to the agent on `site`."""
        normal = _normal(text)
        if not site or not normal:
            return
        settings = self._settings()
        read = self._sites.get(site)
        if read is None:
            read = self._sites[site] = _Read()
            while len(self._sites) > settings.remember_sites:
                self._sites.popitem(last=False)
        self._sites.move_to_end(site)
        if read.bits is None or read.taken + len(normal) > settings.remember_chars_per_site:
            # The newest text is the text remembered.
            read.bits, read.taken = bytearray(settings.filter_bits // 8), 0
        read.taken += len(normal)
        bits, count, hashes = read.bits, len(read.bits) * 8, range(settings.filter_hashes)
        run, salt = settings.run_chars, self._salt
        for start in range(len(normal) - run + 1):
            marked = hash(normal[start : start + run]) ^ salt
            place, stride = marked % count, (marked >> 21) | 1
            for _ in hashes:
                bits[place >> 3] |= 1 << (place & 7)
                place = (place + stride) % count
        for secret in short_secrets(text):
            read.secrets[hash(secret) ^ salt] = None
        while len(read.secrets) > settings.secrets_per_site:
            del read.secrets[next(iter(read.secrets))]

    def _marked(self, read: _Read, run: str) -> bool:
        bits = read.bits
        if bits is None:
            return False
        count = len(bits) * 8
        marked = hash(run) ^ self._salt
        place, stride = marked % count, (marked >> 21) | 1
        for _ in range(self._settings().filter_hashes):
            if not bits[place >> 3] & (1 << (place & 7)):
                return False
            place = (place + stride) % count
        return True

    def copied(self, text: str, to_site: str, *, known: Sequence[str] = ()) -> Copy | None:
        """The copy that `text` holds, if it holds one that was read on a site other than `to_site`.
        `known` is the task and the person's own messages: text that is also there is no copy."""
        settings = self._settings()
        own = self._sites.get(to_site)
        elsewhere = [(site, read) for site, read in self._sites.items() if site != to_site]
        if not elsewhere:
            return None
        aware = [_normal(words) for words in known if words]
        forms = unpacked(text, settings.decode_min_chars)
        best: Copy | None = None
        for form in forms:
            best = self._longest_row(_normal(form), elsewhere, own, aware, best)
        if best is not None:
            return best
        for form in forms:
            for secret in short_secrets(form):
                key = hash(secret) ^ self._salt
                if (own is not None and key in own.secrets) or any(secret in words for words in aware):
                    continue
                for site, read in elsewhere:
                    if key in read.secrets:
                        return Copy(site, len(secret), secret, "secret")
        return None

    def _longest_row(
        self,
        normal: str,
        elsewhere: Sequence[tuple[str, _Read]],
        own: _Read | None,
        aware: Sequence[str],
        best: Copy | None,
    ) -> Copy | None:
        """The longest stretch of `normal` that one other site showed and this site did not."""
        settings = self._settings()
        run, least = settings.run_chars, settings.min_chars
        if len(normal) < least:
            return best
        runs = [normal[start : start + run] for start in range(len(normal) - run + 1)]
        for site, read in elsewhere:
            start: int | None = None
            for index in range(len(runs) + 1):
                inside = index < len(runs) and self._marked(read, runs[index])
                if inside and start is None:
                    start = index
                elif not inside and start is not None:
                    stretch = normal[start : index - 1 + run]
                    start = None
                    if len(stretch) < least or (best is not None and len(stretch) <= best.chars):
                        continue
                    shown_here_too = own is not None and all(
                        self._marked(own, stretch[at : at + run]) for at in range(len(stretch) - run + 1)
                    )
                    if not shown_here_too and not any(stretch.strip() in words for words in aware):
                        best = Copy(site, len(stretch.strip()), stretch.strip(), "text")
        return best


def short_secrets(text: str) -> list[str]:
    """The short secrets in a text, each in the form it is compared in: a number of six or more
    digits; a phone or card number, its separators taken out; a word of eight or more characters
    that holds both a letter and a digit; an email address."""
    found: dict[str, None] = {}
    for match in _EMAIL.finditer(text):
        found[match.group().lower()] = None
    for match in _DIGITS.finditer(text):
        found[match.group()] = None
    for match in _GROUPED.finditer(text):
        digits = re.sub(r"\D", "", match.group())
        if len(digits) >= DIGITS_OF_A_LONG_NUMBER and not _A_DATE.fullmatch(match.group()):
            found[digits] = None
    for match in _A_WORD.finditer(text):
        word = match.group()
        if any(letter.isalpha() for letter in word) and any(letter.isdigit() for letter in word):
            found[word.lower()] = None
    return list(found)


def _as_text(packed: bytes) -> str | None:
    """Bytes that are text a person could read, or None."""
    try:
        text = packed.decode("utf-8")
    except UnicodeDecodeError:
        return None
    return text if text and all(letter.isprintable() or letter in "\n\t" for letter in text) else None


def unpacked(text: str, decode_min_chars: int) -> list[str]:
    """The text as it is, and what it holds after undoing percent-encoding, Base64 and hexadecimal."""
    forms = [text]
    for _ in range(2):
        undone = unquote(forms[-1])
        if undone == forms[-1]:
            break
        forms.append(undone)
    least = max(decode_min_chars, 1)
    for source in list(forms):
        for match in re.finditer(rf"[A-Za-z0-9+/_-]{{{least},}}", source):
            run = match.group()
            if len(run) % 2 == 0 and re.fullmatch(r"[0-9a-fA-F]+", run):
                decoded = _as_text(bytes.fromhex(run))
                if decoded:
                    forms.append(decoded)
            try:
                packed = base64.b64decode(run.replace("-", "+").replace("_", "/") + "=" * (-len(run) % 4))
            except (binascii.Error, ValueError):
                continue
            decoded = _as_text(packed)
            if decoded:
                forms.append(decoded)
    return forms


@dataclass(frozen=True)
class Amount:
    value: Decimal
    currency: str
    """A three-letter code where the sign or the code is known, else the sign as written."""
    shown: str
    """As the page wrote it."""


def _value(number: str) -> Decimal:
    """The number a page wrote. The decimal mark is the last `.` or `,` with one or two digits
    after it; every other mark is grouping."""
    number = number.replace(" ", "").replace("\xa0", "")
    last = max(number.rfind("."), number.rfind(","))
    whole, part = number, ""
    if last != -1 and 1 <= len(number) - last - 1 <= 2:
        whole, part = number[:last], number[last + 1 :]
    whole = whole.replace(".", "").replace(",", "")
    return Decimal(f"{whole}.{part}" if part else whole)


def amounts(text: str) -> list[Amount]:
    """The amounts of money in a text: a currency sign or code before or after a number."""
    found: list[Amount] = []
    for match in _AMOUNT.finditer(text):
        mark = match.group("before") or match.group("after")
        number = match.group("after_mark") or match.group("before_mark")
        code = SIGNS.get(mark) or mark.upper().rstrip(".")
        found.append(Amount(_value(number), "INR" if code == "RS" else code, match.group().strip()))
    return found


def largest(found: Sequence[Amount], currency: str = "") -> Amount | None:
    """The largest amount; with `currency`, the largest in that currency."""
    wanted = [amount for amount in found if not currency or amount.currency == currency.upper()]
    return max(wanted, key=lambda amount: amount.value, default=None)


def _words_of(attribute: str) -> str:
    """An attribute cut into words: at `-`, `_`, `.`, a digit and a change of case."""
    spaced = re.sub(r"([a-z])([A-Z])", r"\1 \2", attribute)
    return " ".join(re.split(r"[-_.\d\s]+", spaced)).lower()


def sensitive_kind(
    words: Mapping[str, Sequence[str]], *, texts: Sequence[str], attributes: Sequence[str]
) -> str | None:
    """The kind of sensitive field that a field's name and label (`texts`) or its `name` and `id`
    attributes say it is, or None. A word counts only whole; "pin" beside "code" is a postal code."""
    said = [text.lower() for text in texts] + [_words_of(attribute) for attribute in attributes]
    for kind, kind_words in words.items():
        for word in kind_words:
            whole = re.compile(
                r"(?<![a-z0-9])" + r"\s+".join(map(re.escape, word.lower().split())) + r"(?![a-z0-9])"
            )
            for candidate in said:
                if not whole.search(candidate):
                    continue
                if word.lower() == "pin" and _POSTAL_PIN.search(candidate):
                    continue
                return kind
    return None


def judged_file(
    name: str, first_bytes: bytes, settings: ArrivingFiles, *, own_machine: bool
) -> Literal["risky", "ask", "keep"]:
    """What is done with a file that arrived: never kept, asked about, or kept."""
    # Windows takes no notice of dots and spaces at the end of a name.
    name = name.rstrip(". ")
    ending = name.rsplit(".", 1)[1].lower() if "." in name else ""
    if ending in settings.risky_extensions or first_bytes.startswith(PROGRAM_BEGINNINGS):
        return "risky"
    if settings.ask == "never":
        return "keep"
    if settings.ask == "always" or own_machine or ending in settings.ask_extensions:
        return "ask"
    return "keep"


def is_long_address(address: str, limit: int) -> bool:
    """Whether the path, the query and the fragment of an address are together longer than `limit`."""
    try:
        parts = urlsplit(address)
    except ValueError:
        return False
    length = len(parts.path) + sum(len(part) + 1 for part in (parts.query, parts.fragment) if part)
    return length > limit


def is_consent_address(address: str, patterns: Sequence[str]) -> bool:
    """Whether an address is one of the known screens on which an app is given access."""
    try:
        parts = urlsplit(address)
    except ValueError:
        return False
    where = f"{(parts.hostname or '').lower()}{parts.path.lower()}"
    return any(fnmatch.fnmatchcase(where, pattern.lower()) for pattern in patterns)


def says_grant_access(texts: Sequence[str]) -> bool:
    """Whether a page's headings and buttons say that an app asks for access to an account."""
    return any(_GRANTS.search(text) for text in texts)


def agrees(name: str) -> bool:
    """Whether a control's name agrees to something."""
    return bool(_AGREES.search(name))
