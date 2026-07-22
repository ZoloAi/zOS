# zOS/core/L4_Orchestration/r_zServer/zServer_modules/lifecycle/pidfile.py

"""
zServer instance registry — lets ``z reload`` (any shell) discover the zServer(s)
running on this machine and target one for a hot reload (SIGHUP).

Each booting server drops a tiny record under the OS temp dir; graceful shutdown
removes it. Records are keyed by PORT (unique per live server) so the
multi-instance case can present a pick list keyed on the one guaranteed-unique
field. Records are plain ``key=value`` text — NO file-format dependency (zLoader
owns formats; this is throwaway runtime infra, not zOS data).

This same registry is the substrate a future blue-green swap will read to see the
old and new instances of one app side by side — but reload itself never swaps a
process, it only re-scans a running one.
"""

from __future__ import annotations

import os
import tempfile
import time

_RUNTIME_SUBDIR = "zos"
_INSTANCES_SUBDIR = "instances"
# ws_port (zOS#43): the app's OTHER half — with port hunting, neither leg is
# guessable anymore, so the registry records both. "" when the app runs no WS.
_FIELDS = ("pid", "port", "ws_port", "title", "cwd", "mode", "started_at")


def _instances_dir() -> str:
    d = os.path.join(tempfile.gettempdir(), _RUNTIME_SUBDIR, _INSTANCES_SUBDIR)
    os.makedirs(d, exist_ok=True)
    return d


def _key(port, pid) -> str:
    "Filename key: port when known (unique per live server), else the pid."
    return str(port) if port else f"pid-{pid}"


def _record_path(key: str) -> str:
    return os.path.join(_instances_dir(), f"{key}.txt")


def _is_alive(pid: int) -> bool:
    "True if the pid is a live process (cross-platform, never signals it)."
    from zSys.process_utils import pid_alive  # pylint: disable=import-outside-toplevel
    return pid_alive(pid)


def register_instance(port=None, title=None, cwd=None, mode=None, ws_port=None) -> int:
    """Record THIS process as a running zServer. Returns the pid."""
    pid = os.getpid()
    cwd = cwd or os.getcwd()
    title = title or os.path.basename(cwd) or "zServer"
    values = {
        "pid": pid,
        "port": port if port is not None else "",
        "ws_port": ws_port if ws_port is not None else "",
        "title": title,
        "cwd": cwd,
        "mode": mode or "",
        "started_at": int(time.time()),
    }
    body = "\n".join(f"{k}={values[k]}" for k in _FIELDS) + "\n"
    try:
        with open(_record_path(_key(port, pid)), "w", encoding="utf-8") as fh:
            fh.write(body)
    except OSError:
        pass
    return pid


def _parse_record(path: str):
    "Parse a key=value record into a normalized dict, or None if unreadable."
    rec: dict = {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.rstrip("\n")
                if not line or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                rec[k] = v
    except OSError:
        return None
    try:
        rec["pid"] = int(rec.get("pid", ""))
    except (ValueError, TypeError):
        return None
    port = rec.get("port", "")
    rec["port"] = int(port) if str(port).isdigit() else None
    return rec


def list_instances() -> list:
    """
    Return live zServer records, pruning stale ones along the way.

    Each record: {pid:int, port:int|None, title:str, cwd:str, mode:str, started_at:str}.
    Sorted by port for a stable pick list.
    """
    out = []
    directory = _instances_dir()
    try:
        names = os.listdir(directory)
    except OSError:
        return out

    for name in names:
        if not name.endswith(".txt"):
            continue
        path = os.path.join(directory, name)
        rec = _parse_record(path)
        if not rec or not _is_alive(rec["pid"]):
            try:
                os.remove(path)
            except OSError:
                pass
            continue
        out.append(rec)

    out.sort(key=lambda r: (r.get("port") or 0, r.get("pid")))
    return out


def unregister_instance(port=None) -> None:
    """Remove THIS process's record (best-effort) — both port-keyed and pid-keyed.

    Only removes a record we actually own: during a zero-downtime self-replace the
    green instance co-binds the same port and rewrites the port-keyed record with its
    OWN pid, so blue exiting must NOT delete green's live entry. We re-read each
    record and skip any whose pid isn't ours.
    """
    pid = os.getpid()
    for key in {_key(port, pid), f"pid-{pid}"}:
        path = _record_path(key)
        rec = _parse_record(path)
        if rec is not None and rec.get("pid") != pid:
            continue  # belongs to another process (e.g. the green that took over)
        try:
            os.remove(path)
        except OSError:
            pass


def read_pid(port=None):
    """Back-compat: first live pid matching ``port`` (or any live server if None)."""
    for rec in list_instances():
        if port is None or rec.get("port") == port:
            return rec["pid"]
    return None


__all__ = ["register_instance", "list_instances", "unregister_instance", "read_pid"]
