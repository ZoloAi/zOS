"""
Login Command Arguments

Defines CLI arguments for the 'login' command — a standalone, app-less
terminal sign-in (Tier-1 / zSession) that persists the machine's platform
identity (git-/gh-style).
"""

import argparse


def add_subparser(subparsers) -> argparse.ArgumentParser:
    """
    Add the 'login' subcommand to the parser.

    Args:
        subparsers: The subparsers object from ArgumentParser

    Returns:
        The created login subparser
    """
    parser = subparsers.add_parser(
        "login",
        help="Sign in to your zolo account (no app/instance required)",
        description=(
            "Authenticate this machine's platform identity against the user "
            "ledger and persist it. Prompts for password if not using --token."
        ),
    )

    parser.add_argument(
        "identity",
        nargs="?",
        help="Email or username (prompted if omitted)",
    )
    parser.add_argument(
        "--token",
        help="Sign in non-interactively with a Personal Access Token (PAT)",
    )
    parser.add_argument(
        "--device",
        action="store_true",
        help="Browser device-login: open a sign-in page, approve, auto-receive a token",
    )
    parser.add_argument(
        "--server",
        help="Auth server base URL for --device (default: configured server)",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show the current signed-in identity and exit",
    )
    parser.add_argument(
        "--logout",
        action="store_true",
        help="Clear the persistent session (sign out)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show bootstrap process and detailed initialization",
    )

    return parser
