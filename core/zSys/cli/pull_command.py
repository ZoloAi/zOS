# zSys/cli/pull_command.py
"""
`zolo pull` CLI seam — public zOS repo.

The implementation (download protocol, receipt linking, safe extraction) lives
in the private ``zguard.pull`` package (binary wheel via zGuard). This file is
the thin dispatcher the CLI router calls; the argparse subparser stays in
``zSys.cli.args.pull_args``. Mirrors the zguard.push / push_command shim.

Public users (no zGuard): a clear "run z patch" message is shown instead.
"""

from __future__ import annotations


def handle_pull_command(boot_logger, args, verbose: bool = False) -> int:
    """Dispatch `zolo pull` to the private runtime."""
    try:
        from zguard.pull import run_pull  # pylint: disable=import-outside-toplevel
    except ImportError:
        print(
            "\n[FAIL] `zolo pull` runtime unavailable "
            "(Python ABI mismatch or missing zguard).\n"
            "       Fix: z patch\n"
            "       Docs: https://zolo.media/zStack/zOS\n"
        )
        return 1
    return run_pull(boot_logger, args, verbose=verbose)
