"""Arguments for the page script's snapshot operation."""

from __future__ import annotations

import re
from typing import Any

from bap_browser.config import Snapshot

NOTICE = "\u2026 more elements not shown. Narrow with `ref=<subtree>`, scroll, or use `browser_find`."


def snapshot_arguments(
    settings: Snapshot,
    *,
    mode: str,
    ref: str | None,
    max_chars: int,
    include_bboxes: bool,
    next_ref: int,
) -> dict[str, Any]:
    return {
        "mode": mode,
        "ref": ref,
        "maxChars": max_chars,
        "maxDepth": settings.max_depth,
        "maxName": settings.max_name_chars,
        "maxValue": settings.max_value_chars,
        "maxText": settings.max_text_chars,
        "maxOptions": settings.max_options,
        "shadow": settings.include_shadow_dom,
        "bboxes": include_bboxes,
        "notice": NOTICE,
        "next": next_ref,
    }


REF = re.compile(r"\[ref=([^\]]+)\]")
# A whole page is searched, however long it is: only the lines that match come back.
WHOLE_PAGE = 10**9


def matching_lines(page: str, query: str, limit: int) -> tuple[list[str], int]:
    """The snapshot lines that hold the words asked for, best first, and how many there are in all.

    A line that holds the whole phrase comes before one that holds only some of its words. A line of
    text has no ref of its own: it is given with the ref of the element it is in.
    """
    words = query.lower().split()
    phrase = " ".join(words)
    found: list[tuple[int, int, str]] = []
    around: dict[int, str | None] = {}
    for index, line in enumerate(page.split("\n")):
        said = line.lstrip(" ")
        if not said.startswith("-"):
            continue
        depth = len(line) - len(said)
        named = REF.search(line)
        ref = named.group(1) if named else None
        around = {level: held for level, held in around.items() if level < depth}
        around[depth] = ref
        # The ref is not part of what the element says: e250 is no match for "250".
        low = REF.sub("", line, count=1).lower()
        score = sum(word in low for word in words)
        if not score:
            continue
        if phrase in low:
            score += len(words)
        parent = (
            None if ref else next((held for _, held in sorted(around.items(), reverse=True) if held), None)
        )
        found.append((-score, index, said + (f" (in {parent})" if parent else "")))
    found.sort()
    return [line for _, _, line in found[:limit]], len(found)
