# zOS/core/L3_Abstraction/m_zData/zData_modules/shared/operations/blob_ops.py
"""
Op-layer blob orchestration.

The adapters own physical storage (SQL inline bytes / CSV sidecar files); these
helpers sit in the backend-agnostic CRUD pipeline and decide *when* to translate:

    write:   coerce_blob_fields  (input → bytes, before validation sizes it)
             store_blob_fields   (bytes → backend cell, after validation)
    read:    describe_blob_fields (cell → JSON-safe descriptor for display/return)
    delete:  cleanup_blob_fields  (release backend storage for removed rows)

Programmatic byte access (e.g. the serve route) goes straight to
``ops.adapter.load_blob`` which returns a ``BlobRef`` — the display path never
ships raw bytes into a table render or a JSON payload.
"""

from zOS import Any, Dict, List

from ..blob import coerce_blob
from ..validators.constants import BLOB_SCHEMA_TYPES, SCHEMA_KEY_TYPE

__all__ = [
    "blob_fields",
    "coerce_blob_fields",
    "store_blob_fields",
    "describe_blob_fields",
    "cleanup_blob_fields",
    "blob_where_error",
]

_EMPTY = (None, "")

# WHERE operators that are meaningful on a binary column (presence checks only).
_BLOB_WHERE_ALLOWED = {"$notnull", "$null"}


def blob_fields(table_schema: Dict[str, Any]) -> List[str]:
    """Return the names of blob-typed fields declared in a table schema."""
    if not isinstance(table_schema, dict):
        return []
    return [
        name for name, fdef in table_schema.items()
        if isinstance(fdef, dict) and fdef.get(SCHEMA_KEY_TYPE) in BLOB_SCHEMA_TYPES
    ]


def coerce_blob_fields(data: Dict[str, Any], table_schema: Dict[str, Any]) -> Dict[str, Any]:
    """Normalise blob inputs in ``data`` to bytes (so validation sizes the bytes)."""
    for name in blob_fields(table_schema):
        if name in data and data[name] not in _EMPTY:
            data[name] = coerce_blob(data[name], table_schema.get(name))
    return data


def store_blob_fields(
    data: Dict[str, Any], table: str, table_schema: Dict[str, Any], ops: Any
) -> Dict[str, Any]:
    """Convert coerced blob bytes into backend storage cells (post-validation)."""
    for name in blob_fields(table_schema):
        if name in data and data[name] not in _EMPTY:
            data[name] = ops.adapter.store_blob(table, name, data[name])
    return data


def _descriptor(ref: Any) -> Any:
    """Build a JSON-safe descriptor from a BlobRef (no byte read — size is lazy/stat)."""
    if ref is None:
        return None
    return {
        "_zblob": True,
        "size": ref.size,
        "mime": getattr(ref, "mime", None),
        "filename": getattr(ref, "filename", None),
    }


def describe_blob_fields(
    rows: List[Dict[str, Any]], table: str, table_schema: Dict[str, Any], ops: Any
) -> List[Dict[str, Any]]:
    """Replace blob cells in result rows with JSON-safe descriptors for display/return."""
    fields = blob_fields(table_schema)
    if not fields or not rows:
        return rows
    for row in rows:
        if not isinstance(row, dict):
            continue
        for name in fields:
            if name in row and row[name] not in _EMPTY:
                row[name] = _descriptor(ops.adapter.load_blob(table, name, row[name]))
    return rows


def blob_where_error(where: Any, table_schema: Dict[str, Any]):
    """Reject filtering on a blob column beyond IS NULL / IS NOT NULL.

    Binary values aren't comparable across backends (inline bytes vs sidecar path),
    so only presence checks are meaningful. Returns an error string on misuse, else
    ``None``. Only the structured dict WHERE form is guarded; a raw-SQL string WHERE
    is an escape hatch and passes through unchecked.
    """
    if not isinstance(where, dict):
        return None
    fields = set(blob_fields(table_schema))
    if not fields:
        return None
    for col, cond in where.items():
        base = str(col).split(".")[-1].split("__")[0]
        if base not in fields:
            continue
        if cond is None:  # IS NULL
            continue
        if isinstance(cond, dict) and set(cond.keys()) <= _BLOB_WHERE_ALLOWED:
            continue
        return (
            f"Cannot filter on blob field '{base}': binary columns support only "
            f"IS NULL / IS NOT NULL, not value comparison"
        )
    return None


def cleanup_blob_fields(
    rows: List[Dict[str, Any]], table: str, table_schema: Dict[str, Any], ops: Any
) -> None:
    """Release backend blob storage for rows that are about to be deleted."""
    fields = blob_fields(table_schema)
    if not fields or not rows:
        return
    for row in rows:
        if not isinstance(row, dict):
            continue
        for name in fields:
            if name in row:
                ops.adapter.delete_blob(table, name, row[name])
