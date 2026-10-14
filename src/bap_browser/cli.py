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
from bap_browser.errors import BapError, ConfigError

STARTER: dict[str, Any] = {
    "browser": {"channel": "chromium", "headless": True},
    "safety": {"allowed_domains": [], "blocked_domains": []},
}


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    # Settings and secrets come from the environment, and from a .env file in the folder the command is run in.
    apply_env_file(Path(".env"))
    try:
        return args.run(args)
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def build_parser() -> argparse.ArgumentParser:
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
    show.add_argument(
        "--tools", action="store_true", help="print the tools on offer and the one value that stands for them"
    )
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
    serve.add_argument(
        "--desktop",
        action="store_true",
        help="serve the desktop of computer use instead of a browser: its computer_* tools and its picture",
    )
    serve.set_defaults(run=_serve)

    studio = commands.add_parser(
        "studio",
        help="one window with the three browsers an agent can work in: the cloud browser, your own "
        "Chrome and the built-in browser, each with its chat",
    )
    studio.add_argument("--config", help="path of config.json")
    studio.add_argument("--open", action="store_true", help="open the window in your browser")
    only = studio.add_mutually_exclusive_group()
    only.add_argument(
        "--browser",
        action="store_true",
        help="only the three browsers and computer use, with none of the admin's own tools",
    )
    only.add_argument(
        "--desktop",
        action="store_true",
        help="only the desktop app's own browser and computer use, for the desktop app itself to start",
    )
    studio.set_defaults(run=_studio)

    computer = commands.add_parser(
        "computer", help="the driver of computer use: install it, see what is missing, allow it on macOS"
    )
    computer_commands = computer.add_subparsers(dest="computer_command", required=True)
    install = computer_commands.add_parser("install", help="install the pinned driver for this system")
    install.add_argument("--config", help="path of config.json")
    install.set_defaults(run=_computer)
    its_doctor = computer_commands.add_parser("doctor", help="what the driver says is ready, check by check")
    its_doctor.add_argument("--config", help="path of config.json")
    its_doctor.add_argument("--json", action="store_true", help="print the report as JSON")
    its_doctor.set_defaults(run=_computer)
    permissions = computer_commands.add_parser(
        "permissions", help="whether the driver is ready; `grant` has macOS ask for what is missing"
    )
    permissions.add_argument("what", nargs="?", choices=["status", "grant"], default="status")
    permissions.add_argument("--config", help="path of config.json")
    permissions.set_defaults(run=_computer)
    its_helper = computer_commands.add_parser(
        "helper",
        help="on a person's own machine: let an engine elsewhere drive it, over the tailnet, with a pairing code",
    )
    its_helper.add_argument("--config", help="path of config.json")
    its_helper.add_argument(
        "--this-machine-alone",
        action="store_true",
        help="take calls from this machine only, not from the tailnet",
    )
    its_helper.set_defaults(run=_computer)
    its_chat = computer_commands.add_parser(
        "chat",
        help="on a person's own machine: keep the chat of a service above every other app, at the screen's edge",
    )
    its_chat.add_argument("service", help="the service's address, for example https://vm.your-tailnet.ts.net")
    its_chat.add_argument("--page", default="computer", help="the page whose chat it is (default: computer)")
    its_chat.add_argument("--config", help="path of config.json")
    its_chat.set_defaults(run=_computer)

    doctor = commands.add_parser(
        "doctor", help="check that this machine has what bap-browser needs, and which browsers launch here"
    )
    doctor.add_argument("--config", help="path of config.json")
    doctor.set_defaults(run=_doctor)

    bench = commands.add_parser(
        "bench", help="time each line of the performance budget and say how it stands (spec 11)"
    )
    bench.add_argument("--config", help="path of config.json")
    bench.add_argument(
        "--browsers",
        default=None,
        help="the browsers to run on, by channel and with commas: chromium,chrome,msedge "
        "(default: the configured one)",
    )
    bench.add_argument("--only", action="append", default=[], help="run this line only; may be repeated")
    bench.set_defaults(run=_bench)

    sets = commands.add_parser(
        "sets", help="run task sets in a browser with no window, and keep their reports (spec 12.7)"
    )
    sets.add_argument("names", nargs="+", help="the sets to run: short, confirm, attack, long")
    sets.add_argument("--trials", type=int, default=1, help="how many times each task is tried (default: 1)")
    sets.add_argument(
        "--reference", action="store_true", help="do each task by its reference solution, with no model"
    )
    sets.add_argument("--config", help="path of config.json")
    sets.set_defaults(run=_sets)

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
    agent.add_argument(
        "--takeover",
        action="store_true",
        help="with --chat: the agent works in a tab of your own Chrome, through the BAP extension",
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
    if args.tools:
        # Imported here so that the other config commands start without loading the tools.
        from bap_browser.tools import tools_for
        from bap_browser.tools.registry import tools_hash

        offered = tools_for(config)
        print(f"tools = {tools_hash(offered)}")
        for tool in offered:
            print(tool.name)
        return 0
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


def _computer(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    # Imported here so that the other commands start without loading computer use.
    from bap_browser.computer import commands

    if args.computer_command == "install":
        return commands.install(config)
    if args.computer_command == "doctor":
        return commands.doctor(config, as_json=args.json)
    if args.computer_command == "chat":
        from bap_browser.agent.window import desktop_app_of

        try:
            return desktop_app_of(config).chat_beside_until_closed(
                args.service, args.page, config.server.side_chat_width
            )
        except BapError as wrong:
            raise ConfigError(str(wrong)) from wrong
        except KeyboardInterrupt:
            return 0
    if args.computer_command == "helper":
        # Imported here: only the helper needs the web server.
        from bap_browser.service.machine_helper import run_helper

        with contextlib.suppress(KeyboardInterrupt):
            return run_helper(config, this_machine_alone=args.this_machine_alone)
        return 0
    return commands.permissions(config, grant=args.what == "grant")


def _doctor(args: argparse.Namespace) -> int:
    config, sources = load_config_with_sources(args.config)
    # Imported here so that the config commands start without loading the browser library.
    from bap_browser import doctor

    found = asyncio.run(doctor.examine(config, sources, os.environ))
    print(doctor.report(found))
    return 0 if doctor.healthy(found) else 1


def _bench(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    # Imported here so that the config commands start without loading the browser library.
    from bap_browser.bench import runner

    lines = runner.load_budget(Path(config.bench.budget_file))
    unknown = [name for name in args.only if name not in {line.id for line in lines}]
    if unknown:
        raise ConfigError(f"the budget has no line {', '.join(unknown)}")
    browsers = args.browsers.split(",") if args.browsers else [config.browser.channel]
    results = Path(config.bench.results_dir)
    before = runner.failed_before(results)
    measured = asyncio.run(runner.run(config, lines, browsers, args.only))
    print(runner.report(measured))
    print(f"Written to {runner.save(measured, results)}", file=sys.stderr)
    counted = runner.blocking(measured, before)
    if counted:
        # A failure counts once it has been seen in two runs one after the other (spec 11.2).
        named = ", ".join(f"{m.line} on {m.browser}" for m in counted)
        print(f"Failed in this run and the one before: {named}", file=sys.stderr)
    return 1 if counted else 0


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
        asyncio.run(run_http(config, open_viewer=args.open, desktop=args.desktop))
    # It runs until it is interrupted, so that is how it always ends.
    return 130


def extension_folder(config: Config) -> Path:
    """Where the extension is put for a person to load into their Chrome. A folder a file chooser
    shows: one whose name begins with a dot is hidden from it."""
    return Path(config.server.extension_dir).expanduser().resolve()


def _key_for_the_model(config: Config) -> str:
    """The key of the hosted model, from the environment or from `.env`. Without one, says how to set it."""
    if config.agent.provider == "scripted":
        raise ConfigError("the scripted model only plays the demonstration. Run: bap-browser agent --demo")
    name = config.agent.api_key_env
    key = os.environ.get(name, "").strip()
    if not key:
        raise ConfigError(
            f"{name} is not set. Put a line {name}=... in a file named .env in this folder, or set it "
            "in the environment. To try without a model: bap-browser agent --demo"
        )
    return key


def _sets(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    key = "" if args.reference else _key_for_the_model(config)
    from bap_browser.agent.anthropic_model import AnthropicModel
    from bap_browser.agent.openai_model import OpenAIModel
    from bap_browser.agent.sets_command import run_sets
    from bap_browser.safeguards.model import ModelClient

    def hosted(service):
        client = ModelClient(config.agent, config.safeguards.model, key, "loop")
        if config.agent.provider == "anthropic":
            return AnthropicModel(config.agent, client)
        return OpenAIModel(config.agent, client)

    logging.basicConfig(level=config.logging.level, stream=sys.stderr)
    asyncio.run(
        run_sets(
            config,
            hosted,
            args.names,
            trials=args.trials,
            mode="reference" if args.reference else "agent",
            tell=print,
        )
    )
    return 0


def _studio(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    key = _key_for_the_model(config)
    # Imported here so that the config commands start without loading the browser and the web server.
    from bap_browser import browser_extension
    from bap_browser.agent.anthropic_model import AnthropicModel
    from bap_browser.agent.command import Interrupted
    from bap_browser.agent.openai_model import OpenAIModel
    from bap_browser.agent.window import run_studio
    from bap_browser.safeguards.model import ModelClient

    def hosted(service):
        client = ModelClient(config.agent, config.safeguards.model, key, "loop")
        if config.agent.provider == "anthropic":
            return AnthropicModel(config.agent, client)
        return OpenAIModel(config.agent, client)

    extension = browser_extension.install(extension_folder(config))
    rooms_mode = "browser" if args.browser else "desktop" if args.desktop else "full"
    logging.basicConfig(level=config.logging.level, stream=sys.stderr)
    with contextlib.suppress(Interrupted, KeyboardInterrupt):
        asyncio.run(
            run_studio(
                config,
                hosted,
                open_viewer=args.open,
                extension=extension,
                rooms_mode=rooms_mode,
            )
        )
    # It runs until it is interrupted, so that is how it always ends.
    return 130


def _agent(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    extension: Path | None = None
    if args.takeover:
        if not args.chat or args.extension or args.show_browser:
            raise ConfigError(
                "taking over your own Chrome goes with the chat, and with no browser of the agent's own. "
                "Use: bap-browser agent --chat --takeover"
            )
        from bap_browser import browser_extension

        extension = browser_extension.install(extension_folder(config))
    elif args.extension:
        if not args.chat:
            raise ConfigError("the extension shows the chat. Use --extension together with --chat")
        from bap_browser import browser_extension

        # Beside the file that says where the service is: both are this machine's own state.
        extension = browser_extension.install(extension_folder(config))
        config = browser_extension.with_extension(with_visible_browser(config), extension)
    elif args.show_browser:
        config = with_visible_browser(config)
    # Imported here so that the config commands start without loading the browser and the web server.
    from bap_browser.agent.command import Interrupted, run_with_viewer
    from bap_browser.agent.loop import Unfinished
    from bap_browser.agent.models import Model
    from bap_browser.errors import ModelError
    from bap_browser.service.server import Service

    model_for: Callable[[Service], Model]
    if args.demo:
        from bap_browser.agent.demo import TASK, demo_script

        task = args.task or TASK

        def scripted(service: Service) -> Model:
            return demo_script(f"{service.address}/demo-site", args.pace)

        model_for = scripted
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
        from bap_browser.agent.anthropic_model import AnthropicModel
        from bap_browser.agent.openai_model import OpenAIModel
        from bap_browser.safeguards.model import ModelClient

        task = args.task

        def hosted(service):
            client = ModelClient(config.agent, config.safeguards.model, key, "loop")
            if config.agent.provider == "anthropic":
                return AnthropicModel(config.agent, client)
            return OpenAIModel(config.agent, client)

        model_for = hosted

    logging.basicConfig(level=config.logging.level, stream=sys.stderr)
    try:
        if args.chat:
            if args.demo:
                raise ConfigError("the demonstration plays one fixed task. Use --chat without --demo")
            from bap_browser.agent.command import chat_with_viewer

            if args.takeover and extension is not None:
                from bap_browser.agent.command import chat_in_own_chrome

                asyncio.run(chat_in_own_chrome(config, model_for, first_task=task, extension=extension))
                return 0
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
