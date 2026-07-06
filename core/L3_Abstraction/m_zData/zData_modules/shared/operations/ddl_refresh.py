# zOS/core/L3_Abstraction/m_zData/zData_modules/shared/operations/ddl_refresh.py
"""
REFRESH operation handler — recompute a materialized view into its backing table.

A materialized view stores the rows of a saved read in an ordinary declared
table (``view: {materialized: true, into: <table>}``). Reading it is a plain,
fast read of that table; ``refresh`` is what re-syncs it with the live base
rows. The recompute is deliberately simple and backend-agnostic:

    1. run the view's saved spec as a silent read  → the current rows
    2. truncate the backing table                  → clear the stale snapshot
    3. bulk-insert the fresh rows                   → the new snapshot

Because step 1 rides the same read pipeline every backend shares, a refresh
means the identical thing on CSV, SQLite and Postgres. Refresh is explicit —
zData never auto-refreshes; the snapshot is stale-until-asked, by design.
"""

from zOS import Any, Dict

try:  # pragma: no cover - import shim (package vs flat)
    from .view_resolver import is_view, is_materialized, backing_table, view_read_spec
    from .crud_read import handle_read
except ImportError:  # pragma: no cover
    from view_resolver import is_view, is_materialized, backing_table, view_read_spec  # type: ignore
    from crud_read import handle_read  # type: ignore

_LOG_NOT_VIEW = "[REFRESH] '%s' is not a view — nothing to refresh"
_LOG_NOT_MATERIALIZED = (
    "[REFRESH] '%s' is a virtual view — it is always live, so there is nothing "
    "to refresh (only materialized views have a stored snapshot)"
)
_LOG_DONE = "[refreshed] '%s' → %d row(s) into '%s'"


def handle_refresh(request: Dict[str, Any], ops: Any) -> bool:
    """Recompute a materialized view's backing table from its saved spec."""
    name = ops._target_table_name(request)  # pylint: disable=protected-access
    schema = getattr(ops, "schema", {}) or {}

    if not name or not is_view(schema, name):
        ops.logger.error(_LOG_NOT_VIEW, name)
        return False

    if not is_materialized(schema, name):
        ops.logger.error(_LOG_NOT_MATERIALIZED, name)
        return False

    into = backing_table(schema, name)
    spec = view_read_spec(schema, name)

    # 1) current rows — silent read so no table paints during a recompute
    rows = handle_read({**spec, "silent": True}, ops)
    if not isinstance(rows, list):
        rows = []

    # 2) clear the stale snapshot (direct truncate: resets PK, no display noise)
    if ops.adapter:
        ops.adapter.truncate(into)

    # 3) write the fresh snapshot
    if rows:
        ops.insert_many(into, rows)

    ops.logger.info(_LOG_DONE, name, len(rows), into)
    if getattr(ops, "display", None) and not request.get("silent"):
        ops.display.success(_LOG_DONE % (name, len(rows), into))
    return True
