# zguard/apps/__init__.py
"""
zguard.apps — the `zolo apps` account CLI (private runtime).

The open-core CLI shim (zSys.cli.apps_command) imports exactly one name:
:func:`run_apps`. Mirrors the zguard.push / zguard.pull boundary.
"""

from .command import run_apps, LIST_ENDPOINT, DELETE_ENDPOINT, VISIBILITY_ENDPOINT

__all__ = ["run_apps", "LIST_ENDPOINT", "DELETE_ENDPOINT", "VISIBILITY_ENDPOINT"]
