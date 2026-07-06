"""CLI arguments for `z swap` — zero-downtime instance replacement (new code / port)."""


def add_subparser(subparsers):
    """Register the `swap` subcommand."""
    parser = subparsers.add_parser(
        "swap",
        help="Zero-downtime replace a running zServer instance (new code / patched binary / port)",
        description=(
            "Signal a running zServer to spawn a FRESH copy of itself on the SAME "
            "port, hand off, and retire the old one — no dropped sessions. Picks up "
            "new open-source Python, a patched zGuard binary, or a changed port, "
            "which a soft `z reload` can't. Fail-safe: if the new copy won't boot, "
            "the old one keeps serving. Run from another shell while the app is "
            "serving; with several servers running it shows a pick list, or use "
            "--all to swap every local instance at once."
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
        help="Swap EVERY running local instance at once (no prompt)",
    )
    return parser


__all__ = ["add_subparser"]
