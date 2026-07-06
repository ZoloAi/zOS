"""
Operator vocabulary — Single Source of Truth for WHERE/filter evaluation.

A single declarative WHERE IR (MongoDB-style ``{field: {"$op": value}}``) is
consumed by three independent evaluators that target different engines:

    * in-memory   — operations.helpers._evaluate_ir   (pure-Python row test)
    * pandas/CSV  — backends.csv_helpers.where_filtering (boolean mask)
    * SQL         — backends.sql_adapter               (parameterized SQL)

Historically each evaluator defined its own operator tokens with inconsistent
casing (``$gt`` vs ``$GT``) and only matched one form. That silently broke
cross-backend parity — e.g. a ``zAbove`` filter (which emits ``$GT``) was
ignored by the lowercase-only in-memory evaluator and degraded to ``=`` by the
SQL operator map. This module is the one place that defines the operator
vocabulary and a normalizer so every evaluator agrees on the same tokens.

The module has NO intra-package imports by design (pure constants + a function)
so it can be imported from parsers, backends and operations without any cycle.
"""

# ── Canonical operator tokens (MongoDB-style, lowercase, ``$``-prefixed) ─────
OP_EQ = "$eq"
OP_NE = "$ne"
OP_GT = "$gt"
OP_GTE = "$gte"
OP_LT = "$lt"
OP_LTE = "$lte"
OP_LIKE = "$like"
OP_NOTLIKE = "$notlike"
OP_IN = "$in"
OP_NIN = "$nin"
OP_BETWEEN = "$between"
OP_NOTBETWEEN = "$notbetween"
OP_NULL = "$null"
OP_NOTNULL = "$notnull"

# Logical operators
OP_AND = "$and"
OP_OR = "$or"

# Set of all canonical tokens (lowercase) for membership tests.
_CANONICAL = frozenset({
    OP_EQ, OP_NE, OP_GT, OP_GTE, OP_LT, OP_LTE,
    OP_LIKE, OP_NOTLIKE, OP_IN, OP_NIN,
    OP_BETWEEN, OP_NOTBETWEEN, OP_NULL, OP_NOTNULL,
    OP_AND, OP_OR,
})

# Symbolic aliases (SQL-style comparison glyphs) → canonical token.
_SYMBOLIC = {
    "=": OP_EQ,
    "==": OP_EQ,
    "!=": OP_NE,
    "<>": OP_NE,
    ">": OP_GT,
    ">=": OP_GTE,
    "<": OP_LT,
    "<=": OP_LTE,
}


def normalize_operator(op):
    """Return the canonical token for any operator spelling.

    Accepts the canonical form (``$gt``), any casing (``$GT``, ``$Gt``), the
    bare/un-prefixed form (``gt`` / ``GT``) and symbolic aliases (``>``, ``>=``,
    ``!=`` …). Non-string or unrecognized operators are returned lower-cased so
    callers can still match/log them deterministically.
    """
    if not isinstance(op, str):
        return op
    if op in _SYMBOLIC:
        return _SYMBOLIC[op]
    low = op.lower()
    if low in _CANONICAL:
        return low
    if not low.startswith("$"):
        prefixed = "$" + low
        if prefixed in _CANONICAL:
            return prefixed
    return low
