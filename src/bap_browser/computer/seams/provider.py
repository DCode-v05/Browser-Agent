"""Hermes chooses a driver among plugins. This engine has one: Hermes' own, `cua-driver`, or the
backend a test names in its place."""

from __future__ import annotations

import abc
from typing import Any

from bap_browser.computer.seams.state import current

DEFAULT_BACKEND = "cua"


class ProviderBase(abc.ABC):
    """What Hermes' providers share: a name."""

    @property
    @abc.abstractmethod
    def name(self) -> str: ...

    @property
    def display_name(self) -> str:
        return self.name


class TheDriver:
    name = DEFAULT_BACKEND
    display_name = "cua-driver"

    def create_backend(self, *, permission_mode: str) -> Any:
        stand_in = current().backend
        if stand_in is not None:
            return stand_in()
        from bap_browser.computer.hermes.computer_use.cua_backend import CuaDriverBackend

        return CuaDriverBackend(permission_mode=permission_mode)

    def is_available(self) -> bool:
        if current().backend is not None:
            return True
        from bap_browser.computer.hermes.computer_use.cua_backend_driver import cua_driver_binary_available

        return cua_driver_binary_available()

    def doctor(self) -> int | None:
        return None


def configured_backend_name() -> str:
    return DEFAULT_BACKEND


def get_active_provider() -> TheDriver:
    return TheDriver()
