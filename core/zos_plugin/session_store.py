"""
Session stores — the externalizable home for Tier-2 (hosted-app) sessions.
"Hold a browser's session so it survives the process that created it" is a
*general* zOS capability, so it lives here in the plugin SDK (sibling to
:mod:`drivers`, which runs instances, and :mod:`bundle_store`, which persists
pushed apps).

Why a seam (Phase 3 — State externalize): today a bridge session lives only in
the zOS process that accepted the WebSocket (``authenticated_clients[ws]`` + the
process-global ``zos.session``). That's fine for one long-lived server, but a
hosted app must **scale-to-zero** (sleep when idle) and **blue-green** (a new
instance replaces the old) without dropping signed-in users. Both require the
session to outlive any single process — i.e. an out-of-process store.

A :class:`SessionStore` is the swappable backend, keyed by ``full_session_id``
(``zS_<spark>:zB_<bridge>``):

    * :class:`InMemorySessionStore` — dev/single-process default. A dict with
      per-key TTL; behaviourally identical to "no store" but through the same
      API, so wiring code is written once.
    * :class:`RedisSessionStore` — local Redis now, ElastiCache in prod (same
      class, different URL). JSON blob per session, native key TTL. ``redis`` is
      imported lazily so the SDK has no hard dependency.
    * A future store (DynamoDB, …) registers via :func:`register_session_store`
      with zero change to callers.

The store only moves the session blob; *what* goes in it (auth_info, the
per-connection slice of zos.session) stays with the caller (the zBifrost
connect/cleanup/resume path). Mirrors the driver/bundle registry pattern:
env (``ZSESSION_STORE``) selects the backend; :func:`get_session_store` resolves it.
"""

from __future__ import annotations

import abc
import json
import os
import threading
import time
from typing import Any, Callable, Dict, Optional

__all__ = [
    "SessionStore", "InMemorySessionStore", "RedisSessionStore",
    "register_session_store", "get_session_store",
    "DEFAULT_SESSION_TTL",
]

# Default lifetime for a stored session when the caller doesn't specify one.
# 7 days mirrors the old "persistent" intent; guests/short sessions pass their own.
DEFAULT_SESSION_TTL = 7 * 24 * 60 * 60  # seconds


class SessionStore(abc.ABC):
    """Backend that persists a Tier-2 session blob keyed by ``full_session_id``.

    A "session blob" is any JSON-serialisable mapping (the bridge stores
    ``auth_info`` + the per-connection session slice). Implementations must treat
    values as opaque and honour TTL so abandoned sessions self-expire.
    """

    @abc.abstractmethod
    def get(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Return the session blob, or ``None`` if missing/expired."""

    @abc.abstractmethod
    def set(self, session_id: str, data: Dict[str, Any], ttl: Optional[int] = None) -> None:
        """Persist ``data`` for ``session_id`` with an optional TTL (seconds)."""

    @abc.abstractmethod
    def delete(self, session_id: str) -> bool:
        """Remove a session. Returns True if something was removed."""

    @abc.abstractmethod
    def touch(self, session_id: str, ttl: Optional[int] = None) -> bool:
        """Extend a session's TTL (sliding expiry). False if it's gone."""

    def exists(self, session_id: str) -> bool:
        """Convenience: True if the session is present and unexpired."""
        return self.get(session_id) is not None


class InMemorySessionStore(SessionStore):
    """Process-local store: a dict with lazy per-key TTL. The dev default.

    Thread-safe (the bridge runs an asyncio loop + worker threads). Expiry is
    checked on access and opportunistically swept, so no background task is
    needed. This is the same lifetime guarantee as today's in-memory sessions —
    just reached through the SessionStore API so the wiring is backend-agnostic.
    """

    def __init__(self) -> None:
        self._data: Dict[str, Dict[str, Any]] = {}
        self._expiry: Dict[str, float] = {}
        self._lock = threading.RLock()

    def _expired(self, session_id: str, now: float) -> bool:
        exp = self._expiry.get(session_id)
        return exp is not None and exp <= now

    def _purge(self, session_id: str) -> None:
        self._data.pop(session_id, None)
        self._expiry.pop(session_id, None)

    def get(self, session_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            if self._expired(session_id, time.time()):
                self._purge(session_id)
                return None
            data = self._data.get(session_id)
            # Hand back a copy so callers can't mutate the stored blob in place.
            return dict(data) if data is not None else None

    def set(self, session_id: str, data: Dict[str, Any], ttl: Optional[int] = None) -> None:
        ttl = DEFAULT_SESSION_TTL if ttl is None else ttl
        with self._lock:
            self._data[session_id] = dict(data)
            self._expiry[session_id] = time.time() + ttl if ttl else 0
            if ttl:
                self._sweep()

    def delete(self, session_id: str) -> bool:
        with self._lock:
            existed = session_id in self._data
            self._purge(session_id)
            return existed

    def touch(self, session_id: str, ttl: Optional[int] = None) -> bool:
        ttl = DEFAULT_SESSION_TTL if ttl is None else ttl
        with self._lock:
            if self._expired(session_id, time.time()) or session_id not in self._data:
                self._purge(session_id)
                return False
            self._expiry[session_id] = time.time() + ttl if ttl else 0
            return True

    def _sweep(self) -> None:
        now = time.time()
        for sid in [s for s, e in self._expiry.items() if e and e <= now]:
            self._purge(sid)


class RedisSessionStore(SessionStore):
    """Out-of-process store: one JSON blob per session, native Redis key TTL.

    Local Redis in dev, ElastiCache in prod — same class, the URL changes. This
    is what makes scale-to-zero / blue-green safe: any instance (old, new, or a
    freshly-woken one) reads the same session by ``full_session_id``.

    ``redis`` is imported lazily so the SDK stays dependency-free unless this
    backend is actually selected.
    """

    def __init__(self, url: Optional[str] = None, prefix: str = "zsession:") -> None:
        try:
            import redis  # pylint: disable=import-outside-toplevel
        except ImportError as exc:  # pragma: no cover - surfaced only when selected
            raise RuntimeError(
                "RedisSessionStore requires the 'redis' package "
                "(pip install redis) — or set ZSESSION_STORE=memory."
            ) from exc
        self._url = url or os.environ.get("ZSESSION_REDIS_URL", "redis://localhost:6379/0")
        self._prefix = prefix
        # decode_responses=True → str in/out; we JSON-encode the blob ourselves.
        self._r = redis.Redis.from_url(self._url, decode_responses=True)

    def _key(self, session_id: str) -> str:
        return f"{self._prefix}{session_id}"

    def get(self, session_id: str) -> Optional[Dict[str, Any]]:
        raw = self._r.get(self._key(session_id))
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (ValueError, TypeError):
            return None

    def set(self, session_id: str, data: Dict[str, Any], ttl: Optional[int] = None) -> None:
        ttl = DEFAULT_SESSION_TTL if ttl is None else ttl
        payload = json.dumps(data, default=str)
        if ttl:
            self._r.set(self._key(session_id), payload, ex=ttl)
        else:
            self._r.set(self._key(session_id), payload)

    def delete(self, session_id: str) -> bool:
        return bool(self._r.delete(self._key(session_id)))

    def touch(self, session_id: str, ttl: Optional[int] = None) -> bool:
        ttl = DEFAULT_SESSION_TTL if ttl is None else ttl
        if not ttl:
            return self._r.persist(self._key(session_id))
        return bool(self._r.expire(self._key(session_id), ttl))


# ─────────────────────────────────────────────────────────────────────────────
# Store registry — env selects the backend (dev=memory, prod=redis, …)
# ─────────────────────────────────────────────────────────────────────────────

_STORES: Dict[str, Callable[[], SessionStore]] = {
    "memory": InMemorySessionStore,
    "redis": RedisSessionStore,
}

# A single process shares one store instance (unlike bundle stores, a session
# store holds live state, so it must be a singleton per backend name).
_SINGLETONS: Dict[str, SessionStore] = {}


def register_session_store(name: str, factory: Callable[[], SessionStore]) -> None:
    """Register a backend factory (e.g. ``register_session_store('dynamo', …)``)."""
    _STORES[name] = factory
    _SINGLETONS.pop(name, None)


def get_session_store(zos: Any = None) -> SessionStore:
    """Resolve the active session store: ``ZSESSION_STORE`` env → zos config → 'memory'.

    Cached as a per-name singleton (the store holds live sessions). Env wins;
    a ``zos.config.get('session_store')`` value is consulted as a fallback so a
    spark/zEnv can pin the backend without an env var.
    """
    name = os.environ.get("ZSESSION_STORE")
    if not name:
        cfg = getattr(zos, "config", None)
        if cfg is not None:
            try:
                name = cfg.get("session_store")
            except Exception:  # pylint: disable=broad-except
                name = None
    name = name or "memory"
    if name not in _STORES:
        name = "memory"
    store = _SINGLETONS.get(name)
    if store is None:
        store = _STORES[name]()
        _SINGLETONS[name] = store
    return store
