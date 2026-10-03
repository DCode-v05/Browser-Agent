"""Arguments for the page script's snapshot operation."""

from __future__ import annotations

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
