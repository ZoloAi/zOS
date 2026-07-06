# zOS/core/L3_Abstraction/m_zData/zData_modules/shared/operations/agg_set.py
"""
SET operation handler — UNION ALL / UNION / INTERSECT / EXCEPT.

All four operations combine two or more `queries` (each resolved via ops.select)
into a single result set, following standard SQL semantics:

    UNION ALL  — concatenate all rows, keep duplicates
    UNION      — concatenate all rows, remove duplicates (all columns)
    INTERSECT  — rows that appear in every operand
    EXCEPT     — rows in the first operand not in any subsequent operand

SQL column-alignment rules (mirrored exactly):
    - All operands must produce the same column COUNT.
    - Output column names are taken from the FIRST operand (SQL standard).
    - Column order must be consistent across operands.
    - If counts differ, an early error is raised.

Request structure
-----------------
    zData:
        action:  set
        type:    union_all        # union_all | union | intersect | except
        queries:
          - {model: @.models...demo_read,   where: score zAbove 90,  fields: [name, country, score]}
          - {model: @.models...demo_read,   where: country = Italy,  fields: [name, country, score]}
        limit:   20               # optional post-operation limit

Each query entry supports all keys accepted by action: read
(model, table, where, fields, order, limit, distinct, with, from).
"""

from typing import Any, Dict, List, Optional
import pandas as pd
from ..chunk_bridge import chunking_active, live_read

# ─── constants ─────────────────────────────────────────────────────────────────
_VALID_TYPES   = {"union_all", "union", "intersect", "except"}
_LOG_SET       = "[zData] set:%s %d operand(s) → %d rows"
_ERR_NO_TYPE   = "set: `type:` is required (union_all|union|intersect|except)"
_ERR_BAD_TYPE  = "set: unknown type '%s'. Supported: union_all, union, intersect, except"
_ERR_NO_QUERIES = "set: `queries:` must be a non-empty list of at least 1 query dict"
_ERR_COL_COUNT = "set: column count mismatch — operand %d returned %d column(s), expected %d from operand 1"


# ──────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────────────────────────

def _resolve_query(q: Dict[str, Any], ops: Any) -> List[Dict]:
    """Execute a single query entry via handle_read (silent) and return rows."""
    from .crud_read import handle_read
    rows = handle_read({**q, 'silent': True}, ops)
    return rows if isinstance(rows, list) else []


def _rows_to_df(rows: List[Dict], columns: List[str]) -> pd.DataFrame:
    """Convert rows to a DataFrame with columns renamed to the reference column set."""
    if not rows:
        return pd.DataFrame(columns=columns)
    df = pd.DataFrame(rows)
    # Rename columns positionally to the reference names (SQL standard)
    df.columns = columns[:len(df.columns)]
    return df


# ──────────────────────────────────────────────────────────────────────────────
# Core computation
# ──────────────────────────────────────────────────────────────────────────────

def _apply_set(
    frames: List[pd.DataFrame],
    set_type: str,
    ref_columns: List[str],
    logger: Any,
) -> List[Dict]:
    """
    Apply the set operation across the list of DataFrames.
    All frames already have columns renamed to ref_columns.
    """
    if not frames:
        return []

    if set_type == "union_all":
        result = pd.concat(frames, ignore_index=True)

    elif set_type == "union":
        result = pd.concat(frames, ignore_index=True).drop_duplicates()

    elif set_type == "intersect":
        result = frames[0]
        for other in frames[1:]:
            result = pd.merge(result, other, how='inner', on=ref_columns).drop_duplicates()

    elif set_type == "except":
        result = frames[0]
        for other in frames[1:]:
            merged = result.merge(other, how='left', on=ref_columns, indicator=True)
            result = merged[merged['_merge'] == 'left_only'].drop(columns=['_merge'])
            result = result.drop_duplicates()

    else:
        return []

    result = result.reset_index(drop=True)
    return result.to_dict(orient='records')


# ──────────────────────────────────────────────────────────────────────────────
# Public handler
# ──────────────────────────────────────────────────────────────────────────────

def handle_set(request: Dict[str, Any], ops: Any) -> Any:
    """
    Execute a SET operation (union_all|union|intersect|except) across N queries
    and display the result as a zTable.

    During a chunked render the zTable push is handled identically to
    handle_read — wrapped in live_read() so the contract buffers it.
    """
    # ── 0. Validate type ───────────────────────────────────────────────────────
    set_type = str(request.get('type', '')).lower().strip()
    if not set_type:
        ops.logger.error(_ERR_NO_TYPE)
        return False
    if set_type not in _VALID_TYPES:
        ops.logger.error(_ERR_BAD_TYPE, set_type)
        return False

    # ── 1. Validate queries list (support list OR ordered dict-of-dicts) ──────
    queries_raw = request.get('queries')
    if isinstance(queries_raw, dict):
        # dict-of-dicts: {q1: {...}, q2: {...}} → ordered list of dicts
        queries = list(queries_raw.values())
    elif isinstance(queries_raw, list):
        queries = queries_raw
    else:
        queries = None

    if not queries or len(queries) < 1:
        ops.logger.error(_ERR_NO_QUERIES)
        return False

    # ── 2. Resolve each operand ────────────────────────────────────────────────
    operand_rows: List[List[Dict]] = []
    for i, q in enumerate(queries):
        if not isinstance(q, dict):
            ops.logger.error("set: queries[%d] must be a dict", i)
            return False
        rows = _resolve_query(q, ops)
        operand_rows.append(rows)

    # ── 3. Column alignment validation (SQL standard) ─────────────────────────
    # Reference columns = first operand that produced at least one row,
    # falling back to first operand's declared `fields:` if empty.
    ref_columns: Optional[List[str]] = None
    for i, rows in enumerate(operand_rows):
        if rows:
            ref_columns = list(rows[0].keys())
            break

    if ref_columns is None:
        # All operands empty — still validate declared fields if present
        first_fields = queries[0].get('fields')
        ref_columns = (
            [f.strip() for f in first_fields.split(',')]
            if isinstance(first_fields, str)
            else list(first_fields)
            if isinstance(first_fields, list)
            else []
        )

    ref_count = len(ref_columns)

    for i, rows in enumerate(operand_rows):
        if not rows:
            continue
        col_count = len(rows[0])
        if col_count != ref_count:
            ops.logger.error(_ERR_COL_COUNT, i + 1, col_count, ref_count)
            ops.display.error(
                _ERR_COL_COUNT % (i + 1, col_count, ref_count)
            )
            return False

    # ── 4. Build DataFrames ────────────────────────────────────────────────────
    frames = [_rows_to_df(rows, ref_columns) for rows in operand_rows]

    # ── 5. Apply set operation ─────────────────────────────────────────────────
    rows = _apply_set(frames, set_type, ref_columns, ops.logger)

    # ── 6. Optional post-operation limit ──────────────────────────────────────
    limit_raw = request.get('limit')
    if limit_raw:
        rows = rows[:int(limit_raw)]

    ops.logger.info(_LOG_SET, set_type, len(queries), len(rows))

    # ── 7. Return early for sub-calls ─────────────────────────────────────────
    if request.get('silent'):
        return rows

    # ── 8. Display as zTable (mirrors crud_read Phase 6 exactly) ──────────────
    label = str(request.get('model', queries[0].get('model', 'set_result'))).split('.')[-1]
    columns = list(rows[0].keys()) if rows else ref_columns

    with live_read(ops.zos):
        if rows:
            ops.display.zTable(label, columns, rows)
        else:
            ops.logger.info("[zData] set:%s → 0 rows", set_type)
            if chunking_active(ops.zos):
                ops.display.zTable(label, [], [])

    return rows
