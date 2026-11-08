# MIT License, Copyright (c) 2025 Nous Research. Changed only by scripts/take_hermes.py.
"""A cached computer_use backend is bound to the display it spawned on; the identity helpers notice a change."""

from __future__ import annotations

from bap_browser.computer.hermes.computer_use import cua_backend


def test_backend_display_identity_tracks_the_display_a_spawn_would_get():
    before = cua_backend.desktop_identity({"HOME": "/x"})
    after = cua_backend.desktop_identity({"HOME": "/x", "DISPLAY": ":37"})
    assert before == "" and after == ":37"
    assert cua_backend.backend_display_stale(before, after)
    assert not cua_backend.backend_display_stale(after, cua_backend.desktop_identity({"DISPLAY": ":37"}))
