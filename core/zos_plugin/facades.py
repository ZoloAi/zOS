"""
Plugin facades — the declarative connection points between a plugin and zOS.

A plugin author writes pure intent::

    @zfunc
    def upload(user, files, transfer, data):
        img = files.image("avatar", max_mb=5)
        stored = transfer.store(img.bytes, key=f"users/{user.id}/avatar.{img.ext}",
                                mime=img.mime, filename=img.filename)
        row = data.upsert("media", where={"user_id": user.id, "kind": "avatar"},
                          values={"storage_key": stored.key, "mime_type": img.mime,
                                  "file_size": img.size})
        data.update("users", {"avatar_media_id": row.id}, where={"id": user.id})
        return {"ok": True, "message": "Avatar updated",
                "data": {"media_id": row.id, "url": stored.cache_busted_url}}

No deep ``from zOS.L2_Handling...`` imports, no manual session traversal, no
hand-built result dicts. Each facade wraps an existing zOS primitive and is the
*single* place that knows the internal path — so when a path moves, plugins do
not. @zfunc injects these by parameter name (see context.py).
"""

from __future__ import annotations

import time
from typing import Any, Dict, Iterable, List, Optional

from .result import ZAbort
from .drivers import AppSpec, Instance, ProxyTarget, get_driver

__all__ = [
    "Row", "Stored", "UploadedFile",
    "UserCtx", "FilesFacade", "TransferFacade", "DataFacade",
    "InstanceFacade", "ProxyFacade",
]

# Canonical image mime → extension map (shared by FilesFacade + callers).
_IMAGE_EXT = {
    "image/jpeg": "jpg",
    "image/jpg":  "jpg",
    "image/png":  "png",
    "image/webp": "webp",
    "image/gif":  "gif",
}


# ─────────────────────────────────────────────────────────────────────────────
# Value objects
# ─────────────────────────────────────────────────────────────────────────────

class Row(dict):
    """A data row that also supports attribute access (``row.id``)."""

    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc


class Stored:
    """Result of a storage write — what the blob became reachable as."""

    __slots__ = ("key", "url", "path")

    def __init__(self, key: str, url: str, path: Optional[str] = None):
        self.key = key
        self.url = url
        self.path = path

    @property
    def cache_busted_url(self) -> str:
        """URL with a ``v=<ts>`` param so a same-keyed replacement reloads."""
        sep = "&" if "?" in (self.url or "") else "?"
        return f"{self.url}{sep}v={int(time.time())}"


class UploadedFile:
    """One uploaded file — transport-agnostic view over the raw upload dict."""

    __slots__ = ("_raw",)

    def __init__(self, raw: Optional[Dict[str, Any]]):
        self._raw = raw or {}

    @property
    def bytes(self) -> bytes:
        return self._raw.get("data") or b""

    @property
    def mime(self) -> str:
        return (self._raw.get("content_type") or self._raw.get("mime") or "").lower().split(";")[0].strip()

    @property
    def filename(self) -> Optional[str]:
        return self._raw.get("filename")

    @property
    def size(self) -> int:
        return int(self._raw.get("size") or len(self.bytes))

    @property
    def ext(self) -> Optional[str]:
        by_mime = _IMAGE_EXT.get(self.mime)
        if by_mime:
            return by_mime
        name = self.filename or ""
        return name.rsplit(".", 1)[-1].lower() if "." in name else None


# ─────────────────────────────────────────────────────────────────────────────
# user — the logged-in account, resolved from the session (SSOT)
# ─────────────────────────────────────────────────────────────────────────────

class UserCtx:
    """The logged-in user for the current invocation."""

    __slots__ = ("id", "name", "email", "role", "raw")

    def __init__(self, id=None, name=None, email=None, role=None, raw=None):  # noqa: A002
        self.id = id
        self.name = name
        self.email = email
        self.role = role
        self.raw = raw or {}

    def __bool__(self) -> bool:
        return self.id is not None

    def require(self) -> "UserCtx":
        """Return self if authenticated, else abort 401 (linear guard)."""
        if not self:
            raise ZAbort("Not authenticated", status=401)
        return self

    @classmethod
    def from_session(cls, session: Optional[dict], app: Optional[str] = None) -> "UserCtx":  # pylint: disable=unused-argument
        # Single signed-in identity — app arg is vestigial (kept for call-site compat).
        acct: Dict[str, Any] = {}
        try:
            acct = (session or {}).get("zVisitor", {}) or {}
        except Exception:  # pylint: disable=broad-except
            acct = {}
        return cls(
            id=acct.get("id"),
            name=acct.get("username") or acct.get("name"),
            email=acct.get("email"),
            role=acct.get("role"),
            raw=acct,
        )


# ─────────────────────────────────────────────────────────────────────────────
# files — uploaded blobs for this invocation (multipart or CLI path source)
# ─────────────────────────────────────────────────────────────────────────────

class FilesFacade:
    """Access uploaded files declared by the transport for this invocation."""

    def __init__(self, raw_files: Optional[Dict[str, Any]]):
        self._files = raw_files or {}

    def __bool__(self) -> bool:
        return bool(self._files)

    def __contains__(self, field: str) -> bool:
        return field in self._files

    def get(self, field: Optional[str] = None) -> Optional[UploadedFile]:
        """Return a named file, or the only/first file when ``field`` is None."""
        raw = None
        if field and field in self._files:
            raw = self._files[field]
        elif self._files:
            raw = next(iter(self._files.values()))
        return UploadedFile(raw) if raw else None

    def image(
        self,
        field: Optional[str] = None,
        max_mb: Optional[float] = None,
        allow: Optional[Iterable[str]] = None,
    ) -> UploadedFile:
        """Return a validated image file, aborting (4xx) on any policy miss."""
        f = self.get(field)
        if not f:
            raise ZAbort("No file in upload", status=400)
        allowed = set(allow) if allow else set(_IMAGE_EXT)
        if f.mime not in allowed:
            raise ZAbort(f"Unsupported image type: {f.mime or 'unknown'}", status=415)
        if f.size <= 0:
            raise ZAbort("Empty file", status=400)
        if max_mb and f.size > max_mb * 1024 * 1024:
            raise ZAbort(
                f"File too large ({f.size} bytes; max {max_mb}MB)", status=413
            )
        return f


# ─────────────────────────────────────────────────────────────────────────────
# transfer — bytes/rows in & out of zOS (local in dev, s3/CDN in prod)
# ─────────────────────────────────────────────────────────────────────────────

class TransferFacade:
    """Thin, declarative front to the zTransfer engine."""

    def __init__(self, zos: Any):
        self._zos = zos

    def _engine(self):
        eng = getattr(self._zos, "transfer", None)
        if eng is not None:
            return eng
        # The ONE place that knows the internal transfer path.
        from zOS.L2_Handling.g_zDispatch.dispatch_modules.transfer import TransferEngine
        eng = TransferEngine(self._zos, None, getattr(self._zos, "logger", None))
        try:
            self._zos.transfer = eng  # cache for reuse across the request
        except Exception:  # pylint: disable=broad-except
            pass
        return eng

    def run(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        """Run a raw zTransfer spec and return its result dict (escape hatch)."""
        return self._engine().run(spec)

    def store(
        self,
        data: bytes,
        key: str,
        mime: Optional[str] = None,
        filename: Optional[str] = None,
    ) -> Stored:
        """Write bytes to object storage under ``key`` → :class:`Stored`."""
        res = self._engine().run({
            "source": {"from": "bytes", "data": data, "filename": filename, "mime": mime},
            "target": {"to": "storage", "key": key},
        })
        if not res.get("success"):
            raise ZAbort(f"Storage write failed: {res.get('error')}", status=500)
        # URL comes from the storage backend (SSOT): the local adapter derives
        # it from STORAGE_PUBLIC_BASE / a relative root; s3 presigns. No app
        # layout (e.g. /static/media) is ever invented here.
        return Stored(
            key=res.get("key", key),
            url=res.get("url") or "",
            path=res.get("path"),
        )


# ─────────────────────────────────────────────────────────────────────────────
# data — declarative CRUD over zData (dict-ergonomic, returns Rows)
# ─────────────────────────────────────────────────────────────────────────────

class DataFacade:
    """Ergonomic CRUD over zData. Values are plain dicts; rows come back as Rows."""

    def __init__(self, zos: Any):
        self._d = zos.data

    def select(
        self,
        table: str,
        where: Optional[dict] = None,
        fields: Optional[List[str]] = None,
    ) -> List[Row]:
        rows = self._d.select(table=table, fields=fields, where=where or {})
        return [Row(r) for r in (rows or [])]

    def first(self, table: str, where: Optional[dict] = None) -> Optional[Row]:
        rows = self.select(table, where=where)
        return rows[0] if rows else None

    def insert(self, table: str, values: dict) -> Optional[Row]:
        if isinstance(values, (list, tuple)):
            raise TypeError(
                "data.insert takes ONE row dict — for a list of rows use "
                "data.insert_many(table, rows)"
            )
        self._d.insert(table=table, fields=list(values), values=list(values.values()))
        # Best-effort: return the freshly inserted row (max id of the match set).
        probe = {k: v for k, v in values.items() if not isinstance(v, (dict, list))}
        rows = self.select(table, where=probe) if probe else []
        if not rows:
            return Row(values)
        return max(rows, key=lambda r: r.get("id", 0))

    def insert_many(self, table: str, rows: List[dict]) -> int:
        """Bulk insert: one write pass, one commit, NO per-row probe-select.

        The single-row ``insert`` above re-selects after every write to hand back
        the fresh row — fine for a form submit, ruinous for an import (34k rows
        become 68k queries). This path delegates straight to the adapter's
        ``insert_many`` (single transaction where the backend allows) and returns
        only the inserted-row count.
        """
        rows = [dict(r) for r in (rows or [])]
        if not rows:
            return 0
        inserted = self._d.insert_many(table, rows)
        return len(inserted) if isinstance(inserted, list) else len(rows)

    def update(self, table: str, values: dict, where: dict) -> Any:
        """Update rows matching ``where``. ``values`` may carry a computed spec
        (``{"$inc": 1}`` / ``$dec``/``$mul``/``$div``/``zExpr``, 18_data_advanced.md
        "computed") — resolved here against the row's OWN current value, because
        ``zos.data.update`` is the plain adapter pass-through (table/fields/values/
        where straight to the backend) and has none of ``handle_update``'s
        ``set:``/``data:`` computed-set detection; left unresolved, a literal
        ``{"$inc": 1}`` dict would land in the cell instead of doing the arithmetic
        (zDemos/zPoll's vote-counter cast_vote is the worked example). Single-row
        semantics only — like `upsert` below, ``where`` is expected to pin one row;
        a computed spec against a multi-row ``where`` reuses that ONE row's base
        value for every match, not a true per-row delta.
        """
        from zOS.L3_Abstraction.m_zData.zData_modules.shared.operations.crud_set_expr import (
            is_computed, resolve_set_value,
        )
        if any(is_computed(v) for v in values.values()):
            base_row = self.first(table, where=where) or {}
            values = {k: resolve_set_value(k, v, base_row) for k, v in values.items()}
        return self._d.update(
            table=table, fields=list(values), values=list(values.values()), where=where
        )

    def delete(self, table: str, where: dict) -> Any:
        """Delete rows matching ``where``. ``where`` is required — no truncate-by-mistake."""
        return self._d.delete(table=table, where=where)

    def upsert(self, table: str, where: dict, values: dict) -> Row:
        """Update the row matching ``where`` (or insert ``where+values``); return it."""
        existing = self.select(table, where=where)
        if existing:
            row = existing[0]
            rid = row.get("id")
            self.update(table, values, where={"id": rid} if rid is not None else where)
            return Row({**row, **values})
        self.insert(table, {**where, **values})
        rows = self.select(table, where=where)
        return max(rows, key=lambda r: r.get("id", 0)) if rows else Row({**where, **values})


# ─────────────────────────────────────────────────────────────────────────────
# instance — lifecycle of *another* zOS app instance (run / reach / sleep)
# ─────────────────────────────────────────────────────────────────────────────

class InstanceFacade:
    """Declarative front to the compute driver: wake / sleep / inspect an app.

    A plugin names ``instance`` and gets this; the backend (local process in dev,
    k8s in prod) is selected by env behind :func:`drivers.get_driver`, so the
    plugin's wake/sleep flow is identical everywhere::

        @zfunc
        def serve(app_id, instance, data):
            row = data.first("apps", where={"app_id": app_id})
            inst = instance.wake({"app_id": app_id, "folder": row["folder"],
                                  "spark": row["spark"]})
            return {"ok": inst.running, "data": {"address": inst.address}}
    """

    def __init__(self, zos: Any):
        self._zos = zos

    def _driver(self):
        return get_driver(self._zos)

    def wake(self, app: Any, timeout: float = 25.0) -> Instance:
        """Ensure the app is running and reachable; return its :class:`Instance`."""
        return self._driver().wake(AppSpec.coerce(app), timeout=timeout)

    def sleep(self, app: Any) -> bool:
        """Tear down the app's instance. Accepts an app_id or an app spec."""
        app_id = app if isinstance(app, str) else AppSpec.coerce(app).app_id
        stopped = self._driver().sleep(app_id)
        # Ingress: retire <slug>.<domain> so the proxy never points at a dead port.
        from .ingress import IngressConfig  # pylint: disable=import-outside-toplevel
        ingress = IngressConfig.from_env()
        if ingress:
            try:
                ingress.unpublish(app_id)
            except Exception:  # pylint: disable=broad-except
                pass  # proxy admin down ≠ failed sleep; route goes stale, not wrong
        return stopped

    def status(self, app: Any) -> Instance:
        """Current :class:`Instance` (state asleep/waking/running) — never raises."""
        app_id = app if isinstance(app, str) else AppSpec.coerce(app).app_id
        return self._driver().status(app_id)


# ─────────────────────────────────────────────────────────────────────────────
# proxy — resolve an app to a reachable public URL (the front-door seam)
# ─────────────────────────────────────────────────────────────────────────────

class ProxyFacade:
    """Wake-and-resolve: turn an app into a URL a visitor can be sent to.

    Sibling to ``instance`` (which owns lifecycle); ``proxy`` owns *addressing*.
    Dev returns the instance's own address (redirect hand-off, no WS proxying);
    prod returns an ingress URL whose reverse-proxy forwards HTTP/WS to the pod —
    so the byte-forwarding lives in the layer built for it, never hand-rolled here.

        @zfunc
        def launch(app_id, proxy, data):
            row = data.first("apps", where={"slug": app_id})
            t = proxy.resolve({"app_id": app_id, "folder": ..., "spark": ...})
            return {"ok": t.ready, "data": {"url": t.url, "state": t.state}}
    """

    def __init__(self, zos: Any):
        self._zos = zos

    def resolve(self, app: Any, timeout: float = 25.0) -> ProxyTarget:
        """Ensure the app is up and return where to reach it (wake-and-hold)."""
        inst = get_driver(self._zos).wake(AppSpec.coerce(app), timeout=timeout)
        return ProxyTarget(
            app_id=inst.app_id,
            state=inst.state,
            url=inst.address,
            ws_url=inst.ws_url,
            error=inst.error,
        )
