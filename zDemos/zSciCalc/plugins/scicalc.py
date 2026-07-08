"""scicalc — evaluates one math expression per call (Python/math syntax).

No session, no server-side state: each call is a pure (expr) -> result. The
zCLI wizard types the expression directly; the Bifrost keypad (scicalc.js)
builds the SAME string client-side and drops it into the SAME input field —
one evaluator, no client-side math.
"""

import ast
import math
import operator as _op

from zos_plugin import zfunc

_BIN_OPS = {
    ast.Add: _op.add,
    ast.Sub: _op.sub,
    ast.Mult: _op.mul,
    ast.Div: _op.truediv,
    ast.Pow: _op.pow,
    ast.Mod: _op.mod,
    ast.FloorDiv: _op.floordiv,
}
_UNARY_OPS = {
    ast.UAdd: _op.pos,
    ast.USub: _op.neg,
}
_FUNCS = {
    "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "asin": math.asin, "acos": math.acos, "atan": math.atan,
    "sqrt": math.sqrt, "log": math.log, "log10": math.log10,
    "exp": math.exp, "abs": abs, "round": round,
    "factorial": math.factorial,
}
_CONSTS = {"pi": math.pi, "e": math.e}


def _eval_node(node):
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError(f"unsupported literal: {node.value!r}")
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
        return _BIN_OPS[type(node.op)](_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return _UNARY_OPS[type(node.op)](_eval_node(node.operand))
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in _FUNCS:
            raise ValueError("unsupported function call")
        args = [_eval_node(a) for a in node.args]
        return _FUNCS[node.func.id](*args)
    if isinstance(node, ast.Name):
        if node.id in _CONSTS:
            return _CONSTS[node.id]
        raise ValueError(f"unknown name: {node.id}")
    raise ValueError(f"unsupported expression: {ast.dump(node)}")


def _safe_eval(expr: str):
    parsed = ast.parse(expr, mode="eval")
    return _eval_node(parsed.body)


def _fmt(n):
    if isinstance(n, float) and n == int(n) and abs(n) < 1e15:
        return str(int(n))
    return str(n)


@zfunc
def evaluate(expr):
    expr = (expr or "").strip()
    if not expr:
        return "Nothing to evaluate"
    try:
        result = _safe_eval(expr)
    except ZeroDivisionError:
        return "Error: division by zero"
    except Exception as exc:  # pylint: disable=broad-except
        return f"Error: {exc}"
    return f"{expr} = {_fmt(result)}"
