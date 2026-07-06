# zOS/core/L3_Abstraction/m_zData/zData_modules/shared/operations/crud_update_join.py
"""
Cross-table UPDATE — the SQL ``UPDATE … FROM`` clause for zData writes.

Update table A using values pulled from a joined table B:

    action: update
    table: members
    from:
      table: teams
      on: members.team_id = teams.id     # A.col = B.col (string or dict)
      where: {tier: premium}             # optional filter on B
    set:
      plan: %teams.name                  # copy a B column into A
      note: %row.name                    # %row / %members → the A row itself
    where: {active: true}                # optional filter on A

SSOT design: no join projection. B is read once into a {join_key → row} map, A's
candidate rows are read once, and each A row's SET values are resolved against its
matched B row via ``resolve_ref``. Rows with no B match are skipped (inner-join
semantics). Resolved rows are batched by value and written through the shared
``commit_assignments`` path — identical on CSV, SQLite and Postgres.
"""

from zOS import Any, Dict

try:
    from .helpers import extract_table_from_request, extract_where_clause
    from .crud_join_refs import parse_on, resolve_ref
    from .crud_update_cond import pk_field, read_rows, commit_assignments
    from .crud_set_expr import is_computed, resolve_set_value
except ImportError:  # pragma: no cover - direct-run fallback
    from helpers import extract_table_from_request, extract_where_clause
    from crud_join_refs import parse_on, resolve_ref
    from crud_update_cond import pk_field, read_rows, commit_assignments
    from crud_set_expr import is_computed, resolve_set_value

__all__ = ["is_join_update", "handle_join_update"]


def is_join_update(request: Dict[str, Any]) -> bool:
    """True when the UPDATE carries a ``from:`` join block (dict with a table)."""
    frm = request.get("from")
    return isinstance(frm, dict) and bool(frm.get("table"))


def handle_join_update(request: Dict[str, Any], ops: Any) -> Any:
    """Execute an UPDATE … FROM. Returns rows when ``returning`` is set, else bool."""
    table = extract_table_from_request(request, "update", ops, check_exists=True)
    if not table:
        return False

    frm = request.get("from") or {}
    # B side may be given as `table:` or `model:` (resolve model → table name).
    if frm.get("table"):
        b_table = frm["table"]
    else:
        b_table = extract_table_from_request({"model": frm.get("model")}, "update", ops, check_exists=True)
    if not b_table:
        ops.logger.error("[zData] UPDATE … FROM needs a from.table or from.model")
        return False
    container = request.get("set")
    if container is None:
        container = request.get("data")
    if not isinstance(container, dict) or not container:
        ops.logger.error("[zData] UPDATE … FROM requires a 'set'/'data' dict")
        return False

    try:
        a_col, b_col = parse_on(frm.get("on"), table, b_table)
    except ValueError as e:
        ops.logger.error(f"[zData] UPDATE … FROM bad join: {e}")
        ops.display.error(str(e))
        return False

    where = extract_where_clause(request, ops, warn_if_missing=True)
    pk = pk_field(ops.schema.get(table, {}))

    # B side → {join_key: row}. Last write wins on duplicate keys (assume unique).
    b_rows = read_rows(b_table, frm.get("where"), ops)
    bmap = {r[b_col]: r for r in b_rows if b_col in r}

    # A candidates → resolve each SET value against its matched B row.
    a_rows = read_rows(table, where, ops)
    assign: Dict[Any, Dict[str, Any]] = {}
    cand_ids = []
    for a in a_rows:
        b = bmap.get(a.get(a_col))
        if b is None:
            continue   # inner-join: no partner → not updated
        # Computed specs ($inc/zExpr) may fold in the joined row (e.g. score = score + %teams.bonus);
        # plain specs copy a literal or a %ref across the join.
        vals = {
            f: (resolve_set_value(f, spec, a, b_row=b, a_table=table, b_table=b_table)
                if is_computed(spec) else resolve_ref(spec, a, b, table, b_table))
            for f, spec in container.items()
        }
        assign[a[pk]] = vals
        cand_ids.append(a[pk])

    if not cand_ids:
        msg = f"[updated] 0 row(s) in {table} (no join matches)"
        ops.display.success(msg)
        return [] if request.get("returning") else False

    return commit_assignments(table, assign, pk, ops, request, cand_ids)
