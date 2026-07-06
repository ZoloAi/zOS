"""CLI arguments for the `z agents` command."""

import argparse


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "agents",
        help="Inject zolo agent instructions into the current workspace",
        description=(
            "Detects your IDE/tooling and copies the right zolo instruction files "
            "(.mdc rules, AGENTS.md, CLAUDE.md, etc.) into the current directory."
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files even if already up to date",
    )
    parser.add_argument(
        "--assoc",
        action="store_true",
        help="(macOS) Install .zolo file association so double-clicking launches z",
    )
    parser.add_argument(
        "--build",
        action="store_true",
        help="(dev) Rebuild generated/ from src/*.md before distributing",
    )
