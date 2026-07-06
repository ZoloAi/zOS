# zOS/core/L3_Abstraction/m_zData/zData_modules/migration/backend_transfer.py
"""
Backend transfer engine — move a whole dataset from one adapter to another through
one shared, in-memory row model. This is the "zOS magic" behind a ``Data_Type``
change (csv ↔ sqlite ↔ postgres): the same declarative schema, replayed onto a
different store, with every row carried across and row counts validated.

Deliberately pure w.r.t. wiring: it speaks only the adapter API (list_tables,
select, register_schema, create_table, insert_many) so it works for ANY registered
backend and is unit-testable without a live server (CSV ↔ SQLite locally).

Row model:
    {table: {"columns": <col defs>, "rows": [ {col: value}, ... ]}}

Two halves — ``export_tables`` reads the source into that model, ``import_tables``
replays it onto the target (create table from declared columns, coerce values to
declared types, bulk insert). ``transfer_backend`` runs both and validates counts.
"""

from zOS import Any, Dict

from ..shared.data_keys import SCHEMA_KEY_META

# Bookkeeping tables never travel with a backend change — they're store-local.
_INTERNAL_PREFIXES = ("__zmigration", "_zdata_migrations", "_zmigrations")


def _user_tables(schema: Dict[str, Any]):
    """Yield (table_name, column_defs) for every declared user table.

    Column defs = only the dict-valued entries in a table def, so table-level
    ``indexes`` (a list) and any other non-column keys are dropped — the target
    gets clean columns (indexes are re-declared + migrated on the new backend).
    """
    for name, table_def in (schema or {}).items():
        if name == SCHEMA_KEY_META or not isinstance(table_def, dict):
            continue
        if any(name.startswith(p) for p in _INTERNAL_PREFIXES):
            continue
        columns = {k: v for k, v in table_def.items() if isinstance(v, dict)}
        yield name, columns


def _coerce_value(value: Any, col_type: Any) -> Any:
    """Cast a (usually string, from CSV) value to its declared abstract type."""
    if value is None or col_type is None or not isinstance(value, str):
        return value
    try:
        if col_type == "int":
            return int(float(value)) if value != "" else None
        if col_type == "float":
            return float(value) if value != "" else None
        if col_type == "bool":
            return value.strip().lower() in ("1", "true", "yes", "t")
    except (ValueError, TypeError):
        return value
    return value


def _coerce_row(row: Dict[str, Any], columns: Dict[str, Any]) -> Dict[str, Any]:
    out = {}
    for key, val in row.items():
        cdef = columns.get(key)
        col_type = cdef.get("type") if isinstance(cdef, dict) else None
        out[key] = _coerce_value(val, col_type)
    return out


def export_tables(source_adapter: Any, schema: Dict[str, Any]) -> Dict[str, Any]:
    """Read every declared user table off the source into the shared row model."""
    dataset: Dict[str, Any] = {}
    for table, columns in _user_tables(schema):
        if hasattr(source_adapter, "table_exists") and not source_adapter.table_exists(table):
            continue
        rows = source_adapter.select(table) or []
        dataset[table] = {"columns": columns, "rows": [dict(r) for r in rows]}
    return dataset


def import_tables(target_adapter: Any, dataset: Dict[str, Any]) -> Dict[str, int]:
    """Replay the row model onto the target: create table, coerce, bulk insert."""
    written: Dict[str, int] = {}
    for table, payload in dataset.items():
        columns = payload["columns"]
        rows = payload["rows"]
        if hasattr(target_adapter, "register_schema"):
            target_adapter.register_schema(table, columns)
        if not (hasattr(target_adapter, "table_exists") and target_adapter.table_exists(table)):
            target_adapter.create_table(table, columns)
        coerced = [_coerce_row(r, columns) for r in rows]
        if coerced:
            target_adapter.insert_many(table, coerced)
        written[table] = len(coerced)
    return written


def transfer_backend(
    source_adapter: Any,
    target_adapter: Any,
    schema: Dict[str, Any],
    logger: Any = None,
) -> Dict[str, Any]:
    """
    Move all declared user tables from source → target, then validate row counts.

    Returns a report: success (all counts matched), tables moved, total rows, the
    per-table written counts, and any {table: {expected, actual}} mismatches.
    """
    dataset = export_tables(source_adapter, schema)
    written = import_tables(target_adapter, dataset)

    mismatches: Dict[str, Any] = {}
    for table, payload in dataset.items():
        expected = len(payload["rows"])
        actual = len(target_adapter.select(table) or [])
        if actual != expected:
            mismatches[table] = {"expected": expected, "actual": actual}

    if logger:
        logger.info(
            "[BackendTransfer] moved %d table(s), %d row(s); %d mismatch(es)",
            len(dataset), sum(written.values()), len(mismatches),
        )

    return {
        "success": not mismatches,
        "tables": len(dataset),
        "rows": sum(written.values()),
        "written": written,
        "mismatches": mismatches,
    }


def preview_transfer(source_adapter: Any, schema: Dict[str, Any]) -> Dict[str, Any]:
    """Dry-run: what WOULD move — per-table source row counts, nothing written."""
    counts: Dict[str, int] = {}
    for table, _columns in _user_tables(schema):
        if hasattr(source_adapter, "table_exists") and not source_adapter.table_exists(table):
            continue
        counts[table] = len(source_adapter.select(table) or [])
    return {"tables": len(counts), "rows": sum(counts.values()), "per_table": counts}


__all__ = ["export_tables", "import_tables", "transfer_backend", "preview_transfer"]
