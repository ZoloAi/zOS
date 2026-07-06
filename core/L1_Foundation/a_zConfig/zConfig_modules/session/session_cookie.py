"""Cookie-bound identity — the durable RESOLVER key shared by both transports.

ZAUTH_INSTANCE.notes.md §19 built per-caller session ISOLATION (registry +
`current()`), but §19.L explicitly deferred *persistence* across connections:
"bind an HTTP request to a prior WS unit via cookie — a future enhancement."
This module is that enhancement, kept transport-agnostic so the three seams
(HTTP request boundary, WS upgrade, login write-through) all speak one SSOT.

The shape:
  * A small opaque `zsid` cookie (httpOnly) is set on the first HTTP response.
    It is host-scoped, so it rides BOTH a plain page load AND the WebSocket
    upgrade — *provided the page origin and the WS origin share a host* (the
    documented loopback SSOT: 127.0.0.1↔localhost must not drift; prod is the
    same `wss://<host>` as the page).
  * The signed-in identity (`session["zVisitor"]`) is mirrored into the externalized
    `session_store` (memory/redis) keyed by that `zsid` — write-through happens at
    the login SSOT (`_apply_zsession`), so any transport's login persists.
  * On a fresh connection/request, whoever holds the `zsid` rehydrates the stored
    `zAuth` into their per-caller unit → the user stays signed in across hard
    reloads and new tabs.

Importable from zGuard via the zOS namespace (optional, like `session_registry`).
Stdlib + the `zos_plugin` session-store seam only — no file-format / transport
assumptions leak in here.
"""

from __future__ import annotations

import copy
from http.cookies import SimpleCookie
from typing import Any, Dict, Optional

# The cookie name + the session slice we persist. Identity only (zAuth) — nav
# state (zCrumbs/zVars) stays fresh per connection, so a reload never replays a
# stale trail; only "who you are" survives.
COOKIE_NAME = "zsid"
_SLICE_KEY = "zVisitor"  # the signed-in caller identity we persist (was "zAuth"/"zLobby")

# 7 days — mirrors the session_store DEFAULT_SESSION_TTL "persistent" intent.
_COOKIE_MAX_AGE = 7 * 24 * 60 * 60


def new_zsid() -> str:
    """Mint a fresh opaque session id (URL-safe, unguessable)."""
    import secrets  # local: keep module import surface tiny
    return secrets.token_urlsafe(24)


def read_zsid(cookie_header: Optional[str]) -> str:
    """Pull the zsid value from a raw ``Cookie:`` header (or '' if absent)."""
    if not cookie_header:
        return ""
    try:
        jar = SimpleCookie()
        jar.load(cookie_header)
        morsel = jar.get(COOKIE_NAME)
        return morsel.value if morsel else ""
    except Exception:  # pylint: disable=broad-except
        return ""


def build_set_cookie(sid: str, *, secure: bool = False) -> str:
    """Build the ``Set-Cookie`` value for the zsid.

    HttpOnly (no JS access) + SameSite=Lax (sent on top-level nav + same-site WS
    upgrade, blocks cross-site CSRF). ``Secure`` is opt-in — omitted on plain-http
    dev/loopback (browsers drop Secure cookies on http), set in prod (https).
    """
    parts = [
        f"{COOKIE_NAME}={sid}",
        "Path=/",
        f"Max-Age={_COOKIE_MAX_AGE}",
        "HttpOnly",
        "SameSite=Lax",
    ]
    if secure:
        parts.append("Secure")
    return "; ".join(parts)


def build_clear_cookie() -> str:
    """Build the ``Set-Cookie`` value that expires the zsid (logout)."""
    return f"{COOKIE_NAME}=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax"


# ── session_store glue (best-effort: a zOS without the plugin just no-ops) ──────

def _store(zos: Any):
    try:
        from zos_plugin import get_session_store  # pylint: disable=import-outside-toplevel
        return get_session_store(zos)
    except Exception:  # pylint: disable=broad-except
        return None


def load_identity(zos: Any, sid: str) -> Optional[Dict[str, Any]]:
    """Return the stored ``zAuth`` blob for ``sid`` (or None if absent/expired)."""
    if not sid:
        return None
    store = _store(zos)
    if store is None:
        return None
    try:
        blob = store.get(sid)
    except Exception:  # pylint: disable=broad-except
        return None
    if not blob:
        return None
    return blob.get(_SLICE_KEY)


def persist_identity(zos: Any, sid: str, session: Dict[str, Any]) -> None:
    """Write-through the current ``zAuth`` slice under ``sid`` (best-effort).

    Called at the login SSOT after ``session[zAuth]`` is written, so a sign-in over
    ANY transport becomes durable. Deep-copied so later in-session mutations don't
    retroactively rewrite the stored snapshot.
    """
    if not sid or not isinstance(session, dict):
        return
    store = _store(zos)
    if store is None:
        return
    zauth = session.get(_SLICE_KEY)
    if not isinstance(zauth, dict):
        return
    try:
        store.set(sid, {_SLICE_KEY: copy.deepcopy(zauth)})
    except Exception:  # pylint: disable=broad-except
        pass


def clear_identity(zos: Any, sid: str) -> None:
    """Drop the stored identity for ``sid`` (logout). Best-effort."""
    if not sid:
        return
    store = _store(zos)
    if store is None:
        return
    try:
        store.delete(sid)
    except Exception:  # pylint: disable=broad-except
        pass


def restore_into_unit(unit: Dict[str, Any], zauth_blob: Optional[Dict[str, Any]]) -> bool:
    """Deep-copy a stored ``zAuth`` blob into a per-caller unit. True if applied."""
    if not isinstance(unit, dict) or not isinstance(zauth_blob, dict):
        return False
    unit[_SLICE_KEY] = copy.deepcopy(zauth_blob)
    return True
