"""
Requirements Command Arguments

Defines CLI arguments for the 'requirements' command, which installs the
Python packages an app declares via `zRequirements` in its zEnv.*.zolo.
"""

import argparse


def add_subparser(subparsers) -> argparse.ArgumentParser:
    """
    Add the 'requirements' subcommand to the parser.

    Args:
        subparsers: The subparsers object from ArgumentParser

    Returns:
        The created requirements subparser
    """
    parser = subparsers.add_parser(
        "requirements",
        help="Install app-declared Python dependencies (zRequirements)",
        description=(
            "Install the Python packages an app declares via `zRequirements` "
            "in its zEnv.*.zolo file. zSpark refuses to launch until these "
            "are installed — this is the one explicit command that installs them."
        ),
    )

    parser.add_argument(
        "app_file",
        help="Path to the app's zSpark.*.zolo file (or any file inside its workspace dir)",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show missing packages without installing them",
    )

    parser.add_argument(
        "--auto-approve",
        action="store_true",
        help="Skip the install confirmation prompt",
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show bootstrap process and detailed initialization",
    )

    return parser
