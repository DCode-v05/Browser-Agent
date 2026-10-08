"""Failures the agent is told about, and failures that stop start-up."""


class BapError(Exception):
    """A failure returned to the agent as a tool result. The message is written for a model."""

    def __init__(self, message: str, *, reason: str | None = None) -> None:
        super().__init__(message)
        self.reason = reason or message
        """The same failure in a few words, for the person watching."""


class BadInput(BapError):
    """The call's arguments cannot be used."""


class StaleRef(BapError):
    """A ref no longer points at an element."""

    def __init__(self, ref: str) -> None:
        super().__init__(
            f"Ref '{ref}' is stale or unknown (the page changed or navigated). "
            "Take a new snapshot and use a fresh ref.",
            reason="the page changed",
        )
        self.ref = ref


class PolicyBlocked(BapError):
    """The safety policy refused an address."""

    def __init__(self, message: str, *, url: str, reason: str) -> None:
        super().__init__(message, reason=reason)
        self.url = url


class BrowserError(BapError):
    """The browser could not do what was asked."""


class ModelError(Exception):
    """The model could not answer. The message is written for the person who ran the command."""


class ConfigError(Exception):
    """The configuration is wrong. Start-up stops with this message."""
