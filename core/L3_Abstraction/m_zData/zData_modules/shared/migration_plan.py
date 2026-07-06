# zOS/core/L3_Abstraction/m_zData/zData_modules/shared/migration_plan.py
"""
Migration plan renderer — turn a schema diff into the ordered DDL statements it
WOULD run, without touching the store. Powers ``z migrate --plan`` / ``--sql``:
a review/CI-friendly preview of exactly what a migration intends to do.

Pure by design (no adapter, no I/O) so it's trivially testable. The optional
``map_type`` callable (an adapter's abstract→SQL resolver) renders column types in
the target dialect; without it, the abstract type is shown as-is. Statement order
mirrors the executor: CREATE tables → per-table RENAME/ADD/DROP/MODIFY → DROP tables.
"""

from zOS import Any, Dict, List

from .schema_diff import (
    KEY_TABLES_ADDED, KEY_TABLES_DROPPED, KEY_TABLES_MODIFIED,
    KEY_COLUMNS_ADDED, KEY_COLUMNS_DROPPED, KEY_COLUMNS_MODIFIED, KEY_COLUMNS_RENAMED,
    KEY_INDEXES_ADDED, KEY_INDEXES_DROPPED,
    KEY_CONSTRAINTS_ADDED, KEY_CONSTRAINTS_DROPPED,
    KEY_TABLES, KEY_COLUMNS, PROP_TYPE,
)
from .index_naming import resolve_index_name, resolve_index_fields


def _render_type(col_def: Any, map_type) -> str:
    t = col_def.get(PROP_TYPE, "str") if isinstance(col_def, dict) else "str"
    return map_type(t) if callable(map_type) else str(t)


def _constraint_label(cdef: Any) -> str:
    """Render a readable ADD CONSTRAINT body for the plan (fk / check)."""
    if not isinstance(cdef, dict):
        return str(cdef)
    name = cdef.get("name", "")
    ctype = str(cdef.get("type", "")).lower()
    if ctype in ("fk", "foreign_key"):
        fields = cdef.get("fields", [])
        fields = [fields] if isinstance(fields, str) else list(fields)
        return f"{name} FOREIGN KEY ({', '.join(fields)}) REFERENCES {cdef.get('ref', '')}"
    if ctype == "check":
        return f"{name} CHECK ({cdef.get('expr', '')})"
    return name


def build_migration_plan(
    diff: Dict[str, Any],
    new_schema: Dict[str, Any],
    map_type=None,
) -> List[str]:
    """Return the ordered DDL statements a migration would execute for ``diff``.

    ``new_schema`` is the diff-format target ({Tables:{t:{Columns:{...}}}}) — needed
    to spell out columns for freshly CREATEd tables. Never runs anything.
    """
    stmts: List[str] = []
    tables = (new_schema or {}).get(KEY_TABLES, {})

    # 1. CREATE TABLE — new tables, with their declared columns
    for table in diff.get(KEY_TABLES_ADDED, []):
        cols = tables.get(table, {}).get(KEY_COLUMNS, {})
        pieces = []
        for col, cdef in cols.items():
            piece = f"{col} {_render_type(cdef, map_type)}"
            if isinstance(cdef, dict) and (cdef.get("pk") or cdef.get("primary_key")):
                piece += " PRIMARY KEY"
            pieces.append(piece)
        stmts.append(f"CREATE TABLE {table} ({', '.join(pieces)})")

    # 2. ALTER TABLE — per modified table, in executor order
    for table, ch in diff.get(KEY_TABLES_MODIFIED, {}).items():
        for new_name, old_name in (ch.get(KEY_COLUMNS_RENAMED) or {}).items():
            stmts.append(f"ALTER TABLE {table} RENAME COLUMN {old_name} TO {new_name}")
        for col, cdef in (ch.get(KEY_COLUMNS_ADDED) or {}).items():
            stmts.append(f"ALTER TABLE {table} ADD COLUMN {col} {_render_type(cdef, map_type)}")
        for col in (ch.get(KEY_COLUMNS_DROPPED) or []):
            stmts.append(f"ALTER TABLE {table} DROP COLUMN {col}")
        for col, mod in (ch.get(KEY_COLUMNS_MODIFIED) or {}).items():
            newd = mod.get("new", mod) if isinstance(mod, dict) else mod
            stmts.append(f"ALTER TABLE {table} ALTER COLUMN {col} TYPE {_render_type(newd, map_type)}")
        for spec in (ch.get(KEY_INDEXES_ADDED) or []):
            name = resolve_index_name(table, spec)
            fields = ", ".join(resolve_index_fields(spec))
            unique = "UNIQUE " if isinstance(spec, dict) and spec.get("unique") else ""
            stmts.append(f"CREATE {unique}INDEX {name} ON {table} ({fields})")
        for name in (ch.get(KEY_INDEXES_DROPPED) or []):
            stmts.append(f"DROP INDEX {name}")
        for cdef in (ch.get(KEY_CONSTRAINTS_ADDED) or []):
            stmts.append(f"ALTER TABLE {table} ADD CONSTRAINT {_constraint_label(cdef)}")
        for cdef in (ch.get(KEY_CONSTRAINTS_DROPPED) or []):
            name = cdef.get("name") if isinstance(cdef, dict) else cdef
            stmts.append(f"ALTER TABLE {table} DROP CONSTRAINT {name}")

    # 3. DROP TABLE — last, after dependents are handled
    for table in diff.get(KEY_TABLES_DROPPED, []):
        stmts.append(f"DROP TABLE {table}")

    return stmts


__all__ = ["build_migration_plan"]
