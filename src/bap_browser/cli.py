"""The bap-browser command."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from bap_browser import __version__
from bap_browser.config import defaults, load_config_with_sources
from bap_browser.config_doc import reference_markdown
from bap_browser.errors import ConfigError

STARTER: dict[str, Any] = {
    "browser": {"channel": "chromium", "headless": True},
    "safety": {"allowed_domains": [], "blocked_domains": []},
}


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return args.run(args)
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bap-browser", description="A browser that AI agents can use and a person can watch."
    )
    parser.add_argument("--version", action="version", version=f"bap-browser {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)

    config = commands.add_parser("config", help="show, create or document the configuration")
    config_commands = config.add_subparsers(dest="config_command", required=True)

    show = config_commands.add_parser("show", help="print the effective configuration")
    show.add_argument("--config", help="path of config.json")
    show.add_argument("--sources", action="store_true", help="print where each overridden value came from")
    show.set_defaults(run=_config_show)

    init = config_commands.add_parser("init", help="write a starter config.json")
    init.add_argument("path", nargs="?", default="config.json")
    init.add_argument("--full", action="store_true", help="write every key with its default")
    init.set_defaults(run=_config_init)

    doc = config_commands.add_parser("doc", help="print the configuration reference")
    doc.set_defaults(run=_config_doc)
    return parser


def _config_show(args: argparse.Namespace) -> int:
    config, sources = load_config_with_sources(args.config)
    data = config.model_dump()
    if not args.sources:
        print(json.dumps(data, indent=2))
        return 0
    if not sources:
        print("Every value is at its default.")
        return 0
    for key in sorted(sources):
        value: Any = data
        for part in key.split("."):
            value = value[part]
        print(f"{key} = {json.dumps(value)}  ({sources[key]})")
    return 0


def _config_init(args: argparse.Namespace) -> int:
    path = Path(args.path)
    if path.exists():
        raise ConfigError(f"{path} already exists; it was not changed")
    content = defaults().model_dump() if args.full else STARTER
    path.write_text(json.dumps(content, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {path}")
    return 0


def _config_doc(args: argparse.Namespace) -> int:
    print(reference_markdown(), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
