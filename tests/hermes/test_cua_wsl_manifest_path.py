# Taken from NousResearch/hermes-agent at 3569e846: tests/computer_use/test_cua_wsl_manifest_path.py
# MIT License, Copyright (c) 2025 Nous Research. Changed only by scripts/take_hermes.py.
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import patch

from bap_browser.computer.hermes.computer_use import cua_backend
from bap_browser.computer.hermes.computer_use import cua_backend_driver


def test_wsl_windows_manifest_path_translates_to_drvfs():
    with patch("bap_browser.computer.seams.home.is_wsl", return_value=True):
        assert cua_backend_driver._wsl_windows_path_to_posix(
            r"C:\Users\Fernando\AppData\Local\cua-driver\cua-driver.exe"
        ) == "/mnt/c/Users/Fernando/AppData/Local/cua-driver/cua-driver.exe"






def test_resolve_mcp_invocation_normalizes_windows_manifest_command_in_wsl():
    manifest = {
        "mcp_invocation": {
            "command": r"C:\Users\Fernando\AppData\Local\cua-driver\cua-driver.exe",
            "args": ["mcp"],
        }
    }
    proc = SimpleNamespace(returncode=0, stdout=json.dumps(manifest))
    with (
        patch.object(cua_backend.subprocess, "run", return_value=proc),
        patch("bap_browser.computer.seams.home.is_wsl", return_value=True),
    ):
        command, args = cua_backend_driver._resolve_mcp_invocation("cua-driver")

    assert command == "/mnt/c/Users/Fernando/AppData/Local/cua-driver/cua-driver.exe"
    assert args == ["mcp"]
