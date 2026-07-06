"""
Visitor view — render this PID's live session registry as a zOwner snapshot.

A "visitor" is one bound caller's live session unit (see session_registry). This
module renders the in-process registry (the visitors currently held by THIS zOS
PID) into a plain text table. It is the read side the zOwner sees:

  - `z visitors` (separate CLI process) signals a running server (SIGUSR1); the
    server's handler calls :func:`render_visitor_table` and prints it to its OWN
    console — exactly the `z reload` "watch the server console" model.
  - A future HTTP/admin endpoint can reuse the same function to return the snapshot
    in-band.

Cross-PID note: the live registry is per process. The zOwner's *global* view across
several running instances is the union of each PID's snapshot (broadcast via
`z visitors --all`), or the durable session_store (Redis) when configured.
"""

from __future__ import annotations

from typing import Any, Dict, List

from . import session_registry

# Local key mirrors (kept dependency-light — no foundation import cycle).
_K_ZS_ID = "zS_id"
_K_ZVISITOR = "zVisitor"
_K_ZMODE = "zMode"
_K_ZVAFILE = "zVaFile"
_K_ZSID = "_zsid"


def _visitor_rows() -> List[Dict[str, Any]]:
    """One normalized row per registered live session unit."""
    rows: List[Dict[str, Any]] = []
    for sid in session_registry.ids():
        unit = session_registry.get(sid) or {}
        visitor = unit.get(_K_ZVISITOR, {}) or {}
        rows.append({
            "sid": sid,
            "authenticated": bool(visitor.get("authenticated")),
            "username": visitor.get("username"),
            "role": visitor.get("role"),
            "user_id": visitor.get("id"),
            "zsid": unit.get(_K_ZSID),
            "mode": unit.get(_K_ZMODE),
            "view": unit.get(_K_ZVAFILE),
        })
    rows.sort(key=lambda r: (not r["authenticated"], str(r["username"] or "~")))
    return rows


def render_visitor_table(title: str = "zVisitors") -> str:
    """Render the live registry as a text table (caller decides where to print)."""
    rows = _visitor_rows()
    signed_in = sum(1 for r in rows if r["authenticated"])

    import os  # local: keep import surface tiny
    header = (
        f"\n=== {title} (pid {os.getpid()}) — "
        f"{len(rows)} live session(s), {signed_in} signed-in ===\n"
    )
    if not rows:
        return header + "  (no live sessions bound right now)\n"

    cols = ("user", "role", "id", "mode", "view", "session_id")
    widths = {"user": 22, "role": 14, "id": 8, "mode": 9, "view": 26, "session_id": 24}

    def _cell(v: Any, w: int) -> str:
        s = "—" if v in (None, "") else str(v)
        return (s[: w - 1] + "…") if len(s) > w else s.ljust(w)

    line = "  " + "  ".join(_cell(c, widths[c]) for c in cols)
    sep = "  " + "  ".join("-" * widths[c] for c in cols)
    out = [header, line, sep]
    for r in rows:
        user = r["username"] or ("(anon)" if not r["authenticated"] else "—")
        out.append(
            "  " + "  ".join([
                _cell(user, widths["user"]),
                _cell(r["role"], widths["role"]),
                _cell(r["user_id"], widths["id"]),
                _cell(r["mode"], widths["mode"]),
                _cell(r["view"], widths["view"]),
                _cell(r["sid"], widths["session_id"]),
            ])
        )
    out.append("")
    return "\n".join(out)


__all__ = ["render_visitor_table"]
