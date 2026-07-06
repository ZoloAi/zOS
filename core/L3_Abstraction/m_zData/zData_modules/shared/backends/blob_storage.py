# zOS/core/L3_Abstraction/m_zData/zData_modules/shared/backends/blob_storage.py
"""
CSV sidecar storage for blob fields.

CSV cells can't hold binary, so a ``type: blob`` value on the CSV backend is
spilled to a hidden sidecar file and the cell stores a relative path. SQL
backends (BLOB/BYTEA) store bytes inline and never touch this module.

Sidecar layout (relative to the CSV data dir):
    .zblobs/<table>/<field>/<uuid>.bin

Hidden ``.zblobs`` dir keeps the table directory spreadsheet-friendly. Pure
filesystem helpers — no pandas, no schema knowledge.
"""

from zOS import os, uuid, Path

__all__ = ["BLOBS_DIRNAME", "spill", "resolve", "unlink"]

BLOBS_DIRNAME = ".zblobs"


def _field_dir(base_path, table: str, field: str) -> Path:
    return Path(base_path) / BLOBS_DIRNAME / table / field


def spill(base_path, table: str, field: str, data: bytes) -> str:
    """Write ``data`` to a new sidecar file; return its path relative to base_path."""
    target_dir = _field_dir(base_path, table, field)
    target_dir.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4()}.bin"
    abs_path = target_dir / name
    with open(abs_path, "wb") as fh:
        fh.write(data if isinstance(data, (bytes, bytearray)) else bytes(data))
    rel = os.path.join(BLOBS_DIRNAME, table, field, name)
    return rel


def resolve(base_path, rel_path: str) -> str:
    """Resolve a stored relative sidecar path to an absolute path."""
    return str(Path(base_path) / rel_path)


def unlink(base_path, rel_path: str) -> bool:
    """Delete a sidecar file. Returns True if removed, False if it was absent."""
    if not rel_path:
        return False
    abs_path = Path(base_path) / rel_path
    try:
        abs_path.unlink()
        return True
    except FileNotFoundError:
        return False
    except OSError:
        return False
