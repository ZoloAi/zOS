# zguard/pull/__init__.py
"""
`zolo pull` — clone a hosted app back to a local working copy (zOS#64).

Public zOS dispatches here through the thin zSys.cli.pull_command shim to
:func:`run_pull`. Mirrors the zguard.push boundary.
"""

from .command import run_pull, PULL_ENDPOINT

__all__ = ["run_pull", "PULL_ENDPOINT"]
