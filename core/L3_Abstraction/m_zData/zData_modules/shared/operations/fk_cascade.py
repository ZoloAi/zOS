# zOS/core/L3_Abstraction/m_zData/zData_modules/shared/operations/fk_cascade.py
"""
Referential-integrity engine for zData DELETE / TRUNCATE.

Extracted from ``operations/helpers.py`` (grab-bag decomposition) into a single-
responsibility module: given a parent table about to lose rows, enforce every
declared ``on_delete`` behaviour across the whole FK subtree — recursively, and
in the safe order (read-only restrict scan first, then mutate bottom-up).

Public surface:
    handle_on_delete(parent_table, where, ops, request=None) -> Optional[str]
        Called before a DELETE. Returns an error string to abort (restrict), or
        None once all cascade / set_null / set_default children are handled.
    resolve_fk_scan_tables(ops, request, current_tables) -> Dict
        Shared "scoped-schema → reload full file" resolver, used by both DELETE
        and the TRUNCATE FK guard so that logic lives in exactly one place.

``helpers.py`` re-exports both names, so existing
``from .helpers import handle_on_delete`` call sites keep working unchanged.
"""

from typing import Set
from zOS import Any, Dict, List, Optional
from ..validators.constants import (
    SCHEMA_KEY_PK, SCHEMA_KEY_FK, SCHEMA_KEY_ON_DELETE, SCHEMA_KEY_DEFAULT,
    ON_DELETE_RESTRICT, ON_DELETE_CASCADE, ON_DELETE_SET_NULL, ON_DELETE_SET_DEFAULT,
    ERR_FK_RESTRICT,
    LOG_ON_DELETE_CASCADE, LOG_ON_DELETE_SET_NULL, LOG_ON_DELETE_SET_DEFAULT,
    LOG_ON_DELETE_RESTRICT, LOG_ON_DELETE_SCAN, LOG_ON_DELETE_SKIP,
)
from ..data_keys import KEY_MODEL, KEY_OPTIONS, SCHEMA_KEY_META
from zOS.zVocabulary import FILE_TYPE_SCHEMA
from ...schema_manager import parse_schema_model_path

_KEY_MODEL = KEY_MODEL
_KEY_OPTIONS = KEY_OPTIONS

__all__ = ["handle_on_delete", "resolve_fk_scan_tables"]


# ── Private helpers for multi-hop FK cascade ─────────────────────────────────

def _get_pk_field(table: str, schema_tables: Dict[str, Any]) -> Optional[str]:
    """Return the PK field name for *table* from *schema_tables*, or None."""
    for field_name, field_def in schema_tables.get(table, {}).items():
        if isinstance(field_def, dict) and field_def.get(SCHEMA_KEY_PK):
            return field_name
    return None


def _build_fk_action_plan(
    parent_table: str,
    pk_values: List[Any],
    schema_tables: Dict[str, Any],
    ops: Any,
) -> List[Any]:
    """
    Collect all direct FK children of *parent_table* that have rows matching
    any value in *pk_values*.

    Returns a list of tuples:
        (on_delete, child_table, fk_field_name, fk_ref, pk_val, child_rows, fk_field_def)
    """
    plan: List[Any] = []
    for child_table, child_schema in schema_tables.items():
        # A table may reference itself (self-referential FK — e.g. manager_id → members.id);
        # such children are legitimate. Infinite recursion is prevented by the `visited`
        # cycle guard in the recursive callers, not by skipping same-table children here.
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
            on_delete = fk_field_def.get(SCHEMA_KEY_ON_DELETE, ON_DELETE_RESTRICT)
            for pk_val in pk_values:
                try:
                    child_rows = ops.select(child_table, where={fk_field_name: pk_val})
                except Exception as exc:  # pylint: disable=broad-except
                    ops.logger.warning(
                        "[on_delete] Could not query child table '%s': %s", child_table, exc
                    )
                    continue
                if not child_rows:
                    continue
                ops.logger.debug(LOG_ON_DELETE_SCAN, child_table, fk_field_name, fk_ref)
                plan.append(
                    (on_delete, child_table, fk_field_name, fk_ref,
                     pk_val, child_rows, fk_field_def)
                )
    return plan


def _check_fk_restrict_recursive(
    parent_table: str,
    pk_values: List[Any],
    schema_tables: Dict[str, Any],
    ops: Any,
    visited: Set[str],
) -> Optional[str]:
    """
    Read-only recursive restrict scan across the entire FK subtree.

    Walks parent_table → its FK children → their FK children, etc.
    Returns the first restrict-violation error string found at any depth,
    or ``None`` if the entire subtree is clear.

    Only cascade children are traversed recursively; set_null / set_default
    branches do not propagate deletes, so their subtrees are not checked.
    """
    if parent_table in visited:
        return None  # cycle guard
    visited = set(visited)
    visited.add(parent_table)

    plan = _build_fk_action_plan(parent_table, pk_values, schema_tables, ops)
    if not plan:
        return None

    for on_delete, child_table, fk_field_name, fk_ref, _pk_val, child_rows, _ in plan:
        if on_delete == ON_DELETE_RESTRICT:
            ops.logger.warning(LOG_ON_DELETE_RESTRICT, len(child_rows), child_table, fk_field_name)
            return ERR_FK_RESTRICT.format(
                count=len(child_rows),
                child_table=child_table,
                fk_field=f"{fk_field_name} → {fk_ref}",
            )

    for on_delete, child_table, _fk_field, _fk_ref, _pk_val, child_rows, _ in plan:
        if on_delete != ON_DELETE_CASCADE:
            continue
        child_pk_field = _get_pk_field(child_table, schema_tables)
        if not child_pk_field:
            continue
        grandchild_pks = [r[child_pk_field] for r in child_rows if child_pk_field in r]
        if grandchild_pks:
            error = _check_fk_restrict_recursive(
                child_table, grandchild_pks, schema_tables, ops, visited
            )
            if error:
                return error

    return None


def _execute_fk_actions_recursive(
    parent_table: str,
    pk_values: List[Any],
    schema_tables: Dict[str, Any],
    ops: Any,
    visited: Set[str],
) -> None:
    """
    Recursively execute FK actions (cascade / set_null / set_default) bottom-up.

    For cascade children, recurses into the child's own subtree *before* deleting
    the child rows — ensuring the deepest level is cleaned up first
    (grandchildren → children → parent).

    Called only after _check_fk_restrict_recursive has confirmed no restrict
    violations exist at any depth.
    """
    if parent_table in visited:
        return  # cycle guard
    visited = set(visited)
    visited.add(parent_table)

    plan = _build_fk_action_plan(parent_table, pk_values, schema_tables, ops)
    if not plan:
        return

    for on_delete, child_table, fk_field_name, _fk_ref, pk_val, child_rows, fk_field_def in plan:
        if on_delete == ON_DELETE_CASCADE:
            child_pk_field = _get_pk_field(child_table, schema_tables)
            if child_pk_field:
                grandchild_pks = [r[child_pk_field] for r in child_rows if child_pk_field in r]
                if grandchild_pks:
                    _execute_fk_actions_recursive(
                        child_table, grandchild_pks, schema_tables, ops, visited
                    )
            ops.logger.info(LOG_ON_DELETE_CASCADE, len(child_rows), child_table, fk_field_name)
            try:
                ops.delete(child_table, {fk_field_name: pk_val})
            except Exception as exc:  # pylint: disable=broad-except
                ops.logger.error(
                    "[on_delete: cascade] Failed to delete child rows in '%s': %s",
                    child_table, exc,
                )

        elif on_delete == ON_DELETE_SET_NULL:
            ops.logger.info(LOG_ON_DELETE_SET_NULL, len(child_rows), child_table, fk_field_name)
            try:
                ops.update(child_table, [fk_field_name], [None], {fk_field_name: pk_val})
            except Exception as exc:  # pylint: disable=broad-except
                ops.logger.error(
                    "[on_delete: set_null] Failed to null FK in '%s': %s",
                    child_table, exc,
                )

        elif on_delete == ON_DELETE_SET_DEFAULT:
            default_val = fk_field_def.get(SCHEMA_KEY_DEFAULT)
            ops.logger.info(
                LOG_ON_DELETE_SET_DEFAULT, len(child_rows), child_table, fk_field_name, default_val
            )
            try:
                ops.update(
                    child_table, [fk_field_name], [default_val], {fk_field_name: pk_val}
                )
            except Exception as exc:  # pylint: disable=broad-except
                ops.logger.error(
                    "[on_delete: set_default] Failed to reset FK in '%s': %s",
                    child_table, exc,
                )


def resolve_fk_scan_tables(
    ops: Any,
    request: Optional[Dict[str, Any]],
    current_tables: Dict[str, Any],
) -> Dict[str, Any]:
    """Return the full ``{table: fields}`` map needed for FK scanning.

    When a request's model path is scoped to a single block (e.g.
    ``@.models.X.zSchema.basic.demo_delete``) ``ops.schema`` holds only that one
    table, so sibling-table FK references are invisible. In that case reload the
    full schema file (block suffix stripped via ``parse_schema_model_path``) and
    return its tables. Otherwise return ``current_tables`` unchanged.

    Shared by ``handle_on_delete`` (DELETE) and the TRUNCATE FK guard so the
    "scoped-schema → reload full file" logic lives in exactly one place.
    """
    if len(current_tables) > 1 or not request:
        return current_tables
    model_path = request.get(_KEY_MODEL) or request.get(_KEY_OPTIONS, {}).get(_KEY_MODEL, "")
    if not model_path or f"{FILE_TYPE_SCHEMA}." not in str(model_path):
        return current_tables
    schema_path, block = parse_schema_model_path(str(model_path))
    if block is None or schema_path == str(model_path):
        return current_tables
    try:
        full_schema = ops.zos.loader.handle(schema_path)
        if full_schema and full_schema != "error":
            return {
                k: v for k, v in full_schema.items()
                if k != SCHEMA_KEY_META and isinstance(v, dict)
            }
    except Exception as exc:  # pylint: disable=broad-except
        ops.logger.warning("[FK scan] Could not load full schema '%s': %s", schema_path, exc)
    return current_tables


def handle_on_delete(
    parent_table: str,
    where: Any,
    ops: Any,
    request: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """
    Enforce referential integrity before a DELETE executes.

    Scans ``ops.schema`` for any table that declares a field with
    ``fk: <parent_table>.<pk_field>``.  For each matched child field the
    declared ``on_delete`` behaviour is applied:

    - ``restrict``    — block the delete and return an error string.
    - ``cascade``     — delete matching child rows first.
    - ``set_null``    — set the FK field to ``None`` on matching child rows.
    - ``set_default`` — set the FK field to its declared ``default`` value
                        (or ``None`` if no default is declared).

    Default behaviour when ``on_delete`` is absent: ``restrict``.

    Args:
        parent_table: Name of the table being deleted from.
        where:        Parsed WHERE dict (from ``extract_where_clause``).
                      ``None`` means "all rows".
        ops:          ``DataOperations`` instance.

    Returns:
        ``None``  — no restriction; delete can proceed (FK children handled).
        ``str``   — human-readable error message; caller MUST abort the delete.
    """
    _META_KEY = SCHEMA_KEY_META

    # ── Phase 1: find parent rows that will be deleted ────────────────────────
    try:
        parent_rows = ops.select(parent_table, where=where) if where else ops.select(parent_table)
    except Exception as exc:  # pylint: disable=broad-except
        ops.logger.warning("[on_delete] Could not fetch parent rows for FK check: %s", exc)
        return None

    if not parent_rows:
        ops.logger.debug(LOG_ON_DELETE_SKIP)
        return None

    # ── Phase 2: resolve full schema for FK scanning ─────────────────────────
    # When the model path includes a table suffix (e.g. @.models.X.zSchema.basic.demo_delete),
    # the loaded ops.schema is scoped to one table.  We must reload the full schema
    # file to discover FK references in sibling tables.
    schema_tables = {k: v for k, v in ops.schema.items() if k != _META_KEY}
    schema_tables = resolve_fk_scan_tables(ops, request, schema_tables)
    parent_schema = schema_tables.get(parent_table, {})
    pk_field: Optional[str] = None
    for field_name, field_def in parent_schema.items():
        if isinstance(field_def, dict) and field_def.get(SCHEMA_KEY_PK):
            pk_field = field_name
            break

    if not pk_field:
        ops.logger.debug("[on_delete] No PK found in '%s' — skipping FK checks", parent_table)
        return None

    pk_values = [row[pk_field] for row in parent_rows if pk_field in row]
    if not pk_values:
        return None

    # ── Phase 3: Multi-hop FK enforcement ────────────────────────────────────
    # Pass 1 (read-only): recursively scan the ENTIRE FK subtree at every depth
    # for restrict violations before touching any data.
    # Pass 2 (mutate): execute cascade / set_null / set_default bottom-up.
    fk_error = _check_fk_restrict_recursive(parent_table, pk_values, schema_tables, ops, set())
    if fk_error:
        return fk_error

    _execute_fk_actions_recursive(parent_table, pk_values, schema_tables, ops, set())
    return None  # All FK constraints satisfied — delete may proceed
