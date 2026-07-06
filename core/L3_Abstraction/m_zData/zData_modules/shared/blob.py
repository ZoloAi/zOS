# zOS/core/L3_Abstraction/m_zData/zData_modules/shared/blob.py
"""
zData blob primitives — the SSOT for binary (`type: blob`) field values.

Two primitives, one canonical shape:

- ``BlobRef`` — the single in-memory form of a blob value. Every backend adapter
  returns a ``BlobRef`` on read (SQL wraps in-row bytes; CSV wraps a sidecar path
  with lazy byte-loading), so callers never branch on backend.
- ``coerce_blob`` — normalises any accepted input form into raw ``bytes`` for
  storage. Invoked in the insert/update pipeline alongside uuid auto-gen / bool
  coercion.

Backend fulfilment of the same ``type: blob`` intent:
    sqlite      → BLOB   (bytes inline)
    postgresql  → BYTEA  (bytes inline)
    csv         → sidecar file; the cell holds a relative path

Stdlib only (via the zOS import shim) — safe to import from any adapter, the
validator, or the migration engine.
"""

from zOS import base64, os, Any, Dict, Optional

__all__ = ["BlobRef", "coerce_blob", "parse_size"]

# ============================================================
# Size parsing
# ============================================================

# Ordered longest-first so "KB"/"MB"/"GB" win over the bare "B" suffix.
_SIZE_UNITS = (("GB", 1024 ** 3), ("MB", 1024 ** 2), ("KB", 1024), ("B", 1))


def parse_size(spec: Any) -> Optional[int]:
    """Parse a human-friendly size into an integer byte count.

    Accepts ints/floats (taken as raw byte counts) and strings like ``"2MB"``,
    ``"512 KB"``, ``"1048576"``. Returns ``None`` for unparseable / absent input
    so callers can treat "no limit" distinctly from "zero".
    """
    if spec is None:
        return None
    if isinstance(spec, bool):  # guard: bool is an int subclass
        return None
    if isinstance(spec, (int, float)):
        return int(spec)
    s = str(spec).strip().upper().replace(" ", "")
    if not s:
        return None
    for unit, factor in _SIZE_UNITS:
        if s.endswith(unit):
            num = s[: -len(unit)]
            try:
                return int(float(num) * factor)
            except ValueError:
                return None
    try:
        return int(s)
    except ValueError:
        return None


# ============================================================
# BlobRef — canonical in-memory blob value
# ============================================================

class BlobRef:
    """Backend-agnostic handle to a binary value.

    Construct from in-memory bytes (SQL backends) or from a sidecar path (CSV).
    Byte access is lazy for path-backed refs, so a wide ``select`` does not pull
    every file into memory until a caller actually reads ``.bytes``.
    """

    __slots__ = ("_data", "_path", "_size", "mime", "filename")

    def __init__(
        self,
        data: Optional[bytes] = None,
        path: Optional[str] = None,
        size: Optional[int] = None,
        mime: Optional[str] = None,
        filename: Optional[str] = None,
    ) -> None:
        self._data = data
        self._path = str(path) if path else None
        self._size = size
        self.mime = mime
        self.filename = filename

    @property
    def path(self) -> Optional[str]:
        """Sidecar path when CSV-backed, else ``None`` (bytes live inline)."""
        return self._path

    @property
    def bytes(self) -> bytes:
        """The binary payload — read from the sidecar on first access if needed."""
        if self._data is None and self._path:
            with open(self._path, "rb") as fh:
                self._data = fh.read()
        return self._data if self._data is not None else b""

    @property
    def size(self) -> int:
        """Byte length — from cached size, in-memory bytes, or a sidecar stat."""
        if self._size is not None:
            return self._size
        if self._data is not None:
            self._size = len(self._data)
        elif self._path and os.path.exists(self._path):
            self._size = os.path.getsize(self._path)
        else:
            self._size = 0
        return self._size

    def save_to(self, dest: str) -> str:
        """Write the payload to ``dest`` and return the destination path."""
        with open(dest, "wb") as fh:
            fh.write(self.bytes)
        return dest

    def __bytes__(self) -> bytes:
        return self.bytes

    def __len__(self) -> int:
        return self.size

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, BlobRef):
            return self.bytes == other.bytes
        if isinstance(other, (bytes, bytearray, memoryview)):
            return self.bytes == bytes(other)
        return NotImplemented

    def __repr__(self) -> str:
        suffix = f" · {self.mime}" if self.mime else ""
        return f"‹blob {self.size} bytes{suffix}›"


# ============================================================
# coerce_blob — normalise any input into raw bytes
# ============================================================

_INPUT_RAW = "raw"
_INPUT_BASE64 = "base64"
_INPUT_PATH = "path"
_RULE_BLOB_INPUT = "blob_input"
_SCHEMA_KEY_RULES = "rules"


def coerce_blob(value: Any, field_def: Optional[Dict[str, Any]] = None) -> Any:
    """Normalise an accepted blob input into raw ``bytes`` for storage.

    Accepted inputs:
        - ``bytes`` / ``bytearray`` / ``memoryview`` — used directly
        - ``BlobRef`` — its payload is returned
        - an upload-like object exposing ``.read()`` (Bifrost multipart)
        - ``str`` — interpreted per the field's ``blob_input`` rule:
            ``raw`` (default) → utf-8 encode | ``base64`` → decode | ``path`` → read file

    Empty / ``None`` values pass through untouched so the required/nullable checks
    upstream own emptiness. Returns ``bytes`` for any provided value.
    """
    if value is None or value == "":
        return value
    if isinstance(value, BlobRef):
        return value.bytes
    if isinstance(value, (bytes, bytearray, memoryview)):
        return bytes(value)

    reader = getattr(value, "read", None)
    if callable(reader):
        data = reader()
        return data if isinstance(data, bytes) else bytes(data)

    rules = {}
    if isinstance(field_def, dict):
        rules = field_def.get(_SCHEMA_KEY_RULES, {}) or {}
    mode = str(rules.get(_RULE_BLOB_INPUT, _INPUT_RAW)).strip().lower()

    if isinstance(value, str):
        if mode == _INPUT_BASE64:
            return base64.b64decode(value)
        if mode == _INPUT_PATH:
            with open(value, "rb") as fh:
                return fh.read()
        return value.encode("utf-8")

    return str(value).encode("utf-8")
