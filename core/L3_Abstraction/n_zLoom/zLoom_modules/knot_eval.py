# zOS/core/L3_Abstraction/n_zLoom/zLoom_modules/knot_eval.py
"""
zLoom KNOT evaluation — the SSOT for a computed value (jinja `{{ a+b }}` / ternary).

A **zKnot** ties `%` threads (and literals) into ONE computed value, declaratively —
no infix mini-language, no ``eval`` (zOS is string-first). The IR is a dict keyed by a
single ``z*`` op, mirroring the zGate/zData comparator family:

    {zAdd: [%a, %b, …]}          a + b + …            (also zSub / zMul / zDiv)
    {zJoin: [Hi , %name]}        string concat (jinja `~`); optional ``sep:``
    {zIf: <zGate predicate>,     value chosen by a condition —
     then: X, else: Y}           the CONDITION delegates to zos.zgate.evaluate (SSOT)

Reuse, not reinvention:
  • operands resolve through ``zos.zloom.resolve_value`` (the token SSOT) — a ``%token``,
    a literal (number / string / bool), or a NESTED knot dict.
  • ``zIf`` conditions resolve through ``zos.zgate.evaluate`` (the gate SSOT) — zKnot does
    only the SELECTION, never comparison/logic.

Fails **safe + visible**: a bad op, a non-numeric operand, div-by-zero, or a missing
branch → ``None`` (the caller leaves the slot empty/literal — never a crash, never a
silently wrong number). Pure functions (need only ``zos`` + optional context), so the
facade path and any boot-time fallback can never diverge.
"""

from zOS import Any

# The recognized knot ops. ``zKnot`` is the authored wrapper / element-child key.
_ARITH = ("zAdd", "zSub", "zMul", "zDiv")
KNOT_OPS = frozenset(_ARITH + ("zJoin", "zIf"))


def is_op_ir(node: Any) -> bool:
    """True when ``node`` is a BARE op IR dict (``{zAdd: […]}`` / ``{zIf: …}``) — the
    value form authored in a non-auto-multiline slot (e.g. ``label: {zAdd: [%a, %b]}``)."""
    return isinstance(node, dict) and any(op in node for op in KNOT_OPS)


def is_knot(node: Any) -> bool:
    """True when ``node`` evaluates as a knot — a bare op IR or a ``{zKnot: …}`` wrapper."""
    return isinstance(node, dict) and (is_op_ir(node) or "zKnot" in node)


def evaluate_knot(ir: Any, zos: Any, context: Any = None) -> Any:
    """Evaluate a knot IR → scalar, or ``None`` on any unresolvable/invalid input."""
    if not isinstance(ir, dict):
        # A bare operand (token / literal) — resolve it directly.
        return _operand(ir, zos, context)
    if "zKnot" in ir:                       # authored wrapper — unwrap once
        return evaluate_knot(ir["zKnot"], zos, context)
    if "zIf" in ir:
        return _eval_if(ir, zos, context)
    for op in _ARITH:
        if op in ir:
            return _eval_arith(op, ir[op], zos, context)
    if "zJoin" in ir:
        return _eval_join(ir, zos, context)
    return None                              # unknown op → fail safe


def _operand(node: Any, zos: Any, context: Any) -> Any:
    """Resolve one operand: nested knot → recurse; ``%token`` → token SSOT; else literal."""
    if is_knot(node):
        return evaluate_knot(node, zos, context)
    if isinstance(node, str) and node.startswith("%"):
        zloom = getattr(zos, "zloom", None)
        resolve = getattr(zloom, "resolve_value", None) if zloom is not None else None
        if resolve is None:
            return None
        try:
            return resolve(node, context)
        except Exception:  # pylint: disable=broad-except
            return None
    return node                              # literal: number / string / bool


def _to_num(v: Any) -> Any:
    """Coerce to int/float for arithmetic; ``None`` if not numeric (bool is NOT a number)."""
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, str):
        s = v.strip()
        try:
            return int(s)
        except ValueError:
            try:
                return float(s)
            except ValueError:
                return None
    return None


def _clean(x: Any) -> Any:
    """Collapse an integral float to int (so ``3 * 3`` renders ``9``, not ``9.0``)."""
    if isinstance(x, float) and x.is_integer():
        return int(x)
    return x


def _eval_arith(op: Any, operands: Any, zos: Any, context: Any) -> Any:
    """Fold an arithmetic op over a list of operands. Any non-numeric / div-by-zero → None."""
    if not isinstance(operands, list) or not operands:
        return None
    nums = [_to_num(_operand(o, zos, context)) for o in operands]
    if any(n is None for n in nums):
        return None
    acc = nums[0]
    for n in nums[1:]:
        if op == "zAdd":
            acc = acc + n
        elif op == "zSub":
            acc = acc - n
        elif op == "zMul":
            acc = acc * n
        elif op == "zDiv":
            if n == 0:
                return None
            acc = acc / n
    return _clean(acc)


def _eval_join(ir: Any, zos: Any, context: Any) -> Any:
    """Concatenate operands as strings (jinja `~`). Optional ``sep:``; None operand → ''."""
    operands = ir.get("zJoin")
    if not isinstance(operands, list):
        return None
    sep = ir.get("sep", "")
    sep = sep if isinstance(sep, str) else ""
    parts = []
    for o in operands:
        val = _operand(o, zos, context)
        parts.append("" if val is None else str(val))
    return sep.join(parts)


def _eval_if(ir: Any, zos: Any, context: Any) -> Any:
    """Ternary: pick ``then``/``else`` by a zGate predicate. Condition → zos.zgate (SSOT)."""
    zgate = getattr(zos, "zgate", None)
    if zgate is None or not hasattr(zgate, "evaluate"):
        return None
    try:
        granted, _reason = zgate.evaluate(ir.get("zIf"), context)
    except Exception:  # pylint: disable=broad-except
        return None
    branch = "then" if granted else "else"
    if branch not in ir:
        return None
    return _operand(ir[branch], zos, context)
