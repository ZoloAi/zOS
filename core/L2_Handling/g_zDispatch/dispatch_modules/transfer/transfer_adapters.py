# zOS/core/L2_Handling/g_zDispatch/dispatch_modules/transfer/transfer_adapters.py
"""
Transfer adapters — backend-agnostic source/target endpoints for zTransfer.

Each adapter is constructed with the engine (for zos / logger / display access)
and declares ``WANTS`` — the payload nature it consumes when acting as a target
(``rows`` or ``blob``). The engine inserts the codec only when a target wants a
nature the source did not produce.

Source role  →  read(spec, context, walker) -> TransferPayload
Target role  →  write(payload, spec, mode, fmt, context, walker) -> dict

Spec keys (a transfer spec is plain zUI dict, file-type agnostic):
    file    : {from|to: file, path|source: @.Data.x.csv}
    model   : {from|to: model, model: @.models..., query: {<zData read dict>}}
    storage : {from|to: storage, key: users/1/avatar.jpg}
    bytes   : {from: bytes, data: <bytes|str>, filename:, mime:}
    inline  : {from: inline, content: <any>}
    response: {to: response, filename:, output:, ...}   (CLI file / Bifrost download)
"""

from pathlib import Path as _Path
from typing import Any, Dict, Optional

import os as _os

from zOS.L1_Foundation.a_zConfig.zConfig_modules import SESSION_KEY_ZMODE

from .transfer_payload import TransferPayload, NATURE_BLOB, NATURE_ROWS
from .transfer_paths import resolve_file_path, resolve_output_dir
from ..dispatch_constants import MODE_BIFROST

_EXPORT_DIR = "exports"


class TransferAdapter:
    """Base class. Subclasses implement read (source) and/or write (target)."""

    WANTS = NATURE_BLOB

    def __init__(self, engine: Any) -> None:
        self.engine = engine
        self.zos = engine.zos
        self.logger = engine.logger

    def read(self, spec, context, walker) -> TransferPayload:  # noqa: D401
        raise NotImplementedError(f"{type(self).__name__} cannot be a source")

    def write(self, payload, spec, mode, fmt, context, walker) -> Dict[str, Any]:
        raise NotImplementedError(f"{type(self).__name__} cannot be a target")

    def _display(self, walker):
        if walker is not None and getattr(walker, "display", None) is not None:
            return walker.display
        return self.engine.display


# ─────────────────────────────────────────────────────────────────────────────
# file  ── local filesystem (zPath dot-notation)
# ─────────────────────────────────────────────────────────────────────────────

class FileAdapter(TransferAdapter):
    WANTS = NATURE_BLOB

    def read(self, spec, context, walker) -> TransferPayload:
        src = spec.get("path") or spec.get("source")
        if not src:
            raise ValueError("file source requires 'path'")
        os_path = resolve_file_path(self.zos, src)
        data = _Path(os_path).read_bytes()
        return TransferPayload(data=data, meta={"path": os_path,
                                                "filename": _os.path.basename(os_path)})

    def write(self, payload, spec, mode, fmt, context, walker) -> Dict[str, Any]:
        out = spec.get("path") or spec.get("output")
        if not out:
            raise ValueError("file target requires 'path'")
        os_path = resolve_file_path(self.zos, out)
        _Path(os_path).parent.mkdir(parents=True, exist_ok=True)
        _Path(os_path).write_bytes(payload.as_bytes())
        return {"success": True, "path": os_path}


# ─────────────────────────────────────────────────────────────────────────────
# model  ── zData rows (silent read / insert)
# ─────────────────────────────────────────────────────────────────────────────

class ModelAdapter(TransferAdapter):
    WANTS = NATURE_ROWS

    def read(self, spec, context, walker) -> TransferPayload:
        query: Dict[str, Any] = dict(spec.get("query") or {})
        if not query and spec.get("model"):
            query = {"model": spec["model"]}
        query.setdefault("action", "read")
        query["silent"] = True  # return List[Dict], do not print a table
        rows = self.zos.data.handle_request(query, context=context)
        if not isinstance(rows, list):
            self.logger.warning(
                f"[zTransfer] model source did not return a list (got {type(rows).__name__})"
            )
            rows = []
        return TransferPayload(rows=rows)

    def write(self, payload, spec, mode, fmt, context, walker) -> Dict[str, Any]:
        target = spec.get("model") or spec.get("target")
        if not target:
            raise ValueError("model target requires 'model'")
        rows = payload.rows or []

        # replace mode → truncate first (the real zData action; the old zImport
        # used a non-existent 'delete_all' that silently no-op'd).
        if mode == "replace":
            self.zos.data.handle_request(
                {"action": "truncate", "model": target}, context=context
            )

        inserted = 0
        for row in rows:
            result = self.zos.data.handle_request(
                {"action": "insert", "model": target, "data": row},
                context=None,  # row data already resolved; passing a context here breaks .items()
            )
            if result and isinstance(result, dict) and not result.get("success", True):
                return {
                    "success": False,
                    "error": str(result.get("error", "unknown")),
                    "inserted": inserted,
                }
            inserted += 1
        return {"success": True, "count": inserted}


# ─────────────────────────────────────────────────────────────────────────────
# storage  ── object storage (zos.comm.storage: local / s3 / …)
# ─────────────────────────────────────────────────────────────────────────────

class StorageAdapter(TransferAdapter):
    WANTS = NATURE_BLOB

    def _storage(self):
        storage = getattr(self.zos.comm, "storage", None)
        if storage is None:
            raise RuntimeError("zos.comm.storage is not available")
        return storage

    def read(self, spec, context, walker) -> TransferPayload:
        key = spec.get("key")
        if not key:
            raise ValueError("storage source requires 'key'")
        data = self._storage().get(key)
        return TransferPayload(data=data, meta={"key": key,
                                                "filename": _os.path.basename(key)})

    def write(self, payload, spec, mode, fmt, context, walker) -> Dict[str, Any]:
        key = spec.get("key")
        if not key:
            raise ValueError("storage target requires 'key'")
        storage = self._storage()
        stored_path = storage.put(key, payload.as_bytes())
        try:
            url = storage.get_url(key)
        except Exception:  # pylint: disable=broad-except
            url = stored_path
        return {"success": True, "key": key, "path": stored_path, "url": url}


# ─────────────────────────────────────────────────────────────────────────────
# bytes  ── in-memory payload (uploads, programmatic callers)
# ─────────────────────────────────────────────────────────────────────────────

class BytesAdapter(TransferAdapter):
    WANTS = NATURE_BLOB

    def read(self, spec, context, walker) -> TransferPayload:
        raw = spec.get("data")
        if raw is None:
            raise ValueError("bytes source requires 'data'")
        data = raw if isinstance(raw, (bytes, bytearray)) else str(raw).encode("utf-8")
        return TransferPayload(
            data=bytes(data),
            meta={"filename": spec.get("filename"), "mime": spec.get("mime")},
        )


# ─────────────────────────────────────────────────────────────────────────────
# inline  ── literal content (no rows)
# ─────────────────────────────────────────────────────────────────────────────

class InlineAdapter(TransferAdapter):
    WANTS = NATURE_BLOB

    def read(self, spec, context, walker) -> TransferPayload:
        # Content is encoded by the bridge (engine passes source['content']).
        return TransferPayload(meta={"content": spec.get("content")})


# ─────────────────────────────────────────────────────────────────────────────
# response  ── deliver to the user (CLI file + print / Bifrost download)
# ─────────────────────────────────────────────────────────────────────────────

class ResponseAdapter(TransferAdapter):
    WANTS = NATURE_BLOB

    def write(self, payload, spec, mode, fmt, context, walker) -> Dict[str, Any]:
        filename = str(spec.get("filename", "export"))
        full_filename = f"{filename}.{fmt}"
        encoded = payload.as_text()

        zmode = self.zos.session.get(SESSION_KEY_ZMODE, "")
        if zmode == MODE_BIFROST:
            return self._deliver_bifrost(full_filename, encoded, fmt, walker)
        return self._deliver_cli(full_filename, encoded, spec.get("output"), walker)

    def _deliver_cli(self, filename, encoded, output, walker) -> Dict[str, Any]:
        if output:
            export_dir = _Path(resolve_output_dir(self.zos, output))
        else:
            zspace = self.zos.session.get("zSpace", _os.getcwd())
            export_dir = _Path(zspace) / "Data" / _EXPORT_DIR
        export_dir.mkdir(parents=True, exist_ok=True)
        out_path = export_dir / filename
        out_path.write_text(encoded, encoding="utf-8")

        display = self._display(walker)
        rows = max(len(encoded.splitlines()) - 1, 0)
        display.text(f"✅  Exported {rows} row(s) → {out_path}")
        self.logger.info(f"[zTransfer] Wrote {out_path}")
        return {"success": True, "path": str(out_path)}

    def _deliver_bifrost(self, filename, encoded, fmt, walker) -> Dict[str, Any]:
        display = self._display(walker)
        if hasattr(display, "zExport"):
            display.zExport(filename, encoded, fmt)
        else:
            event = {"event": "download", "filename": filename,
                     "content": encoded, "format": fmt}
            if hasattr(display, "_push_event"):
                display._push_event(event)
        self.logger.info(f"[zTransfer] Bifrost download queued: {filename}")
        return {"success": True, "filename": filename}


# Registry: kind string → adapter class
ADAPTER_REGISTRY = {
    "file": FileAdapter,
    "model": ModelAdapter,
    "storage": StorageAdapter,
    "bytes": BytesAdapter,
    "inline": InlineAdapter,
    "response": ResponseAdapter,
}
