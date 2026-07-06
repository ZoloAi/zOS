# zOS/core/L3_Abstraction/m_zData/zData_modules/shared/operations/agg_window.py
"""
WINDOW operation handler — analytic functions over ordered/partitioned row sets.

Supported functions
-------------------
ranking:
    row_number    — unique sequential integer per partition, ties broken by sort order
    rank          — rank with gaps (1, 1, 3 …)
    dense_rank    — rank without gaps (1, 1, 2 …)

offset:
    lag           — value of `field` from n rows before in the partition (default n=1)
    lead          — value of `field` from n rows after  in the partition (default n=1)

Request structure
-----------------
    zData:
        action:       window
        model:        @.models...
        function:     row_number          # required
        field:        score               # required for lag/lead; ignored for ranking
        offset:       1                   # row offset for lag/lead (default 1)
        partition_by: country             # optional column to group within
        order_by:     score DESC          # sort within partition
        alias:        rank                # name for the computed column (default: function name)
        where:        score > 80          # optional pre-filter on source rows
        fields:       [name, country, score, rank]   # output projection incl. alias
        limit:        20

All source rows are kept (no collapsing). The computed column is appended to
each row dict, then optional field projection is applied.
"""

from typing import Any, Dict, List, Optional
from ..chunk_bridge import chunking_active, live_read

# ─── module constants ──────────────────────────────────────────────────────────
_LOG_WINDOW  = "[zData] window %s() PARTITION BY %s ORDER BY %s → %d rows"
_LOG_CTE     = "[zData] window reading from CTE '%s' (%d rows)"
_ERR_NO_FUNC = "window: `function:` is required (row_number|rank|dense_rank|lag|lead|...)"
_ERR_NO_FLD  = "window: function '%s' requires a `field:` key"
_ERR_UNKNOWN = ("window: unknown function '%s'. Supported: row_number, rank, dense_rank, "
                "percent_rank, cume_dist, ntile, lag, lead, first_value, last_value, "
                "nth_value, sum, avg, count, min, max")

_RANKING_FUNCS = {"row_number", "rank", "dense_rank", "percent_rank", "cume_dist", "ntile"}
_OFFSET_FUNCS  = {"lag", "lead"}
_VALUE_FUNCS   = {"first_value", "last_value", "nth_value"}
_AGG_WIN_FUNCS = {"sum", "avg", "count", "min", "max"}
_ALL_FUNCS     = _RANKING_FUNCS | _OFFSET_FUNCS | _VALUE_FUNCS | _AGG_WIN_FUNCS

# Functions that require a `field:` (count is the only aggregate that does not)
_NEEDS_FIELD   = _OFFSET_FUNCS | _VALUE_FUNCS | (_AGG_WIN_FUNCS - {"count"})


def _num(v: Any) -> Optional[float]:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _parse_frame(raw: Any) -> Optional[tuple]:
    """
    Parse an explicit window frame into (start, end) row offsets.

        ROWS BETWEEN 1 PRECEDING AND CURRENT ROW      → (-1, 0)
        ROWS BETWEEN 2 PRECEDING AND 2 FOLLOWING       → (-2, 2)
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW → (None, 0)
        ROWS BETWEEN CURRENT ROW AND UNBOUNDED FOLLOWING → (0, "INF")

    `None` start → unbounded preceding (partition start); `"INF"` end → unbounded
    following (partition end). Offsets are physical row counts relative to the
    current row (negative = preceding, 0 = current, positive = following).
    Returns None when there is no parseable frame (caller keeps the default frame).
    """
    if not raw:
        return None
    s = str(raw).upper().replace("ROWS", " ").replace("RANGE", " ").strip()
    if s.startswith("BETWEEN"):
        s = s[len("BETWEEN"):].strip()
    if " AND " not in s:
        return None
    lo_raw, hi_raw = [p.strip() for p in s.split(" AND ", 1)]

    def _bound(tok: str):
        tok = tok.strip()
        if tok == "UNBOUNDED PRECEDING":
            return None
        if tok == "UNBOUNDED FOLLOWING":
            return "INF"
        if tok == "CURRENT ROW":
            return 0
        parts = tok.split()
        if len(parts) == 2 and parts[0].lstrip("-").isdigit():
            n = int(parts[0])
            if parts[1] == "PRECEDING":
                return -n
            if parts[1] == "FOLLOWING":
                return n
        return 0

    return (_bound(lo_raw), _bound(hi_raw))


def _agg_over(values: List[Any], fn: str) -> Any:
    """Aggregate a list of raw cell values for an aggregate-window function."""
    if fn == "count":
        return sum(1 for v in values if v is not None)
    present = [v for v in values if v is not None]
    if not present:
        return None
    if fn == "min":
        return min(present)
    if fn == "max":
        return max(present)
    nums = [x for x in (_num(v) for v in present) if x is not None]
    if not nums:
        return None
    if fn == "sum":
        s = sum(nums)
        return int(s) if all(float(x).is_integer() for x in nums) else s
    if fn == "avg":
        return sum(nums) / len(nums)
    return None


# ──────────────────────────────────────────────────────────────────────────────
# Core computation
# ──────────────────────────────────────────────────────────────────────────────

def _apply_window(
    rows: List[Dict],
    function: str,
    field: Optional[str],
    offset: int,
    partition_by: Optional[str],
    order_col: Optional[str],
    order_desc: bool,
    alias: str,
    ntile_buckets: Optional[int] = None,
    frame: Optional[tuple] = None,
) -> List[Dict]:
    """Pure-Python window computation. Mutates copies of rows (does not modify originals)."""
    if not rows:
        return rows

    # Build partition index → list of original positions
    if partition_by:
        partitions: Dict[Any, List[int]] = {}
        for idx, row in enumerate(rows):
            partitions.setdefault(row.get(partition_by), []).append(idx)
    else:
        partitions = {None: list(range(len(rows)))}

    result = [dict(r) for r in rows]

    def _ordval(i):
        return rows[i].get(order_col) if order_col else None

    for _, idxs in partitions.items():
        if order_col:
            idxs = sorted(
                idxs,
                key=lambda i: (rows[i].get(order_col) is None,
                               rows[i].get(order_col, '')),
                reverse=order_desc,
            )

        n = len(idxs)

        if function == "row_number":
            for rn, i in enumerate(idxs, start=1):
                result[i][alias] = rn

        elif function in ("rank", "dense_rank", "percent_rank"):
            prev_val = object()
            prev_rank = 0
            dense = 0
            gap_rank: Dict[int, int] = {}
            for pos, i in enumerate(idxs, start=1):
                cur = _ordval(i)
                if cur != prev_val:
                    prev_rank, prev_val = pos, cur
                    dense += 1
                if function == "dense_rank":
                    result[i][alias] = dense
                elif function == "rank":
                    result[i][alias] = prev_rank
                else:
                    gap_rank[i] = prev_rank
            if function == "percent_rank":
                for i in idxs:
                    result[i][alias] = (gap_rank[i] - 1) / (n - 1) if n > 1 else 0.0

        elif function == "cume_dist":
            pos = 0
            while pos < n:
                j = pos
                cur = _ordval(idxs[pos])
                while j + 1 < n and _ordval(idxs[j + 1]) == cur:
                    j += 1
                cd = (j + 1) / n if n else 0.0
                for k in range(pos, j + 1):
                    result[idxs[k]][alias] = cd
                pos = j + 1

        elif function == "ntile":
            buckets = max(1, int(ntile_buckets or 1))
            base, rem = divmod(n, buckets)
            pos = 0
            for bucket in range(1, buckets + 1):
                size = base + (1 if bucket <= rem else 0)
                for _ in range(size):
                    if pos < n:
                        result[idxs[pos]][alias] = bucket
                        pos += 1

        elif function == "lag":
            for pos, i in enumerate(idxs):
                src = pos - offset
                result[i][alias] = rows[idxs[src]].get(field) if src >= 0 else None

        elif function == "lead":
            for pos, i in enumerate(idxs):
                src = pos + offset
                result[i][alias] = rows[idxs[src]].get(field) if src < n else None

        elif function == "first_value":
            fv = rows[idxs[0]].get(field) if n else None
            for i in idxs:
                result[i][alias] = fv

        elif function == "last_value":
            lv = rows[idxs[-1]].get(field) if n else None
            for i in idxs:
                result[i][alias] = lv

        elif function == "nth_value":
            nv = rows[idxs[offset - 1]].get(field) if 1 <= offset <= n else None
            for i in idxs:
                result[i][alias] = nv

        elif function in _AGG_WIN_FUNCS:
            if frame is not None:
                # Explicit ROWS frame: aggregate a physical window around each row.
                start_b, end_b = frame
                for pos in range(n):
                    lo = 0 if start_b is None else max(0, pos + start_b)
                    hi = n - 1 if end_b == "INF" else min(n - 1, pos + int(end_b))
                    win = [rows[idxs[k]].get(field) for k in range(lo, hi + 1)] if hi >= lo else []
                    result[idxs[pos]][alias] = _agg_over(win, function)
            elif order_col:
                # Cumulative through last peer (SQL default RANGE frame)
                pos = 0
                acc: List[Any] = []
                while pos < n:
                    j = pos
                    cur = _ordval(idxs[pos])
                    while j + 1 < n and _ordval(idxs[j + 1]) == cur:
                        j += 1
                    for k in range(pos, j + 1):
                        acc.append(rows[idxs[k]].get(field))
                    val = _agg_over(acc, function)
                    for k in range(pos, j + 1):
                        result[idxs[k]][alias] = val
                    pos = j + 1
            else:
                val = _agg_over([rows[i].get(field) for i in idxs], function)
                for i in idxs:
                    result[i][alias] = val

    return result


# ──────────────────────────────────────────────────────────────────────────────
# Public handler
# ──────────────────────────────────────────────────────────────────────────────

def handle_window(request: Dict[str, Any], ops: Any) -> Any:
    """
    Execute a WINDOW operation: fetch rows, append a computed analytic column,
    and display the result as a zTable.

    During a chunked render the zTable push is handled identically to
    handle_read — wrapped in live_read() so the contract buffers it.
    """
    # ── 0. Optional CTE source ─────────────────────────────────────────────────
    from .crud_read import _execute_with_block, _apply_cte_filters

    cte_rows: Optional[List[Dict]] = None
    with_block = request.get('with')
    cte_from   = request.get('from')

    if isinstance(with_block, dict):
        cte_context = _execute_with_block(with_block, ops)
        if cte_from and cte_from in cte_context:
            cte_rows = list(cte_context[cte_from])
            ops.logger.info(_LOG_CTE, cte_from, len(cte_rows))

    # ── 1. Resolve function & parameters ───────────────────────────────────────
    function = str(request.get('function', '')).lower().strip()
    if not function:
        ops.logger.error(_ERR_NO_FUNC)
        return False

    # Support inline arg notation: "lag(score, 2)"
    field_arg: Optional[str] = None
    offset_arg: int = 1
    if '(' in function:
        fname, rest = function.split('(', 1)
        function = fname.strip()
        args = [a.strip().rstrip(')') for a in rest.split(',')]
        if args:
            field_arg = args[0] or None
        if len(args) > 1:
            try:
                offset_arg = int(args[1])
            except ValueError:
                pass

    if function not in _ALL_FUNCS:
        ops.logger.error(_ERR_UNKNOWN, function)
        return False

    field      = field_arg or request.get('field')
    row_offset = int(request.get('offset', offset_arg))
    alias      = request.get('alias') or function
    partition  = request.get('partition_by')
    order_raw  = request.get('order_by') or request.get('order')
    fields_out = request.get('fields')
    limit_raw  = request.get('limit')
    silent     = request.get('silent', False)
    frame      = _parse_frame(request.get('frame'))

    # ntile(N): N arrives as the inline arg or `buckets`/`n` — never a field
    ntile_buckets: Optional[int] = None
    if function == "ntile":
        cand = field_arg or request.get('buckets') or request.get('n') or request.get('offset')
        try:
            ntile_buckets = int(cand)
        except (TypeError, ValueError):
            ntile_buckets = 1
        field = None

    if function in _NEEDS_FIELD and not field:
        ops.logger.error(_ERR_NO_FLD, function)
        return False

    order_col, order_desc = None, False
    if order_raw:
        parts = str(order_raw).strip().split()
        order_col = parts[0]
        order_desc = len(parts) > 1 and parts[1].upper() == 'DESC'

    # ── 2. Fetch rows ───────────────────────────────────────────────────────────
    if cte_rows is not None:
        # CTE rows: apply any where filter in-memory
        where_raw = request.get('where')
        if where_raw:
            rows = _apply_cte_filters(
                cte_rows, where_raw=where_raw,
                fields=None, order=None, limit=None, offset=0, distinct=False,
            )
        else:
            rows = list(cte_rows)
    else:
        # Adapter read — pass through all relevant keys, strip window-specific ones
        _WINDOW_KEYS = {'function', 'field', 'offset', 'alias',
                        'partition_by', 'action', 'with', 'from', 'frame', 'buckets'}
        inner = {k: v for k, v in request.items() if k not in _WINDOW_KEYS}
        from .crud_read import handle_read
        rows = handle_read({**inner, 'silent': True}, ops) or []

    if not isinstance(rows, list):
        rows = []

    # ── 3. Compute window ───────────────────────────────────────────────────────
    rows = _apply_window(rows, function, field, row_offset,
                         partition, order_col, order_desc, alias,
                         ntile_buckets=ntile_buckets, frame=frame)

    # ── 4. Post-processing ──────────────────────────────────────────────────────
    if fields_out:
        if isinstance(fields_out, str):
            fields_out = [f.strip() for f in fields_out.split(',')]
        rows = [{k: r.get(k) for k in fields_out} for r in rows]

    if limit_raw:
        rows = rows[:int(limit_raw)]

    ops.logger.info(_LOG_WINDOW, function, partition or '*', order_raw or '-', len(rows))

    # ── 5. Return early for sub-calls ──────────────────────────────────────────
    if silent:
        return rows

    # ── 6. Display as zTable (mirrors crud_read Phase 6 exactly) ───────────────
    table_label = (cte_from or request.get('table') or
                   str(request.get('model', '')).split('.')[-1])
    columns = list(rows[0].keys()) if rows else []

    with live_read(ops.zos):
        if rows:
            ops.display.zTable(table_label, columns, rows)
        else:
            ops.logger.info("[zData] window %s() → 0 rows", function)
            if chunking_active(ops.zos):
                ops.display.zTable(table_label, [], [])

    return rows
