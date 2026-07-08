"""
zRaven Command Arguments

z raven --gen               Generate tests from current UI (archives previous)
z raven --gen zVaF          Generate from zSpark.zVaF.zolo when multiple sparks exist
z raven --gen --v v1.0.0    Generate tests from a UI backup snapshot
z raven --run               Boot spark + run active raven (auto-detects single spark)
z raven --run crm_cli       Boot zSpark.crm_cli.zolo when multiple sparks exist in cwd
z raven --run --r 2         Boot spark + run archived raven r2
z raven --run --v 1.0.0     Boot spark + run latest raven for UI v1.0.0
z raven --run --v 1.0.0 --r 1  Exact coordinate: UI v1.0.0 + raven r1
z raven --hint              Analyze past run history and surface actionable hints
"""

import argparse


def add_subparser(subparsers) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "raven",
        help="Generate and run zRaven test files",
        description="Generate structural zRaven tests from zUI definitions, and run them",
    )

    parser.add_argument(
        "--gen",
        nargs="?",
        const=True,
        default=False,
        metavar="SPARK_NAME",
        help=(
            "Generate zRaven file from current (or versioned) zUI. "
            "Optionally pass the middle value of zSpark.<name>.zolo "
            "to select a specific spark when multiple exist in cwd "
            "(e.g. --gen zVaF to use zSpark.zVaF.zolo)."
        ),
    )

    parser.add_argument(
        "--run",
        nargs="?",
        const=True,
        default=False,
        metavar="SPARK_NAME",
        help=(
            "Boot the spark and run zRaven tests. "
            "Optionally pass the middle value of zSpark.<name>.zolo "
            "to select a specific spark when multiple exist in cwd "
            "(e.g. --run crm_cli to use zSpark.crm_cli.zolo)."
        ),
    )

    parser.add_argument(
        "--hint",
        action="store_true",
        help="Analyze past run history and surface actionable hints",
    )

    parser.add_argument(
        "--commit",
        nargs="?",
        const=True,
        default=False,
        metavar="LABEL",
        help=(
            "Archive a milestone snapshot of the current flow (spark + raven) "
            "under zVersions/commits/. Optionally pass a short label."
        ),
    )

    parser.add_argument(
        "--clear",
        nargs="?",
        const=True,
        default=False,
        metavar="FLOW_NAME",
        help=(
            "Remove committed _zSpark.<flow>.zolo dev flows (+ paired raven + shots) "
            "from the working tree, and any orphaned zShots/ folders. Only clears a "
            "flow with a matching commit whose snapshot matches the working copy. "
            "Optionally scope to one flow name; default scans every _zSpark.*.zolo in cwd."
        ),
    )

    parser.add_argument(
        "--revive",
        nargs="?",
        const=True,
        default=False,
        metavar="FLOW_NAME",
        help=(
            "Restore a flow's own spark+raven files from a zCommit back into "
            "the working tree. Pass a flow name to revive its latest commit "
            "(add --r N to target commit cN instead); omit the name to list "
            "available commits across the project."
        ),
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help=(
            "--commit: archive even if the flow's last run didn't pass. "
            "--clear: clear a dev flow even if it drifted from its last commit. "
            "--revive: overwrite working files that diverged from the target commit."
        ),
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="--clear: print what would be removed without deleting anything",
    )

    parser.add_argument(
        "--spark",
        metavar="SPARK_FILE",
        help="Path to zSpark file (default: auto-detect in cwd)",
    )

    parser.add_argument(
        "--v",
        metavar="UI_VERSION",
        dest="ui_version",
        help="Target a specific UI version backup (e.g. v1.0.0)",
    )

    parser.add_argument(
        "--r",
        metavar="RAVEN_VER",
        dest="raven_ver",
        help=(
            "--run: target a specific archived raven version number (e.g. 2). "
            "--revive: target a specific commit number (e.g. 2 → c2) instead of the latest."
        ),
    )

    parser.add_argument(
        "--out",
        metavar="OUTPUT_PATH",
        help="Override output path for the generated zRaven file (--gen only)",
    )

    # Screenshot viewports (--gen only). Emit zViewport + full-page zShot steps for
    # each requested viewport after the page is ready. Choice is stamped into the
    # raven header (# zRavenShots:) so a later plain --gen keeps it. zBifrost only.
    parser.add_argument(
        "--mobile", action="store_true",
        help="--gen: capture a mobile-viewport screenshot (390x844)",
    )
    parser.add_argument(
        "--tablet", action="store_true",
        help="--gen: capture a tablet-viewport screenshot (768x1024)",
    )
    parser.add_argument(
        "--desktop", action="store_true",
        help="--gen: capture a desktop-viewport screenshot (1280x720)",
    )
    parser.add_argument(
        "--all", action="store_true", dest="all_viewports",
        help="--gen: capture mobile + tablet + desktop screenshots",
    )

    parser.add_argument(
        "--verbose", "-V",
        action="store_true",
        help="Verbose output",
    )

    return parser
