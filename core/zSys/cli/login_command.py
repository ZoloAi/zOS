# zSys/cli/login_command.py
"""
`z login` CLI seam — public zOS repo.

zOwnership sign-in (the zOS/zMachine instance OWNER) verifies against the Zolo
Media registrar authority — an ecosystem concern, not a zOS framework one — so
the implementation (registrar verify, PAT replay, browser device flow, the
zOwnership persist) lives in the private ``zguard.auth`` package (binary wheel
via zGuard). This file is the thin dispatcher the CLI router calls; the argparse
subparser stays in ``zSys.cli.args``. Mirrors the zguard.push shim.

Public users (no zGuard): a clear "run z patch" message is shown instead.
"""

from __future__ import annotations


def handle_login_command(boot_logger, args, verbose: bool = False) -> int:
    """Dispatch `z login` (zOwnership) to the private runtime."""
    try:
        from zguard.auth import run_login  # pylint: disable=import-outside-toplevel
    except ImportError:
        print(
            "\n[FAIL] `z login` runtime unavailable "
            "(Python ABI mismatch or missing zguard).\n"
            "       Fix: z patch\n"
            "       Docs: http://127.0.0.1:9090/zStack/zOS\n"
        )
        return 1
    return run_login(boot_logger, args, verbose=verbose)
