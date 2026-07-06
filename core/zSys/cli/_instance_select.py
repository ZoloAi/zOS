"""Shared zServer instance targeting for the control commands (`z reload`, `z swap`).

Both commands answer the same question first — *which* running server do I signal? —
by reading the instance registry and resolving a target from ``--port`` or a pick
list. That selection logic is the SSOT here so reload and swap can never drift.
The commands themselves differ only in the signal they send and their wording.
"""


def list_instances():
    """Read live zServer records from the registry (installed or dev import)."""
    try:
        from zOS.L4_Orchestration.r_zServer.zServer_modules.lifecycle.pidfile import list_instances as _li
    except ImportError:  # dev / alternate package root
        from L4_Orchestration.r_zServer.zServer_modules.lifecycle.pidfile import list_instances as _li
    return _li()


def _row(index, rec):
    """One line in the pick list: index, title, port, cwd."""
    port = rec.get("port")
    port_s = f":{port}" if port else ":?"
    title = (rec.get("title") or "zServer")[:18]
    cwd = rec.get("cwd") or ""
    return f"  [{index}] {title:<18} {port_s:<7} {cwd}"


def _prompt_select(instances, label):
    """Show a numbered pick list and return the chosen record (or None if cancelled)."""
    print(f"\n[{label}] Multiple zServers are running — pick one:\n")
    for i, rec in enumerate(instances, 1):
        print(_row(i, rec))
    print()
    try:
        raw = input(f"Select [1-{len(instances)}] (q to cancel): ").strip()
    except (EOFError, KeyboardInterrupt):
        print(f"\n[{label}] Cancelled.\n")
        return None
    if raw.lower() in ("", "q", "quit"):
        print(f"\n[{label}] Cancelled.\n")
        return None
    if not raw.isdigit() or not 1 <= int(raw) <= len(instances):
        print(f"\n[{label}] Invalid selection — cancelled.\n")
        return None
    return instances[int(raw) - 1]


def resolve_target(port, instances, label):
    """Pick ONE instance to signal from ``--port`` / count. Returns (rec, error_code).

    ``label`` prefixes every message (``zReload`` / ``zSwap``) so the shared flow
    speaks in the caller's voice.
    """
    if port is not None:
        match = [r for r in instances if r.get("port") == port]
        if not match:
            print(f"\n[{label}] No running zServer found on port {port}.\n")
            return None, 1
        return match[0], 0

    if not instances:
        print(f"\n[{label}] No running zServer found. "
              "Is an app running with zServer enabled?\n")
        return None, 1
    if len(instances) == 1:
        return instances[0], 0

    target = _prompt_select(instances, label)
    return (target, 0) if target else (None, 1)


def resolve_targets(port, every, instances, label):
    """Resolve a LIST of instances to signal — one, a chosen one, or all local ones.

    Precedence: ``--port`` (that one) → ``--all`` (every local instance, no prompt)
    → single running (that one) → several (numbered pick list). Returns
    (targets, error_code); ``targets`` is ``[]`` on error/cancel. This is the
    "swap one or all" SSOT — the single- and all-target paths never diverge.
    """
    if port is not None:
        match = [r for r in instances if r.get("port") == port]
        if not match:
            print(f"\n[{label}] No running zServer found on port {port}.\n")
            return [], 1
        return match, 0

    if not instances:
        print(f"\n[{label}] No running zServer found. "
              "Is an app running with zServer enabled?\n")
        return [], 1

    if every:
        return list(instances), 0
    if len(instances) == 1:
        return list(instances), 0

    chosen = _prompt_select(instances, label)
    return ([chosen], 0) if chosen else ([], 1)


__all__ = ["list_instances", "resolve_target", "resolve_targets"]
