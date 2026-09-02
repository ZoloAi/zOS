# zOS/core/L3_Abstraction/n_zLoom/zLoom_modules/shuttle_expand.py
"""zShuttle lowering — the ``{% for %}`` half of zLoom, load-time.

A **zShuttle** weaves one **zPattern** across every row of a list **zSpool** — the
loom's shuttle carrying the weft row by row. It is pure SUGAR: it lowers to the
proven ``zList`` + ``%pattern`` mechanism, then the existing pipeline does the rest
(``component_expand`` fills the pattern at load; ``loop_ops`` copies it per row at
bind, binding ``%item.*``). Nothing new runs at render time.

Grammar
-------
    Grid:
        zShuttle:
            zSpool:   products      # the list source (a spool returning rows)
            zPattern: productCard   # the shape drawn once per row

Lowering (what this module produces, before component expansion)::

    Grid:
        zList:
            source: %data.products
            each:
                %productCard:
                    image:   %item.image     # AUTO-FILLED from the pattern's slots
                    name:    %item.name
                    tagline: %item.tagline
                    price:   %item.price

**Auto-fill** is the point: the pattern's ``%slot`` names are discovered from its
definition and each is fed ``%item.<slot>`` — so the author never repeats the slot
list. Row column names must match the pattern's slot names (fails open + visible
if not — a missing column leaves ``%item.x`` literal at render).

Ordering: runs at the SAME loader seam as ``expand_components``, but FIRST — it emits
a ``%pattern`` invocation which component expansion then resolves. Idempotent + a
no-op when no ``zShuttle`` is present, so it is safe on every load.
"""

from zOS import re, Any, Dict

# a bare pattern slot: %word NOT part of a longer word and NOT a dotted path
# (so render tokens like %item.x / %data.x / %session.x are never mistaken for slots).
_SLOT_PATTERN = re.compile(r"%([A-Za-z_]\w*)(?![\w.])")

_KEY_SHUTTLE = "zShuttle"
_KEY_SPOOL = "zSpool"
_KEY_PATTERN = "zPattern"
_KEY_GATE = "zGate"  # carried through inert; per-row filtering wired in a later phase


def expand_shuttles(tree: Any, zos: Any, registry: Dict[str, Any] = None) -> Any:
    """Lower every ``zShuttle`` in ``tree`` to ``zList`` + a ``%pattern`` invocation.

    ``registry`` is optional (injected for tests); otherwise loaded from
    zLoom/patterns/ (needed to discover the pattern's slot names for auto-fill).
    No shuttle declared → the original tree is returned untouched (fast path).
    """
    if not _has_shuttle(tree):
        return tree
    if registry is None:
        from .component_expand import load_component_registry
        registry = load_component_registry(zos)
    return _lower_node(tree, registry, zos)


def _has_shuttle(node: Any) -> bool:
    """Cheap pre-scan so a shuttle-free load pays nothing but one walk."""
    if isinstance(node, dict):
        if _KEY_SHUTTLE in node:
            return True
        return any(_has_shuttle(v) for v in node.values())
    if isinstance(node, list):
        return any(_has_shuttle(v) for v in node)
    return False


def _lower_node(node: Any, registry: Dict[str, Any], zos: Any) -> Any:
    if isinstance(node, dict):
        out: Dict[str, Any] = {}
        for key, val in node.items():
            if key == _KEY_SHUTTLE and isinstance(val, dict):
                lowered = _lower_shuttle(val, registry, zos)
                if lowered is not None:
                    # Replace zShuttle with the zList form AT ITS OWN POSITION,
                    # under a collision-free key: a sibling authored `zList` on
                    # the same block used to be silently overwritten by this
                    # dict merge — the zOS#50 "second list kills the page"
                    # shape. loop_ops treats `zList__dupN` as one more list.
                    out[_free_zlist_key(node, out)] = lowered["zList"]
                    continue
                # invalid shuttle — leave as-is (fails open, warned in _lower_shuttle)
                out[key] = val
            else:
                out[key] = _lower_node(val, registry, zos)
        return out
    if isinstance(node, list):
        return [_lower_node(item, registry, zos) for item in node]
    return node


def _free_zlist_key(node: Dict[str, Any], out: Dict[str, Any]) -> str:
    """First ``zList``/``zList__dupN`` name unused by BOTH the lowered output so
    far and the source block (an authored ``zList`` may appear AFTER the shuttle
    in declaration order — it must keep its own key)."""
    if "zList" not in out and "zList" not in node:
        return "zList"
    n = 2
    while f"zList__dup{n}" in out or f"zList__dup{n}" in node:
        n += 1
    return f"zList__dup{n}"


def _lower_shuttle(cfg: Dict[str, Any], registry: Dict[str, Any], zos: Any) -> Any:
    """Turn one ``zShuttle`` config into a ``{zList: {source, each}}`` dict."""
    spool = cfg.get(_KEY_SPOOL)
    pattern = cfg.get(_KEY_PATTERN)
    if not isinstance(spool, str) or not isinstance(pattern, str):
        zos.logger.framework.warning(
            f"[zShuttle] needs '{_KEY_SPOOL}: <list>' and '{_KEY_PATTERN}: <name>' "
            f"(got spool={spool!r}, pattern={pattern!r}) — left as-is"
        )
        return None

    # zSpool accepts a bare name (products) or an explicit %data.<name>.
    source = spool if spool.startswith("%data.") else f"%data.{spool}"

    # AUTO-FILL: discover the pattern's slots, feed each from the current row.
    body = registry.get(pattern)
    if body is None:
        zos.logger.framework.warning(
            f"[zShuttle] pattern '%{pattern}' not in zLoom/patterns/ — weaving it "
            f"with no auto-fill (slots will surface literal)"
        )
        slots = {}
    else:
        slots = {name: f"%item.{name}" for name in sorted(_discover_slots(body))}

    zlist: Dict[str, Any] = {
        "source": source,
        "each": {f"%{pattern}": slots},
    }
    # Optional per-row filter — jinja's ``{% for … if … %}``. loop_ops evaluates it
    # against each row (``%item.*``) via zos.zgate and drops rows that fail. A CONCISE
    # bare token (``zGate: %item.in_stock``) means "row is kept when truthy" → lower it
    # to the zGate truthiness IR ``{%item.in_stock: zSet}``. A dict gate (comparator /
    # combinator, e.g. ``{%item.price: {zBelow: 100}}``) passes straight through.
    if _KEY_GATE in cfg:
        zlist[_KEY_GATE] = _normalize_gate(cfg[_KEY_GATE])

    return {"zList": zlist}


def _normalize_gate(gate: Any) -> Any:
    """A bare ``%token`` string gate → the zGate truthiness IR ``{token: zSet}``;
    anything else (dict IR) is returned unchanged. The evaluator rejects bare
    strings, so this is what makes the concise form answerable."""
    if isinstance(gate, str) and gate.startswith("%"):
        return {gate: "zSet"}
    return gate


def _discover_slots(node: Any, found: set = None) -> set:
    """Collect the bare ``%slot`` names declared in a pattern definition."""
    if found is None:
        found = set()
    if isinstance(node, str):
        for m in _SLOT_PATTERN.finditer(node):
            found.add(m.group(1))
    elif isinstance(node, dict):
        for k, v in node.items():
            if isinstance(k, str):
                for m in _SLOT_PATTERN.finditer(k):
                    found.add(m.group(1))
            _discover_slots(v, found)
    elif isinstance(node, list):
        for item in node:
            _discover_slots(item, found)
    return found
