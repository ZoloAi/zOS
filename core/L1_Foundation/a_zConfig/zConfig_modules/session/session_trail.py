"""Per-tab trail persistence — the durable mirror for zCrumbs across reconnects.

Sibling of ``session_cookie`` (identity persistence). The two answer ONE question
— "what survives a reconnect?" — but at different scopes, and scope dictates the
browser primitive that carries the key:

    identity (zVisitor)  → per BROWSER → ``zsid`` COOKIE         → session_cookie.py
    trail    (zCrumbs)   → per TAB     → ``ztab`` sessionStorage → THIS module

The browser already keeps a per-tab memory that survives a reload (sessionStorage
/ ``history.state``); without a matching engine-side trail, a refresh wiped the
crumb trail while the browser kept its Back/Forward stack — so browser Back moved
the URL but the engine had nothing to pop. Mirroring the trail under the tab's
``ztab`` token closes that gap: reload → same token → trail rehydrated → the two
memories stay in lockstep. A new tab has no token → a fresh trail (unchanged).

The client mints an opaque ``ztab`` in sessionStorage and presents it on the WS
upgrade (a ``?ztab=`` query param — NOT a cookie, which would bleed across tabs).
The trail slice (``session["zCrumbs"]``) is mirrored into the externalized
``session_store`` keyed by that token; ``_seed_session`` rehydrates it on connect.

Stdlib + the ``zos_plugin`` session-store seam only — no file-format / transport
assumptions leak in here.
"""

from __future__ import annotations

import copy
from typing import Any, Dict, Optional

# The query param the client presents on the WS upgrade + the session slice we
# persist. Trail only (zCrumbs); identity lives in session_cookie under the cookie.
TAB_PARAM = "ztab"
_SLICE_KEY = "zCrumbs"
# Namespace the store key so a ztab token can never collide with a zsid identity
# key (session_cookie stores identity under the bare sid).
_STORE_PREFIX = "ztab:"


def _store(zos: Any):
    try:
        from zos_plugin import get_session_store  # pylint: disable=import-outside-toplevel
        return get_session_store(zos)
    except Exception:  # pylint: disable=broad-except
        return None


def _key(ztab: str) -> str:
    return f"{_STORE_PREFIX}{ztab}"


def load_trail(zos: Any, ztab: str) -> Optional[Dict[str, Any]]:
    """Return the stored ``zCrumbs`` blob for ``ztab`` (or None if absent/expired)."""
    if not ztab:
        return None
    store = _store(zos)
    if store is None:
        return None
    try:
        blob = store.get(_key(ztab))
    except Exception:  # pylint: disable=broad-except
        return None
    if not blob:
        return None
    return blob.get(_SLICE_KEY)


def persist_trail(zos: Any, ztab: str, session: Dict[str, Any]) -> None:
    """Write-through the current ``zCrumbs`` slice under ``ztab`` (best-effort).

    Called at the walker-complete seam after each nav, so the stored trail always
    mirrors the live one. Deep-copied so later in-session mutations don't
    retroactively rewrite the stored snapshot.
    """
    if not ztab or not isinstance(session, dict):
        return
    store = _store(zos)
    if store is None:
        return
    trail = session.get(_SLICE_KEY)
    if not isinstance(trail, dict):
        return
    try:
        store.set(_key(ztab), {_SLICE_KEY: copy.deepcopy(trail)})
    except Exception:  # pylint: disable=broad-except
        pass


def clear_trail(zos: Any, ztab: str) -> None:
    """Drop the stored trail for ``ztab`` (best-effort)."""
    if not ztab:
        return
    store = _store(zos)
    if store is None:
        return
    try:
        store.delete(_key(ztab))
    except Exception:  # pylint: disable=broad-except
        pass


def restore_trail_into_unit(unit: Dict[str, Any], trail_blob: Optional[Dict[str, Any]]) -> bool:
    """Deep-copy a stored ``zCrumbs`` blob into a per-caller unit. True if applied."""
    if not isinstance(unit, dict) or not isinstance(trail_blob, dict):
        return False
    unit[_SLICE_KEY] = copy.deepcopy(trail_blob)
    return True
