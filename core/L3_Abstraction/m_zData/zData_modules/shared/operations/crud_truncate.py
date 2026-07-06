# zOS/core/L3_Abstraction/m_zData/zData_modules/shared/operations/crud_truncate.py
"""
TRUNCATE operation handler — removes all rows and resets the PK auto-increment sequence.

⚠️ **WARNING: IRREVERSIBLE OPERATION** ⚠️

TRUNCATE differs from DELETE-all-rows in two key ways:
1. **PK sequence is reset** — the next INSERT will receive id=1
2. **FK safety check** — zOS blocks TRUNCATE if any child rows exist that
   reference the parent table, regardless of on_delete setting.
   The caller must clean up (or truncate) child tables first.

Execution Flow
-------------
1. Table Extraction  → validate table exists
2. FK Safety Check   → block if any child FK rows reference this table
3. Truncate          → wipe all rows, preserve column headers, reset PK sequence
"""

from zOS import Any, Dict, Optional, List

# ============================================================
# Constants
# ============================================================

from ..data_keys import SCHEMA_KEY_META  # pylint: disable=wrong-import-position
_OP_TRUNCATE = "TRUNCATE"
_META_KEY = SCHEMA_KEY_META

_LOG_TRUNCATE = "[TRUNCATE] Removed %d row(s) from '%s'; PK sequence reset to 1"
_LOG_BLOCKED  = "[TRUNCATE] Blocked by FK child rows: %s"
_LOG_FK_SCAN  = "[TRUNCATE] Scanning child table '%s' field '%s' for FK references"

_ERR_FK_BLOCKED = (
    "Cannot truncate '{table}': {count} row(s) in '{child_table}' reference this table "
    "via '{fk_field}'. Truncate or clean up the child table first."
)

# ============================================================
# Imports
# ============================================================

try:
    from .helpers import extract_table_from_request, resolve_fk_scan_tables
    from ..validators.constants import SCHEMA_KEY_FK, SCHEMA_KEY_PK
except ImportError:
    from helpers import extract_table_from_request, resolve_fk_scan_tables
    from validators.constants import SCHEMA_KEY_FK, SCHEMA_KEY_PK

__all__ = ["handle_truncate"]


# ============================================================
# DDL Operation — TRUNCATE
# ============================================================

def handle_truncate(request: Dict[str, Any], ops: Any) -> bool:
    """
    Truncate a table: remove all rows and reset the PK auto-increment sequence.

    Blocks if any child FK rows reference the parent table (caller must clean up
    child tables first).

    Args:
        request: Must contain "table" (or resolvable via "model").
        ops: DataOperations instance (logger, display, adapter, schema).

    Returns:
        True if table was truncated successfully, False otherwise.
    """
    # ── Phase 1: Resolve table name ──────────────────────────────────────────
    table = extract_table_from_request(request, _OP_TRUNCATE, ops, check_exists=True)
    if not table:
        return False

    # ── Phase 2: FK safety check (block if any child rows exist) ─────────────
    fk_error = _check_no_fk_children(table, ops, request)
    if fk_error:
        ops.logger.warning(_LOG_BLOCKED, fk_error)
        ops.display.error(fk_error)
        return False

    # ── Phase 3: Truncate execution ───────────────────────────────────────────
    count = ops.adapter.truncate(table)
    ops.logger.info(_LOG_TRUNCATE, count, table)
    return True


# ============================================================
# FK Safety Check (read-only)
# ============================================================

def _check_no_fk_children(
    parent_table: str,
    ops: Any,
    request: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """
    Return an error string if any child table has FK rows referencing parent_table.
    Returns None if it is safe to truncate.

    Unlike handle_on_delete this is read-only (no mutations), and it treats every
    FK relationship as an implicit restrict — the entire parent table is being wiped.
    """
    # Resolve full schema (same logic as handle_on_delete)
    schema = getattr(ops, 'schema', None) or {}
    schema_tables = {k: v for k, v in schema.items() if k != _META_KEY}
    schema_tables = resolve_fk_scan_tables(ops, request, schema_tables)

    # Find parent PK field
    parent_schema = schema_tables.get(parent_table, {})
    pk_field: Optional[str] = None
    for field_name, field_def in parent_schema.items():
        if isinstance(field_def, dict) and field_def.get(SCHEMA_KEY_PK):
            pk_field = field_name
            break

    if not pk_field:
        return None  # No PK found — cannot determine FK references; allow truncate

    # Fetch all parent PK values
    try:
        parent_rows = ops.select(parent_table)
    except Exception as exc:  # pylint: disable=broad-except
        ops.logger.warning("[TRUNCATE] Could not fetch parent rows for FK check: %s", exc)
        return None

    if not parent_rows:
        return None  # Already empty — safe to truncate

    pk_values: List[Any] = [row[pk_field] for row in parent_rows if pk_field in row]
    if not pk_values:
        return None

    # Scan all sibling tables for FK references to parent_table
    for child_table, child_schema in schema_tables.items():
        if child_table == parent_table:
            continue
        if not isinstance(child_schema, dict):
            continue

        for fk_field_name, fk_field_def in child_schema.items():
            if not isinstance(fk_field_def, dict):
                continue
            fk_ref = fk_field_def.get(SCHEMA_KEY_FK)
            if not fk_ref or "." not in str(fk_ref):
                continue

            ref_table, _ = str(fk_ref).split(".", 1)
            if ref_table != parent_table:
                continue

            ops.logger.debug(_LOG_FK_SCAN, child_table, fk_field_name)

            for pk_val in pk_values:
                try:
                    child_rows = ops.select(child_table, where={fk_field_name: pk_val})
                except Exception as exc:  # pylint: disable=broad-except
                    ops.logger.warning(
                        "[TRUNCATE] Could not query child table '%s': %s", child_table, exc
                    )
                    continue

                if child_rows:
                    return _ERR_FK_BLOCKED.format(
                        table=parent_table,
                        count=len(child_rows),
                        child_table=child_table,
                        fk_field=f"{fk_field_name} → {fk_ref}",
                    )

    return None  # No FK children — safe to truncate
