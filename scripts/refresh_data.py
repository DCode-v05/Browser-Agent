"""Fetches the Public Suffix List and Unicode's confusables data again, for a release.

Run as `uv run python scripts/refresh_data.py`. Standard library only: a release machine may have
no network access to PyPI, but it can always reach these two public pages.
"""

from __future__ import annotations

import urllib.request
from pathlib import Path

PSL_URL = "https://publicsuffix.org/list/public_suffix_list.dat"
CONFUSABLES_URL = "https://www.unicode.org/Public/security/latest/confusables.txt"
POLICY_DIR = Path(__file__).resolve().parent.parent / "src" / "bap_browser" / "policy"

CONFUSABLES_HEADER = (
    "# This is the part of Unicode's confusables data that maps a character to a Latin letter or a digit.\n"
)
# The header lines of confusables.txt that state its version or its licence and terms of use.
KEPT_HEADER_KEYWORDS = ("Version:", "Date:", "license")


def _fetch(url: str) -> str:
    with urllib.request.urlopen(url) as response:
        return response.read().decode("utf-8")


def refresh_public_suffix_list() -> None:
    """Saves the list exactly as published, private section included."""
    text = _fetch(PSL_URL)
    (POLICY_DIR / "public_suffix_list.dat").write_text(text, encoding="utf-8", newline="\n")


def refresh_confusables() -> None:
    """Saves only the mappings to a Latin letter or a digit, with the header that gives their version
    and licence."""
    lines = _fetch(CONFUSABLES_URL).splitlines()
    kept: list[str] = [CONFUSABLES_HEADER.rstrip("\n")]
    for line in lines:
        if line.startswith("#"):
            if any(keyword in line for keyword in KEPT_HEADER_KEYWORDS):
                kept.append(line)
            continue
        target = _single_ascii_letter_or_digit(line)
        if target is not None:
            kept.append(line)
    (POLICY_DIR / "confusables.txt").write_text("\n".join(kept) + "\n", encoding="utf-8", newline="\n")


def _single_ascii_letter_or_digit(line: str) -> str | None:
    """The line's target, lower-cased, when it is one character and that character is an ASCII
    letter or digit. None for a blank line, a comment, or a target of more than one character."""
    fields = line.split(";", 2)
    if len(fields) != 3:
        return None
    codepoints = fields[1].split()
    if len(codepoints) != 1:
        return None
    try:
        character = chr(int(codepoints[0], 16))
    except ValueError:
        return None
    lowered = character.lower()
    if len(lowered) == 1 and lowered.isascii() and lowered.isalnum():
        return lowered
    return None


def main() -> None:
    refresh_public_suffix_list()
    refresh_confusables()


if __name__ == "__main__":
    main()
