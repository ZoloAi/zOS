# zOS/core/L3_Abstraction/m_zData/zData_modules/shared/operations/ddl_index.py
"""
INDEX / DROP_INDEX operation handlers — add or drop an index on an EXISTING table.

Declaring `indexes:` on a table builds them at create time (see the schema key).
These two actions cover the *after* case: a table already exists and you want to
add an index for a query that got slow, or drop one you no longer need. Both are
backend-agnostic by the same trick as the rest of DDL — the SQL adapters emit a
real `CREATE INDEX` / `DROP INDEX`, and CSV (which has no index concept) inherits
a harmless no-op, so the identical `.zolo` runs on every backend.

Request shape:
    action: index                 # create
    model / table: <existing table>
    index: status                 # a field  → idx_<table>_status
    #   or [team_id, role]        # a field list → composite
    #   or {fields: [...], unique: true, name: uq_...}

    action: drop_index            # drop
    model / table: <existing table>
    index: status                 # by field  → idx_<table>_status
    #   or idx_members_status     # by explicit name
"""

from zOS import Any, Dict

try:  # pragma: no cover - import shim (package vs flat)
    from .helpers import extract_table_from_request
except ImportError:  # pragma: no cover
    from helpers import extract_table_from_request  # type: ignore

_OP_INDEX = "INDEX"
_OP_DROP_INDEX = "DROP_INDEX"
_KEY_INDEX = "index"
_KEY_NAME = "name"

_ERR_NO_SPEC = "index: requires a field, a [field list], or a {fields, unique, name} spec"
_ERR_NO_TARGET = "drop_index: name the index by `index:` (field or idx_ name)"
_LOG_CREATED = "[index] created %s on %s"
_LOG_CREATED_NOOP = "[index] %s: no index concept on this backend — declared, no-op"
_LOG_DROPPED = "[index] dropped %s from %s"


def handle_create_index(request: Dict[str, Any], ops: Any) -> bool:
    """Create one index on an existing table (CSV: benign no-op)."""
    table = extract_table_from_request(request, _OP_INDEX, ops, check_exists=True)
    if not table:
        return False

    spec = request.get(_KEY_INDEX)
    if spec is None:
        ops.logger.error(_ERR_NO_SPEC)
        if getattr(ops, "display", None):
            ops.display.error(_ERR_NO_SPEC)
        return False

    name = ops.adapter.create_index(table, spec)
    if name:
        ops.logger.info(_LOG_CREATED, name, table)
        if getattr(ops, "display", None) and not request.get("silent"):
            ops.display.success(_LOG_CREATED % (name, table))
    else:
        # None = CSV/flat no-op (table + spec were valid) — declared, nothing built
        ops.logger.info(_LOG_CREATED_NOOP, table)
    return True


def handle_drop_index(request: Dict[str, Any], ops: Any) -> bool:
    """Drop one index from an existing table by field or explicit name (CSV: no-op)."""
    table = extract_table_from_request(request, _OP_DROP_INDEX, ops, check_exists=True)
    if not table:
        return False

    spec = request.get(_KEY_INDEX)
    if spec is None:
        spec = request.get(_KEY_NAME)
    if spec is None:
        ops.logger.error(_ERR_NO_TARGET)
        if getattr(ops, "display", None):
            ops.display.error(_ERR_NO_TARGET)
        return False

    name = ops.adapter.drop_index(table, spec)
    if name:
        ops.logger.info(_LOG_DROPPED, name, table)
        if getattr(ops, "display", None) and not request.get("silent"):
            ops.display.success(_LOG_DROPPED % (name, table))
    else:
        ops.logger.info(_LOG_CREATED_NOOP, table)
    return True
