# zOS/core/L3_Abstraction/m_zData/zData_modules/shared/operations/constraints_check.py
"""
Constraint enforcement + in-memory row predicate for zData writes.

Extracted from ``operations/helpers.py`` (grab-bag decomposition). This module
owns everything needed to decide whether a write satisfies the schema's declared
constraints, all evaluated in pure Python so the behaviour is identical across
every backend:

    check_unique_constraints(table, data, table_schema, ops, exclude_where=None)
        Single-column ``unique: true`` + composite ``zConstraints: unique: [...]``.
    check_row_constraints(table, data, table_schema, ops, current_row=None)
        Cross-field ``zConstraints: check:`` rules (RHS may be a field name).

Private helpers (``_resolve_field_refs``, ``_evaluate_ir``, ``_row_matches_where``)
implement the in-memory evaluation of a parsed where-clause IR. ``_evaluate_ir``
is re-exported by ``helpers.py`` because ``crud_read`` uses it for in-memory
filtering; the two public checks are re-exported for all CRUD write paths.
"""

from zOS import Any, Dict, List, Optional
from ..parsers import parse_where_clause
from ..validators.constants import SCHEMA_KEY_UNIQUE, ERR_UNIQUE_VIOLATION
from ..operators import (
    normalize_operator,
    OP_GT, OP_GTE, OP_LT, OP_LTE, OP_NE, OP_EQ, OP_LIKE, OP_NOTNULL,
    OP_AND, OP_OR,
)

__all__ = ["check_unique_constraints", "check_row_constraints", "_evaluate_ir"]


def check_unique_constraints(
    table: str,
    data: Dict[str, Any],
    table_schema: Dict[str, Any],
    ops: Any,
    exclude_where: Optional[Dict[str, Any]] = None
) -> Dict[str, str]:
    """
    Check unique constraints for fields marked ``unique: true`` in the schema,
    and composite unique constraints declared in ``zConstraints``.

    This is shared by INSERT and UPDATE operations.  For UPDATE, pass
    ``exclude_where`` (the operation's WHERE clause, e.g. ``{"id": 1}``) so that
    the row being updated is excluded from the existence check — preventing a
    false violation when a field is updated to the value it already holds.

    Args:
        table: Table name.
        data: Field/value dict being written.
        table_schema: Schema dict for this table (pre-filtered, no zMeta).
        ops: DataOperations facade (provides ``ops.select`` and ``ops.logger``).
        exclude_where: Optional simple WHERE dict identifying the current row
                       (UPDATE only).  Rows whose fields match ALL keys in this
                       dict are excluded from the conflict check.

    Returns:
        Dict of ``{field_name: error_message}`` for each unique violation,
        empty dict when all constraints are satisfied.
    """
    errors: Dict[str, str] = {}

    # ── Phase 1: single-column unique: true ──────────────────────────────────
    for field_name, value in data.items():
        field_def = table_schema.get(field_name, {})
        if not isinstance(field_def, dict):
            continue
        if not field_def.get(SCHEMA_KEY_UNIQUE, False):
            continue
        try:
            existing: List[Any] = ops.select(table, where={field_name: value})
            if existing and exclude_where:
                existing = [
                    row for row in existing
                    if not _row_matches_where(row, exclude_where)
                ]
            if existing:
                errors[field_name] = ERR_UNIQUE_VIOLATION.format(
                    field_name=field_name, value=value
                )
        except Exception as exc:  # pylint: disable=broad-except
            ops.logger.warning(
                "[zData] Unique check failed for '%s.%s': %s (skipping)",
                table, field_name, exc
            )

    # ── Phase 2: composite unique via zConstraints ───────────────────────────
    # zConstraints is a list of constraint dicts at the table level, e.g.:
    #   zConstraints:
    #     - unique: [username, role]
    _z_constraints = table_schema.get('zConstraints', [])
    seen_composites: set = set()
    for constraint in _z_constraints:
        group = []
        if isinstance(constraint, dict):
            group = constraint.get('unique', [])
        elif isinstance(constraint, str):
            # zolo parser may yield "unique: [name, role]" as a plain string
            # Parse it into a list of field names
            if constraint.strip().startswith('unique:'):
                raw = constraint.split(':', 1)[1].strip()
                raw = raw.strip('[]')
                group = [f.strip() for f in raw.split(',') if f.strip()]
        if not isinstance(group, list) or len(group) < 2:
            continue
        group_key = frozenset(group)
        if group_key in seen_composites:
            continue  # deduplicate if declared on multiple fields
        seen_composites.add(group_key)

        # Only check if ALL fields in the group are present in the payload
        combo_where = {f: data[f] for f in group if f in data}
        if len(combo_where) < len(group):
            continue

        try:
            existing = ops.select(table, where=combo_where)
            if existing and exclude_where:
                existing = [
                    row for row in existing
                    if not _row_matches_where(row, exclude_where)
                ]
            if existing:
                error_key = '+'.join(group)
                errors[error_key] = (
                    f"The combination of {', '.join(group)} must be unique — "
                    f"({', '.join(str(combo_where[f]) for f in group)}) already exists"
                )
        except Exception as exc:  # pylint: disable=broad-except
            ops.logger.warning(
                "[zData] Composite unique check failed for '%s' %s: %s (skipping)",
                table, group, exc
            )

    return errors


def check_row_constraints(
    table: str,
    data: Dict[str, Any],
    table_schema: Dict[str, Any],
    ops: Any,
    current_row: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    """Evaluate ``zConstraints: check:`` cross-field rules against a merged row.

    Each ``check:`` entry in ``zConstraints`` is a zFilters-style expression
    where the RHS of a comparison can be either a literal **or a field name** in
    the row.  The expression is parsed by ``parse_where_clause`` and then
    evaluated in-memory against the merged row dict (``current_row`` overlaid
    with the incoming ``data``).

    For INSERT ``current_row`` is None (only payload fields are available).
    For UPDATE ``current_row`` contains the existing DB row so that fields not
    present in the payload still participate in cross-field checks.

    Returns:
        Dict mapping a synthetic error key to an error message (empty → no errors).
    """
    errors: Dict[str, str] = {}
    _z_constraints = table_schema.get('zConstraints', [])
    if not _z_constraints:
        return errors

    # Merge current row (if any) with incoming data so cross-field checks have
    # access to all column values even if only a subset was submitted.
    merged: Dict[str, Any] = {}
    if isinstance(current_row, dict):
        merged.update(current_row)
    merged.update(data)

    for constraint in _z_constraints:
        check_expr = None
        error_msg = None

        if isinstance(constraint, dict):
            check_expr = constraint.get('check')
            error_msg = constraint.get('error_message')
        elif isinstance(constraint, str) and constraint.strip().startswith('check:'):
            raw = constraint.split(':', 1)[1].strip()
            # zolo parser may concat a trailing " error_message: <msg>" into the string
            if ' error_message:' in raw:
                raw, em = raw.split(' error_message:', 1)
                check_expr = raw.strip()
                error_msg = em.strip()
            else:
                check_expr = raw

        if not check_expr:
            continue

        try:
            ir = parse_where_clause(str(check_expr))
            if ir is None:
                ops.logger.warning(
                    "[zData] check constraint unparseable for '%s': %r (skipping)",
                    table, check_expr
                )
                continue

            # Resolve field references in the IR before evaluation.
            # In a standard zFilters query the RHS is always a literal.
            # Here the RHS may be a field name — substitute its value from the row.
            resolved_ir = _resolve_field_refs(ir, merged)

            if not _evaluate_ir(resolved_ir, merged):
                key = f"check:{check_expr[:40]}"
                errors[key] = error_msg or (
                    f"Row constraint violated: {check_expr}"
                )
        except Exception as exc:  # pylint: disable=broad-except
            ops.logger.warning(
                "[zData] check constraint evaluation failed for '%s' %r: %s (skipping)",
                table, check_expr, exc
            )

    return errors


def _resolve_field_refs(ir: Any, row: Dict[str, Any]) -> Any:
    """Recursively substitute field-name references in an IR dict.

    If the RHS of any comparison is a string that exactly matches a key in
    ``row``, replace it with the row value so the subsequent ``_evaluate_ir``
    sees concrete values.
    """
    if not isinstance(ir, dict):
        return ir

    out: Dict[str, Any] = {}
    for key, val in ir.items():
        if key.startswith('$'):
            # Operator node — recurse into list or dict values
            if isinstance(val, list):
                out[key] = [_resolve_field_refs(v, row) for v in val]
            elif isinstance(val, dict):
                out[key] = _resolve_field_refs(val, row)
            else:
                # Scalar operator value — check if it names a field
                out[key] = row[val] if (isinstance(val, str) and val in row) else val
        else:
            # Field node — val is either a literal, operator dict, or list (IN)
            if isinstance(val, dict):
                out[key] = _resolve_field_refs(val, row)
            elif isinstance(val, list):
                out[key] = val  # IN list — leave as-is
            else:
                # Direct equality — val could be a field ref
                out[key] = row[val] if (isinstance(val, str) and val in row) else val
    return out


def _evaluate_ir(ir: Any, row: Dict[str, Any]) -> bool:
    """Evaluate a parsed where-clause IR dict against a row dict.

    Returns True when the row satisfies all conditions (i.e. the constraint
    PASSES).  Returns False when any condition is violated.
    """
    if not isinstance(ir, dict):
        return True

    for key, condition in ir.items():
        # ── Logical operators ──────────────────────────────────────────────
        # Case-insensitive ($AND/$and) but NOT bare-word promotion, so a field
        # literally named "and"/"or" is never mistaken for a logical node.
        key_lc = key.lower() if isinstance(key, str) else key
        if key_lc == OP_AND:
            if isinstance(condition, list):
                if not all(_evaluate_ir(c, row) for c in condition):
                    return False
            continue
        if key_lc == OP_OR:
            if isinstance(condition, list):
                if not any(_evaluate_ir(c, row) for c in condition):
                    return False
            continue

        # ── Field comparison ───────────────────────────────────────────────
        raw = row.get(key)

        # Coerce raw value to numeric when possible for comparison operators
        def _num(v: Any) -> Any:
            try:
                return float(v) if '.' in str(v) else int(v)
            except (TypeError, ValueError):
                return v

        if condition is None:
            if raw is not None and raw != '':
                return False
        elif isinstance(condition, dict):
            raw_cmp = _num(raw)
            for op, rhs in condition.items():
                n_op = normalize_operator(op)
                rhs_cmp = _num(rhs) if n_op in (OP_GT, OP_GTE, OP_LT, OP_LTE) else rhs
                if n_op == OP_GT:
                    if not (raw_cmp > rhs_cmp):
                        return False
                elif n_op == OP_GTE:
                    if not (raw_cmp >= rhs_cmp):
                        return False
                elif n_op == OP_LT:
                    if not (raw_cmp < rhs_cmp):
                        return False
                elif n_op == OP_LTE:
                    if not (raw_cmp <= rhs_cmp):
                        return False
                elif n_op == OP_NE:
                    if not (str(raw) != str(rhs)):
                        return False
                elif n_op == OP_EQ:
                    if not (str(raw) == str(rhs)):
                        return False
                elif n_op == OP_NOTNULL:
                    if raw is None or raw == '':
                        return False
                elif n_op == OP_LIKE:
                    import re as _re
                    pat = str(rhs).replace('%', '.*').replace('_', '.')
                    if not _re.fullmatch(pat, str(raw), _re.IGNORECASE):
                        return False
        elif isinstance(condition, list):
            if str(raw) not in [str(v) for v in condition]:
                return False
        else:
            if str(raw) != str(condition):
                return False

    return True


def _row_matches_where(row: Any, where: Dict[str, Any]) -> bool:
    """Return True when *row* satisfies all equality conditions in *where*.

    Only handles simple ``{field: value}`` dicts (as produced by
    ``parse_where_clause`` for plain equality expressions such as ``id = 1``).
    Complex IR operators are ignored — the check degrades to "no match" so
    we err on the side of allowing the write rather than blocking it.
    """
    if not isinstance(row, dict) or not where:
        return False
    for field, condition in where.items():
        if isinstance(condition, dict):
            continue  # IR operator — skip (conservative: do not exclude)
        if str(row.get(field, "")) != str(condition):
            return False
    return True
