"""CLI arguments for `z reload` — hot-reload a running zServer (no downtime)."""


def add_subparser(subparsers):
    """Register the `reload` subcommand."""
    parser = subparsers.add_parser(
        "reload",
        help="Hot-reload a running zServer (routes/zAPIs) with no downtime",
        description=(
            "Signal a running zServer to re-scan zViews/routes/zAPIs and bust the "
            "parsed-file cache — without dropping live sessions. Run from another "
            "shell while the app is serving. With one server running it reloads "
            "that one; with several, it shows a pick list. Use --port to target "
            "a specific server directly."
        ),
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Target a specific running server by port (skips the pick list)",
    )
    return parser


__all__ = ["add_subparser"]
