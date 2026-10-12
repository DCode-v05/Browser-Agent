# Taken from NousResearch/hermes-agent at 3569e846: tests/computer_use/test_cua_perf_knobs.py
# MIT License, Copyright (c) 2025 Nous Research. Changed only by scripts/take_hermes.py.
"""Behavior contracts for computer_use latency knobs."""


from bap_browser.computer.hermes.computer_use import tool as cu_tool


def test_aux_vision_route_follows_a_config_change_without_restart(monkeypatch):
    """The capture route reads the signature-cached config on every capture, so an ``image_input_mode`` edit
    (or /model, or a profile switch) applies to the next screenshot instead of a per-process verdict."""
    cfg = {"agent": {"image_input_mode": "native"}}
    monkeypatch.setattr("bap_browser.computer.seams.vision.read_main_provider", lambda: "anthropic")
    monkeypatch.setattr("bap_browser.computer.seams.vision.read_main_model", lambda: "claude-opus-4-5")
    monkeypatch.setattr("bap_browser.computer.seams.settings.load_config_readonly", lambda: cfg)
    monkeypatch.setattr("agent.image_routing._lookup_supports_vision", lambda *a, **k: True)
    monkeypatch.setattr("bap_browser.computer.seams.vision._profile_rejects_tool_media", lambda *a, **k: False)

    assert cu_tool._should_route_through_aux_vision() is False
    cfg["agent"]["image_input_mode"] = "text"
    assert cu_tool._should_route_through_aux_vision() is True
