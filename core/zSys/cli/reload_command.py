"""
`z reload` — signal a running zServer to hot-reload its app (no downtime).

This command does NOT boot zOS. It reads the zServer instance registry to find
running server(s), then sends SIGHUP to the chosen one — which the server turns
into an in-place re-scan of routes/zAPIs + a parsed-file cache bust + zEnv/navbar
refresh. Live sessions are preserved; the receipt prints on the SERVER's console.

For picking up NEW code (a fresh zOS version, a patched binary) or moving the
port — anything that needs a fresh process — use ``z swap`` instead.

Targeting (shared with `z swap` via _instance_select):
  - ``--port N``  → reload that server directly (no prompt)
  - no flag, 1 server  → reload it
  - no flag, N servers → pick from a numbered list
"""

import os
import signal

from zSys.cli._instance_select import list_instances, resolve_target

_LABEL = "zReload"


def handle_reload_command(logger, args, verbose=False):  # pylint: disable=unused-argument
    """Signal a chosen running zServer to soft-reload (SIGHUP).

    Soft reload: re-scan routes/zAPIs, bust the parsed-file cache, re-inject
    zEnv/navbar — all in place, no dropped sessions. New Python / a new port
    live in ``z swap`` (a fresh process), not here.
    """
    port = getattr(args, "port", None)

    if not hasattr(signal, "SIGHUP"):
        print(f"\n[{_LABEL}] SIGHUP is unavailable on this platform (Windows) — "
              "restart the app to pick up changes.\n")
        return 1

    target, code = resolve_target(port, list_instances(), _LABEL)
    if target is None:
        return code

    pid = target["pid"]
    try:
        os.kill(pid, signal.SIGHUP)
    except ProcessLookupError:
        print(f"\n[{_LABEL}] Stale record — process {pid} is gone. Is the app running?\n")
        return 1
    except PermissionError:
        print(f"\n[{_LABEL}] Not permitted to signal process {pid}.\n")
        return 1

    where = f" on port {target.get('port')}" if target.get("port") else ""
    print(f"\n[{_LABEL}] Reload signal sent to {target.get('title', 'zServer')}{where} "
          f"(pid {pid}). Watch that server's console for the receipt.\n")
    return 0


__all__ = ["handle_reload_command"]
