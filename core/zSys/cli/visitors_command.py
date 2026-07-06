"""
`z visitors` — show the zOwner's live visitor view for a running zServer.

Like `z reload`, this command does NOT boot zOS. It reads the zServer instance
registry to find running server(s), then signals the chosen one (SIGUSR1) to print
its live zVisitors table — the in-process session snapshot — on the SERVER's own
console (the "watch the server console" receipt model).

Targeting:
  - ``--port N``  → that server directly (no prompt)
  - ``--all``     → every running instance (cross-PID global sweep; each prints
                    on its own console)
  - no flag, 1 server  → that one
  - no flag, N servers → numbered pick list keyed on zSpark title
"""

import os
import signal


def _list_instances():
    """Read live zServer records from the registry (installed or dev import)."""
    try:
        from zOS.L4_Orchestration.r_zServer.zServer_modules.lifecycle.pidfile import list_instances
    except ImportError:  # dev / alternate package root
        from L4_Orchestration.r_zServer.zServer_modules.lifecycle.pidfile import list_instances
    return list_instances()


def _row(index, rec):
    """One line in the pick list: index, title, port, cwd."""
    port = rec.get("port")
    port_s = f":{port}" if port else ":?"
    title = (rec.get("title") or "zServer")[:18]
    cwd = rec.get("cwd") or ""
    return f"  [{index}] {title:<18} {port_s:<7} {cwd}"


def _prompt_select(instances):
    """Show a numbered pick list and return the chosen record (or None if cancelled)."""
    print("\n[zVisitors] Multiple zServers are running — pick one to inspect:\n")
    for i, rec in enumerate(instances, 1):
        print(_row(i, rec))
    print()
    try:
        raw = input(f"Select [1-{len(instances)}] (q to cancel): ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\n[zVisitors] Cancelled.\n")
        return None
    if raw.lower() in ("", "q", "quit"):
        print("\n[zVisitors] Cancelled.\n")
        return None
    if not raw.isdigit() or not 1 <= int(raw) <= len(instances):
        print("\n[zVisitors] Invalid selection — cancelled.\n")
        return None
    return instances[int(raw) - 1]


def _signal_one(rec):
    """Send SIGUSR1 to one instance; print a receipt line. Returns 0/1."""
    pid = rec["pid"]
    try:
        os.kill(pid, signal.SIGUSR1)
    except ProcessLookupError:
        print(f"\n[zVisitors] Stale record — process {pid} is gone.\n")
        return 1
    except PermissionError:
        print(f"\n[zVisitors] Not permitted to signal process {pid}.\n")
        return 1
    where = f" on port {rec.get('port')}" if rec.get("port") else ""
    print(f"  ✓ {rec.get('title', 'zServer')}{where} (pid {pid}) — "
          "snapshot requested; see that server's console.")
    return 0


def handle_visitors_command(logger, args, verbose=False):  # pylint: disable=unused-argument
    """Signal a running zServer to dump its live zVisitors table to its console."""
    if not hasattr(signal, "SIGUSR1"):
        print("\n[zVisitors] SIGUSR1 is unavailable on this platform (Windows).\n")
        return 1

    port = getattr(args, "port", None)
    every = getattr(args, "all", False)
    instances = _list_instances()

    if not instances:
        print("\n[zVisitors] No running zServer found. "
              "Is an app running with zServer enabled?\n")
        return 1

    if port is not None:
        match = [r for r in instances if r.get("port") == port]
        if not match:
            print(f"\n[zVisitors] No running zServer found on port {port}.\n")
            return 1
        targets = match
    elif every:
        print(f"\n[zVisitors] Requesting snapshots from {len(instances)} running "
              "instance(s):\n")
        targets = instances
    elif len(instances) == 1:
        targets = instances
    else:
        chosen = _prompt_select(instances)
        if chosen is None:
            return 1
        targets = [chosen]

    rc = 0
    for rec in targets:
        rc |= _signal_one(rec)
    print()
    return rc


__all__ = ["handle_visitors_command"]
