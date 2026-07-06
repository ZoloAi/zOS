# zOS/core/L3_Abstraction/m_zData/zData_modules/shared/migration_backfill.py
"""
Declarative data backfill for migrations.

A schema `add column` only reshapes structure. Backfill is the *data* half of a
migration: when a freshly-added column carries a ``backfill:`` directive, this
module populates the existing rows for it — the declarative answer to Alembic's
``op.execute`` / Django's ``RunPython``.

Design (why it's SSOT + backend-agnostic)
-----------------------------------------
- ``backfill`` is a COLUMN-LEVEL property, so it rides inside the column def
  exactly like ``default`` / ``rules`` / ``renamed_from``. create_table and the
  validator already pass unknown column props through untouched, and the diff
  engine already carries the full column def in ``columns_added`` — so nothing
  else in the stack needs to learn about backfill.
- The value is computed IN PYTHON from each row dict (never SQL), then written via
  the adapter's own ``update``. So csv, sqlite and postgres behave identically —
  the same zOS-layer resolution as views. No dialect, no raw SQL.
- Idempotent by construction: it only runs for columns ADDED in this migration
  (a re-migrate sees them as existing, not added → skipped), and even then only
  fills rows whose target is currently empty — so it never clobbers real data.

Backfill spec vocabulary (declarative)
--------------------------------------
    backfill: free                     # literal — every empty row gets "free"
    backfill: %name                    # copy — mirror another column's value
    backfill: {copy: name}             #   (explicit form of the above)
    backfill: {concat: [%first, " ", %last]}   # join columns + literal strings
    backfill: {value: "%literal"}      # escape hatch for a literal that starts with %

A ``%col`` token resolves to that column's value in the current row; anything else
is a literal. A backfill that can't resolve to a value (e.g. copy of a missing
column) is skipped for that row, not written as null.
"""

from zOS import Any, Dict

_BACKFILL_KEY = "backfill"
_PK_KEYS = ("pk", "primary_key")


def _pk_column(columns: Dict[str, Any]):
    """Return the single-column primary key name, or None."""
    for name, cdef in (columns or {}).items():
        if isinstance(cdef, dict) and any(cdef.get(k) for k in _PK_KEYS):
            return name
    return None


def _resolve_token(token: Any, row: Dict[str, Any]) -> Any:
    """A ``%col`` string reads that column off the row; anything else is literal."""
    if isinstance(token, str) and token.startswith("%"):
        return row.get(token[1:])
    return token


def compute_backfill_value(spec: Any, row: Dict[str, Any]) -> Any:
    """Resolve one backfill spec against one row → the value to write (or None)."""
    if isinstance(spec, dict):
        if "value" in spec:
            return spec["value"]
        if "copy" in spec:
            return row.get(spec["copy"])
        if "from" in spec:
            return row.get(spec["from"])
        if "concat" in spec:
            parts = spec.get("concat") or []
            out = []
            for part in parts:
                resolved = _resolve_token(part, row)
                out.append("" if resolved is None else str(resolved))
            return "".join(out)
        return None
    return _resolve_token(spec, row)


def _is_empty(value: Any) -> bool:
    """A cell is 'unfilled' if it's None or the empty string (CSV adds "")."""
    return value is None or value == ""


def apply_backfills(
    ops: Any,
    tables_modified: Dict[str, Any],
    schema: Dict[str, Any],
    logger: Any = None,
) -> int:
    """
    Populate freshly-added columns that declare ``backfill:``.

    Runs AFTER the structural DDL (so the column exists), inside the migration
    transaction (so a failure rolls back with the rest). Only touches columns in
    ``columns_added`` for this migration, and within those only rows whose value is
    still empty — making a re-run a clean no-op.

    Args:
        ops: DataOperations/ops facade (adapter.select + adapter.update, .schema).
        tables_modified: diff['tables_modified'] — {table: {columns_added: {...}}}.
        schema: the loaded (zCLI) schema {table: {col: def}} — for pk lookup.
        logger: optional logger.

    Returns:
        Count of row-values written.
    """
    filled = 0
    for table, changes in (tables_modified or {}).items():
        added = changes.get("columns_added", {}) or {}
        specs = {
            col: cdef[_BACKFILL_KEY]
            for col, cdef in added.items()
            if isinstance(cdef, dict) and _BACKFILL_KEY in cdef
        }
        if not specs:
            continue

        columns = schema.get(table) if isinstance(schema, dict) else None
        pk = _pk_column(columns if isinstance(columns, dict) else {})
        if not pk:
            if logger:
                logger.warning(
                    "[zBackfill] %s has no single primary key — skipping backfill "
                    "(computed backfill needs a pk to target rows).", table
                )
            continue

        try:
            rows = ops.adapter.select(table)
        except Exception as exc:  # pylint: disable=broad-except
            if logger:
                logger.warning("[zBackfill] Could not read %s: %s", table, exc)
            continue

        for col, spec in specs.items():
            for row in rows:
                if not _is_empty(row.get(col)):
                    continue
                key = row.get(pk)
                if key is None:
                    continue
                value = compute_backfill_value(spec, row)
                if value is None:
                    continue
                try:
                    ops.adapter.update(table, [col], [value], {pk: key})
                    filled += 1
                except Exception as exc:  # pylint: disable=broad-except
                    if logger:
                        logger.warning(
                            "[zBackfill] %s.%s row %s failed: %s", table, col, key, exc
                        )
    return filled


__all__ = ["apply_backfills", "compute_backfill_value"]
