"""Keys, tokens and passwords never reach the repository: git ignores every file that holds one,
wherever it is put, and keeps the template that holds none."""

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]

KEPT_OUT = [
    ".env",
    ".env.local",
    ".env.production",
    "deploy/.env",
    "config.json",
    ".bap-browser/accounts.json",
    ".bap-browser/service.json",
    ".bap-browser/helper.json",
    ".bap-browser/start-helper.command",
    "remote-service.json",
    "serve.json",
    "server.pem",
    "deploy/tls.key",
    "certificate.p12",
    "signing.pfx",
    "id_rsa",
    "id_ed25519",
    "id_ed25519.pub",
    "secrets/openai.txt",
    "credentials.json",
    "tailscale.key",
]


def ignored(path: str) -> bool:
    return (
        subprocess.run(["git", "check-ignore", "-q", "--no-index", path], cwd=ROOT, check=False).returncode
        == 0
    )


@pytest.mark.parametrize("path", KEPT_OUT)
def test_a_file_that_holds_a_secret_is_never_committed(path: str) -> None:
    assert ignored(path), f"{path} could be committed"


def test_the_template_that_holds_no_secret_is_kept() -> None:
    assert not ignored(".env.example")
