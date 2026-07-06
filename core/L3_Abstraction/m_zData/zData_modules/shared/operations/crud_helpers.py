# zOS/core/L3_Abstraction/m_zData/zData_modules/shared/operations/crud_helpers.py
"""
Shared RETURNING helper — the SQL ``RETURNING`` clause for every write.

One copy imported by crud_insert / crud_update / crud_upsert / crud_delete (SSOT),
so INSERT / UPDATE / DELETE / UPSERT all surface the affected rows identically:

    returning: true            → all columns
    returning: [id, name]      → only those columns

The write handlers return the projected rows (list[dict]) when ``returning`` is set
— programmatically usable, not just displayed — and their usual bool otherwise.
DELETE snapshots the rows *before* removal and hands them in via ``emit_returning``;
INSERT/UPDATE/UPSERT fetch post-write by id via ``display_returning``.
"""

from zOS import Any
from ..chunk_bridge import live_read


def _project_returning(rows: list, returning) -> list:
    """Column-project the returned rows when ``returning`` is a list of names."""
    if isinstance(returning, list):
        return [{k: v for k, v in row.items() if k in returning} for row in rows]
    return rows


def emit_returning(table: str, rows: list, returning, ops: Any) -> list:
    """
    Display already-fetched ``rows`` as a zTable and return them (column-projected).

    Used when the caller already holds the rows — notably DELETE, which must
    snapshot rows *before* they are removed.
    """
    if not rows:
        return []
    rows = _project_returning(rows, returning)
    columns = list(rows[0].keys()) if rows else []
    ops.logger.info(f"[zData] RETURNING {len(rows)} row(s) from {table}")
    with live_read(ops.zos):
        ops.display.zTable(table, columns, rows)
    return rows


def _display_returning(table: str, row_ids: list, returning, ops: Any) -> list:
    """
    Fetch rows by their IDs (post-write), display as a zTable, and return them.

    Used by INSERT / UPDATE / UPSERT … RETURNING. Uses per-row dict WHERE queries
    to avoid the string-WHERE limitation in the CSV adapter.

    `returning` can be:
      - True / "true" / "*"  → all columns
      - list[str]            → specific columns only
    """
    if not row_ids:
        return []

    table_schema = ops.schema.get(table, {})
    auto_id_field = 'id'
    for field_name, field_def in table_schema.items():
        if isinstance(field_def, dict) and field_def.get('auto_increment'):
            auto_id_field = field_name
            break

    rows = []
    for rid in row_ids:
        try:
            fetched = ops.select(table, where={auto_id_field: rid})
            if fetched:
                rows.extend(fetched)
        except Exception as e:  # pylint: disable=broad-except
            ops.logger.warning(f"[zData] RETURNING fetch failed for id {rid}: {e}")

    if not rows:
        ops.logger.warning(f"[zData] RETURNING: no rows fetched for {table} ids={row_ids}")
        return []

    return emit_returning(table, rows, returning, ops)
