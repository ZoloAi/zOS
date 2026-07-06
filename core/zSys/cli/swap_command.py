"""
`z swap` — zero-downtime replacement of a running zServer *instance*.

Where ``z reload`` re-reads your declarations in place, ``z swap`` replaces the
whole process: it signals a running server (SIGUSR2) to spawn a FRESH copy of
itself that co-binds the same port (SO_REUSEPORT), waits for the new copy to pass
its readiness handshake, hands traffic over, then retires the old one. Because the
new copy is a brand-new interpreter it picks up things a soft reload can't —
new open-source Python, a patched zGuard binary, or a changed port.

Fail-safe: if the fresh copy won't boot, the old one keeps serving and the swap
rolls back. This is the same engine ``z patch --live`` rides on across the fleet.

Targeting is shared with `z reload` (see _instance_select): pick ONE with a
number/``--port``, or swap every local instance with ``--all`` (each replaces
itself independently — they don't share a socket, so there's no coordination to
do). The receipt prints on each SERVER's console, not here.
"""

import os
import signal

from zSys.cli._instance_select import list_instances, resolve_targets

_LABEL = "zSwap"


def _signal_one(rec):
    """Send SIGUSR2 to one instance; print a receipt line. Returns 0/1."""
    pid = rec["pid"]
    try:
        os.kill(pid, signal.SIGUSR2)
    except ProcessLookupError:
        print(f"  ✗ pid {pid} is gone (stale record).")
        return 1
    except PermissionError:
        print(f"  ✗ not permitted to signal pid {pid}.")
        return 1
    where = f" on port {rec.get('port')}" if rec.get("port") else ""
    print(f"  ✓ {rec.get('title', 'zServer')}{where} (pid {pid}) — "
          "self-replace requested; watch that server's console for the handoff.")
    return 0


def handle_swap_command(logger, args, verbose=False):  # pylint: disable=unused-argument
    """Signal running zServer(s) to self-replace (SIGUSR2) — one, a chosen one, or all."""
    port = getattr(args, "port", None)
    every = getattr(args, "all", False)

    if not hasattr(signal, "SIGUSR2"):
        print(f"\n[{_LABEL}] SIGUSR2 is unavailable on this platform (Windows) — "
              "restart the app to pick up new code.\n")
        return 1

    targets, code = resolve_targets(port, every, list_instances(), _LABEL)
    if not targets:
        return code

    if len(targets) > 1:
        print(f"\n[{_LABEL}] Zero-downtime self-replace of {len(targets)} running "
              "instance(s):\n")
    else:
        print(f"\n[{_LABEL}] Zero-downtime self-replace:\n")

    rc = 0
    for rec in targets:
        rc |= _signal_one(rec)
    print()
    return rc


__all__ = ["handle_swap_command"]
