# zOS/core/L3_Abstraction/m_zData/zData_modules/shared/operations/crud_set_expr.py
"""
Computed / relative SET — the ``SET x = x + 1`` shape for zData writes.

A plain SET writes a literal to every matching row. A *computed* SET derives each
row's new value from that row's own columns — counters, decays, cross-column math,
or a value pulled from a joined row:

    action: update
    table: members
    set:
      score: {$inc: 1}              # score = score + 1
      credits: {$dec: %cost}        # credits = credits - <that row's cost>
      streak: {zExpr: streak + 1}   # general arithmetic over the row's columns
      total: {zExpr: price * qty}   # cross-column
    where: {active: true}

Two spellings, both adapter-agnostic:

  • terse operators — ``{$inc: n}`` / ``{$dec: n}`` / ``{$mul: n}`` / ``{$div: n}``
    operate on the SET field itself; the operand is a number, a ``%col`` (same row),
    or (in UPDATE … FROM) a ``%table.col`` from the joined row.
  • general expression — ``{zExpr: "..."}`` evaluated over the row's columns by bare
    name (plus non-colliding joined columns in the FROM path). Only arithmetic is
    allowed — parsed with ``ast``, never ``eval`` — so no code can run here.

SSOT design: there is no per-row SQL arithmetic. The value is computed in Python
from rows the read engine already returned, then written as a normal literal — so
CSV, SQLite and Postgres share one code path (see crud_update_cond / crud_update_join).
"""

import ast
import operator

__all__ = ["is_computed", "has_computed_set", "resolve_set_value"]

# Terse counter operators → the binary op applied to (current_field_value, operand).
_INC_OPS = {
    "$inc": operator.add,
    "$dec": operator.sub,
    "$mul": operator.mul,
    "$div": operator.truediv,
}

# Arithmetic-only AST node whitelist for the zExpr evaluator.
_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPS = {ast.USub: operator.neg, ast.UAdd: operator.pos}

_ZEXPR = "zExpr"


def _num(x):
    """Coerce a cell to a number for arithmetic (CSV stores everything as text)."""
    if isinstance(x, bool) or isinstance(x, (int, float)):
        return x
    if isinstance(x, str):
        s = x.strip()
        try:
            return int(s)
        except ValueError:
            try:
                return float(s)
            except ValueError:
                return x
    return x


def is_computed(spec):
    """True when a SET value is a computed spec (``$inc``-family or ``zExpr``)."""
    return isinstance(spec, dict) and (_ZEXPR in spec or any(k in _INC_OPS for k in spec))


def has_computed_set(container):
    """True when any field in the SET container carries a computed spec."""
    return isinstance(container, dict) and any(is_computed(v) for v in container.values())


def _resolve_operand(val, row, b_row, a_table, b_table):
    """A ``$inc`` operand: number, ``%col`` (same row) or ``%table.col`` (joined row)."""
    if isinstance(val, str) and val.startswith("%"):
        part = val[1:]
        if "." in part:
            tbl, _, col = part.partition(".")
            if b_row is not None and tbl == b_table:
                return b_row.get(col)
            return row.get(col)
        return row.get(part)
    return val


def _eval_node(node, names):
    if isinstance(node, ast.Expression):
        return _eval_node(node.body, names)
    if isinstance(node, ast.Constant):          # numbers / booleans
        return node.value
    if isinstance(node, ast.Name):              # a bare column reference
        return _num(names.get(node.id, 0))
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
        return _BIN_OPS[type(node.op)](_eval_node(node.left, names), _eval_node(node.right, names))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return _UNARY_OPS[type(node.op)](_eval_node(node.operand, names))
    raise ValueError(f"zExpr: unsupported expression element: {ast.dump(node)}")


def _eval_expr(expr, names):
    return _eval_node(ast.parse(str(expr), mode="eval"), names)


def resolve_set_value(field, spec, row, b_row=None, a_table=None, b_table=None):
    """
    Resolve one computed SET value against ``row`` (and an optional joined ``b_row``).

    ``field`` is the target column — it is the implicit operand for the ``$inc`` family
    (``score: {$inc: 1}`` → ``score + 1``). Non-computed specs are returned unchanged.
    """
    if not is_computed(spec):
        return spec

    if _ZEXPR in spec:
        names = {}
        if b_row:
            names.update(b_row)
        names.update(row)                       # A wins on name collision
        return _eval_expr(spec[_ZEXPR], names)

    op_key = next(k for k in spec if k in _INC_OPS)
    base = _num(row.get(field, 0))
    operand = _num(_resolve_operand(spec[op_key], row, b_row, a_table, b_table))
    return _INC_OPS[op_key](base, operand)
