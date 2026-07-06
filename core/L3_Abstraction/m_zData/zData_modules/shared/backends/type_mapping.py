"""
Abstract → SQL type mapping — Single Source of Truth for the SQL adapters.

Every SQL adapter must turn an abstract zSchema field type (``str``, ``int``,
``bool``, ``datetime``, ``json`` …) into a backend column type. Historically each
adapter carried its own copy of this table AND there were two parallel
resolvers — a dict-based ``map_type`` and a ``startswith``-based
``_map_field_type`` — that silently disagreed. In particular the base
``_map_field_type`` short-circuited ``bool``→INTEGER / ``datetime``→TEXT before
the PostgreSQL dict (``bool``→BOOLEAN / ``datetime``→TIMESTAMP) could run, so
Postgres columns were created with the wrong types.

This module is the one place that defines the abstract type vocabulary, the
per-dialect type tables, and a single ``resolve_sql_type`` resolver. Adapters
keep only their dialect table and delegate resolution here.

No intra-package imports by design → safe to import from every adapter.
"""

from typing import Any, Dict, Optional

# Default backend type when an abstract type is unknown / non-string.
SQL_DEFAULT_TYPE = "TEXT"

# Base SQL profile (SQLite / generic-SQL semantics). PostgreSQL overrides the
# deltas below. Keys are the canonical (normalized) abstract type spellings.
_SQL_BASE: Dict[str, str] = {
    "str": "TEXT",
    "string": "TEXT",
    "int": "INTEGER",
    "integer": "INTEGER",
    "float": "REAL",
    "real": "REAL",
    "bool": "INTEGER",
    "boolean": "INTEGER",
    "datetime": "TEXT",
    "date": "TEXT",
    "time": "TEXT",
    "json": "TEXT",
    "blob": "BLOB",
}

# SQLite uses the base profile verbatim.
SQLITE_TYPE_MAP: Dict[str, str] = dict(_SQL_BASE)

# PostgreSQL: native boolean, temporal and JSON/binary types.
POSTGRESQL_TYPE_MAP: Dict[str, str] = {
    **_SQL_BASE,
    "bool": "BOOLEAN",
    "boolean": "BOOLEAN",
    "datetime": "TIMESTAMP",
    "date": "DATE",
    "time": "TIME",
    "json": "JSONB",
    "blob": "BYTEA",
}

# Aliases usable as prefixes for parametrized/compound spellings
# (e.g. "varchar(255)" → str, "int unsigned" → int). Ordered longest-first so
# "integer"/"boolean" win over "int"/"bool" on a prefix match.
_PREFIX_ALIASES = tuple(sorted(
    ("datetime", "boolean", "integer", "string", "float", "real",
     "date", "time", "json", "blob", "bool", "str", "int"),
    key=len, reverse=True,
))


def normalize_abstract_type(abstract_type: Any) -> Optional[str]:
    """Return the canonical spelling of an abstract type, or ``None``.

    Strips surrounding whitespace and trailing required/optional markers
    (``!`` / ``?``) and lower-cases. Non-string input returns ``None`` so the
    caller can apply its default.
    """
    if not isinstance(abstract_type, str):
        return None
    return abstract_type.strip().rstrip("!?").lower()


# Reverse direction: a raw backend column type (from PRAGMA table_info /
# information_schema) → a canonical abstract type. Matched by substring, longest
# discriminators first (so "timestamp" wins over "time", "integer" over "int").
# This is inherently LOSSY — SQLite stores bool AND int as INTEGER, datetime/json
# as TEXT — so introspection alone cannot recover intent. `reconcile_live_types`
# below restores the declared spelling whenever both resolve to the same SQL type.
_SQL_FAMILY_TO_ABSTRACT = (
    ("timestamp", "datetime"),
    ("datetime", "datetime"),
    ("bool", "bool"),
    ("json", "json"),
    ("bytea", "blob"),
    ("blob", "blob"),
    ("serial", "int"),
    ("int", "int"),           # int / integer / bigint / smallint
    ("double", "float"),
    ("real", "float"),
    ("float", "float"),
    ("numeric", "float"),
    ("decimal", "float"),
    ("date", "date"),
    ("time", "time"),
    ("char", "str"),          # char / varchar / character varying
    ("text", "str"),
    ("clob", "str"),
    ("uuid", "str"),
)


def reverse_sql_type(sql_type: Any) -> str:
    """Map a raw backend column type string to a canonical abstract type.

    Lossy by nature (INTEGER↦int even if it was authored as bool) — pair with
    ``reconcile_live_types`` to recover the declared intent. Unknown → ``"str"``.
    """
    if not isinstance(sql_type, str):
        return "str"
    t = sql_type.strip().lower()
    for needle, abstract in _SQL_FAMILY_TO_ABSTRACT:
        if needle in t:
            return abstract
    return "str"


def reconcile_live_types(
    live_cols: Dict[str, Any],
    declared_cols: Dict[str, Any],
    map_type,
) -> Dict[str, Any]:
    """Reconcile introspected columns against the declared schema.

    For each LIVE column, keep the DECLARED abstract spelling when the declared
    type and the live (reverse-mapped) type resolve to the *same* backend SQL type
    — so a lossy family (``bool``↦INTEGER, ``datetime``↦TEXT) never produces a
    phantom "modified" diff. When they resolve differently it's a genuine
    stored-type change, so the live type is kept (diff flags a real MODIFY). A
    column absent from ``declared_cols`` is kept as-is, so the diff can see it as a
    genuine DROP. ``map_type`` is the adapter's abstract→SQL resolver.
    """
    out: Dict[str, Any] = {}
    for col, live_def in live_cols.items():
        live_type = (live_def or {}).get("type", "str")
        decl = declared_cols.get(col) if isinstance(declared_cols, dict) else None
        decl_type = decl.get("type") if isinstance(decl, dict) else None
        if decl_type and map_type(decl_type) == map_type(live_type):
            out[col] = {"type": decl_type}
        else:
            out[col] = {"type": live_type}
    return out


def resolve_sql_type(
    abstract_type: Any,
    type_map: Dict[str, str],
    default: str = SQL_DEFAULT_TYPE,
) -> str:
    """Resolve an abstract type to a backend SQL type using ``type_map``.

    Exact match first, then a longest-prefix fallback for compound spellings
    (``varchar(255)``, ``int unsigned``…), then ``default``. The prefix fallback
    reads the dialect's own table so e.g. ``datetime2`` resolves to TIMESTAMP on
    PostgreSQL rather than degrading to TEXT.
    """
    norm = normalize_abstract_type(abstract_type)
    if norm is None:
        return default
    if norm in type_map:
        return type_map[norm]
    for alias in _PREFIX_ALIASES:
        if norm.startswith(alias) and alias in type_map:
            return type_map[alias]
    return default
