"""
SSOT for FK auto-join policy — shared by EVERY zData backend adapter.

`auto_join` on a read block accepts:
    - ``True``            → enabled, default join type (LEFT — preserves base rows)
    - ``False`` / ``None`` / ""  → disabled
    - a type string       → enabled with that type: ``left`` | ``right`` | ``inner`` | ``full``

Why LEFT is the default: a schema-declared FK auto-join is "give me these rows
*and* their related record". INNER silently drops any base row whose FK is null
or orphaned (e.g. a member with no team vanishes) — surprising. LEFT preserves
the base table, which is the industry norm for eager FK fetch. For a required +
valid FK, LEFT and INNER return the same rows, so the default is low-risk.

This module owns the default, the accepted tokens, and the per-backend rendering
(SQL keyword vs pandas merge ``how``). Adapters never hardcode a join type — they
resolve through here, so CSV, SQLite, PostgreSQL (and any future backend) cannot
drift.

Note: RIGHT / FULL OUTER are valid SQL but require SQLite >= 3.39; LEFT (default)
and INNER work everywhere. pandas (csv) supports all four.
"""

from typing import Any, Optional, Tuple

__all__ = [
    "DEFAULT_AUTO_JOIN",
    "resolve_auto_join",
    "normalize_join_type",
    "to_sql_keyword",
    "to_pandas_how",
]

# FK auto-join preserves the base table's rows by default.
DEFAULT_AUTO_JOIN = "LEFT"

# canonical type → (SQL keyword, pandas merge "how")
_JOIN_TYPES = {
    "INNER": ("INNER JOIN", "inner"),
    "LEFT": ("LEFT JOIN", "left"),
    "RIGHT": ("RIGHT JOIN", "right"),
    "FULL": ("FULL OUTER JOIN", "outer"),
}

_TRUE_TOKENS = {"true", "yes", "on"}
_FALSE_TOKENS = {"false", "no", "off", "none", ""}


def normalize_join_type(value: Any, default: str = DEFAULT_AUTO_JOIN) -> str:
    """Canonicalise a join-type token (case/synonym-insensitive). Unknown → default."""
    if not isinstance(value, str):
        return default
    key = value.strip().upper()
    if key in ("FULL OUTER", "OUTER"):
        key = "FULL"
    return key if key in _JOIN_TYPES else default


def resolve_auto_join(value: Any) -> Tuple[bool, Optional[str]]:
    """Map a read block's ``auto_join`` value to ``(enabled, canonical_join_type)``.

    ``False`` / ``None`` / falsy → ``(False, None)``; ``True`` → ``(True, DEFAULT)``;
    a type string → ``(True, normalized)``; the strings "false"/"off"/… → disabled.
    """
    if value is True:
        return True, DEFAULT_AUTO_JOIN
    if not value:
        return False, None
    if isinstance(value, str):
        token = value.strip().lower()
        if token in _FALSE_TOKENS:
            return False, None
        if token in _TRUE_TOKENS:
            return True, DEFAULT_AUTO_JOIN
        return True, normalize_join_type(value)
    # any other truthy value → enabled with the safe default
    return True, DEFAULT_AUTO_JOIN


def to_sql_keyword(join_type: str) -> str:
    """Canonical join type → SQL keyword (e.g. ``LEFT`` → ``LEFT JOIN``)."""
    return _JOIN_TYPES[normalize_join_type(join_type)][0]


def to_pandas_how(join_type: str) -> str:
    """Canonical join type → pandas ``merge(how=...)`` (e.g. ``FULL`` → ``outer``)."""
    return _JOIN_TYPES[normalize_join_type(join_type)][1]
