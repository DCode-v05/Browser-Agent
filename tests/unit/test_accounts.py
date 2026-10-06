"""Who may sign in, and as what (spec 4.11): the admin and the user, each with a password of which
only a salted hash is kept."""

import json
import stat
from collections.abc import Callable
from pathlib import Path

import pytest

from bap_browser.config import Config
from bap_browser.service.accounts import Accounts, BadPassword, LockedOut

MakeConfig = Callable[..., Config]
ADMINS, USERS = "the admin's own words", "what users sign in with"


class Clock:
    def __init__(self) -> None:
        self.now = 1_791_300_000.0

    def __call__(self) -> float:
        return self.now


def accounts_in(
    make_config: MakeConfig, tmp_path: Path, clock: Clock | None = None
) -> tuple[Config, Accounts]:
    config = make_config(tmp_path)
    return config, Accounts(config.auth, clock or Clock())


def test_nobody_signs_in_before_a_password_is_set(make_config: MakeConfig, tmp_path: Path) -> None:
    _, accounts = accounts_in(make_config, tmp_path)
    assert not accounts.has("admin") and not accounts.has("user")
    assert accounts.sign_in("admin", "") is None and accounts.sign_in("admin", ADMINS) is None
    assert accounts.role_of("anything") is None and accounts.role_of(None) is None


def test_signing_in_gives_a_token_for_the_visit_in_that_role(make_config: MakeConfig, tmp_path: Path) -> None:
    _, accounts = accounts_in(make_config, tmp_path)
    accounts.set_password("admin", ADMINS)
    accounts.set_password("user", USERS)
    admin, user = accounts.sign_in("admin", ADMINS), accounts.sign_in("user", USERS)
    assert admin and user and admin != user and len(admin) >= 32
    assert accounts.role_of(admin) == "admin" and accounts.role_of(user) == "user"
    # One role's password opens nothing of the other's.
    assert accounts.sign_in("admin", USERS) is None and accounts.sign_in("user", ADMINS) is None
    # Fewer tries than hold sign-in back: that is another test's matter.
    for wrong in ("", ADMINS + " ", None):
        assert accounts.sign_in("admin", wrong) is None
    accounts.sign_out(user)
    assert accounts.role_of(user) is None and accounts.role_of(admin) == "admin"


def test_only_a_salted_hash_is_kept_for_the_person_alone_to_read(
    make_config: MakeConfig, tmp_path: Path
) -> None:
    config, accounts = accounts_in(make_config, tmp_path)
    accounts.set_password("admin", ADMINS)
    accounts.set_password("user", ADMINS)
    file = Path(config.auth.file)
    kept = json.loads(file.read_text(encoding="utf-8"))
    assert ADMINS not in file.read_text(encoding="utf-8")
    assert set(kept) == {"admin", "user"} and set(kept["admin"]) == {"salt", "hash"}
    # The same password twice is not the same hash: each has a salt of its own.
    assert kept["admin"]["hash"] != kept["user"]["hash"]
    assert stat.S_IMODE(file.stat().st_mode) == 0o600
    # It is there the next time the service starts. A visit is not: it lives in memory.
    visit = accounts.sign_in("admin", ADMINS)
    later = Accounts(config.auth)
    assert later.has("admin") and later.sign_in("admin", ADMINS) and later.role_of(visit) is None


@pytest.mark.parametrize("password", ["", "short", "1234567", None, 12345678, "x" * 201])
def test_a_password_that_is_too_short_or_too_long_is_not_taken(
    make_config: MakeConfig, tmp_path: Path, password: object
) -> None:
    _, accounts = accounts_in(make_config, tmp_path)
    with pytest.raises(BadPassword, match=r"Use at (least 8|most 200) characters"):
        accounts.set_password("admin", password)
    assert not accounts.has("admin")


def test_too_many_wrong_passwords_hold_sign_in_back_for_a_while(
    make_config: MakeConfig, tmp_path: Path
) -> None:
    clock = Clock()
    config, accounts = accounts_in(make_config, tmp_path, clock)
    accounts.set_password("admin", ADMINS)
    accounts.set_password("user", USERS)
    for _ in range(config.auth.max_failures):
        assert accounts.sign_in("admin", "a guess at it") is None
    with pytest.raises(LockedOut) as locked:
        accounts.sign_in("admin", ADMINS)
    assert 0 < locked.value.wait_s <= config.auth.lock_s
    # The right password does not open it either, until the wait is over. The other role is not held.
    assert accounts.sign_in("user", USERS)
    clock.now += config.auth.lock_s + 1
    assert accounts.sign_in("admin", ADMINS)
    # A right password in between starts the count again.
    for _ in range(config.auth.max_failures - 1):
        assert accounts.sign_in("admin", "another guess") is None
    assert accounts.sign_in("admin", ADMINS)
    for _ in range(config.auth.max_failures - 1):
        assert accounts.sign_in("admin", "another guess") is None
    assert accounts.sign_in("admin", ADMINS)


def test_a_visit_runs_out_and_a_new_password_ends_the_visits_made_with_the_old(
    make_config: MakeConfig, tmp_path: Path
) -> None:
    clock = Clock()
    config, accounts = accounts_in(make_config, tmp_path, clock)
    accounts.set_password("admin", ADMINS)
    accounts.set_password("user", USERS)
    admin, user = accounts.sign_in("admin", ADMINS), accounts.sign_in("user", USERS)
    clock.now += config.auth.session_hours * 3600 - 1
    assert accounts.role_of(admin) == "admin"
    late = accounts.sign_in("user", USERS)
    clock.now += 2
    assert accounts.role_of(admin) is None and accounts.role_of(user) is None
    assert accounts.role_of(late) == "user"
    # The admin gives users a new password: whoever signed in with the old one signs in again.
    admin = accounts.sign_in("admin", ADMINS)
    accounts.set_password("user", "a new one for the users")
    assert accounts.role_of(late) is None and accounts.role_of(admin) == "admin"
    assert accounts.sign_in("user", USERS) is None
    assert accounts.sign_in("user", "a new one for the users")


def test_a_file_that_cannot_be_read_holds_no_account(make_config: MakeConfig, tmp_path: Path) -> None:
    config = make_config(tmp_path)
    for spoiled in ("{not json", "[]", '{"admin": "a string", "user": {"salt": "zz", "hash": "zz"}}'):
        Path(config.auth.file).write_text(spoiled, encoding="utf-8")
        accounts = Accounts(config.auth)
        assert not accounts.has("admin")
        # A record that is there and makes no sense opens nothing.
        assert accounts.sign_in("user", "anything at all") is None
