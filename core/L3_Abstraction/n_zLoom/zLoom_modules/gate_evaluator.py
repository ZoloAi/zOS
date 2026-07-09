# zOS/core/L3_Abstraction/n_zLoom/zLoom_modules/gate_evaluator.py
"""zGate — the one predicate evaluator (the decision engine behind zos.zgate).

A **gate** is a yes/no question asked before a block renders or an action runs:
"is the visitor signed in?", "are they an admin?", "is the cart over $100?".
Historically those questions were asked in three unrelated dialects (``zRBAC:`` for
auth, ``if:`` strings in the wizard, ``zAbove``/``zBelow`` in zData). This module is
the single place that answers ALL of them, so every gate in zOS speaks one grammar
and returns one contract: ``(granted, reason)`` — ``reason`` is ``None`` when
granted, else a short human-readable denial for audit/UX.

Reuse, don't rewrite (the whole point):
  * AUTH questions delegate to ``zos.auth.check_zrbac`` — the untouched SSOT for
    "signed in / has role / has attribute". We never reimplement auth here.
  * VALUE questions (``%data.cart.total``) resolve through ``zos.zloom.resolve_value``
    — the same navigator render strings and WHERE clauses use.
  * COMPARATORS reuse zData's authored vocabulary (``zAbove``/``zBelow``/``zIN``/
    ``zBetween``/``zNull``) so a gate reads like a WHERE clause.

The only *new* grammar is the combinators (``zAll``/``zAny``; ``zNot`` already
exists in zData). Everything else is a word zOS authors already know.

TRUST INVARIANT (do not violate): zGate NEVER decides trust inline. Every
``authed``/``role``/``require`` predicate is delegated to ``check_zrbac``, which owns
the zGuard seam (identity/ownership/watermark live in the private wheel). This module
holds no secrets and makes no identity decision of its own — that is exactly why it
is safe to live in the public runtime. Comparisons are for BUSINESS values (cart
total, tier), not trust facts. Fail closed: any malformed gate, missing resolver, or
errored auth → denied.
"""

from zOS import Any

# ── Vocabulary ───────────────────────────────────────────────────────────────
# Combinator keys: a dict with exactly one of these IS a combinator node.
_COMBINATORS = ("zAll", "zAny", "zNot")

# Auth keys → mapped into a zRBAC block and answered by check_zrbac. The lean
# authored word is ``authed``; the rest are the legacy zRBAC spellings, accepted
# so lowered blocks and hand-written zRBAC both flow through unchanged.
_AUTH_AUTHED = "authed"          # authed: true/false  → authenticated alias
_AUTH_ROLE = "role"              # role: admin         → require_role
_AUTH_REQUIRE = "require"        # require: {attr: v}   → require (attribute gate)
_AUTH_LEGACY = ("authenticated", "require_auth", "require_role", "zGuest")

# Comparator tokens (reused verbatim from zData's WHERE vocabulary).
_CMP_ABOVE = "zAbove"      # actual >  operand   (numeric)
_CMP_BELOW = "zBelow"      # actual <  operand   (numeric)
_CMP_IN = "zIN"            # actual in operand   (membership)
_CMP_BETWEEN = "zBetween"  # min <= actual <= max ([lo, hi])
_CMP_NULL = "zNull"        # actual is None (zNull: true) / not None (zNull: false)
_CMP_SET = "zSet"          # actual is present & non-empty & not false-ish (truthy)
_CMP_NOTSET = "zNotSet"    # complement of zSet


# ── Public entry ─────────────────────────────────────────────────────────────
def evaluate_gate(predicate: Any, zos: Any, context: Any = None):
    """Answer a zGate predicate → ``(granted: bool, reason: str | None)``.

    ``predicate`` shapes:
      * ``None`` / empty        → open gate → ``(True, None)``
      * ``list``                → implicit ``zAll`` (every item must pass)
      * ``{zAll: [...]}``       → AND    (deny reason = first failing child)
      * ``{zAny: [...]}``       → OR     (grant if any child passes)
      * ``{zNot: {...}}``       → negate a child
      * leaf ``{...}``          → one or more conditions AND'd:
          - ``authed`` / ``role`` / ``require`` / legacy zRBAC keys → auth
          - bare word key (``plan: pro``)                          → attribute gate
          - ``%token: expected`` (scalar)                          → equality
          - ``%token: {zAbove: n}`` (dict)                         → comparator
    """
    if predicate is None or predicate == "" or predicate == {} or predicate == []:
        return True, None

    if isinstance(predicate, list):
        return _eval_all(predicate, zos, context)

    if not isinstance(predicate, dict):
        return False, f"zGate: malformed predicate ({type(predicate).__name__})"

    # Combinator node — exactly one combinator key owns the dict.
    combinator = [k for k in _COMBINATORS if k in predicate]
    if combinator:
        if len(combinator) > 1 or len(predicate) > 1:
            return False, "zGate: a combinator node takes exactly one key"
        key = combinator[0]
        if key == "zAll":
            return _eval_all(predicate[key], zos, context)
        if key == "zAny":
            return _eval_any(predicate[key], zos, context)
        return _eval_not(predicate[key], zos, context)

    # Leaf node — AND across every condition key.
    return _eval_leaf(predicate, zos, context)


# ── Combinators ──────────────────────────────────────────────────────────────
def _as_children(node: Any):
    """A combinator body may be a list of predicates or a single predicate."""
    if isinstance(node, list):
        return node
    return [node]


def _eval_all(node: Any, zos: Any, context: Any):
    for child in _as_children(node):
        granted, reason = evaluate_gate(child, zos, context)
        if not granted:
            return False, reason  # short-circuit: first denial wins
    return True, None


def _eval_any(node: Any, zos: Any, context: Any):
    children = _as_children(node)
    if not children:
        return True, None  # empty zAny is vacuously open (matches empty-gate rule)
    last_reason = None
    for child in children:
        granted, reason = evaluate_gate(child, zos, context)
        if granted:
            return True, None
        last_reason = reason
    return False, last_reason or "zGate: no zAny branch matched"


def _eval_not(node: Any, zos: Any, context: Any):
    granted, _reason = evaluate_gate(node, zos, context)
    if granted:
        return False, "zGate: zNot condition matched"
    return True, None


# ── Leaf: auth + comparisons, AND'd ──────────────────────────────────────────
def _eval_leaf(predicate: Any, zos: Any, context: Any):
    """Split leaf keys into an auth block (→ check_zrbac) and value comparisons.

    Auth and attribute keys are folded into ONE zRBAC-shaped block so a single
    ``check_zrbac`` call answers them together (matching its short-circuit order).
    ``%token`` keys are compared against resolved live values. All AND together.
    """
    rbac_block: dict = {}
    require_map: dict = {}
    comparisons = []

    for key, value in predicate.items():
        skey = str(key)
        if key == _AUTH_AUTHED:
            rbac_block["authenticated"] = value           # true→require_auth, false→zGuest
        elif key == _AUTH_ROLE:
            rbac_block["require_role"] = value
        elif key in _AUTH_LEGACY:
            rbac_block[skey] = value
        elif key == _AUTH_REQUIRE and isinstance(value, dict):
            require_map.update(value)
        elif skey.startswith("%"):
            comparisons.append((skey, value))
        else:
            require_map[skey] = value                      # bare attr → attribute gate

    if require_map:
        merged = dict(rbac_block.get("require", {}))
        merged.update(require_map)
        rbac_block["require"] = merged

    # Auth verdict first (cheap, session-only, reuses the SSOT).
    if rbac_block:
        granted, reason = _delegate_auth(rbac_block, zos)
        if not granted:
            return False, reason

    # Then value comparisons.
    for token, expected in comparisons:
        granted, reason = _eval_comparison(token, expected, zos, context)
        if not granted:
            return False, reason

    return True, None


def _delegate_auth(rbac_block: Any, zos: Any):
    """Reuse the auth SSOT. Never reimplement auth/role logic here (trust invariant)."""
    auth = getattr(zos, "auth", None)
    check = getattr(auth, "check_zrbac", None) if auth is not None else None
    if check is None:
        return False, "zGate: auth engine unavailable"
    try:
        granted, reason = check(rbac_block)
        return bool(granted), reason
    except Exception:  # pylint: disable=broad-except
        return False, "zGate: auth check errored"


# ── Value comparisons (reuse zData comparator vocabulary) ────────────────────
def _eval_comparison(token: Any, expected: Any, zos: Any, context: Any):
    """Resolve a ``%token`` to its live value and test it against ``expected``."""
    zloom = getattr(zos, "zloom", None)
    resolve = getattr(zloom, "resolve_value", None) if zloom is not None else None
    if resolve is None:
        return False, "zGate: value resolver unavailable"
    try:
        actual = resolve(token, context)
    except Exception:  # pylint: disable=broad-except
        return False, f"zGate: could not resolve {token}"

    # Unary value operator in bare-string position: ``%token: zSet`` / ``zNotSet``
    # (the clean truthiness sugar — "is this field filled in?"). Checked against
    # the RAW expected (never a resolvable token — an authored literal sentinel).
    if isinstance(expected, str) and expected in (_CMP_SET, _CMP_NOTSET):
        ok = _is_set(actual) if expected == _CMP_SET else not _is_set(actual)
        if ok:
            return True, None
        state = "unset" if expected == _CMP_SET else "set"
        return False, f"zGate: {token} is {state}"

    # A per-row ownership check ("only the row's own author") needs BOTH sides
    # live — ``%item.Posts.author_id: %session.zVisitor.id`` — so the RHS
    # resolves through the same navigator as the LHS token whenever it is
    # itself a ``%token`` string (an authored literal like ``zAdmin`` never
    # starts with ``%``, so this can't shadow an ordinary fixed-value gate).
    expected = _resolve_if_token(expected, resolve, context)

    if isinstance(expected, dict):
        for op, operand in expected.items():
            operand = _resolve_if_token(operand, resolve, context)
            if not _apply_op(actual, op, operand):
                return False, f"zGate: {token} failed {op}"
        return True, None

    # Bare scalar → equality (string-coerced, list = membership).
    if _eq(actual, expected):
        return True, None
    return False, f"zGate: {token} != {expected!r}"


def _resolve_if_token(value: Any, resolve: Any, context: Any) -> Any:
    """Resolve ``value`` through the same navigator as the gate's LHS token,
    but only when it actually IS one (a bare ``%...`` string) — anything else
    (a literal, a comparator dict's static operand) passes through unchanged."""
    if isinstance(value, str) and value.startswith("%"):
        try:
            return resolve(value, context)
        except Exception:  # pylint: disable=broad-except
            return value
    return value


def _apply_op(actual: Any, op: Any, operand: Any) -> bool:
    if op == _CMP_ABOVE:
        return _num(actual) is not None and _num(operand) is not None and _num(actual) > _num(operand)
    if op == _CMP_BELOW:
        return _num(actual) is not None and _num(operand) is not None and _num(actual) < _num(operand)
    if op == _CMP_IN:
        pool = operand if isinstance(operand, (list, tuple, set)) else [operand]
        return any(_eq(actual, item) for item in pool)
    if op == _CMP_BETWEEN:
        if not isinstance(operand, (list, tuple)) or len(operand) != 2:
            return False
        a, lo, hi = _num(actual), _num(operand[0]), _num(operand[1])
        return None not in (a, lo, hi) and lo <= a <= hi
    if op == _CMP_NULL:
        want_null = _truthy(operand)
        return (actual is None) if want_null else (actual is not None)
    if op == _CMP_SET:
        return _is_set(actual) if _truthy(operand) else not _is_set(actual)
    if op == _CMP_NOTSET:
        return not _is_set(actual) if _truthy(operand) else _is_set(actual)
    return False  # unknown operator → fail closed


# ── Small helpers (fail-safe coercions) ──────────────────────────────────────
def _num(v: Any):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        try:
            return float(v.strip())
        except (TypeError, ValueError):
            return None
    return None


def _truthy(v: Any) -> bool:
    if isinstance(v, str):
        return v.strip().lower() in ("true", "1", "yes")
    return bool(v)


def _is_set(actual: Any) -> bool:
    """Is a live value 'filled in'? Present, non-empty, and not a false-ish string.

    This is the zGate truthiness contract for ``zSet`` — the wizard checkbox/answer
    sense of "did they provide this?". None → unset; empty string/collection →
    unset; the strings ``false``/``0``/``no`` → unset; everything else → set.
    """
    if actual is None:
        return False
    if isinstance(actual, bool):
        return actual
    if isinstance(actual, str):
        s = actual.strip()
        return bool(s) and s.lower() not in ("false", "0", "no")
    if isinstance(actual, (list, tuple, set, dict)):
        return len(actual) > 0
    return bool(actual)


def _eq(actual: Any, expected: Any) -> bool:
    """Equality that survives type drift: a resolved ``"5"`` matches ``5``, and a
    list actual matches by membership (mirrors zRBAC's ``_attr_match``)."""
    if isinstance(actual, (list, tuple, set)):
        return any(_eq(item, expected) for item in actual)
    if actual == expected:
        return True
    return str(actual) == str(expected)
