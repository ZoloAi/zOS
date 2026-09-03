# zSys/cli/apps_command.py
"""
`z apps` CLI seam — public zOS repo.

Managing an account's hosted apps (list / delete / set-visibility, zOS#64) is
an ecosystem concern — it talks to the zCloud registrar over the account API —
so the implementation lives in the private ``zguard.apps`` package (binary
wheel via zGuard). This file is the thin dispatcher the CLI router calls; the
argparse subparser stays in ``zSys.cli.args``. Mirrors the zguard.push shim.

Public users (no zGuard): a clear "run z patch" message is shown instead.
"""

from __future__ import annotations


def handle_apps_command(boot_logger, args, verbose: bool = False) -> int:
    """Dispatch `z apps` (hosted-app management) to the private runtime."""
    try:
        from zguard.apps import run_apps  # pylint: disable=import-outside-toplevel
    except ImportError:
        print(
            "\n[FAIL] `z apps` runtime unavailable "
            "(Python ABI mismatch or missing zguard).\n"
            "       Fix: z patch\n"
            "       Docs: https://zolo.media/zStack/zOS\n"
        )
        return 1
    return run_apps(boot_logger, args, verbose=verbose)
