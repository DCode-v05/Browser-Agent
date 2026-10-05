"""The bap-browser command."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import logging
import os
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from bap_browser import __version__
from bap_browser.config import Config, defaults, load_config, load_config_with_sources
from bap_browser.config_doc import reference_markdown
from bap_browser.env_file import apply_env_file
from bap_browser.errors import ConfigError

STARTER: dict[str, Any] = {
    "browser": {"channel": "chromium", "headless": True},
    "safety": {"allowed_domains": [], "blocked_domains": []},
}


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    # Settings and secrets come from the environment, and from a .env file in the folder the command is run in.
    apply_env_file(Path(".env"))
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

    mcp = commands.add_parser("mcp", help="serve the browser tools over MCP on stdio, for an agent to start")
    mcp.add_argument("--config", help="path of config.json")
    mcp.set_defaults(run=_mcp)

    serve = commands.add_parser(
        "serve", help="serve the browser tools over MCP on HTTP, with the viewer, for an agent elsewhere"
    )
    serve.add_argument("--config", help="path of config.json")
    serve.add_argument("--open", action="store_true", help="open the viewer in your browser")
    serve.add_argument(
        "--show-browser",
        action="store_true",
        help="run the browser in a window on this screen, so the agent is seen working in it",
    )
    serve.set_defaults(run=_serve)

    agent = commands.add_parser(
        "agent", help="run the reference agent on a task, with the viewer to watch and control it"
    )
    agent.add_argument("task", nargs="?", help="what the agent should do")
    agent.add_argument("--config", help="path of config.json")
    agent.add_argument(
        "--demo",
        action="store_true",
        help="sign up on the built-in demo site with a scripted model; needs no key",
    )
    agent.add_argument(
        "--pace",
        type=float,
        default=1.0,
        help="seconds the demonstration waits before each step, for a person watching (default 1)",
    )
    agent.add_argument(
        "--wait-for-viewer", action="store_true", help="start the task only once a viewer has connected"
    )
    agent.add_argument(
        "--open", action="store_true", help="open the viewer in your browser, and wait for it to connect"
    )
    agent.add_argument(
        "--exit-when-done",
        action="store_true",
        help="end when the task is finished, instead of keeping the viewer open",
    )
    agent.add_argument(
        "--chat",
        action="store_true",
        help="keep the session open and take tasks from the chat in the viewer, one after another",
    )
    agent.add_argument(
        "--show-browser",
        action="store_true",
        help="run the browser in a window on this screen, so the agent is seen working in it",
    )
    agent.add_argument(
        "--extension",
        action="store_true",
        help="with --chat: show the browser with the BAP extension in it, the chat in its side panel",
    )
    agent.set_defaults(run=_agent)
    return parser


def with_visible_browser(config: Config) -> Config:
    """The same configuration with the browser in a window a person can watch, the page as large as
    that window."""
    browser = config.browser.model_copy(update={"headless": False, "viewport": None})
    return config.model_copy(update={"browser": browser})


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


def _mcp(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    # Standard output carries the protocol, so everything else goes to the error stream.
    logging.basicConfig(level=config.logging.level, stream=sys.stderr)
    # Imported here so that the config commands start without loading the browser and MCP libraries.
    from bap_browser.mcp.server import run_stdio

    asyncio.run(run_stdio(config))
    return 0


def _serve(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    if args.show_browser:
        config = with_visible_browser(config)
    # Imported here so that the config commands start without loading the browser and the web server.
    from bap_browser.mcp.server import run_http

    logging.basicConfig(level=config.logging.level, stream=sys.stderr)
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(run_http(config, open_viewer=args.open))
    # It runs until it is interrupted, so that is how it always ends.
    return 130


def _agent(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    extension: Path | None = None
    if args.extension:
        if not args.chat:
            raise ConfigError("the extension shows the chat. Use --extension together with --chat")
        from bap_browser import browser_extension

        # Beside the file that says where the service is: both are this machine's own state.
        extension = browser_extension.install(Path(config.server.state_file).resolve().parent / "extension")
        config = browser_extension.with_extension(with_visible_browser(config), extension)
    elif args.show_browser:
        config = with_visible_browser(config)
    # Imported here so that the config commands start without loading the browser and the web server.
    from bap_browser.agent.command import Interrupted, run_with_viewer
    from bap_browser.agent.loop import Unfinished
    from bap_browser.agent.models import Model, ModelError
    from bap_browser.service.server import Service

    model_for: Callable[[Service], Model]
    if args.demo:
        from bap_browser.agent.demo import TASK, demo_script

        task = args.task or TASK
        model_for = lambda service: demo_script(f"{service.address}/demo-site", args.pace)  # noqa: E731
    else:
        if not args.task and not args.chat:
            raise ConfigError(
                'say what the agent should do, for example: bap-browser agent "Find the opening hours", '
                "or run the demonstration: bap-browser agent --demo"
            )
        if config.agent.provider == "scripted":
            raise ConfigError(
                "the scripted model only plays the demonstration. Run: bap-browser agent --demo"
            )
        name = config.agent.api_key_env
        key = os.environ.get(name, "").strip()
        if not key:
            raise ConfigError(
                f"{name} is not set. Put a line {name}=... in a file named .env in this folder, or set it "
                "in the environment. To try without a model: bap-browser agent --demo"
            )
        from bap_browser.agent.openai_model import OpenAIModel

        task = args.task
        model_for = lambda service: OpenAIModel(config.agent, key)  # noqa: E731

    logging.basicConfig(level=config.logging.level, stream=sys.stderr)
    try:
        if args.chat:
            if args.demo:
                raise ConfigError("the demonstration plays one fixed task. Use --chat without --demo")
            from bap_browser.agent.command import chat_with_viewer

            asyncio.run(
                chat_with_viewer(
                    config, model_for, first_task=task, open_viewer=args.open, extension=extension
                )
            )
            return 0
        asyncio.run(
            run_with_viewer(
                config,
                task,
                model_for,
                exit_when_done=args.exit_when_done,
                wait_for_viewer=args.wait_for_viewer,
                open_viewer=args.open,
            )
        )
    except (Interrupted, KeyboardInterrupt):
        return 130
    except (ModelError, Unfinished) as stopped:
        print(f"error: {stopped}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
