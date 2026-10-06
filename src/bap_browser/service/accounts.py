"""Who may sign in to the window, and as what (spec 4.11): the admin, who sets the system up, and
the user, who works with the agent inside what the admin allows.

Each has a password. Only a salted hash of it is kept, in a file for the person who runs the
service alone to read. Signing in gives a token for the rest of the visit; the token is held in
memory only, and is gone when it runs out, when the person signs out, or when the service stops.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time
from collections.abc import Callable
from pathlib import Path
from typing import Literal, get_args

from bap_browser.config import Auth

Role = Literal["admin", "user"]
ROLES: tuple[Role, ...] = get_args(Role)

# How the hash is made (scrypt). A password that is guessed must cost the guesser at each try.
COST, BLOCK, PARALLEL, LENGTH = 2**14, 8, 1, 32


class BadPassword(Exception):
    """A password that cannot be taken, and why, in words for the person."""


class LockedOut(Exception):
    """Too many wrong passwords in a row. `wait_s` is how long until the next try."""

    def __init__(self, wait_s: float) -> None:
        super().__init__(f"locked for {wait_s:.0f} s")
        self.wait_s = wait_s


def _hash(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(password.encode(), salt=salt, n=COST, r=BLOCK, p=PARALLEL, dklen=LENGTH)


class Accounts:
    def __init__(self, settings: Auth, clock: Callable[[], float] = time.time) -> None:
        self._settings = settings
        self._path = Path(settings.file)
        self._clock = clock
        self._kept = _read(self._path)
        # A token of a visit, the role it was given for, and when it runs out.
        self._visits: dict[str, tuple[Role, float]] = {}
        # Wrong passwords in a row for a role, and until when no further try is taken.
        self._wrong: dict[Role, int] = {}
        self._locked_until: dict[Role, float] = {}

    def has(self, role: Role) -> bool:
        """Whether a password has been set for this role. Until it has, nobody signs in as it."""
        return role in self._kept

    def set_password(self, role: Role, password: object) -> None:
        if not isinstance(password, str) or len(password) < self._settings.min_chars:
            raise BadPassword(f"Use at least {self._settings.min_chars} characters.")
        if len(password) > self._settings.max_chars:
            raise BadPassword(f"Use at most {self._settings.max_chars} characters.")
        salt = secrets.token_bytes(16)
        kept = dict(self._kept)
        kept[role] = {"salt": salt.hex(), "hash": _hash(password, salt).hex()}
        self._kept = kept
        _write(self._path, kept)
        # Whoever signed in with the password before must sign in again with the new one.
        self._visits = {token: visit for token, visit in self._visits.items() if visit[0] != role}
        self._wrong.pop(role, None)
        self._locked_until.pop(role, None)

    def _matches(self, role: Role, password: object) -> bool:
        kept = self._kept.get(role)
        if kept is None or not isinstance(password, str):
            return False
        try:
            salt, expected = bytes.fromhex(kept["salt"]), bytes.fromhex(kept["hash"])
        except (KeyError, ValueError):
            return False
        return hmac.compare_digest(_hash(password[: self._settings.max_chars], salt), expected)

    def sign_in(self, role: Role, password: object) -> str | None:
        """A token for the visit when the password is right, None when it is wrong. After too
        many wrong ones in a row, LockedOut until the wait is over."""
        now = self._clock()
        wait = self._locked_until.get(role, 0.0) - now
        if wait > 0:
            raise LockedOut(wait)
        if not self._matches(role, password):
            self._wrong[role] = self._wrong.get(role, 0) + 1
            if self._wrong[role] >= self._settings.max_failures:
                self._wrong[role] = 0
                self._locked_until[role] = now + self._settings.lock_s
            return None
        self._wrong.pop(role, None)
        return self.visit(role)

    def visit(self, role: Role) -> str:
        """A token for a visit in this role, for someone whose right to it is already known."""
        token = secrets.token_urlsafe(32)
        self._visits[token] = (role, self._clock() + self._settings.session_hours * 3600)
        return token

    def role_of(self, token: object) -> Role | None:
        """The role a token was given for, while it lasts."""
        if not isinstance(token, str):
            return None
        visit = self._visits.get(token)
        if visit is None:
            return None
        if visit[1] <= self._clock():
            del self._visits[token]
            return None
        return visit[0]

    def sign_out(self, token: object) -> None:
        if isinstance(token, str):
            self._visits.pop(token, None)


def _read(path: Path) -> dict[Role, dict[str, str]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    kept: dict[Role, dict[str, str]] = {}
    for role in ROLES:
        one = data.get(role) if isinstance(data, dict) else None
        if isinstance(one, dict):
            kept[role] = {str(name): str(value) for name, value in one.items()}
    return kept


def _write(path: Path, kept: dict[Role, dict[str, str]]) -> None:
    """For the person who runs the service alone to read, and never left half written."""
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + ".partial")
    handle = os.open(partial, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(handle, "w", encoding="utf-8") as file:
        json.dump(kept, file)
    os.replace(partial, path)
