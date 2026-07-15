# zOS/core/L3_Abstraction/m_zData/zData_modules/shared/operations/request_extract.py
"""
Request-shape extraction for zData operations.

Extracted from ``operations/helpers.py`` (grab-bag decomposition). These three
functions turn a raw request dict — which may arrive in YAML (declarative) or
shell (imperative) shape — into the pieces every CRUD/DDL operation needs:

    extract_table_from_request(request, operation_name, ops, check_exists=True)
        3-tier fallback (tables → table → model tail) + optional existence check.
    extract_where_clause(request, ops, warn_if_missing=False)
        Dual-source (top-level / options) WHERE, quote-stripped and parsed.
    extract_field_values(request, operation_name, ops)
        Field/value pairs from options, with reserved control-keys filtered out
        and values type-coerced via ``parse_value``.

``helpers.py`` re-exports all three so existing
``from .helpers import extract_table_from_request`` call sites keep working.
"""

from zSys.errors import DatabaseNotInitializedError
from zOS import Any, Dict, Optional, Tuple
from ..parsers import parse_where_clause, parse_value
from ..data_keys import (
    KEY_TABLE, KEY_TABLES, KEY_MODEL, KEY_WHERE, KEY_OPTIONS,
    KEY_LIMIT, KEY_ORDER, KEY_OFFSET, KEY_JOINS,
)

__all__ = [
    "extract_table_from_request",
    "extract_where_clause",
    "extract_field_values",
]

# ── Request keys (SSOT: shared/data_keys) ────────────────────────────────────
_KEY_TABLES = KEY_TABLES
_KEY_TABLE = KEY_TABLE
_KEY_MODEL = KEY_MODEL
_KEY_WHERE = KEY_WHERE
_KEY_OPTIONS = KEY_OPTIONS

# ── Reserved options (filtered from field extraction) — same SSOT keys ────────
_RESERVED_MODEL = KEY_MODEL
_RESERVED_LIMIT = KEY_LIMIT
_RESERVED_WHERE = KEY_WHERE
_RESERVED_ORDER = KEY_ORDER
_RESERVED_OFFSET = KEY_OFFSET
_RESERVED_TABLES = KEY_TABLES
_RESERVED_JOINS = KEY_JOINS

# ── Error / log messages ─────────────────────────────────────────────────────
_ERR_NO_TABLE = "No table specified for %s"
_ERR_TABLE_NOT_EXISTS = "Table '%s' does not exist. Please run 'Setup Database' first to create tables."
_ERR_TABLE_NOT_EXISTS_LOG = "[FAIL] Table '%s' does not exist"
_ERR_NO_FIELDS = "No fields provided for %s. Use --field_name value syntax"
_LOG_WARN_NO_WHERE = "[WARN] No WHERE clause - operation will affect ALL rows!"

# zFilters rule vocabulary (mirror of crud_read._build_where_from_filters).
# A where-dict value that is itself a dict of ONLY these tokens is the authored
# rule dialect, not a literal — it must compile, never compare by equality.
_ZFILTER_RULE_TOKENS = frozenset({
    "zAbove", "zBelow", "zIs", "zIncludes", "zStarts", "zEnds",
    "zIN", "zBetween", "zNull", "zKnown",
})
# Flat unary spellings: `where: {deleted_at: zNull}` — the condensed-doc form.
_ZFILTER_FLAT_TOKENS = frozenset({"zNull", "zKnown"})


def _normalize_rule_dialect(where: Dict[str, Any], ops: Any) -> Dict[str, Any]:
    """Compile zFilters rule entries found inside a ``where:`` dict (zOS#17).

    ``where:`` historically compared dict values by plain equality, so the rule
    dialect (`{deleted_at: {zNull: true}}`) silently matched nothing — while the
    same rules under ``zFilters:`` parsed fine. Every dict WHERE flows through
    here (read/aggregate/window/update/delete all extract via this module), so
    the two spellings now agree:

        {col: {zNull: true}}   → IS NULL          (nested rule dict)
        {col: zNull}           → IS NULL          (flat unary token)
        {col: {zAbove: 5}}     → {col: {"$gt": 5}}

    Anything else — scalars, IN lists, subquery dicts ({zData: ...}), IR dicts
    ({"$gt": ...}) — passes through untouched. Only a dict whose keys are ALL
    recognized rule tokens compiles; a mixed dict is not the dialect.
    """
    out: Dict[str, Any] = {}
    for col, cond in where.items():
        rules = None
        if isinstance(cond, str) and cond in _ZFILTER_FLAT_TOKENS:
            rules = {cond: True}
        elif isinstance(cond, dict) and cond and all(
            k in _ZFILTER_RULE_TOKENS for k in cond
        ):
            rules = cond
        if rules is None:
            out[col] = cond
            continue
        # Deferred import — crud_read imports this module via helpers.
        from .crud_read import _build_where_from_filters  # pylint: disable=import-outside-toplevel
        compiled = _build_where_from_filters({col: rules})
        if col in compiled:
            out[col] = compiled[col]
            if ops and getattr(ops, "logger", None):
                ops.logger.debug(
                    "[zData] where: rule dialect compiled on '%s': %r → %r",
                    col, cond, compiled[col],
                )
        else:
            out[col] = cond
    return out


def extract_table_from_request(
    request: Dict[str, Any],
    operation_name: str,
    ops: Any,
    check_exists: bool = True
) -> Optional[str]:
    """
    Extract and validate table name from request using 3-tier fallback logic.

    3-Tier Fallback Logic:
        1. Check "tables" key (list of table names - preferred format)
        2. Check "table" key (single table name or list - alternate format)
        3. Fallback to "model" key — path tail as last resort

    If ``check_exists`` is True, validates the table exists; if not, displays a
    user-friendly error and raises ``DatabaseNotInitializedError``.

    Returns the extracted table name (first if multiple), or None if none found.
    """
    # ─────────────────────────────────────────────────────────────────────────
    # Phase 1: 3-Tier Fallback - Extract table from request
    # ─────────────────────────────────────────────────────────────────────────

    # Tier 1: Check "tables" key (list of table names - preferred)
    tables = request.get(_KEY_TABLES, [])

    # Tier 2: Check singular "table" parameter (alternate format)
    if not tables:
        table_param = request.get(_KEY_TABLE)
        if table_param:
            if isinstance(table_param, str):
                tables = [table_param]
            elif isinstance(table_param, list):
                tables = table_param

    # Tier 3: Derive table from model path tail as a last resort.
    # Extended paths (e.g. @.models.Demos.zSchema.basic.demo_basic) are resolved
    # upstream — the block is extracted by parse_schema_model_path() and injected
    # as an explicit "table" key (handled by Tier 2 above).
    # If we reach here without a table, the caller used a short model path without
    # an explicit table field — use path tail, which will fail the existence check
    # and surface a clear "Table 'X' does not exist" error.
    if not tables:
        model = request.get(_KEY_MODEL)
        if isinstance(model, str):
            tables = [model.split(".")[-1]]

    # ─────────────────────────────────────────────────────────────────────────
    # Phase 2: Validation - Ensure table was extracted
    # ─────────────────────────────────────────────────────────────────────────
    if not tables:
        ops.logger.error(_ERR_NO_TABLE, operation_name)
        return None

    table = tables[0]  # Use first table if multiple provided

    # ─────────────────────────────────────────────────────────────────────────
    # Phase 3: Existence Check - Verify table exists in database (if requested)
    # ─────────────────────────────────────────────────────────────────────────
    if check_exists and not ops.adapter.table_exists(table):
        ops.logger.error(_ERR_TABLE_NOT_EXISTS_LOG, table)

        # Display user-friendly error first (mode-agnostic via zDisplay)
        ops.display.error(_ERR_TABLE_NOT_EXISTS % table)

        # Then raise actionable exception with hints
        raise DatabaseNotInitializedError(operation=operation_name, table=table)

    return table


def extract_where_clause(
    request: Dict[str, Any],
    ops: Any,
    warn_if_missing: bool = False
) -> Optional[Dict[str, Any]]:
    """
    Extract and parse the WHERE clause using dual-source extraction.

    Sources (top-level "where" wins over options "where"):
        1. {"where": "id > 5"}                (YAML-based)
        2. {"options": {"where": "id > 5"}}   (shell-based)

    Surrounding single/double quotes (a shell artifact) are stripped, and a dict
    WHERE is passed through untouched. When ``warn_if_missing`` is True and no
    WHERE is found, logs a warning (UPDATE/DELETE would affect ALL rows).

    Returns the parsed WHERE dict, or None if absent.
    """
    # ─────────────────────────────────────────────────────────────────────────
    # Phase 1: Dual-Source Extraction - Get WHERE string from request
    # ─────────────────────────────────────────────────────────────────────────

    # Source 1: Check top-level "where" key (YAML-based requests - preferred)
    where_str = request.get(_KEY_WHERE)

    # Source 2: Check options "where" key (shell command requests - fallback)
    if not where_str:
        options = request.get(_KEY_OPTIONS, {})
        where_str = options.get(_KEY_WHERE)

    # ─────────────────────────────────────────────────────────────────────────
    # Phase 2: Dict Passthrough - If already a dict, skip string processing
    # ─────────────────────────────────────────────────────────────────────────
    if where_str and isinstance(where_str, dict):
        # WHERE clause is already in dict format (e.g., from auto-query).
        # Compile any zFilters rule-dialect entries so `where:` and `zFilters:`
        # accept the same vocabulary (zOS#17).
        where = _normalize_rule_dialect(where_str, ops)
    else:
        # ─────────────────────────────────────────────────────────────────────
        # Phase 3: Quote Stripping - Remove surrounding quotes (shell artifact)
        # ─────────────────────────────────────────────────────────────────────
        if where_str:
            where_str = where_str.strip()
            # Strip surrounding quotes (single or double)
            if (where_str.startswith('"') and where_str.endswith('"')) or \
               (where_str.startswith("'") and where_str.endswith("'")):
                where_str = where_str[1:-1]

        # ─────────────────────────────────────────────────────────────────────
        # Phase 4: Parsing - Convert WHERE string to dictionary
        # ─────────────────────────────────────────────────────────────────────
        where = parse_where_clause(where_str) if where_str else None

    # ─────────────────────────────────────────────────────────────────────────
    # Phase 5: Optional Warning - Alert if WHERE clause is missing
    # ─────────────────────────────────────────────────────────────────────────
    if warn_if_missing and not where:
        ops.logger.warning(_LOG_WARN_NO_WHERE)

    return where


def extract_field_values(
    request: Dict[str, Any],
    operation_name: str,
    ops: Any
) -> Tuple[Optional[list], Optional[list]]:
    """
    Extract field/value pairs from request options, filtering reserved keys.

    Reserved control keys (model, limit, where, order, offset, tables, joins) are
    excluded so they are never mistaken for table fields. Remaining values are
    type-coerced via ``parse_value`` ("123" → 123, "true" → True, "None" → None).

    Returns (fields, values), or (None, None) if no fields remain after filtering.
    """
    # ─────────────────────────────────────────────────────────────────────────
    # Phase 1: Extract Options - Get options dictionary from request
    # ─────────────────────────────────────────────────────────────────────────
    options = request.get(_KEY_OPTIONS, {})

    # ─────────────────────────────────────────────────────────────────────────
    # Phase 2: Reserved Options Filtering - Build reserved options set
    # ─────────────────────────────────────────────────────────────────────────
    reserved_options = {
        _RESERVED_MODEL,
        _RESERVED_LIMIT,
        _RESERVED_WHERE,
        _RESERVED_ORDER,
        _RESERVED_OFFSET,
        _RESERVED_TABLES,
        _RESERVED_JOINS
    }

    # ─────────────────────────────────────────────────────────────────────────
    # Phase 3: Field/Value Extraction - Filter out reserved options
    # ─────────────────────────────────────────────────────────────────────────
    fields_dict = {k: v for k, v in options.items() if k not in reserved_options}

    # ─────────────────────────────────────────────────────────────────────────
    # Phase 4: Validation - Ensure at least one field provided
    # ─────────────────────────────────────────────────────────────────────────
    if not fields_dict:
        ops.logger.error(_ERR_NO_FIELDS, operation_name)
        return None, None

    # ─────────────────────────────────────────────────────────────────────────
    # Phase 5: Type Conversion - Parse values to Python types
    # ─────────────────────────────────────────────────────────────────────────
    fields = list(fields_dict.keys())
    values = [parse_value(str(v)) for v in fields_dict.values()]

    return fields, values
