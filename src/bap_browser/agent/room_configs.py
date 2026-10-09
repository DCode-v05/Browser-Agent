"""How each page of the window has its browser set up, before a person's settings (spec 9.16)."""

from __future__ import annotations

from pathlib import Path

from bap_browser.config import Config

# The folder, inside the data folder, where the built-in browser keeps its sign-ins.
BUILT_IN_PROFILE = "built-in-browser"


def cloud_config(config: Config) -> Config:
    """A headless browser that starts with nothing: no profile is kept from one session to the next."""
    browser = config.browser.model_copy(update={"headless": True, "user_data_dir": None, "cdp_url": None})
    return config.model_copy(update={"browser": browser})


def built_in_config(config: Config) -> Config:
    """The app's own browser: it keeps its sign-ins, apart from the person's own browser and from
    the cloud browser."""
    profile = Path(config.data_dir).expanduser() / BUILT_IN_PROFILE
    browser = config.browser.model_copy(
        update={"headless": True, "user_data_dir": str(profile), "cdp_url": None}
    )
    return config.model_copy(update={"browser": browser})


def with_its_own_log(config: Config, system: str) -> Config:
    """Each browser of the window writes a log of its own (spec 9.17), where the deployment keeps a
    log at all."""
    if config.logging.event_log is None:
        return config
    own = Path(config.logging.systems_dir) / f"{system}.jsonl"
    return config.model_copy(update={"logging": config.logging.model_copy(update={"event_log": str(own)})})
