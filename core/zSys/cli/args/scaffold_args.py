"""CLI arguments for the `zolo scaffold` command."""

import argparse


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "scaffold",
        help="Scaffold a new zolo app from confirmed templates",
        description=(
            "Creates a new app directory with confirmed zSpark, routes, templates, "
            "UI stub, schema stub, zRaven stub, and empty Data/plugins/static folders. "
            "Never write zSpark/routes/zVaF.html by hand — always scaffold first."
        ),
    )
    parser.add_argument(
        "appname",
        help="App name (lowercase, no spaces) — e.g. crm, invoices, dashboard",
    )
    parser.add_argument(
        "--title",
        default=None,
        help="Human-readable app title (defaults to capitalized appname)",
    )
    parser.add_argument(
        "--dest",
        default=None,
        help="Destination directory (defaults to AGENT_GEN_DEMOS/<appname> or ./<appname>)",
    )
