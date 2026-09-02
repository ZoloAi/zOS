"""
zResult — the canonical handler/plugin return envelope for zOS.

One shape, consumed by every front-end (HTTP/zAPI, CLI, Bifrost, zRaven/zAgent)
so feedback is uniform no matter which subsystem produced it:

    ok:      bool            success flag
    data:    Any             payload (rows, ids, urls, dicts, ...)
    message: str             human / agent-facing note
    error:   str | None      error text when ok is False
    status:  int             HTTP-ish status hint (200 / 201 / 4xx / 5xx)
    meta:    dict            extra hints (action, count, ...)

`coerce()` normalises an arbitrary plugin/handler return into a ZResult, so
imperative plugins can keep returning plain dicts / values while the framework
still gets structured, legible feedback.
"""

from typing import Any, Optional

__all__ = ["ZResult", "ZAbort"]

# Control keys understood directly on a returned dict.
_CTRL_KEYS = {"ok", "success", "data", "message", "error", "status", "status_code", "meta"}


class ZResult:
    """Structured result envelope shared across zOS subsystems."""

    __slots__ = ("ok", "data", "message", "error", "status", "meta", "content_type", "filename")

    def __init__(
        self,
        ok: bool = True,
        data: Any = None,
        message: str = "",
        error: Optional[str] = None,
        status: Optional[int] = None,
        meta: Optional[dict] = None,
        content_type: Optional[str] = None,
        filename: Optional[str] = None,
    ):
        self.ok = bool(ok)
        self.data = data
        self.message = message or ""
        self.error = error
        self.status = int(status) if status is not None else (200 if self.ok else 500)
        self.meta = meta or {}
        # Binary-response hint: when content_type is set, `data` is the raw byte
        # payload and a transport writes it verbatim (see `is_binary`) instead of
        # the JSON envelope. Generic — a file, an image, any non-JSON body.
        self.content_type = content_type
        self.filename = filename

    # ── constructors ────────────────────────────────────────────────────────
    @classmethod
    def success(cls, data: Any = None, message: str = "", status: int = 200, meta: Optional[dict] = None) -> "ZResult":
        return cls(ok=True, data=data, message=message, status=status, meta=meta)

    @classmethod
    def failure(cls, error: str, status: int = 500, data: Any = None, meta: Optional[dict] = None) -> "ZResult":
        return cls(ok=False, error=str(error), status=status, data=data, meta=meta)

    @classmethod
    def binary(
        cls,
        data: Any,
        content_type: str,
        status: int = 200,
        filename: Optional[str] = None,
        meta: Optional[dict] = None,
    ) -> "ZResult":
        """A RAW binary response — bytes emitted verbatim, not the JSON envelope.

        Generic across subsystems: any handler that must return a non-JSON body
        (a file download, an image, a stream) returns this. ``data`` is the byte
        payload (``bytes``/``bytearray`` or a ``.bytes``-exposing ref); the
        transport writes it under ``content_type``. ``filename`` (optional) sets a
        Content-Disposition. Carries no app vocabulary — the caller decides what
        the bytes are.
        """
        return cls(ok=True, data=data, status=status, meta=meta,
                   content_type=content_type, filename=filename)

    @classmethod
    def coerce(cls, value: Any) -> "ZResult":
        """Normalise an arbitrary handler/plugin return into a ZResult."""
        if isinstance(value, ZResult):
            return value

        # The wizard hard-abort sentinel.
        if value == "error":
            return cls.failure("Handler returned 'error'")

        # An "error: <detail>" string is a FAILURE carrying its own sentence
        # (zOS#90): it used to coerce as a SUCCESS with the text as message —
        # the one place the author DID write a real error sentence, and the
        # envelope threw it away (ok:true, no error field).
        if isinstance(value, str) and value[:6].lower() == "error:":
            detail = value[6:].strip() or "Handler returned an error"
            return cls.failure(detail)

        if isinstance(value, dict):
            d = value
            # Explicit envelope (already ok-shaped).
            if "ok" in d:
                return cls(
                    ok=d.get("ok"),
                    data=d.get("data", _payload_minus_ctrl(d)),
                    message=d.get("message", ""),
                    error=d.get("error"),
                    status=d.get("status", d.get("status_code")),
                    meta=d.get("meta"),
                )
            # Legacy plugin shape: {success, error, status_code, ...}.
            if "success" in d:
                ok = bool(d.get("success"))
                return cls(
                    ok=ok,
                    data=d.get("data", _payload_minus_ctrl(d)),
                    message=d.get("message", ""),
                    error=d.get("error") if not ok else None,
                    status=d.get("status_code", d.get("status")),
                    meta=d.get("meta"),
                )
            # Plain data dict.
            return cls.success(data=d)

        # Bare values: None/False → no-op success-empty.
        if value is None or value is False:
            return cls.success(data=None)
        # Bare string → the detail AS the message (documented contract: "a plain
        # return → a zSignal, the detail as message" — 12_zfunc.md). Non-string
        # truthy values (dict handled above; numbers/lists/etc.) stay structured
        # payload in .data since they aren't human-facing text.
        if isinstance(value, str):
            return cls.success(message=value)
        return cls.success(data=value)

    # ── binary response ─────────────────────────────────────────────────────
    @property
    def is_binary(self) -> bool:
        """True when this result carries a raw byte body (see :meth:`binary`)."""
        return self.content_type is not None

    def as_bytes(self) -> bytes:
        """Return the binary payload as ``bytes`` (accepts bytes-like or a
        ``.bytes``-exposing ref such as a zData ``BlobRef``)."""
        data = self.data
        if isinstance(data, (bytes, bytearray, memoryview)):
            return bytes(data)
        ref_bytes = getattr(data, "bytes", None)
        if isinstance(ref_bytes, (bytes, bytearray, memoryview)):
            return bytes(ref_bytes)
        if data is None:
            return b""
        return str(data).encode("utf-8")

    # ── serialisation ─────────────────────────────────────────────────────────
    def to_dict(self) -> dict:
        out: dict = {"ok": self.ok}
        if self.data is not None:
            out["data"] = self.data
        if self.message:
            out["message"] = self.message
        if self.error:
            out["error"] = self.error
        if self.meta:
            out["meta"] = self.meta
        return out

    def to_http(self):
        """Return (status_code, json_payload_dict)."""
        return self.status, self.to_dict()

    def __repr__(self) -> str:
        return f"ZResult(ok={self.ok}, status={self.status}, error={self.error!r})"


class ZAbort(Exception):
    """Raise inside a plugin to abort with a structured failure ZResult.

    Lets plugin code stay linear — validation/guard failures read as a single
    ``raise ZAbort("...", status=4xx)`` instead of hand-built return dicts. The
    @zfunc wrapper (and facades) catch it and surface ``.result`` so every
    front-end gets the same envelope.
    """

    def __init__(
        self,
        error: str,
        status: int = 400,
        data: Any = None,
        meta: Optional[dict] = None,
    ):
        self.result = ZResult.failure(str(error), status=status, data=data, meta=meta)
        super().__init__(str(error))


def _payload_minus_ctrl(d: dict) -> dict:
    """Strip control keys so leftover keys become the data payload."""
    return {k: v for k, v in d.items() if k not in _CTRL_KEYS}
