"""Failures the agent is told about, and failures that stop start-up."""


class BapError(Exception):
    """A failure returned to the agent as a tool result. The message is written for a model."""


class BadInput(BapError):
    """The call's arguments cannot be used."""


class StaleRef(BapError):
    """A ref no longer points at an element."""

    def __init__(self, ref: str) -> None:
        super().__init__(
            f"Ref '{ref}' is stale or unknown (the page changed or navigated). "
            "Take a new snapshot and use a fresh ref."
        )
        self.ref = ref


class PolicyBlocked(BapError):
    """The safety policy refused the action."""


class BrowserError(BapError):
    """The browser could not do what was asked."""


class ConfigError(Exception):
    """The configuration is wrong. Start-up stops with this message."""
