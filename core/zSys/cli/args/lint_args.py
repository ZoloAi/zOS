"""
Lint Command Arguments

Defines CLI arguments for the 'lint' command, which runs the same static
fault checks the strict boot gate enforces (zOS#84) — standalone, no boot.
"""

import argparse


def add_subparser(subparsers) -> argparse.ArgumentParser:
    """
    Add the 'lint' subcommand to the parser.

    Args:
        subparsers: The subparsers object from ArgumentParser

    Returns:
        The created lint subparser
    """
    parser = subparsers.add_parser(
        "lint",
        help="Statically check an app's .zolo files for faults (same checks as strict boot)",
        description=(
            "Walk every authored .zolo file in the app and report statically-"
            "detectable faults: parse/comment anomalies, duplicate sibling "
            "blocks, zShuttle reels/patterns that don't exist, %tokens in "
            "_zClass, unknown onSuccess verbs. These are the exact checks the "
            "strict boot gate enforces — lint is the no-boot way to see them."
        ),
    )

    parser.add_argument(
        "app_file",
        nargs="?",
        default=".",
        help="Path to the app's zSpark.*.zolo file, the app dir, or any file inside it (default: cwd)",
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show every file checked, not only the faulty ones",
    )

    return parser
