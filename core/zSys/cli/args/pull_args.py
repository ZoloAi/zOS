"""
Pull Command Arguments

Defines CLI arguments for `zolo pull` — clone one of YOUR hosted apps from
zCloud back to a local working copy (source by default; live data opt-in),
authenticated by the machine's persisted PAT (`zolo login`).
"""

import argparse


def add_subparser(subparsers) -> argparse.ArgumentParser:
    """Add the 'pull' subcommand to the parser."""
    parser = subparsers.add_parser(
        "pull",
        help="Clone one of your hosted apps to a local folder",
        description=(
            "Download the live build of an app you own into ./<slug>/ (or "
            "--dest), receipt-linked so `zolo push` from that folder continues "
            "the SAME hosted app. Data/ stays on the server unless --with-data."
        ),
    )

    parser.add_argument(
        "slug",
        help="The hosted app's slug (as shown in MyApps / the push receipt)",
    )
    parser.add_argument(
        "--with-data",
        action="store_true",
        dest="with_data",
        help="Also pull the live Data/ snapshot (point-in-time copy of LIVE "
             "data — pushing it later overwrites anything written since)",
    )
    parser.add_argument(
        "--dest",
        help="Destination folder (default: ./<slug>/; refused if not empty)",
    )
    parser.add_argument(
        "--url",
        help="zCloud base URL (default: https://zolo.media; ZOLO_ZCLOUD_URL also overrides)",
    )
    parser.add_argument(
        "--token",
        help="PAT to authenticate with (default: the persisted `zolo login` identity)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show bootstrap output",
    )

    return parser
