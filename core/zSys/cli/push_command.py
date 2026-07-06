# zSys/cli/push_command.py
"""
`zolo push` CLI seam — public zOS repo.

The implementation (manifest resolution, bundle closure, upload protocol) lives
in the private ``zguard.push`` package (binary wheel via zGuard). This file is
the thin dispatcher the CLI router calls; the argparse subparser stays in
``zSys.cli.args.push_args``. Mirrors the zguard.bifrost / zguard.zengine shims.

Public users (no zGuard): a clear "run z patch" message is shown instead.
"""

from __future__ import annotations


def handle_push_command(boot_logger, args, verbose: bool = False) -> int:
    """Dispatch `zolo push` to the private runtime."""
    try:
        from zguard.push import run_push  # pylint: disable=import-outside-toplevel
    except ImportError:
        print(
            "\n[FAIL] `zolo push` runtime unavailable "
            "(Python ABI mismatch or missing zguard).\n"
            "       Fix: z patch\n"
            "       Docs: https://zolo.media\n"
        )
        return 1
    return run_push(boot_logger, args, verbose=verbose)
