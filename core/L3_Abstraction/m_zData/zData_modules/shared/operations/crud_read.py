# zOS/core/L3_Abstraction/m_zData/zData_modules/shared/operations/crud_read.py
"""
READ operation handler with JOIN support, filtering, and mode-aware display.

This module implements the READ operation for zData's CRUD system. It provides
a comprehensive handler for querying and selecting rows from database tables with
support for single/multi-table queries, JOINs, WHERE filtering, ORDER BY, LIMIT,
mode-aware display, and pagination.

Operation Overview
-----------------
The READ operation queries rows from one or more tables. The handler supports:
- Single-table queries (SELECT * FROM users)
- Multi-table queries with JOINs (SELECT * FROM users, orders)
- Manual JOIN definitions (explicit join conditions)
- Auto-join from foreign key detection (adapter scans FK relationships)
- WHERE clause filtering (age > 18, name LIKE 'A%')
- ORDER BY sorting (order by name ASC, created DESC)
- LIMIT + OFFSET pagination (limit 10, offset 20 for page 3)
- Mode-aware display (zBifrost returns rows, zCLI displays table)
- Interactive pagination (pause + "Press Enter to continue")

Single vs Multi-Table Queries
-----------------------------
**Single-Table Query:**
    request = {"table": "users", "where": "age > 18", "order": "name", "limit": 10}
    - Queries one table
    - Simple SELECT with WHERE/ORDER/LIMIT

**Multi-Table Query:**
    request = {"tables": ["users", "orders"], "auto_join": True}
    - Queries multiple tables
    - Requires JOIN (manual or auto)
    - Returns combined result set

JOIN Support
-----------
The handler supports two JOIN mechanisms:

**1. Manual JOINs (Explicit):**
    request = {
        "tables": ["users", "orders"],
        "joins": [{"table": "orders", "on": "users.id = orders.user_id"}]
    }
    - Explicit join conditions provided in request
    - Full control over join type and conditions

**2. Auto-Join (FK Detection):**
    request = {"tables": ["users", "orders"], "auto_join": True}
    - Adapter automatically detects foreign key relationships
    - Generates JOIN conditions from schema metadata
    - Scans forward FKs (users.id → orders.user_id)
    - Scans reverse FKs (orders.user_id → users.id)

WHERE Clause Filtering
---------------------
WHERE clause supports SQL-like conditions:
- Comparison: age > 18, price <= 100
- Pattern matching: name LIKE 'A%'
- IN lists: status IN ('active', 'pending')
- NULL checks: email IS NULL, phone IS NOT NULL
- Logical: (age > 18 AND status = 'active') OR role = 'admin'

ORDER BY and LIMIT
-----------------
**ORDER BY:**
    request = {"order": "name ASC, created DESC"}
    - Sorts results by one or more columns
    - ASC (ascending) or DESC (descending)

**LIMIT:**
    request = {"limit": 10}
    - Limits number of rows returned
    - Useful for pagination

**LIMIT + OFFSET (Pagination):**
    request = {"limit": 20, "offset": 40}
    - Shows rows 41-60 (page 3, assuming 20 rows per page)
    - offset: Number of rows to skip
    - limit: Maximum rows to return
    - Common pattern: offset = (page_number - 1) * page_size

Display Integration
------------------
The handler uses zDisplay (AdvancedData) for output:
- **zDisplay.zTable(table_name, columns, rows, limit, offset):** Displays results as paginated table
- **Column extraction:** Automatically extracts column names from first row
- **Pagination metadata:** AdvancedData displays "Showing X-Y of Z" footer
- **Empty result handling:** Displays "[OK] Read 0 rows (table is empty or no matches)"

Mode-Aware Behavior
------------------
The handler adapts behavior based on zMode from session:

**zCLI Mode (zMode = "zCLI" or "Walker"):**
    - Displays results via zDisplay.zTable()
    - Pauses with "Press Enter to continue" (if pause=True)
    - Returns True (success indicator)

**zBifrost Mode (zMode = "zBifrost"):**
    - Does NOT display table (Bifrost renders on frontend)
    - Does NOT pause (non-interactive)
    - Returns rows list (for JSON serialization)

Pagination
---------
Interactive pagination controlled by:
- **pause parameter:** request.get("pause", True) - default True
- **zMode:** Only pauses in zCLI/Walker modes
- **zTraceback:** Must be True (session diagnostic mode)
- **Prompt:** "Press Enter to continue..." via zDisplay.read_string()

zSession Integration
-------------------
The handler reads session variables:
- **zMode:** Execution mode (zCLI, Walker, zBifrost)
- **zTraceback:** Diagnostic mode flag (True = enable pause/prompts)

Table Extraction
---------------
The handler supports three table sources (checked in order):

**1. tables parameter (list):**
    request = {"tables": ["users", "orders"]}
    - Most explicit, preferred source

**2. table parameter (string or list):**
    request = {"table": "users"}
    request = {"table": "users, orders"}  # Comma-separated
    - Single or comma-separated list
    - Parsed and split if contains comma

**3. model parameter (string):**
    request = {"model": "myapp.users"}
    - Extracts table name from model path
    - Supports comma-separated: "myapp.users, myapp.orders"

Usage Examples
-------------
**Basic Single-Table Read:**
    >>> request = {"table": "users"}
    >>> result = handle_read(request, ops)
    [OK] Read 15 row(s) from users

**Read with WHERE and ORDER:**
    >>> request = {"table": "users", "where": "age > 18", "order": "name"}
    >>> result = handle_read(request, ops)
    [OK] Read 8 row(s) from users

**Multi-Table with Auto-Join:**
    >>> request = {"tables": ["users", "orders"], "auto_join": True}
    >>> result = handle_read(request, ops)
    [OK] Read 42 row(s) from users + orders

**Read in zBifrost Mode (returns rows):**
    >>> ops.zos.session["zMode"] = "zBifrost"
    >>> rows = handle_read(request, ops)
    >>> # Returns list of dicts for JSON serialization

Integration
----------
This module is used by:
- classical_data.py: Classical paradigm READ operations
- quantum_data.py: Quantum paradigm READ operations
- data_operations.py: CRUD operation router
"""

from zOS import Any, Dict, List, Union
from ..chunk_bridge import chunking_active, live_read
from .view_resolver import is_view, resolve_view_read

# ============================================================
# Module Constants - Operation Name
# ============================================================

_OP_READ = "READ"

# ============================================================
# Module Constants - Request Keys (SSOT: shared/data_keys)
# ============================================================

from ..data_keys import (  # pylint: disable=wrong-import-position
    KEY_TABLE, KEY_TABLES, KEY_MODEL, KEY_FIELDS, KEY_WHERE,
    KEY_ORDER, KEY_LIMIT, KEY_OFFSET, KEY_JOINS,
)
from ..operators import (  # pylint: disable=wrong-import-position
    OP_GT, OP_LT, OP_GTE, OP_LTE, OP_NOTNULL, OP_LIKE, OP_NIN,
)

_KEY_TABLES = KEY_TABLES
_KEY_TABLE = KEY_TABLE
_KEY_MODEL = KEY_MODEL
_KEY_FIELDS = KEY_FIELDS
_KEY_WHERE = KEY_WHERE
_KEY_ORDER = KEY_ORDER
_KEY_LIMIT = KEY_LIMIT
_KEY_OFFSET = KEY_OFFSET
_KEY_JOINS = KEY_JOINS
_KEY_AUTO_JOIN = "auto_join"
_KEY_PAUSE = "pause"
_KEY_SEARCH        = "search"
_KEY_SEARCH_FIELDS = "search_fields"
_KEY_SEARCH_MODE   = "search_mode"   # any | all | phrase
_KEY_SEARCH_SCORE  = "_score"

# Pagination limits
_DEFAULT_LIMIT = 100  # Reasonable default page size
_MAX_LIMIT = 1000     # Prevent excessive queries

# ============================================================
# Module Constants - Session Keys
# ============================================================

_SESSION_ZMODE = "zMode"
_SESSION_ZPAGINATE = "zPaginate"

# ============================================================
# Module Constants - Mode Names
# ============================================================

_MODE_WALKER = "Walker"
_MODE_ZCLI = "zCLI"
_MODE_ZBIFROST = "zBifrost"

# ============================================================
# Module Constants - Display Keys
# ============================================================

_DISPLAY_SEPARATOR = " + "
_DISPLAY_PROMPT = "Press Enter to continue..."

# ============================================================
# _zCells: value-conditional cell styling helper
# ============================================================

def _build_where_from_filters(z_filters: Dict) -> Dict:
    """
    Compile a zFilters block into a CSV adapter dict WHERE clause.

    Operator mapping (canonical tokens — SSOT: shared/operators.py):
        <scalar>:  col: value  → {col: value}           plain equality
        zAbove:    val  → {col: {"$gt": val}}
        zBelow:    val  → {col: {"$lt": val}}
        zIs:       val  → {col: val}                    scalar or list → IN
        zIncludes: val  → {col: {"$like": "%val%"}}
        zStarts:   val  → {col: {"$like": "val%"}}
        zEnds:     val  → {col: {"$like": "%val"}}
        zIN:       [v1,v2]  → {col: [v1, v2]}           IN operator
        zBetween:  [min,max] → {col: {"$gte": min, "$lte": max}}
        zNull:     true → {col: None}                   IS NULL
        zKnown:    true → {col: {"$notnull": True}}     IS NOT NULL
        zWhere:    str  → parsed raw SQL string, merged into result dict

    Returns a dict compatible with csv_helpers/where_filtering.py.
    Supports qualified column names (table.column) for filtered JOINs.
    """
    _UNSET = object()
    result: Dict = {}
    z_where_str = None

    for col, rules in z_filters.items():
        if col == 'zWhere':
            # Raw SQL escape hatch — parsed and merged at the end
            z_where_str = rules
            continue

        # Plain scalar equality: col: value (no operator block needed)
        if not isinstance(rules, dict):
            result[col] = rules
            continue

        col_cond: Dict = {}
        simple_eq = _UNSET
        for op, val in rules.items():
            if   op == 'zAbove':    col_cond[OP_GT] = val
            elif op == 'zBelow':    col_cond[OP_LT] = val
            elif op == 'zIs':       simple_eq = val
            elif op == 'zIncludes': col_cond[OP_LIKE] = f'%{val}%'
            elif op == 'zStarts':   col_cond[OP_LIKE] = f'{val}%'
            elif op == 'zEnds':     col_cond[OP_LIKE] = f'%{val}'
            elif op == 'zIN':       simple_eq = val if isinstance(val, list) else [val]
            elif op == 'zBetween' and isinstance(val, list) and len(val) == 2:
                col_cond[OP_GTE] = val[0]
                col_cond[OP_LTE] = val[1]
            elif op == 'zNull':     simple_eq = None      # None → IS NULL in adapter
            elif op == 'zKnown':    col_cond[OP_NOTNULL] = True
        if col_cond:
            result[col] = col_cond
        elif simple_eq is not _UNSET:
            result[col] = simple_eq

    # Merge zWhere raw string conditions into result dict
    if z_where_str and isinstance(z_where_str, str):
        parsed = parse_where_clause(z_where_str)
        if parsed and isinstance(parsed, dict):
            for col, cond in parsed.items():
                if col in result and isinstance(result[col], dict) and isinstance(cond, dict):
                    result[col] = {**result[col], **cond}
                else:
                    result[col] = cond

    return result


def _apply_zcells(rows: List[Dict], z_cells: Dict) -> List[Dict]:
    """
    Wrap cell values matching _zCells rules into {val, _zClass} descriptors.

    Supported operators (evaluated in declaration order, first match wins):
        zAbove: [threshold, class]  — numeric value > threshold
        zBelow: [threshold, class]  — numeric value < threshold
        zIs:    [target,    class]  — value == target (any type)

    Unmatched cells are left as-is (raw value).
    """
    result = []
    for row in rows:
        new_row = dict(row)
        for col, rules in z_cells.items():
            if col not in new_row or not isinstance(rules, dict):
                continue
            raw = new_row[col]
            matched = None
            for op, args in rules.items():
                if not isinstance(args, (list, tuple)) or len(args) < 2:
                    continue
                threshold, cls = args[0], args[1]
                if op == 'zIs':
                    # TODO: multi-value zIs — support zIs: [[New York, Dubai], zText-warning]
                    #       where args[0] is a list → match any value in list (IN semantics).
                    # String-safe equality — compare stripped strings so CSV whitespace is ignored
                    if str(raw).strip() == str(threshold).strip():
                        matched = cls
                elif op == 'zIncludes':
                    # Case-insensitive substring match: "New York" zIncludes "New" → True
                    if str(threshold).lower() in str(raw).lower():
                        matched = cls
                elif op == 'zStarts':
                    # Case-insensitive prefix match: "New York" zStarts "New" → True
                    if str(raw).lower().startswith(str(threshold).lower()):
                        matched = cls
                elif op == 'zEnds':
                    # Case-insensitive suffix match: "New York" zEnds "York" → True
                    if str(raw).lower().endswith(str(threshold).lower()):
                        matched = cls
                else:
                    try:
                        if op == 'zAbove' and float(raw) > float(threshold):
                            matched = cls
                        elif op == 'zBelow' and float(raw) < float(threshold):
                            matched = cls
                    except (TypeError, ValueError):
                        pass
                if matched:
                    break
            if matched:
                new_row[col] = {'val': raw, '_zClass': matched}
        result.append(new_row)
    return result


def _resolve_subqueries(where: Dict, ops: Any) -> Dict:
    """
    Walk a WHERE dict and execute any nested {zData: {...}} subqueries in-place.

    Syntax in zolo:
        where:
          country:
            zData:
              action: read
              model: @.models.Demos.zSchema.basic.demo_read
              fields: [country]
              where: "score > 90"
              distinct: true

    The inner zData block is executed as a silent read; the first entry in
    ``fields`` is extracted from each result row to build the IN value list.
    That list replaces the {zData: ...} condition so the outer query receives
    a plain list value, which where_filtering.py maps to pandas isin().

    Three subquery shapes are supported (all uncorrelated):

        IN      col: {zData: {...}}                  → col IN  (values)
        NOT IN  col: {zData: {...}, zNot: true}       → col NOT IN (values)
        scalar  col: {$gt: {zData: {...}}}            → col > (single value)
                (any operator whose value is a {zData:{...}} block; the inner
                 read/aggregate is resolved to one scalar and inlined)

    Only dict WHERE clauses are walked; string WHERE clauses pass through unchanged.
    Correlated subqueries (inner referencing the outer row) are not handled here.
    """
    if not isinstance(where, dict):
        return where
    resolved: Dict = {}
    for col, condition in where.items():
        if isinstance(condition, dict) and 'zData' in condition:
            values = _subquery_values(condition['zData'], ops)
            if ops.logger:
                ops.logger.info(_LOG_SUBQUERY, col, len(values), values[:5])
            resolved[col] = {OP_NIN: values} if condition.get('zNot') else values
        elif isinstance(condition, dict):
            # Operator dict — inline any nested scalar subquery (e.g. {$gt: {zData:{...}}})
            new_cond: Dict = {}
            for op, val in condition.items():
                if isinstance(val, dict) and 'zData' in val:
                    new_cond[op] = _subquery_scalar(val['zData'], ops)
                else:
                    new_cond[op] = val
            resolved[col] = new_cond
        else:
            resolved[col] = condition
    return resolved


def _subquery_values(inner_req: Dict, ops: Any) -> List:
    """Run a subquery read and return a flat list of values (IN / NOT IN sets)."""
    inner = dict(inner_req)
    fields = inner.get('fields') or []
    extract = fields[0] if fields else None
    rows = handle_read({**inner, 'silent': True}, ops)
    if not isinstance(rows, list) or not rows:
        return []
    key = extract or next(iter(rows[0].keys()))
    return [row[key] for row in rows if key in row]


def _subquery_scalar(inner_req: Dict, ops: Any) -> Any:
    """Resolve a subquery to a single scalar (first value, or aggregate result)."""
    inner = dict(inner_req)
    action = str(inner.get('action', 'read')).lower()
    if action == 'aggregate':
        from .agg_aggregate import handle_aggregate
        return handle_aggregate({**inner, 'silent': True}, ops)
    rows = handle_read({**inner, 'silent': True}, ops)
    if isinstance(rows, list) and rows:
        fields = inner.get('fields') or []
        key = fields[0] if fields else next(iter(rows[0].keys()))
        return rows[0].get(key)
    return None


# ============================================================
# Correlated subqueries + EXISTS / NOT EXISTS (per-outer-row)
# ============================================================
# These cannot be inlined once like an uncorrelated subquery — the inner query
# references the current outer row via a `%outer.<field>` token, so it must be
# re-evaluated for each outer row AFTER the outer rows are fetched. We split them
# out of the WHERE dict, fetch the candidate rows with the plain WHERE, then apply
# each correlated predicate row-by-row. All in-memory → identical on every backend.

_OUTER_PREFIX = "%outer."


def _has_outer_ref(obj: Any) -> bool:
    """True if any string anywhere in obj references the outer row (`%outer.`)."""
    if isinstance(obj, str):
        return _OUTER_PREFIX in obj
    if isinstance(obj, dict):
        return any(_has_outer_ref(v) for v in obj.values())
    if isinstance(obj, list):
        return any(_has_outer_ref(v) for v in obj)
    return False


def _bind_outer(obj: Any, outer: Dict) -> Any:
    """Deep-copy obj, replacing a bare `%outer.<field>` string with the outer row's
    typed value (embedded refs fall back to string substitution)."""
    if isinstance(obj, str):
        if obj.startswith(_OUTER_PREFIX):
            return outer.get(obj[len(_OUTER_PREFIX):])
        if _OUTER_PREFIX in obj:
            out = obj
            for k, v in outer.items():
                out = out.replace(f"{_OUTER_PREFIX}{k}", str(v))
            return out
        return obj
    if isinstance(obj, dict):
        return {k: _bind_outer(v, outer) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_bind_outer(v, outer) for v in obj]
    return obj


def _split_row_predicates(where: Dict, ops: Any):
    """
    Pull correlated / EXISTS conditions out of a WHERE dict.

    Returns ``(plain_where, preds)`` where ``plain_where`` holds only the
    uncorrelated conditions (safe to hand to the adapter) and ``preds`` is a list
    of per-row predicate specs evaluated after the fetch:

        EXISTS      where: {zExists:    {zData: {...}}}   → keep row if inner has ≥1 row
        NOT EXISTS  where: {zNotExists: {zData: {...}}}   → keep row if inner has 0 rows
        corr scalar where: {col: {$gt: {zData: {... %outer.x ...}}}}
        corr IN     where: {col: {zData: {... %outer.x ...}}}

    Only conditions carrying a `%outer.` token (or the EXISTS keys) are treated as
    correlated; everything else stays in ``plain_where`` for the uncorrelated path.
    """
    if not isinstance(where, dict):
        return where, []
    plain: Dict = {}
    preds: List[Dict] = []
    for col, cond in where.items():
        if col in ("zExists", "zNotExists"):
            inner = cond.get('zData') if isinstance(cond, dict) else None
            if inner is not None:
                preds.append({"kind": "exists", "inner": inner,
                              "negate": col == "zNotExists" or bool(cond.get('zNot'))})
                continue
        if isinstance(cond, dict) and 'zData' in cond and _has_outer_ref(cond['zData']):
            preds.append({"kind": "in", "col": col, "inner": cond['zData'],
                          "negate": bool(cond.get('zNot'))})
            continue
        if isinstance(cond, dict) and 'zData' not in cond:
            corr = next(((op, val['zData']) for op, val in cond.items()
                         if isinstance(val, dict) and 'zData' in val
                         and _has_outer_ref(val['zData'])), None)
            if corr:
                preds.append({"kind": "scalar_cmp", "col": col, "op": corr[0], "inner": corr[1]})
                continue
        plain[col] = cond
    return plain, preds


def _eval_row_predicates(rows: List[Dict], preds: List[Dict], ops: Any) -> List[Dict]:
    """Keep only rows that satisfy every correlated predicate (see _split_row_predicates)."""
    if not preds:
        return rows
    kept: List[Dict] = []
    for row in rows:
        ok = True
        for p in preds:
            inner = _bind_outer(p["inner"], row)
            if p["kind"] == "exists":
                sub = handle_read({**inner, "silent": True}, ops)
                present = bool(sub) if isinstance(sub, list) else False
                if present == p["negate"]:
                    ok = False
                    break
            elif p["kind"] == "scalar_cmp":
                val = _subquery_scalar(inner, ops)
                if not _evaluate_ir({p["col"]: {p["op"]: val}}, row):
                    ok = False
                    break
            elif p["kind"] == "in":
                vals = _subquery_values(inner, ops)
                contained = _evaluate_ir({p["col"]: vals}, row)
                if bool(contained) == p["negate"]:
                    ok = False
                    break
        if ok:
            kept.append(row)
    return kept


# ============================================================
# Module Constants - Log Messages
# ============================================================

_LOG_SUBQUERY = "[zData] Subquery on '%s': resolved %d value(s) → %s"
_LOG_CTE_EXEC  = "[zData] CTE '%s': resolved %d row(s)"
_LOG_CTE_FROM  = "[zData] Main query reading from CTE '%s' (%d rows)"
_LOG_FTS       = "[zData] FTS '%s' mode=%s fields=%s → %d / %d rows scored"
_LOG_NO_TABLE = "No table specified for %s operation"
_LOG_VALIDATE_TABLES = "Validating table existence: %s"
_LOG_MULTI_TABLE = "Multi-table query detected: %s"
_LOG_SINGLE_TABLE = "Single-table query: %s"
_LOG_EXECUTE_SELECT = "Executing SELECT on %s"
_LOG_DISPLAY_RESULTS = "Displaying %d row(s) from %s"
_LOG_SUCCESS = "[OK] Read %d row(s) from %s"
_LOG_EMPTY = "[OK] Read 0 rows from %s (table is empty or no matches)"
_LOG_TABLE_NOT_EXIST = "[FAIL] Table '%s' does not exist"
_LOG_PAUSE = "Pausing for user interaction"

# ============================================================
# Module Constants - Error Messages
# ============================================================

_ERR_NO_TABLE = "No table specified"
_ERR_TABLE_NOT_EXIST = "Table does not exist"
_ERR_INVALID_TABLE = "Invalid table name"
_ERR_SELECT_FAILED = "SELECT operation failed"
_ERR_DISPLAY_FAILED = "Display operation failed"

# ============================================================
# Imports - Helper Functions
# ============================================================

try:
    from .helpers import extract_where_clause, _evaluate_ir
    from .blob_ops import describe_blob_fields, blob_where_error
    from ..parsers.where_parser import parse_where_clause
except ImportError:
    from helpers import extract_where_clause, _evaluate_ir
    from blob_ops import describe_blob_fields, blob_where_error
    from parsers.where_parser import parse_where_clause

# ============================================================
# CTE (WITH clause) helpers
# ============================================================

def _apply_cte_filters(
    rows: List[Dict[str, Any]],
    where_raw: Any,
    fields: Any,
    order: Any,
    limit: Any,
    offset: int,
    distinct: bool,
) -> List[Dict[str, Any]]:
    """
    Apply WHERE / field-projection / ORDER / LIMIT / OFFSET / DISTINCT
    to an in-memory list of row dicts (CTE result or CTE-sourced main query).

    ``where_raw`` may be:
      - None / empty      → no filtering
      - str               → parsed with parse_where_clause into an IR dict
      - dict              → already an IR-compatible filter dict (parse_where_clause)

    Row matching reuses ``_evaluate_ir`` from helpers so all zFilters operators
    ($gt, $lt, $in, $like, $and/$or, …) work identically on CTE rows.
    """
    # 1. WHERE filtering
    if where_raw:
        if isinstance(where_raw, str):
            ir = parse_where_clause(where_raw)
        elif isinstance(where_raw, dict):
            # dict is already a field→value map; wrap in a flat IR form that
            # _evaluate_ir understands (direct key → value equality / operator check)
            ir = where_raw
        else:
            ir = None
        if ir:
            rows = [r for r in rows if _evaluate_ir(ir, r)]

    # 2. Field projection
    if fields:
        rows = [{k: r[k] for k in fields if k in r} for r in rows]

    # 3. DISTINCT
    if distinct:
        seen: List[tuple] = []
        unique: List[Dict[str, Any]] = []
        for r in rows:
            key = tuple(sorted((k, str(v)) for k, v in r.items()))
            if key not in seen:
                seen.append(key)
                unique.append(r)
        rows = unique

    # 4. ORDER BY  (single-column: "field" or "field ASC|DESC")
    if order and rows:
        parts = str(order).strip().split()
        col = parts[0]
        reverse = len(parts) > 1 and parts[1].upper() == 'DESC'
        rows = sorted(rows, key=lambda r: (r.get(col) is None, r.get(col, '')), reverse=reverse)

    # 5. OFFSET / LIMIT
    start = int(offset) if offset else 0
    rows = rows[start:]
    if limit:
        rows = rows[: int(limit)]

    return rows


def _execute_recursive_cte(entry: Dict[str, Any], ops: Any) -> List[Dict[str, Any]]:
    """
    Evaluate a recursive CTE (``WITH RECURSIVE``) as an in-memory fixpoint over a
    self-referential link — e.g. walk an org chart down ``manager_id``.

    Declarative shape::

        with:
          org:
            recursive: true
            anchor: {table: members, where: {id: 1}}     # seed rows
            step:   {table: members}                     # rows joined each round
            link:   {parent: id, child: manager_id}      # child.child == parent.parent
            max_depth: 100                               # safety cap (optional)

    Each round: take the ``parent`` values from the rows added last round, fetch
    ``step`` rows whose ``child`` value is in that set, and add the ones not seen
    yet (deduped by ``key``, default = ``parent``). Stops when a round adds nothing,
    or at ``max_depth`` — the guard against a cyclic graph.
    """
    anchor    = entry.get('anchor') or {}
    step      = entry.get('step') or {}
    link      = entry.get('link') or {}
    parent_key = link.get('parent', 'id')
    child_key  = link.get('child')
    id_key     = entry.get('key', parent_key)
    max_depth  = int(entry.get('max_depth', 100))

    seed = handle_read({**anchor, 'silent': True}, ops)
    seed = seed if isinstance(seed, list) else []
    result: List[Dict[str, Any]] = list(seed)
    seen = {r.get(id_key) for r in seed}
    frontier = list(seed)
    step_where = step.get('where') if isinstance(step.get('where'), dict) else {}

    depth = 0
    while frontier and child_key and depth < max_depth:
        parent_vals = [r.get(parent_key) for r in frontier if r.get(parent_key) is not None]
        if not parent_vals:
            break
        nxt = handle_read({**step, 'where': {**step_where, child_key: parent_vals},
                           'silent': True}, ops)
        nxt = nxt if isinstance(nxt, list) else []
        frontier = [r for r in nxt if r.get(id_key) not in seen]
        for r in frontier:
            seen.add(r.get(id_key))
            result.append(r)
        depth += 1

    return result


def _execute_with_block(
    with_dict: Dict[str, Any],
    ops: Any,
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Execute each CTE sub-request in declaration order, returning a
    ``{name: rows}`` context dict.

    Each entry in ``with_dict`` is a zData sub-request.  If its ``from:``
    key references a previously built CTE name the result rows come from the
    context (in-memory); otherwise the entry is executed as a silent adapter
    read via ``handle_read``.

    Ordering guarantee: Python dicts preserve insertion order (3.7+), so CTEs
    can reference earlier siblings by name.
    """
    context: Dict[str, List[Dict[str, Any]]] = {}
    for cte_name, sub_req in with_dict.items():
        if not isinstance(sub_req, dict):
            continue
        if sub_req.get('recursive'):
            rows = _execute_recursive_cte(sub_req, ops)
            if ops.logger:
                ops.logger.info(_LOG_CTE_EXEC, cte_name, len(rows))
            context[cte_name] = rows
            continue
        from_name = sub_req.get('from')
        if from_name and from_name in context:
            # CTE reads from a prior CTE — filter in memory
            rows = _apply_cte_filters(
                list(context[from_name]),
                where_raw=sub_req.get('where'),
                fields=sub_req.get('fields'),
                order=sub_req.get('order'),
                limit=sub_req.get('limit'),
                offset=sub_req.get('offset', 0),
                distinct=bool(sub_req.get('distinct', False)),
            )
        else:
            # Regular adapter read
            rows = handle_read({**sub_req, 'silent': True}, ops) or []
            if not isinstance(rows, list):
                rows = []
        if ops.logger:
            ops.logger.info(_LOG_CTE_EXEC, cte_name, len(rows))
        context[cte_name] = rows
    return context


# ============================================================
# Public API
# ============================================================

__all__ = ["handle_read"]


# ============================================================
# Full-Text Search helper
# ============================================================

def _apply_fts(
    rows: List[Dict],
    query: str,
    search_fields: List[str],
    mode: str,
) -> List[Dict]:
    """
    In-memory full-text search with relevance scoring.

    For each row, count how many query tokens appear (case-insensitive) across
    the searched fields.  The count is stored as _score.  Rows with _score == 0
    are dropped, and survivors are returned sorted by _score DESC.

    Modes
    -----
    any    (default) — row matches if *at least one* token is found in any field
    all              — row matches only if *every* token is found across the fields
    phrase           — row matches only if the *exact phrase* (lowercased) appears
                       in at least one field value
    """
    if not query or not rows:
        return rows

    q = query.lower().strip()
    tokens = q.split()

    def _text(row: Dict) -> str:
        """Concatenate all searched field values into a single search string."""
        parts = []
        for f in search_fields or list(row.keys()):
            v = row.get(f)
            if v is not None:
                parts.append(str(v).lower())
        return ' '.join(parts)

    def _score_row(row: Dict) -> int:
        text = _text(row)
        if mode == 'phrase':
            return 1 if q in text else 0
        if mode == 'all':
            return len(tokens) if all(t in text for t in tokens) else 0
        # default: any
        return sum(1 for t in tokens if t in text)

    scored = []
    for row in rows:
        s = _score_row(row)
        if s > 0:
            r = dict(row)
            r[_KEY_SEARCH_SCORE] = s
            scored.append(r)

    scored.sort(key=lambda r: r[_KEY_SEARCH_SCORE], reverse=True)
    return scored


# ============================================================
# CRUD Operations - READ
# ============================================================

def handle_read(request: Dict[str, Any], ops: Any) -> Union[bool, List[Dict[str, Any]]]:
    """
    Handle READ operation to query and select rows from one or more tables.

    This function implements the complete READ workflow including table extraction,
    validation, JOIN support (manual + auto), WHERE filtering, ORDER BY sorting,
    LIMIT pagination, mode-aware display, and interactive pagination.

    Args:
        request: Request dictionary containing query parameters
            - "tables" (list, optional): List of table names
            - "table" (str/list, optional): Single table or comma-separated list
            - "model" (str, optional): Model path (e.g., "myapp.users")
            - "fields" (list, optional): Column names to select
            - "where" (str, optional): WHERE clause (e.g., "age > 18")
            - "order" (str, optional): ORDER BY clause (e.g., "name ASC")
            - "limit" (int, optional): LIMIT clause (e.g., 10)
            - "joins" (list, optional): Manual JOIN definitions
            - "auto_join" (bool, optional): Auto-detect JOINs from FK (default False)
            - "pause" (bool, optional): Pause after display (default True)
        ops: Operations object providing:
            - adapter: Adapter instance for table_exists() and select()
            - logger: Logger instance for diagnostic output
            - display: Display instance for zTable() and read_string()
            - zos.session: Session dict with zMode and zTraceback

    Returns:
        Union[bool, List[Dict[str, Any]]]:
            - zCLI/Walker modes: True (success), False (failure)
            - zBifrost mode: List of row dicts (for JSON serialization)

    Raises:
        None: All errors are logged and return False

    Examples:
        >>> # Basic single-table read
        >>> request = {"table": "users"}
        >>> result = handle_read(request, ops)
        [OK] Read 15 row(s) from users

        >>> # Multi-table with auto-join
        >>> request = {"tables": ["users", "orders"], "auto_join": True}
        >>> result = handle_read(request, ops)
        [OK] Read 42 row(s) from users + orders

        >>> # zBifrost mode (returns rows)
        >>> ops.zos.session["zMode"] = "zBifrost"
        >>> rows = handle_read(request, ops)
        >>> len(rows)
        42

    Notes:
        - Table sources checked in order: tables, table, model
        - Multi-table queries require JOIN (manual or auto_join)
        - zBifrost mode returns rows (no display)
        - zCLI mode displays table and returns True
        - Pagination only in zCLI/Walker with zTraceback=True
    """
    # Phase 0: CTE (WITH clause) — build named result sets before table resolution.
    # If the main query's `from:` key references a CTE name, Phase 1–2 (table
    # extraction + adapter validation) are bypassed; the CTE rows are filtered
    # in memory instead of queried through the adapter.
    with_block = request.get('with')
    cte_context: Dict[str, List[Dict[str, Any]]] = {}
    if isinstance(with_block, dict):
        cte_context = _execute_with_block(with_block, ops)

    cte_from = request.get('from')
    _is_cte_query = bool(cte_context and isinstance(cte_from, str) and cte_from in cte_context)

    if _is_cte_query:
        # Skip adapter-based table resolution entirely for CTE-sourced queries.
        tables = [cte_from]
        is_multi_table = False
    else:
        # Phase 1: Extract table(s) from request (may be single or comma-separated list)
        tables = request.get(_KEY_TABLES, [])

        # Check singular "table" parameter
        if not tables:
            table_param = request.get(_KEY_TABLE)
            if table_param:
                if isinstance(table_param, str):
                    if "," in table_param:
                        tables = [t.strip() for t in table_param.split(",")]
                    else:
                        tables = [table_param]
                elif isinstance(table_param, list):
                    tables = table_param

        # Fallback to extracting from model path
        if not tables:
            model = request.get(_KEY_MODEL)
            if isinstance(model, str):
                # Check if model has comma (multi-table)
                table_name = model.split(".")[-1]
                if "," in table_name:
                    tables = [t.strip() for t in table_name.split(",")]
                else:
                    tables = [table_name]

        if not tables:
            ops.logger.error(_LOG_NO_TABLE, _OP_READ)
            return False

        # Phase 1.5: View interception. When the sole target is a declared view,
        # swap the name for its saved read — virtual views substitute the spec,
        # materialized views redirect to their backing table — compose the
        # caller's WHERE/fields/order on top, and re-enter the pipeline. This is
        # where a view stays backend-agnostic: it becomes a normal read before
        # any adapter is touched. (Cycle / depth breaches log and fail cleanly.)
        if len(tables) == 1 and is_view(getattr(ops, "schema", {}) or {}, tables[0]):
            resolved = resolve_view_read(tables[0], request, ops)
            if resolved is None:
                return False
            return handle_read(resolved, ops)

        # Phase 2: Validate all tables exist
        for tbl in tables:
            if not ops.adapter.table_exists(tbl):
                ops.logger.error(_LOG_TABLE_NOT_EXIST, tbl)
                return False

    # Phase 3: Determine if multi-table query
    if not _is_cte_query:
        is_multi_table = len(tables) > 1
    if is_multi_table:
        ops.logger.debug(_LOG_MULTI_TABLE, ", ".join(tables))
    else:
        ops.logger.debug(_LOG_SINGLE_TABLE, tables[0])

    # Phase 4: Parse query options
    fields = request.get(_KEY_FIELDS)
    # `order_by:` is the ONLY documented author-facing spelling (08_data_crud.md);
    # the dispatch layer passes it through verbatim (dispatch_constants.KEY_ORDER_BY
    # is a deliberately distinct key, never renamed to "order" en route). Accept
    # both, same alias already proven in agg_window.py's window ordering.
    order = request.get(_KEY_ORDER) or request.get('order_by')
    limit = request.get(_KEY_LIMIT)
    offset = request.get(_KEY_OFFSET, 0)  # Default to 0 (no offset)
    distinct = bool(request.get('distinct', False))
    where = extract_where_clause(request, ops, warn_if_missing=False)

    # zFilters: unified WHERE entry point — accepts a raw string (longhand) or structured dict
    z_filters = request.get('zFilters')
    if z_filters:
        if isinstance(z_filters, str):
            # Raw string form: zFilters: "score > 90" — same logic as where:
            # Inject into request under 'where' key so extract_where_clause can parse it
            raw_request = dict(request)
            raw_request['where'] = z_filters
            where = extract_where_clause(raw_request, ops, warn_if_missing=False)
            ops.logger.debug(f"[zFilters] Raw string WHERE: {where}")
        elif isinstance(z_filters, dict):
            filter_dict = _build_where_from_filters(z_filters)
            if filter_dict:
                if where and isinstance(where, dict):
                    # Merge: for same column, merge inner condition dicts
                    merged = dict(where)
                    for col, cond in filter_dict.items():
                        if col in merged and isinstance(merged[col], dict) and isinstance(cond, dict):
                            merged[col] = {**merged[col], **cond}
                        else:
                            merged[col] = cond
                    where = merged
                else:
                    where = filter_dict
                ops.logger.debug(f"[zFilters] Compiled WHERE dict: {where}")

    # Pull correlated / EXISTS conditions out first — they reference the outer row
    # (`%outer.<field>`) and must be evaluated per-row after the fetch.
    row_preds: List[Dict[str, Any]] = []
    if isinstance(where, dict):
        where, row_preds = _split_row_predicates(where, ops)

    # Resolve nested zData subqueries before the query reaches the adapter.
    # Any {col: {zData: {...}}} entry in the WHERE dict is executed as a silent
    # read and replaced with a plain list of values (IN semantics).
    if isinstance(where, dict):
        where = _resolve_subqueries(where, ops)

    # Guard: blob columns are non-comparable — only IS NULL / IS NOT NULL allowed.
    if isinstance(where, dict) and not _is_cte_query and len(tables) == 1:
        _blob_err = blob_where_error(where, ops.schema.get(tables[0], {}) if getattr(ops, 'schema', None) else {})
        if _blob_err:
            ops.logger.error("[zData] %s", _blob_err)
            ops.display.error(_blob_err)
            return False

    # Validate limit against MAX_LIMIT
    if limit and limit > _MAX_LIMIT:
        ops.logger.warning(f"Limit {limit} exceeds _MAX_LIMIT {_MAX_LIMIT}, capping to {_MAX_LIMIT}")
        limit = _MAX_LIMIT

    # Extract JOIN options
    joins = request.get(_KEY_JOINS)  # Manual join definitions
    auto_join = request.get(_KEY_AUTO_JOIN, False)  # Auto-detect from FK

    # zTable block holds all display/rendering props; zData owns only query-level params.
    # ShorthandExpander wraps recognised event keys: zTable:{limit:5} → {zDisplay:{event:'zTable',limit:5}}.
    # Unwrap the zDisplay envelope so the original props are accessible; filter the 'event' key.
    _raw_ztable = request.get('zTable') or {}
    _zdisplay_inner = _raw_ztable.get('zDisplay') if isinstance(_raw_ztable, dict) else None
    if isinstance(_zdisplay_inner, dict):
        z_table_opts = {k: v for k, v in _zdisplay_inner.items() if k != 'event'}
    else:
        z_table_opts = dict(_raw_ztable)
    z_pages = z_table_opts.get('zPages', request.get('zPages', False))
    display_limit = z_table_opts.get('limit', limit)
    display_offset = z_table_opts.get('offset', offset)

    # When zPages=True, fetch ALL rows so the client can paginate client-side.
    # zData.limit (flat) still acts as a safety cap on the DB query.
    query_limit = None if z_pages else limit

    # Phase 5: Execute SELECT (CTE in-memory or adapter)
    table_arg = tables[0] if len(tables) == 1 else tables
    ops.logger.debug(_LOG_EXECUTE_SELECT, table_arg)

    if _is_cte_query:
        # Operate on the CTE rows in Python — no adapter call
        cte_rows = list(cte_context[cte_from])
        if ops.logger:
            ops.logger.info(_LOG_CTE_FROM, cte_from, len(cte_rows))
        rows = _apply_cte_filters(
            cte_rows,
            where_raw=where,
            fields=fields,
            order=order,
            limit=query_limit,
            offset=display_offset,
            distinct=distinct,
        )
    elif row_preds:
        # Correlated / EXISTS: fetch the candidate superset (full columns, unbounded
        # so the per-row predicate — not the DB — decides the final set), evaluate the
        # correlated predicate per outer row, then project/dedupe/sort/page in Python.
        candidates = ops.select(
            table_arg, None, where=where, joins=joins, order=None,
            limit=None, offset=0, auto_join=auto_join, distinct=False
        ) or []
        rows = _eval_row_predicates(candidates, row_preds, ops)
        rows = _apply_cte_filters(rows, None, fields, order, query_limit, display_offset, distinct)
    else:
        rows = ops.select(
            table_arg, fields, where=where, joins=joins, order=order,
            limit=query_limit, offset=display_offset, auto_join=auto_join,
            distinct=distinct
        )

    # Phase 5a: Blob columns — replace raw stored cells with JSON-safe descriptors
    # ({_zblob, size, mime, filename}) for both zCLI display and zBifrost return.
    # Programmatic byte access goes through adapter.load_blob (e.g. the serve route).
    if not _is_cte_query and len(tables) == 1 and rows:
        _tbl_schema = ops.schema.get(tables[0], {}) if getattr(ops, 'schema', None) else {}
        rows = describe_blob_fields(rows, tables[0], _tbl_schema, ops)

    # Phase 5b: Apply _zCells value-conditional cell styling (server-side transform)
    # Wraps matched cells into {val, _zClass} descriptors consumed by table_renderer.js.
    z_cells = z_table_opts.get('_zCells')
    if z_cells and rows:
        rows = _apply_zcells(rows, z_cells)

    # Phase 5c: Full-text search (search: / search_fields: / search_mode:)
    # Applied post-select so it works identically across all backends (CSV, SQLite, PG).
    # Rows are scored by token-hit count (_score column) and sorted DESC by score.
    # Rows scoring 0 are dropped.  search_fields defaults to all row columns.
    fts_query = request.get(_KEY_SEARCH)
    if fts_query and rows:
        fts_fields = request.get(_KEY_SEARCH_FIELDS) or []
        if isinstance(fts_fields, str):
            fts_fields = [f.strip() for f in fts_fields.split(',')]
        fts_mode = str(request.get(_KEY_SEARCH_MODE, 'any')).lower()
        before = len(rows)
        rows = _apply_fts(rows, str(fts_query), fts_fields, fts_mode)
        ops.logger.info(_LOG_FTS, fts_query, fts_mode,
                        fts_fields or '*', len(rows), before)

    # Phase 6: Display results (mode-aware with AdvancedData pagination)
    # NEW v1.5.12: Support silent mode for background data fetching (_data blocks)
    silent = request.get("silent", False)

    if not silent:
        table_display = _DISPLAY_SEPARATOR.join(tables) if is_multi_table else tables[0]
        # Build display kwargs once (shared by both rows and empty-rows paths)
        _QUERY_KEYS = {'limit', 'offset', 'zPages'}
        _SERVER_KEYS = {'_zCells'}
        display_kwargs = {
            'limit': display_limit,
            'offset': display_offset,
            'zPages': z_pages,
            'caption': z_table_opts.get('caption', request.get('caption')),
            'truncate': z_table_opts.get('truncate', request.get('truncate', False)),
            'show_header': z_table_opts.get('show_header', request.get('show_header', True)),
            '_zColumn': z_table_opts.get('_zColumn', request.get('_zColumn')),
        }
        for k, v in z_table_opts.items():
            if k not in _QUERY_KEYS and k not in _SERVER_KEYS and k not in display_kwargs:
                display_kwargs[k] = v

        with live_read(ops.zos):
            if rows:
                # Extract column names from first row (assuming dict rows)
                columns = list(rows[0].keys()) if rows and isinstance(rows[0], dict) else []
                ops.display.zTable(table_display, columns, rows, **display_kwargs)
                ops.logger.info(_LOG_SUCCESS, len(rows), table_display)
            else:
                ops.logger.info(_LOG_EMPTY, table_display)
                # A zero-row read must still emit one (empty) zTable so chunked
                # rendering keeps block/payload positions aligned.
                if chunking_active(ops.zos):
                    ops.display.zTable(table_display, [], [], **display_kwargs)

        # Phase 7: Pagination (pause after displaying results)
        pause = request.get(_KEY_PAUSE, True)  # Default to True
        # Don't pause in zBifrost mode, when zMode is not Walker/zCLI, or when zPaginate is off.
        # zPaginate defaults False (preserves prior behavior: the former "zTraceback" flag was
        # seeded False, so table pagination-pause was effectively off).
        zMode = ops.zos.session.get(_SESSION_ZMODE, "")
        zPaginate = ops.zos.session.get(_SESSION_ZPAGINATE, False)
        if pause and zPaginate and zMode in (_MODE_WALKER, _MODE_ZCLI, ""):
            ops.logger.debug(_LOG_PAUSE)
            ops.display.read_string(_DISPLAY_PROMPT)

    # Phase 8: Return results (mode-aware)
    # NEW v1.5.12: Return rows for silent mode (background data fetching)
    # Return the actual rows for zBifrost mode or silent mode, True for terminal display mode
    zMode = ops.zos.session.get(_SESSION_ZMODE, "")
    if silent or zMode == _MODE_ZBIFROST:
        return rows
    return True
