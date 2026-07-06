# zOS/core/L3_Abstraction/m_zData/zData_modules/shared/operations/agg_compute.py
"""
Shared, backend-agnostic AGGREGATE computer (SSOT).

Every zData aggregate — count/sum/avg/min/max plus the extended set
(count_distinct, stddev, variance, median, group_concat/string_agg) — is computed
here in pure Python over rows already fetched by ``handle_read``. This is the
single source of truth: csv, sqlite and postgres all flow through the same code,
so a statistic behaves identically regardless of backend (SQLite has no native
STDDEV/MEDIAN; routing through here removes that divergence).

Return contract (mirrors the legacy adapter.aggregate contract exactly):
    - group_by + alias   → list[dict]  e.g. [{country: USA, total: 12}, ...]
    - group_by, no alias → dict         e.g. {USA: 12, IE: 4}  (tuple keys if multi-field)
    - no group_by        → scalar       e.g. 12 / 87.5 / "a, b, c"

Statistical semantics follow PostgreSQL (the high-end target):
    - stddev / variance are SAMPLE (n-1); n < 2 → None  (matches stddev_samp/var_samp)
    - median uses the continuous median (statistics.median)
"""

from typing import Any, Dict, List, Optional
import statistics

# ── Function registry (SSOT for the operation layer) ────────────────────────────
BASE_FUNCS = {"count", "sum", "avg", "min", "max"}
EXT_FUNCS  = {"count_distinct", "stddev", "variance", "median", "group_concat", "string_agg"}
VALID_FUNCS = BASE_FUNCS | EXT_FUNCS

_CONCAT_FUNCS = {"group_concat", "string_agg"}


def _to_numbers(values: List[Any]) -> List[float]:
    """Coerce a list of raw values to floats, dropping anything non-numeric/None."""
    out: List[float] = []
    for v in values:
        if v is None:
            continue
        try:
            out.append(float(v))
        except (TypeError, ValueError):
            continue
    return out


def _unique_preserve(values: List[Any]) -> List[Any]:
    """Deduplicate while preserving first-seen order (DISTINCT semantics)."""
    seen: set = set()
    out: List[Any] = []
    for v in values:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out


def _compute_scalar(
    function: str,
    field: Optional[str],
    rows: List[Dict],
    distinct: bool,
    separator: str,
) -> Any:
    """Compute a single aggregate value over ``rows`` for one (sub)group."""
    fn = function.lower()
    if fn == "count_distinct":
        fn, distinct = "count", True

    # COUNT — the only function that works without a field
    if fn == "count":
        if field:
            vals = [r.get(field) for r in rows if r.get(field) is not None]
            return len(set(vals)) if distinct else len(vals)
        return len(rows)

    # Everything below operates on the field's non-null values
    raw = [r.get(field) for r in rows if r.get(field) is not None]
    if distinct:
        raw = _unique_preserve(raw)

    if fn in _CONCAT_FUNCS:
        return separator.join(str(x) for x in raw)

    if fn == "min":
        return min(raw) if raw else None
    if fn == "max":
        return max(raw) if raw else None

    nums = _to_numbers(raw)
    if not nums:
        return None

    if fn == "sum":
        s = sum(nums)
        return int(s) if all(float(x).is_integer() for x in nums) else s
    if fn == "avg":
        return sum(nums) / len(nums)
    if fn == "median":
        return statistics.median(nums)
    if fn == "stddev":
        return statistics.stdev(nums) if len(nums) > 1 else None
    if fn == "variance":
        return statistics.variance(nums) if len(nums) > 1 else None

    raise ValueError(f"Unsupported aggregate function: {function}")


def compute_aggregate(
    rows: List[Dict],
    function: str,
    field: Optional[str] = None,
    group_by: Optional[Any] = None,
    alias: Optional[str] = None,
    distinct: bool = False,
    separator: str = ", ",
) -> Any:
    """
    Compute an aggregate over already-fetched rows. Backend-agnostic SSOT.

    See module docstring for the return contract.
    """
    if not group_by:
        result = _compute_scalar(function, field, rows, distinct, separator)
        if result is None and function.lower() in ("count", "count_distinct"):
            return 0
        return result

    group_fields = [group_by] if isinstance(group_by, str) else list(group_by)

    # Group rows preserving first-seen key order
    groups: Dict[tuple, List[Dict]] = {}
    order: List[tuple] = []
    for r in rows:
        key = tuple(r.get(g) for g in group_fields)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(r)

    computed = {key: _compute_scalar(function, field, groups[key], distinct, separator)
                for key in order}

    if alias:
        return [
            {**dict(zip(group_fields, key)), alias: val}
            for key, val in computed.items()
        ]

    # No alias → flat dict. Single group field → scalar key; multi → tuple key.
    if len(group_fields) == 1:
        return {key[0]: val for key, val in computed.items()}
    return dict(computed.items())
