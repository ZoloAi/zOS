# zOS/core/L3_Abstraction/n_zLoom/zLoom_modules/token_resolver.py
"""
zLoom token/value resolution — the SSOT for every ``%token``.

Phase 1 (zLoom subsystem): this module unifies token resolution that used to be
split between zParser (render strings, with a BROKEN flat ``%session`` lookup) and
zDispatch's resolver (WHERE clauses + gates, with correct deep-nav). There is now
ONE navigator (``deep_nav``) and ONE per-namespace contract, used by:

  • render string interpolation      → ``resolve_token_string`` (zParser delegates here)
  • scalar gate/value resolution     → ``resolve_token_value``   (zRBAC gates, zList src)
  • WHERE-clause interpolation        → ``deep_nav`` via QueryOps._interpolate_session_values

Namespaces (string-first; a non-``%`` value passes through):
    %session.<a.b.c>   deep-nav the live zSession root      (was flat → now fixed)
    %zloom.<a.b.c>     deep-nav the live zSession root      (attribute-agnostic alias)
    %auth.<field>      zSession["zVisitor"][field], gated by `authenticated`
    %data.<a.b.c>      deep-nav resolved data (context["_resolved_data"] or the
                       CLI panel stash session["_current_block_data"])
    %route.<name>      zSession["zRoute"][name] — dynamic-route params (zLoom-owned,
                       request-scoped; fed by zServer via zos.zloom.set_route_params)
    %item[.<field>]    current loop row — top of context[LOOP_FRAME_KEY] (render-scoped,
                       LoopOps-owned; NOT session). Outside a loop → None.
    %<var>[.<field>]   zSession["zVars"][var] (+ optional deep-nav)

Pure functions: they need only ``zos.session`` (+ optional context), so they work
identically whether called through the ``zos.zloom`` facade or as a boot-time
fallback before the facade is attached — the two paths can never diverge.
"""

from zOS import re, Any

from zOS.zVocabulary import SESSION_KEY_ZROUTE

from .dye_ops import DYES, apply_dyes

# Render-scoped loop-frame stack key (lives in the render ``context``, NEVER in
# session). A ``zShuttle``/``zList`` pushes the current row here per iteration; the
# ``%item`` namespace reads the TOP of the stack. A list = stack so nested loops work
# (a shuttle inside a shuttle). Written by LoopOps (the loop owner), read here — the
# resolver never mutates it. Kept off ``session`` because a row cursor must not outlive
# its render (contrast %route, which is request-scoped and DOES live in session).
LOOP_FRAME_KEY = "_loom_loop"

# Pattern: %namespace(.segment)* — namespace is an identifier; each dotted
# segment is an identifier OR a numeric list index. A single-char field
# (%item.x) and a leading index (%data.0) are both valid (was broken: the old
# field group required 2+ chars and an alpha first char).
_VAR_PATTERN = re.compile(r'%([a-zA-Z_][a-zA-Z0-9_]*)(?:\.([a-zA-Z0-9_]+(?:\.[a-zA-Z0-9_]+)*))?')

# Same token, plus an optional trailing zDye chain (``| name`` / ``| name(arg)``,
# repeated). DISPLAY ONLY — decisions (resolve_token_value) never run dyes, so the
# chain lives on its own pattern rather than on the shared _VAR_PATTERN.
#
# The chain matches ONLY KNOWN dye names (built from the registry, longest-first so
# e.g. `truncate` wins over any prefix). This is deliberate: a literal ``| word`` in
# prose right after a token is left as plain text, never silently consumed — an
# unknown name is a visible typo, not eaten content. `\b` stops `title` matching
# `titlecase`.
_DYE_NAMES = "|".join(sorted((re.escape(n) for n in DYES), key=len, reverse=True))
_DYE_PATTERN = re.compile(
    r'%([a-zA-Z_][a-zA-Z0-9_]*)(?:\.([a-zA-Z0-9_]+(?:\.[a-zA-Z0-9_]+)*))?'
    r'((?:\s*\|\s*(?:' + _DYE_NAMES + r')\b(?:\([^)]*\))?)*)'
)


def deep_nav(root: Any, dotted: Any) -> Any:
    """The ONE navigator: walk ``root`` by a dotted path → value or None.

    Dict segments read by key; list segments read by integer index. Any missing
    or non-traversable segment yields None (secure default: a gate fails closed,
    a render collapses to empty — never leaks a sibling value). This single
    primitive backs render tokens, gate values, and WHERE interpolation so their
    semantics cannot drift apart (the Phase-1 SSOT fix).
    """
    node = root
    if node is None:
        return None
    # An auto_join read (18_data_advanced.md "columns") returns rows whose keys are
    # table-qualified LITERALS ("Posts.title"), not nested dicts — a bare %item.title
    # would otherwise require every caller to know a row came from a join. At EVERY
    # dict hop, try the whole remaining path as one literal key first (not just the
    # top level — a joined row can sit one level deep, e.g. a limit-1 spool unwrap:
    # %data.subs_sel_row.zSubscriptions.plan). A plain (non-joined) dict is
    # exceedingly unlikely to also carry a literal dotted key, so this never shadows
    # genuine nested access below.
    parts = str(dotted).split(".")
    for i, part in enumerate(parts):
        if isinstance(node, dict):
            remaining = ".".join(parts[i:])
            if remaining in node:
                return node[remaining]
            node = node.get(part)
        elif isinstance(node, list) and part.isdigit():
            idx = int(part)
            node = node[idx] if 0 <= idx < len(node) else None
        else:
            return None
    return node


def _session(zos: Any) -> Any:
    return zos.session if hasattr(zos, "session") else {}


def _lookup(namespace: Any, field_path: Any, session: Any, context: Any = None) -> Any:
    """The ONE namespace lookup: (namespace, field_path) → raw value or None.

    Shared by both entry points so a token means the SAME thing whether it is
    interpolated into a render string or resolved for a gate/WHERE/zList source
    (DRY/SSOT). Container-vs-scalar and miss handling are the CALLER's job —
    this only navigates.

        session / zloom → the live zSession root (deep-nav; bare → the root dict)
        auth            → zSession["zVisitor"], gated by `authenticated`
        data            → resolved block data (context or the CLI panel stash)
        route           → zSession["zRoute"] — request-scoped dynamic-route params
        item            → top of context[LOOP_FRAME_KEY] — render-scoped loop row
        <var>           → zSession["zVars"][name]
    """
    sess = session if isinstance(session, dict) else {}

    if namespace in ("session", "zloom"):
        return deep_nav(sess, field_path) if field_path else sess

    if namespace == "auth":
        visitor = sess.get("zVisitor", {})
        if not (isinstance(visitor, dict) and visitor.get("authenticated")):
            return None
        return deep_nav(visitor, field_path) if field_path else visitor

    if namespace == "data":
        resolved = None
        if context and "_resolved_data" in context:
            resolved = context["_resolved_data"]
        else:
            resolved = sess.get("_current_block_data")
        if resolved is None:
            return None
        return deep_nav(resolved, field_path) if field_path else resolved

    if namespace == "route":
        # Request-scoped dynamic-route params, OWNED by zLoom (RouteOps store),
        # NOT the zVars bag. Kept separate so a URL segment can never collide with
        # a durable user var. %route → the whole param dict; %route.<name> → one.
        rparams = sess.get(SESSION_KEY_ZROUTE, {})
        if not isinstance(rparams, dict):
            return None
        return deep_nav(rparams, field_path) if field_path else rparams

    if namespace == "item":
        # Loop row cursor — the current row inside a zShuttle/zList, read off the TOP
        # of the render-scoped loop-frame stack (context, never session). %item → the
        # whole row; %item.<field> → one field. OUTSIDE a loop → None (no stack frame):
        # fails closed like any miss, and can never pick up a stale session value (the
        # zVars["item"] transitional fallback was cut at P3 — the stack is the sole home).
        if isinstance(context, dict):
            stack = context.get(LOOP_FRAME_KEY)
            if isinstance(stack, list) and stack and isinstance(stack[-1], dict):
                frame = stack[-1]
                return deep_nav(frame, field_path) if field_path else frame
        return None

    # %<var> or %<var>.<field> — DURABLE user/app vars ONLY. Route params live
    # exclusively under %route.* (see the `route` namespace above); a bare name never
    # reaches into the route store (the P2 transitional net was cut at P4).
    zvars = sess.get("zVars", {})
    if not isinstance(zvars, dict) or namespace not in zvars:
        return None
    base = zvars[namespace]
    return deep_nav(base, field_path) if field_path else base


def resolve_token_value(expr: Any, zos: Any, context: Any = None) -> Any:
    """Resolve a SINGLE ``%token`` to its raw VALUE (or None on miss).

    Used where a DECISION needs the real value, not display text — zRBAC gates,
    zList source lookups, WHERE clauses. Containers pass through unchanged (a
    zList source IS a list); missing → None (fail closed).
    """
    if not isinstance(expr, str) or not expr.startswith("%"):
        return expr
    body = expr[1:]
    namespace, field_path = body.split(".", 1) if "." in body else (body, None)
    return _lookup(namespace, field_path, _session(zos), context)


def resolve_whole_token(value: Any, zos: Any, context: Any = None) -> "tuple[bool, Any]":
    """Whole-value token resolution → ``(is_whole, raw)`` — types survive.

    ``is_whole`` is True only when the ENTIRE string is one ``%token`` (an
    optional trailing zDye chain allowed). ``raw`` is the post-dye value —
    which may be None on a miss/null. The MISS POLICY is the caller's: display
    surfaces keep the literal token (debuggable), STRUCTURAL positions — a
    dialog field's ``options:``/``readonly:``/``default:``, a baked loop row —
    take the raw value so a list stays a list and False stays falsy (the
    str()-flattening in resolve_token_string is a DISPLAY contract only; it is
    what turned ``readonly: %target_locked`` into the truthy string "False"
    and shipped ``options: %data.names`` as a literal — zOS#92 / zOS#57).
    """
    if not isinstance(value, str):
        return False, None
    match = _DYE_PATTERN.fullmatch(value.strip())
    if not match:
        return False, None
    raw = _lookup(match.group(1), match.group(2), _session(zos), context)
    raw = apply_dyes(raw, match.group(3))
    return True, raw


def resolve_token_string(value: Any, zos: Any, context: Any = None) -> str:
    """Interpolate every ``%token`` inside a render string → resolved string.

    zParser delegates here. ONE display contract for every namespace: a token
    renders ONLY if it resolves to a scalar (str / number / bool). A miss, a
    None, or a container (dict/list) is left as its LITERAL token — visible and
    debuggable, and a bare ``%session`` can never dump the live session into the
    page. (Containers belong to decisions, not display — see resolve_token_value.)

    An optional trailing ``| dye`` chain (zDye) runs BETWEEN the raw lookup and
    the scalar rule, so ``default`` can rescue a miss before it falls to literal.
    """
    if not isinstance(value, str) or not zos or not hasattr(zos, "session"):
        return value
    session = zos.session

    def replace_variable(match):
        val = _lookup(match.group(1), match.group(2), session, context)
        val = apply_dyes(val, match.group(3))  # zDye chain (no-op if absent)
        # bool is an int subclass → renders as "True"/"False"; that's intended.
        if isinstance(val, (str, int, float)):
            return str(val)
        return match.group(0)  # miss / None / container → keep the literal token

    return _DYE_PATTERN.sub(replace_variable, value)
