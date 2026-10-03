"""Patterns scrubbed from every result before it reaches the agent or a log."""

from __future__ import annotations

import re
from collections.abc import Sequence

from bap_browser.errors import ConfigError

REPLACEMENT = "[REDACTED]"


class Redactor:
    def __init__(self, patterns: Sequence[str]) -> None:
        self._patterns: list[re.Pattern[str]] = []
        for pattern in patterns:
            try:
                self._patterns.append(re.compile(pattern))
            except re.error as exc:
                raise ConfigError(
                    f"safety.redact_patterns: '{pattern}' is not a valid pattern ({exc})"
                ) from exc

    def __call__(self, text: str) -> str:
        for pattern in self._patterns:
            text = pattern.sub(REPLACEMENT, text)
        return text
