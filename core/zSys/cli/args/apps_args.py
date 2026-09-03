"""
Apps Command Arguments

Defines CLI arguments for `zolo apps` — manage the hosted apps on YOUR zCloud
account from the terminal (zOS#64): list them, delete one, change visibility.
Authenticated by the machine's persisted PAT (`zolo login`).
"""

import argparse


def add_subparser(subparsers) -> argparse.ArgumentParser:
    """Add the 'apps' subcommand (with its own verb subparsers) to the parser."""
    parser = subparsers.add_parser(
        "apps",
        help="Manage your hosted zCloud apps (list / delete / set-visibility)",
        description=(
            "Account-level controls for the apps you host on zCloud — the "
            "CLI face of the MyApps dashboard. Delete is a SOFT delete "
            "(re-push revives); visibility is public|unlisted|private."
        ),
    )
    verbs = parser.add_subparsers(dest="apps_action", metavar="verb")

    def _common(p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "--url",
            help="zCloud base URL (default: https://zolo.media; "
                 "ZOLO_ZCLOUD_URL also overrides)",
        )
        p.add_argument(
            "--token",
            help="PAT to authenticate with (default: the persisted "
                 "`zolo login` identity)",
        )
        p.add_argument(
            "--verbose", "-v",
            action="store_true",
            help="Show bootstrap output",
        )

    p_list = verbs.add_parser(
        "list",
        help="Every app on your account: slug, status, visibility, URL",
    )
    _common(p_list)

    p_delete = verbs.add_parser(
        "delete",
        help="Soft-delete a hosted app (type-the-slug confirm; re-push revives)",
    )
    p_delete.add_argument("slug", help="The hosted app's slug")
    p_delete.add_argument(
        "--yes",
        action="store_true",
        help="Skip the type-the-slug confirmation (for scripts)",
    )
    _common(p_delete)

    p_vis = verbs.add_parser(
        "set-visibility",
        help="Set an app's visibility: public (zFeed) | unlisted (link-only) | private",
    )
    p_vis.add_argument("slug", help="The hosted app's slug")
    p_vis.add_argument(
        "visibility",
        choices=["public", "unlisted", "private"],
        help="public = on the zFeed; unlisted = live but link-only; private = owner-only",
    )
    _common(p_vis)

    return parser
