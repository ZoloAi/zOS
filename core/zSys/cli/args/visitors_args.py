"""CLI arguments for `z visitors` — show a running zServer's live visitor view."""


def add_subparser(subparsers):
    """Register the `visitors` subcommand."""
    parser = subparsers.add_parser(
        "visitors",
        help="Show the live zVisitors of a running zServer (zOwner view)",
        description=(
            "Signal a running zServer to print its live zVisitors table — the "
            "in-process session snapshot — on that server's console. Run from "
            "another shell while the app is serving. With one server running it "
            "targets that one; with several, it shows a pick list keyed on zSpark "
            "title. Use --port to target one directly, or --all to sweep every "
            "running instance (cross-PID global view)."
        ),
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Target a specific running server by port (skips the pick list)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        default=False,
        help="Request a snapshot from every running instance (global sweep)",
    )
    return parser


__all__ = ["add_subparser"]
