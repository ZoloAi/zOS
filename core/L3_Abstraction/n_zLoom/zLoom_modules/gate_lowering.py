# zOS/core/L3_Abstraction/n_zLoom/zLoom_modules/gate_lowering.py
"""zGate — lowering the old gate surfaces into the one IR.

Before zGate becomes the *authored* verb, it must first prove it can *reproduce*
every verdict the old surfaces already make. That proof is "lowering": take a
``zRBAC:`` block or a wizard ``if:`` string and translate it into a zGate
predicate (the shape ``gate_evaluator.evaluate_gate`` understands). During the
migration the old engines still enforce — the lowered IR is run *alongside* them
and any disagreement is logged (shadow compare).

Two lowerings, two risk levels:

  * ``lower_zrbac`` — mechanical and parity-safe *by construction*. The evaluator
    already delegates auth to ``check_zrbac``, so a lowered block that reconstructs
    the same auth keys must return the identical verdict. This lowering only
    renames legacy keys to the lean vocab (``authenticated``/``require_auth`` →
    ``authed``, ``require_role`` → ``role``); ``require`` passes through.

  * ``lower_if`` — parses the zHat expression with the SAME ``ast`` module the
    wizard uses (so parse behavior can't drift) and rewrites it into IR. zHat
    step-results become ``%zHat.<key>`` value tokens; comparisons map onto zData's
    comparator vocabulary; ``and``/``or``/``not`` map onto ``zAll``/``zAny``/
    ``zNot``. Anything we cannot lower *losslessly* raises ``GateLoweringError``
    rather than guessing. A bare ``zHat[k]`` truthiness test lowers to the ``zSet``
    sugar (present & non-empty & not false-ish) — the wizard checkbox/answer sense
    of "did they fill this in?".
"""

import ast

from zOS import Any


class GateLoweringError(Exception):
    """A construct that cannot be lowered losslessly into the zGate IR yet."""


# ── zRBAC block → lean zGate IR ──────────────────────────────────────────────
def lower_zrbac(block: Any) -> Any:
    """Translate a resolved ``zRBAC`` block into a lean zGate leaf predicate.

    Parity is guaranteed because the evaluator forwards auth keys straight back to
    ``check_zrbac`` — this only renames legacy spellings to the lean vocab so the
    eventual authored surface is tidy. An empty/absent block → open gate (``{}``).
    """
    if not isinstance(block, dict) or not block:
        return {}

    ir: dict = {}

    alias = block.get("authenticated")
    if isinstance(alias, str):
        alias = {"true": True, "false": False}.get(alias.strip().lower())

    if block.get("require_auth") or alias is True:
        ir["authed"] = True
    if block.get("zGuest") or alias is False:
        ir["authed"] = False  # guest-only (a block never sensibly sets both)

    # Deprecated `require_predicate` was never wired — check_zrbac degrades it to
    # require_auth. Mirror that here so the transitional bridge stays faithful (a
    # dropped key would fail OPEN). Authored migration should move to authed/role.
    if block.get("require_predicate") is not None:
        ir["authed"] = True

    role = block.get("require_role")
    if role is not None:
        ir["role"] = role

    require = block.get("require")
    if isinstance(require, dict) and require:
        ir["require"] = dict(require)

    return ir


# ── wizard `if:` string → zGate IR ───────────────────────────────────────────
_ZHAT = "zHat"
_ZHAT_TOKEN = "%zHat."


def lower_if(expression: Any) -> Any:
    """Translate a wizard ``if:`` zHat expression string into a zGate predicate.

    Reuses Python's ``ast`` (eval mode) — identical parsing to the wizard's own
    allowlist interpreter — then rewrites the tree into IR. Raises
    ``GateLoweringError`` for any construct outside the supported subset.
    """
    if not isinstance(expression, str) or not expression.strip():
        raise GateLoweringError("if: expects a non-empty zHat expression string")
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise GateLoweringError(f"if: unparseable ({exc})") from exc
    return _lower_node(tree.body)


def _lower_node(node: ast.AST) -> Any:
    if isinstance(node, ast.BoolOp):
        children = [_lower_node(v) for v in node.values]
        if isinstance(node.op, ast.And):
            return {"zAll": children}
        if isinstance(node.op, ast.Or):
            return {"zAny": children}
        raise GateLoweringError("unsupported boolean operator")

    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return {"zNot": _lower_node(node.operand)}

    if isinstance(node, ast.Compare):
        return _lower_compare(node)

    # Bare ``zHat[k]`` used as a truthiness test → the zSet sugar ("is it filled
    # in?"). zSet is stricter than not-null (empty string / false-ish → unset),
    # which matches the wizard checkbox/answer sense of a bare condition.
    if isinstance(node, ast.Subscript):
        token = _token_from_subscript(node)
        return {token: "zSet"}

    raise GateLoweringError(f"unsupported if: construct ({type(node).__name__})")


def _lower_compare(node: ast.Compare) -> Any:
    if len(node.ops) != 1 or len(node.comparators) != 1:
        raise GateLoweringError("chained comparisons are not supported")

    op = node.ops[0]
    left, right = node.left, node.comparators[0]

    # Normalize to (zHat token) OP (literal). Allow the reversed authoring form
    # (literal OP zHat) by flipping the operator.
    if _is_zhat(left):
        token = _token_from_subscript(left)
        value = _literal(right)
    elif _is_zhat(right):
        token = _token_from_subscript(right)
        value = _literal(left)
        op = _flip(op)
    else:
        raise GateLoweringError("a comparison must reference zHat[...] on one side")

    if isinstance(op, ast.Eq):
        return {token: value}
    if isinstance(op, ast.NotEq):
        return {"zNot": {token: value}}
    if isinstance(op, ast.Lt):
        return {token: {"zBelow": value}}
    if isinstance(op, ast.Gt):
        return {token: {"zAbove": value}}
    if isinstance(op, ast.LtE):
        return {"zNot": {token: {"zAbove": value}}}   # not(> v) == <= v
    if isinstance(op, ast.GtE):
        return {"zNot": {token: {"zBelow": value}}}   # not(< v) == >= v
    if isinstance(op, ast.In):
        return {token: {"zIN": value if isinstance(value, list) else [value]}}
    if isinstance(op, ast.NotIn):
        return {"zNot": {token: {"zIN": value if isinstance(value, list) else [value]}}}
    if isinstance(op, (ast.Is, ast.IsNot)):
        if value is not None:
            raise GateLoweringError("is / is not is only supported against None")
        return {token: {"zNull": isinstance(op, ast.Is)}}

    raise GateLoweringError("unsupported comparison operator")


# ── helpers ──────────────────────────────────────────────────────────────────
def _is_zhat(node: ast.AST) -> bool:
    return isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) \
        and node.value.id == _ZHAT


def _token_from_subscript(node: ast.Subscript) -> str:
    """``zHat[0]`` → ``%zHat.0`` · ``zHat[User_Type]`` → ``%zHat.User_Type``."""
    if not _is_zhat(node):
        raise GateLoweringError("expected a zHat[...] reference")
    index = node.slice
    if isinstance(index, ast.Index):           # py<3.9 shim
        index = index.value                    # type: ignore[attr-defined]
    if isinstance(index, ast.Constant):
        key = index.value
    elif isinstance(index, ast.Name):          # bare name → its own string (wizard convention)
        key = index.id
    else:
        raise GateLoweringError("zHat[...] index must be a literal or a step name")
    return f"{_ZHAT_TOKEN}{key}"


def _literal(node: ast.AST) -> Any:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):             # bare name → its own string (wizard convention)
        return node.id
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return [_literal(elt) for elt in node.elts]
    raise GateLoweringError(f"unsupported literal ({type(node).__name__})")


def _flip(op: ast.AST) -> ast.AST:
    """Flip a comparison operator for the reversed (literal OP zHat) form."""
    return {
        ast.Lt: ast.Gt(), ast.Gt: ast.Lt(),
        ast.LtE: ast.GtE(), ast.GtE: ast.LtE(),
    }.get(type(op), op)   # Eq/NotEq/In/Is are order-preserving here
