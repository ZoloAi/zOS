# zOS/core/L3_Abstraction/m_zData/zData_modules/shared/operations/view_resolver.py
"""
zData Views — resolve a saved declarative read into a live read request.

A *view* is an ordinary schema entry that carries a ``view:`` block instead of
``fields:``. It is a read given a name — nothing more. When any read targets a
view name, the pipeline swaps the name for the saved spec and re-enters itself,
so a view rides the exact same JOIN / WHERE / ORDER / LIMIT machinery every
backend already shares. Views are therefore backend-agnostic by construction:
CSV, SQLite and Postgres all resolve them the identical way, because resolution
happens in the zOS layer, above the adapter.

Two kinds:

  * **virtual** — the default. The spec is re-resolved on every read, so it
    always reflects the current base rows. Substitute-and-recurse.
  * **materialized** — ``view: {materialized: true, into: <table>}``. The spec's
    rows are stored in a normally-declared backing table (``into:``); a read of
    the view simply reads that table, and a ``refresh`` recomputes it. Fast to
    read, stale until refreshed — the classic trade.

Composition: a caller may layer extra ``where`` / ``fields`` / ``order`` /
``limit`` / ``offset`` on top of a view. WHERE is AND-merged at the dict level
(reusing the same merge shape as zFilters); projection/order/paging override.

Nesting: a view's ``tables:`` may name another view — resolution recurses,
guarded by a per-request chain (cycle → error) and a hard depth cap.
"""

from zOS import Any, Dict, List, Optional

try:  # pragma: no cover - import shim (package vs flat)
    from ..validators.constants import SCHEMA_KEY_VIEW
except ImportError:  # pragma: no cover
    from validators.constants import SCHEMA_KEY_VIEW  # type: ignore

# ── view-control keys (stripped before the spec becomes a read request) ──────
_VIEW_KEY_MATERIALIZED = "materialized"
_VIEW_KEY_INTO = "into"
_VIEW_CONTROL_KEYS = {_VIEW_KEY_MATERIALIZED, _VIEW_KEY_INTO}

# ── request-scoped bookkeeping for nesting / cycles ──────────────────────────
_CHAIN_KEY = "_view_chain"
_MAX_VIEW_DEPTH = 10

# ── keys a caller may compose on top of a view ───────────────────────────────
_COMPOSE_OVERRIDE_KEYS = ("fields", "order", "limit", "offset", "distinct")

_LOG_CYCLE = "[view] cycle detected resolving '%s' (chain: %s) — refusing to loop"
_LOG_DEPTH = "[view] view nesting deeper than %d resolving '%s' — aborting"
_LOG_WHERE_UNMERGEABLE = (
    "[view] could not compose caller WHERE onto view '%s' — using the view's own "
    "WHERE only (caller filter ignored; use a dict WHERE to compose)"
)


def is_view(schema: Any, name: Any) -> bool:
    """True when ``name`` is a schema entry carrying a ``view:`` block."""
    if not isinstance(schema, dict) or not isinstance(name, str):
        return False
    entry = schema.get(name)
    return isinstance(entry, dict) and SCHEMA_KEY_VIEW in entry


def view_block(schema: Dict[str, Any], name: str) -> Dict[str, Any]:
    """Return the ``view:`` block for ``name`` (assumes ``is_view`` is True)."""
    block = schema[name][SCHEMA_KEY_VIEW]
    return dict(block) if isinstance(block, dict) else {}


def is_materialized(schema: Any, name: Any) -> bool:
    """True when ``name`` is a materialized view (has a backing table)."""
    if not is_view(schema, name):
        return False
    return bool(view_block(schema, name).get(_VIEW_KEY_MATERIALIZED))


def backing_table(schema: Dict[str, Any], name: str) -> str:
    """Backing table for a materialized view — ``into:`` or the view name."""
    return view_block(schema, name).get(_VIEW_KEY_INTO, name)


def _compose_where(base_where: Any, caller_where: Any, ops: Any, name: str) -> Any:
    """AND-merge a caller WHERE onto the view's own WHERE (dict level)."""
    if caller_where is None:
        return base_where
    if base_where is None:
        return caller_where

    def _as_dict(w: Any) -> Optional[Dict[str, Any]]:
        if isinstance(w, dict):
            return w
        if isinstance(w, str):
            try:  # parse a longhand string into the dict WHERE shape
                try:
                    from ..parsers.where_parser import parse_where_clause
                except ImportError:  # pragma: no cover
                    from parsers.where_parser import parse_where_clause  # type: ignore
                parsed = parse_where_clause(w)
                return parsed if isinstance(parsed, dict) else None
            except Exception:  # pylint: disable=broad-except
                return None
        return None

    base_d, caller_d = _as_dict(base_where), _as_dict(caller_where)
    if isinstance(base_d, dict) and isinstance(caller_d, dict):
        merged = dict(base_d)
        for col, cond in caller_d.items():
            if col in merged and isinstance(merged[col], dict) and isinstance(cond, dict):
                merged[col] = {**merged[col], **cond}
            else:
                merged[col] = cond
        return merged

    # Cannot safely AND two opaque string WHEREs — keep the view's, warn once.
    if getattr(ops, "logger", None):
        ops.logger.warning(_LOG_WHERE_UNMERGEABLE, name)
    return base_where


def resolve_view_read(name: str, request: Dict[str, Any], ops: Any) -> Optional[Dict[str, Any]]:
    """
    Build the read request that a view name stands for.

    * virtual → the saved spec (control keys stripped) with the caller's
      WHERE AND-merged and projection/order/paging layered on top.
    * materialized → a plain read of the backing table, same composition.

    Returns the merged request dict, or ``None`` on a cycle / depth breach
    (logged) so the caller can fail the read cleanly.
    """
    schema = getattr(ops, "schema", {}) or {}

    # cycle + depth guard, threaded through the request chain
    chain: List[str] = list(request.get(_CHAIN_KEY, []) or [])
    if name in chain:
        if getattr(ops, "logger", None):
            ops.logger.error(_LOG_CYCLE, name, " → ".join(chain + [name]))
        return None
    if len(chain) >= _MAX_VIEW_DEPTH:
        if getattr(ops, "logger", None):
            ops.logger.error(_LOG_DEPTH, _MAX_VIEW_DEPTH, name)
        return None
    chain = chain + [name]

    block = view_block(schema, name)

    if block.get(_VIEW_KEY_MATERIALIZED):
        base: Dict[str, Any] = {"table": backing_table(schema, name)}
        base_where: Any = None
    else:
        base = {k: v for k, v in block.items() if k not in _VIEW_CONTROL_KEYS}
        base_where = base.pop("where", None)

    merged: Dict[str, Any] = dict(base)
    merged[_CHAIN_KEY] = chain

    # carry mode-affecting flags from the caller so silent reads stay silent
    for flag in ("silent",):
        if request.get(flag) is not None:
            merged[flag] = request[flag]

    composed_where = _compose_where(base_where, request.get("where"), ops, name)
    if composed_where is not None:
        merged["where"] = composed_where

    for key in _COMPOSE_OVERRIDE_KEYS:
        if request.get(key) is not None:
            merged[key] = request[key]

    return merged


def view_read_spec(schema: Dict[str, Any], name: str) -> Dict[str, Any]:
    """
    The bare read spec for a view (control keys stripped) — used by ``refresh``
    to recompute a materialized view's rows via a silent read.
    """
    block = view_block(schema, name)
    return {k: v for k, v in block.items() if k not in _VIEW_CONTROL_KEYS}
