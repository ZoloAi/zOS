# zOS/core/L3_Abstraction/m_zData/zData_modules/shared/operations/agg_aggregate.py
"""
AGGREGATE operation handler for statistical functions on table data.

This module implements the AGGREGATE operation for zData's query system. It provides
a handler for performing statistical aggregate functions (COUNT, SUM, AVG, MIN, MAX)
on table data with support for WHERE filtering and GROUP BY grouping.

Operation Overview
-----------------
The AGGREGATE operation performs statistical calculations on table data:
- count: Count rows (optionally by field for non-null counts)
- sum: Sum numeric field values
- avg: Average numeric field values
- min: Minimum field value
- max: Maximum field value

The handler supports:
- Simple aggregations (scalar result): COUNT(*), SUM(used_mb)
- Grouped aggregations (dict result): COUNT(*) GROUP BY role_id
- WHERE filtering (count active users only)
- Mode-aware output (zBifrost returns data, Terminal displays result)

Request Structure
----------------
**Simple Aggregation:**
    request = {
        "table": "users",
        "function": "count"
    }
    # Returns: 12

**Aggregation with Field:**
    request = {
        "table": "user_storage",
        "function": "sum",
        "field": "used_mb"
    }
    # Returns: 34200

**Aggregation with WHERE:**
    request = {
        "table": "users",
        "function": "count",
        "where": {"status": "active"}
    }
    # Returns: 10

**Aggregation with GROUP BY:**
    request = {
        "table": "user_roles",
        "function": "count",
        "group_by": "role_id"
    }
    # Returns: {1: 1, 2: 3, 3: 8}

Supported Functions
------------------
- **count**: Count rows or non-null values in field
  - Field optional (defaults to * for row count)
  - Returns int (0 for empty result)

- **sum**: Sum numeric values in field
  - Field required
  - Returns int/float (None for empty result)

- **avg**: Average numeric values in field
  - Field required
  - Returns float (None for empty result)

- **min**: Minimum value in field
  - Field required
  - Returns value (None for empty result)

- **max**: Maximum value in field
  - Field required
  - Returns value (None for empty result)

Mode-Aware Display
-----------------
**zCLI Mode:**
- Displays result in human-readable format
- Simple: "Total Users: 12"
- Grouped: Table with group values and counts

**zBifrost Mode:**
- Returns result data directly for frontend rendering
- Simple: {"result": 12}
- Grouped: {"result": {1: 1, 2: 3, 3: 8}}

Integration with Data Layer
---------------------------
The handler delegates to adapter.aggregate() for backend-specific execution:
- SQLite/PostgreSQL: Uses SQL aggregate functions (SELECT COUNT(*), SUM(), etc.)
- CSV: Uses pandas DataFrame aggregate methods (.count(), .sum(), .mean(), etc.)

Error Handling
-------------
The handler validates:
- Function name (must be count/sum/avg/min/max)
- Field requirement (sum/avg/min/max require field, count is optional)
- Table existence (via adapter)
- WHERE clause syntax (via adapter)

Returns "error" string and logs error on failure.

Examples
-------
**Count all users:**
    >>> request = {"table": "users", "function": "count"}
    >>> result = handle_aggregate(request, ops)
    >>> # 12

**Sum storage usage:**
    >>> request = {"table": "user_storage", "function": "sum", "field": "used_mb"}
    >>> result = handle_aggregate(request, ops)
    >>> # 34200

**Count by role:**
    >>> request = {"table": "user_roles", "function": "count", "group_by": "role_id"}
    >>> result = handle_aggregate(request, ops)
    >>> # {1: 1, 2: 3, 3: 8}

See Also
-------
- crud_read.py: READ operation with JOIN support
- base_adapter.py: Abstract aggregate() method definition
- sql_adapter.py: SQL aggregate implementation
- csv_adapter.py: pandas aggregate implementation
"""

from zOS import Dict, Any
from ..chunk_bridge import capture, live_read

# ============================================================
# Constants
# ============================================================

# Request keys (shared keys SSOT: shared/data_keys)
from ..data_keys import KEY_TABLE, KEY_WHERE  # pylint: disable=wrong-import-position
_KEY_TABLE = KEY_TABLE
_KEY_FUNCTION = "function"
_KEY_FIELD = "field"
_KEY_WHERE = KEY_WHERE
_KEY_GROUP_BY = "group_by"
_KEY_ALIAS = "alias"
_KEY_HAVING = "having"

# Error messages
_ERR_NO_TABLE = "AGGREGATE requires 'table' key"
_ERR_NO_FUNCTION = "AGGREGATE requires 'function' key"
_ERR_INVALID_FUNCTION = ("Invalid aggregate function. Must be: count, sum, avg, min, max, "
                         "count_distinct, stddev, variance, median, group_concat/string_agg")
_ERR_MISSING_FIELD = "Aggregate function '{function}' requires 'field' key"
_ERR_HAVING_ALIAS = "HAVING requires 'alias' to be set (the computed column name)"

# Log messages
_LOG_AGGREGATE_START = "Executing AGGREGATE %s(%s) on table '%s'"
_LOG_AGGREGATE_WHERE = "  WHERE: %s"
_LOG_AGGREGATE_GROUP = "  GROUP BY: %s"
_LOG_AGGREGATE_ALIAS = "  ALIAS: %s"
_LOG_AGGREGATE_HAVING = "  HAVING: %s → %d rows after filter"
_LOG_AGGREGATE_SUCCESS = "AGGREGATE completed: %s"
_LOG_AGGREGATE_FAIL = "AGGREGATE failed: %s"

# Valid functions (SSOT: agg_compute.VALID_FUNCS)
from .agg_compute import VALID_FUNCS, compute_aggregate  # pylint: disable=wrong-import-position
_VALID_FUNCTIONS = VALID_FUNCS

# Keys consumed by AGGREGATE itself — stripped before the inner read so they do
# not leak into handle_read (which would mis-project or prematurely limit rows).
_AGG_STRIP_KEYS = {
    "function", "field", "group_by", "alias", "having", "distinct", "separator",
    "fields", "limit", "offset", "order", "order_by", "silent", "action", "zTable",
}

# ============================================================
# Private Helpers
# ============================================================

_HAVING_OPS = {
    ">=": lambda a, b: a >= b,
    "<=": lambda a, b: a <= b,
    "!=": lambda a, b: a != b,
    ">":  lambda a, b: a > b,
    "<":  lambda a, b: a < b,
    "=":  lambda a, b: a == b,
}


def _apply_having(rows, having_expr: str, alias: str):
    """Filter row dicts by a simple HAVING expression on the alias column.

    Accepts: ``alias > N``, ``alias >= N``, ``alias < N``, ``alias <= N``,
             ``alias = N``, ``alias != N``  (field name is stripped before
             comparing so the user can write either ``total > 1`` or just ``> 1``).
    """
    expr = having_expr.strip()
    # Strip leading alias token if present (e.g. "total > 1" → "> 1")
    if expr.lower().startswith(alias.lower()):
        expr = expr[len(alias):].strip()
    for op_str, op_fn in _HAVING_OPS.items():
        if expr.startswith(op_str):
            raw_val = expr[len(op_str):].strip()
            try:
                threshold = float(raw_val)
            except ValueError:
                return rows  # unparseable — skip filter silently
            return [r for r in rows if op_fn(float(r.get(alias, 0)), threshold)]
    return rows


# ============================================================
# Public API
# ============================================================

__all__ = ["handle_aggregate"]


def handle_aggregate(request: Dict[str, Any], ops: Any) -> Any:
    """
    Handle AGGREGATE operation with statistical functions.
    
    Validates request parameters, delegates to adapter.aggregate(), and handles
    mode-aware display. Returns scalar for simple aggregations or dict for
    grouped aggregations.
    
    Args:
        request: Request dict with keys:
                 - table (str): Table name
                 - function (str): Aggregate function (count/sum/avg/min/max)
                 - field (str, optional): Field to aggregate
                 - where (dict, optional): WHERE clause for filtering
                 - group_by (str, optional): Field to group by
        ops: DataOperations facade instance
    
    Returns:
        Scalar value (int/float) for simple aggregation
        Dict {group_value: aggregate_value} for GROUP BY aggregation
        "error" string on failure
    
    Examples:
        >>> request = {"table": "users", "function": "count"}
        >>> result = handle_aggregate(request, ops)
        >>> # 12
        
        >>> request = {"table": "user_storage", "function": "sum", "field": "used_mb"}
        >>> result = handle_aggregate(request, ops)
        >>> # 34200
    
    Notes:
        - Validates function name and field requirement
        - Uses adapter.aggregate() for backend execution
        - Logs operation details for debugging
        - Returns "error" string on failure
    """
    logger = ops.logger
    display = ops.display

    # ═══════════════════════════════════════════════════════════
    # 1. VALIDATE REQUEST
    # ═══════════════════════════════════════════════════════════

    # Resolve table: prefer explicit 'table' key, fall back to last segment of 'model' path
    table = request.get(_KEY_TABLE)
    if not table:
        model = request.get("model")
        if isinstance(model, str):
            table = model.split(".")[-1]

    if not table:
        if logger:
            logger.error(_ERR_NO_TABLE)
        if display:
            display.error(_ERR_NO_TABLE)
        return "error"

    # Validate function
    if _KEY_FUNCTION not in request:
        if logger:
            logger.error(_ERR_NO_FUNCTION)
        if display:
            display.error(_ERR_NO_FUNCTION)
        return "error"

    function = request[_KEY_FUNCTION]
    function_lower = function.lower()

    if function_lower not in _VALID_FUNCTIONS:
        if logger:
            logger.error(_ERR_INVALID_FUNCTION)
        if display:
            display.error(_ERR_INVALID_FUNCTION)
        return "error"

    # Extract optional parameters
    field = request.get(_KEY_FIELD)
    where = request.get(_KEY_WHERE)
    group_by = request.get(_KEY_GROUP_BY)
    # Normalise: accept str or list; keep None as-is
    if isinstance(group_by, str):
        group_by = group_by  # single-field — stays str for backward compat display
    elif isinstance(group_by, list):
        group_by = [g.strip() for g in group_by if g]
        if len(group_by) == 1:
            group_by = group_by[0]  # unwrap single-element list
    alias = request.get(_KEY_ALIAS)
    having = request.get(_KEY_HAVING)
    silent = request.get("silent", False)  # subquery / sub-call → return value, no display

    # HAVING requires alias so the filter knows which column to compare
    if having and not alias:
        err_msg = _ERR_HAVING_ALIAS
        if logger:
            logger.error(err_msg)
        if display:
            display.error(err_msg)
        return "error"

    # Validate field requirement
    if function_lower != "count" and not field:
        err_msg = _ERR_MISSING_FIELD.format(function=function)
        if logger:
            logger.error(err_msg)
        if display:
            display.error(err_msg)
        return "error"

    # ═══════════════════════════════════════════════════════════
    # 2. LOG OPERATION
    # ═══════════════════════════════════════════════════════════

    if logger:
        logger.info(_LOG_AGGREGATE_START, function, field or "*", table)
        if where:
            logger.info(_LOG_AGGREGATE_WHERE, where)
        if group_by:
            logger.info(_LOG_AGGREGATE_GROUP, group_by)
        if alias:
            logger.info(_LOG_AGGREGATE_ALIAS, alias)

    # ═══════════════════════════════════════════════════════════
    # 3. EXECUTE AGGREGATION
    # ═══════════════════════════════════════════════════════════

    try:
        # SSOT: fetch matching rows through the normal read pipeline (one path for
        # csv/sqlite/postgres, inheriting the full zFilters + subquery dialect) and
        # compute every statistic in the shared backend-agnostic computer.
        from .crud_read import handle_read

        distinct = bool(request.get("distinct", False))
        separator = request.get("separator", ", ")

        inner = {k: v for k, v in request.items() if k not in _AGG_STRIP_KEYS}
        rows = handle_read({**inner, "silent": True}, ops)
        if not isinstance(rows, list):
            rows = []

        result = compute_aggregate(
            rows,
            function_lower,
            field=field,
            group_by=group_by,
            alias=alias,
            distinct=distinct,
            separator=separator,
        )

        if logger:
            logger.info(_LOG_AGGREGATE_SUCCESS, result)

        # ═══════════════════════════════════════════════════════
        # 4. POST-PROCESS: HAVING filter + display
        # ═══════════════════════════════════════════════════════

        # When alias + group_by produced row dicts, apply HAVING and display as zTable
        if isinstance(result, list) and alias and group_by:
            if having:
                result = _apply_having(result, having, alias)
                if logger:
                    logger.info(_LOG_AGGREGATE_HAVING, having, len(result))

            # Optional display cap — flat `limit` slices the grouped output (post-HAVING),
            # matching read/window/set which all honor a flat limit.
            out_limit = request.get("limit")
            if out_limit:
                result = result[:int(out_limit)]

            if silent:
                return result
            columns = (list(group_by) if isinstance(group_by, list) else [group_by]) + [alias]
            with live_read(ops.zos):
                display.zTable(table, columns, result)

        elif silent:
            return result

        elif not isinstance(result, (list, dict)):
            # Scalar result — display inline
            func_label = f"{function}({field})" if field else f"{function}(*)"
            msg = f"{func_label} → {result}"
            if not capture(ops.zos, {'event': 'success', 'content': msg}):
                display.success(msg)

        elif isinstance(result, dict):
            # Flat GROUP BY dict (no alias) — display as summarised key: value pairs
            func_label = f"{function}({field})" if field else f"{function}(*)"
            lines = ", ".join(f"{k}: {v}" for k, v in list(result.items())[:10])
            suffix = f" (+{len(result) - 10} more)" if len(result) > 10 else ""
            group_label = ", ".join(group_by) if isinstance(group_by, list) else group_by
            msg = f"{func_label} GROUP BY {group_label} → {{{lines}{suffix}}}"
            if not capture(ops.zos, {'event': 'success', 'content': msg}):
                display.success(msg)

        return result

    except Exception as e:
        if logger:
            logger.error(_LOG_AGGREGATE_FAIL, str(e), exc_info=True)
        if display:
            display.error(f"Aggregation failed: {str(e)}")
        return "error"
