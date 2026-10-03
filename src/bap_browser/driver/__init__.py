"""Browser driving: one adapter per backend."""

from bap_browser.driver.session import BrowserSession, open_session

__all__ = ["BrowserSession", "open_session"]
