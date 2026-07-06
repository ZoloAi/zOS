# zOS/core/L1_Foundation/a_zConfig/zConfig_modules/session/session_registry.py
# ═══════════════════════════════════════════════════════════════════════════════
"""
Session registry — the per-caller indirection for the live session dict (Phase 1).

WHY (SSOT decomposition, ZAUTH_INSTANCE.notes.md §19):
    A "session" in zOS is THREE separable things:
      1. UNIT     — the dict that SessionConfig.create_session() builds. (already SSOT)
      2. REGISTRY — a keyed {id -> unit} container.        ← THIS MODULE (foundation)
      3. RESOLVER — caller -> which id (cookie / WS conn).   (zServer boundary, later)

    zCLI (no server) uses the registry at N=1: one human, one process, one entry.
    zServer reuses the SAME registry at N callers by setting the context-current id
    per request/connection. The capability lives at the foundation SSOT level so it
    cascades to CLI / HTTP-render / WS for free — exactly the decision in §19.D.

    This module holds LIVE dict objects (by reference), NOT serialized blobs — it is
    the in-process Plane-2 indirection. `zos_plugin/session_store.py` remains the
    out-of-process (Redis/TTL) backend for surviving a process; the two compose
    later (registry = live current; store = durable home).

    "current" is a contextvars.ContextVar, mirroring engine._current_zos — so
    concurrent async tasks / threads each see their own current session without any
    locking on the read path.

PHASE-1 CONTRACT (behaviour-neutral at N=1):
    Today only one session is ever registered, and `get_current()` returns it. The
    zOS.session property falls back to the instance default if no context id is set,
    so existing single-session CLI behaviour is byte-for-byte unchanged.
"""

from __future__ import annotations

import contextvars
import threading
from typing import Any, Dict, List, Optional

__all__ = [
    "register",
    "unregister",
    "set_current",
    "clear_current",
    "get_current",
    "get_current_id",
    "get",
    "ids",
    "reset",
]

# Session id key inside the unit dict (mirrors SESSION_KEY_ZS_ID, kept local to
# avoid a foundation import cycle — this module must stay dependency-light).
_ZS_ID_KEY: str = "zS_id"

# id -> live session dict. Process-global on purpose: under one server process all
# callers share this container; isolation comes from the context-current id below,
# not from separate registries.
_registry: Dict[str, Dict[str, Any]] = {}
_lock = threading.RLock()

# The session id the CURRENT context (thread / async task) should see. Unset =>
# the zOS.session property uses its instance default (the single CLI session).
_current_session_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "current_session_id", default=None
)


def register(session: Dict[str, Any], session_id: Optional[str] = None) -> str:
    """Register a live session dict; return the id it was registered under.

    ``session_id`` lets the caller key the unit explicitly (the zServer request
    boundary registers a per-connection unit under its ``full_session_id``,
    independent of the unit's own ``zS_id``). When omitted the id is the unit's
    ``zS_id`` (the zCLI default path). Idempotent by id — re-registering the same
    id replaces the reference.
    """
    if not isinstance(session, dict):
        raise TypeError("session_registry.register expects a dict session unit")
    sid = session_id or session.get(_ZS_ID_KEY) or f"anon_{id(session)}"
    with _lock:
        _registry[sid] = session
    return sid


def restore(token) -> None:
    """Restore the current session id from a Token returned by :func:`set_current`."""
    try:
        _current_session_id.reset(token)
    except (ValueError, LookupError):
        # Token from a different context (e.g. reset in a child task) — ignore.
        pass


def unregister(session_id: str) -> bool:
    """Drop a session from the registry. True if it was present."""
    with _lock:
        return _registry.pop(session_id, None) is not None


def set_current(session_id: Optional[str]) -> contextvars.Token:
    """Bind ``session_id`` as the current context's session. Returns a reset Token.

    The token lets a caller (e.g. the zServer request boundary, later) restore the
    prior value with :func:`contextvars.ContextVar.reset` when the scope ends.
    """
    return _current_session_id.set(session_id)


def clear_current() -> None:
    """Unset the current context's session id (falls back to instance default)."""
    _current_session_id.set(None)


def get_current_id() -> Optional[str]:
    """The session id bound to the current context, or None."""
    return _current_session_id.get()


def get_current() -> Optional[Dict[str, Any]]:
    """The live session dict for the current context, or None if unset/unknown.

    None is the signal for the zOS.session property to use its instance default —
    this is what keeps N=1 CLI behaviour identical while the resolver is unwired.
    """
    sid = _current_session_id.get()
    if sid is None:
        return None
    with _lock:
        return _registry.get(sid)


def get(session_id: str) -> Optional[Dict[str, Any]]:
    """Look up a registered session by id (no effect on current)."""
    with _lock:
        return _registry.get(session_id)


def ids() -> List[str]:
    """All registered session ids (snapshot)."""
    with _lock:
        return list(_registry.keys())


def reset() -> None:
    """Clear the whole registry + current id. Test/teardown helper only."""
    with _lock:
        _registry.clear()
    _current_session_id.set(None)
