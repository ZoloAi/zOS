"""
z demos — list and inspect zOS reference demo apps.

z demos                          List all available demos
z demos <name>                   Show detail for a specific demo
z demos <name> --clone --name x  Clone demo into cwd as a new app
"""

import argparse


def add_subparser(subparsers) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "demos",
        help="List and inspect zOS reference demo apps",
        description="Browse zDemos — reference apps built on zOS",
    )

    parser.add_argument(
        "name",
        nargs="?",
        metavar="DEMO",
        help="Demo name (e.g. zCRM). Omit to list all.",
    )

    parser.add_argument(
        "--clone",
        action="store_true",
        help="Clone the demo into cwd as a starting point (requires --name)",
    )

    parser.add_argument(
        "--name",
        dest="new_name",
        metavar="APPNAME",
        help="Name for the cloned app (used with --clone)",
    )

    parser.add_argument(
        "--dest",
        metavar="PATH",
        help="Destination directory for clone (default: cwd)",
    )

    return parser
