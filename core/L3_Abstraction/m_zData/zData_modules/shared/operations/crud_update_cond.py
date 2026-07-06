# zOS/core/L3_Abstraction/m_zData/zData_modules/shared/operations/crud_update_cond.py
"""
Conditional UPDATE — the SQL ``CASE WHEN`` clause for zData writes.

Different SET values per row, decided by a per-row predicate:

    action: update
    table: members
    set:
      tier:
        zCase:
          - {when: {score: {$gte: 90}}, then: gold}
          - {when: {score: {$gte: 75}}, then: silver}
        else: bronze          # omit → unmatched rows keep their current value
    where: {team_id: 1}        # optional outer narrowing of candidate rows

SSOT design: every ``when`` predicate is evaluated through the *real* read/where
engine (``handle_read``), so it speaks the full zFilters dialect — string or dict,
operators, presence checks — with zero bespoke matching logic. Branches are tried
top-down (first match wins); rows that land on the same resolved value are batched
into one adapter update, so N rows cost one write per distinct value, not per row.

A field whose value is a plain literal (no ``zCase``) is applied unconditionally to
every candidate — conditional and constant SET fields can mix in one request.
"""

from collections import defaultdict

from zOS import Any, Dict, List

try:
    from .helpers import extract_table_from_request, extract_where_clause, display_validation_errors, surface_errors_to_session
    from .crud_helpers import emit_returning
    from .crud_read import handle_read
    from .crud_set_expr import is_computed, resolve_set_value
except ImportError:  # pragma: no cover - direct-run fallback
    from helpers import extract_table_from_request, extract_where_clause, display_validation_errors, surface_errors_to_session
    from crud_helpers import emit_returning
    from crud_read import handle_read
    from crud_set_expr import is_computed, resolve_set_value

__all__ = [
    "has_conditional_set", "handle_conditional_update",
    "pk_field", "read_rows", "commit_assignments",
]

_ZCASE = "zCase"
_UNCHANGED = object()   # sentinel — field left untouched when no branch matches and no else


def has_conditional_set(container: Any) -> bool:
    """True when any field in the SET container carries a ``zCase`` block."""
    return isinstance(container, dict) and any(
        isinstance(v, dict) and _ZCASE in v for v in container.values()
    )


def pk_field(table_schema: Dict[str, Any]) -> str:
    """Resolve the primary-key column (auto_increment / pk:true), defaulting to 'id'."""
    for name, fdef in table_schema.items():
        if isinstance(fdef, dict) and (fdef.get("auto_increment") or fdef.get("pk")):
            return name
    return "id"


def read_rows(table: str, where: Any, ops: Any) -> List[Dict[str, Any]]:
    """Silent read through the SSOT engine — full zFilters dialect for free."""
    req: Dict[str, Any] = {"table": table, "silent": True}
    if where:
        req["where"] = where
    return handle_read(req, ops) or []


# Back-compat private aliases (kept so internal callers below read cleanly).
_pk_field = pk_field
_read_rows = read_rows


def commit_assignments(table: str, assign: Dict[Any, Dict[str, Any]], pk: str,
                       ops: Any, request: Dict[str, Any], cand_ids: List[Any]) -> Any:
    """
    Batch rows sharing the same resolved SET signature into one adapter write,
    validating each distinct payload. Shared by conditional (zCase) and join
    (UPDATE … FROM) updates. Returns rows when ``returning`` is set, else bool.
    """
    groups: Dict[tuple, List[Any]] = defaultdict(list)
    for cid, vals in assign.items():
        if vals:
            groups[tuple(sorted(vals.items()))].append(cid)

    total = 0
    for keyvals, ids in groups.items():
        data = dict(keyvals)
        is_valid, errors = ops.validator.validate_update(table, data)
        if not is_valid:
            ops.logger.error("[zData] Cross-row update validation failed for %s", table)
            display_validation_errors(table, errors, ops)
            surface_errors_to_session(errors, ops)
            return False
        total += ops.update(table, list(data.keys()), list(data.values()), {pk: ids})

    msg = f"[updated] {total} row(s) in {table} (conditional)"
    ops.display.success(msg)

    if request.get("returning"):
        rows = read_rows(table, {pk: cand_ids}, ops)
        return emit_returning(table, rows, request.get("returning"), ops)
    return total > 0


def handle_conditional_update(request: Dict[str, Any], ops: Any) -> Any:
    """
    Execute a conditional (zCase) UPDATE. Returns rows when ``returning`` is set,
    otherwise True/False on whether any row changed.
    """
    table = extract_table_from_request(request, "update", ops, check_exists=True)
    if not table:
        return False

    container = request.get("set")
    if container is None:
        container = request.get("data")
    if not isinstance(container, dict) or not container:
        ops.logger.error("[zData] Conditional update requires a 'set'/'data' dict")
        return False

    where = extract_where_clause(request, ops, warn_if_missing=True)
    table_schema = ops.schema.get(table, {})
    pk = _pk_field(table_schema)

    # Candidate rows — the outer WHERE decides who is eligible at all.
    candidates = _read_rows(table, where, ops)
    if not candidates:
        msg = f"[updated] 0 row(s) in {table} (no rows matched)"
        ops.display.success(msg)
        return [] if request.get("returning") else False
    cand_ids = [r[pk] for r in candidates if pk in r]
    cand_by_id = {r[pk]: r for r in candidates if pk in r}

    # Per-field assignment: pk → {field: resolved_value}. Constant fields fill all;
    # zCase fields resolve per row by trying branches top-down over the read engine;
    # computed fields ($inc / zExpr) derive from each row's own current values.
    assign: Dict[Any, Dict[str, Any]] = {cid: {} for cid in cand_ids}
    cand_set = set(cand_ids)

    for field, spec in container.items():
        if isinstance(spec, dict) and _ZCASE in spec:
            branches = spec.get(_ZCASE) or []
            else_val = spec.get("else", _UNCHANGED)
            decided: set = set()
            for branch in branches:
                when = branch.get("when")
                then = branch.get("then")
                hits = _read_rows(table, when, ops)
                for row in hits:
                    cid = row.get(pk)
                    if cid in cand_set and cid not in decided:
                        # A branch's `then` may itself be computed (e.g. score + bonus).
                        assign[cid][field] = resolve_set_value(field, then, cand_by_id.get(cid, row)) \
                            if is_computed(then) else then
                        decided.add(cid)
            if else_val is not _UNCHANGED:
                for cid in cand_ids:
                    if cid not in decided:
                        assign[cid][field] = resolve_set_value(field, else_val, cand_by_id[cid]) \
                            if is_computed(else_val) else else_val
            # no else → unmatched rows keep their current value (field omitted)
        elif is_computed(spec):
            for cid in cand_ids:
                assign[cid][field] = resolve_set_value(field, spec, cand_by_id[cid])
        else:
            for cid in cand_ids:
                assign[cid][field] = spec

    # Batch rows that resolved to the same SET signature into one adapter write.
    return commit_assignments(table, assign, pk, ops, request, cand_ids)
