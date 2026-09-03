"""
Push Command Arguments

Defines CLI arguments for `zolo push` — ship a zProject (distribution manifest)
to zCloud, authenticated by the machine's persisted PAT (`zolo login`).
"""

import argparse


def add_subparser(subparsers) -> argparse.ArgumentParser:
    """Add the 'push' subcommand to the parser."""
    parser = subparsers.add_parser(
        "push",
        help="Ship a zProject to your zCloud account",
        description=(
            "Resolve a zProject.<name>.zolo manifest, bundle its app slice "
            "(+ optional dormant attachments), and upload it to zCloud. The "
            "server binds the app to your account (owner_id) via your PAT."
        ),
    )

    parser.add_argument(
        "project",
        nargs="?",
        help="zProject name (e.g. 'hello') or a project folder; "
             "omit to use the single zProject in the current directory",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would ship (slug, spark, file plan) without uploading",
    )
    parser.add_argument(
        "--slug",
        help="Override the zApps slug declared in the manifest",
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
        "--replace-data",
        action="store_true",
        dest="replace_data",
        help="Confirm a push that removes Data/ files present in the live hosted "
             "build (every push is a full replace; `ignore` does NOT preserve "
             "hosted files — without this flag such a push is refused)",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip the first-public-push confirmation prompt (for scripts)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="List every shipped file and show bootstrap output",
    )

    return parser
