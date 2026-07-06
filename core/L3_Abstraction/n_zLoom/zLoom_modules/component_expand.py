# zOS/core/L3_Abstraction/n_zLoom/zLoom_modules/component_expand.py
"""
zPattern component expansion — load-time structural reuse for zLoom.

A zPattern is a named, reusable zUI structure with named slots. It lets leaves stop
copy-pasting the same hero / section / card scaffolding (which invites drift and
DRY violations) and instead DECLARE the intent and fill the content.

Two halves of the ``%`` sigil, disambiguated by POSITION:
    • VALUE position  → render-time token   (``content: %session.zVisitor.id``)
    • KEY position    → load-time component  (``%leafHero: {…}``)
This module owns the KEY-position half; the VALUE-position half is token_resolver.

Grammar
-------
**Definition** — one file per concern under ``<app>/zLoom/patterns/*.{zolo,json,yaml,yml}``
(a child of the zLoom home, sibling to the named reads at ``zLoom/`` root); each
top-level key IS a component name (mirrors the zLoom read convention):

    leafHero:
        Inner:
            Badge:   { zText: { content: %eyebrow } }
            zH1:     { label: %title }
            zH2:     { label: %lead }

``%<param>`` placeholders mark slots. A value that is EXACTLY ``%param`` is replaced
by the slot value (may be a scalar OR a whole subtree — block slots). ``%param``
embedded inside a longer string is textual-substituted.

**Invocation** — a KEY starting with ``%`` whose name is a registered component;
its dict value supplies the slots:

    Page_Hero:
        %leafHero:
            eyebrow: Advanced · zLoom
            title:   Live values, declared by name.
            lead:    A page says what it needs; the read lives somewhere safe.

Expansion replaces the ``%leafHero`` entry IN PLACE with the component body, so
``Page_Hero`` becomes ``{ Inner: { Badge…, zH1…, zH2… } }``.

Guarantees
----------
- **Idempotent**: after expansion no ``%<component>`` keys remain, so re-running is
  a no-op — safe to invoke from more than one load seam.
- **Render-safe**: only the invocation's declared slot names are substituted, so
  render tokens like ``%session.*`` pass through UNTOUCHED to render time.
- **Fails open + visible**: an unknown component is left as-is with a warning; a
  missing slot leaves its ``%param`` literal (surfaces the gap, never crashes).
- **Cycle-guarded**: nested/recursive components stop at ``_MAX_DEPTH``.
"""

from zOS import re, Any, Dict

_MAX_DEPTH = 25
_ZPATTERN_EXTS = (".zolo", ".json", ".yaml", ".yml")


def load_component_registry(zos: Any) -> Dict[str, Any]:
    """Scan ``<zSpace>/zLoom/patterns/`` → {component_name: definition}.

    Components live under the zLoom home as a child dir (``zLoom/patterns/``), a
    sibling to the named reads that sit at ``zLoom/`` root. Mirrors the zLoom read
    registry: each file's top-level keys are the names (zMeta skipped). Per-file
    parses are cached by the loader, so the dir scan is cheap and keeps dev edits live.
    """
    import os
    registry: Dict[str, Any] = {}
    base = zos.session.get("zSpace") if hasattr(zos, "session") else None
    base = base or os.getcwd()
    zforms_dir = os.path.join(base, "zLoom", "patterns")
    if not os.path.isdir(zforms_dir):
        return registry
    for fname in sorted(os.listdir(zforms_dir)):
        if os.path.splitext(fname)[1].lower() not in _ZPATTERN_EXTS:
            continue
        fpath = os.path.join(zforms_dir, fname)
        try:
            data = zos.loader.handle_absolute_path(fpath)
        except Exception as exc:  # pylint: disable=broad-except
            zos.logger.framework.error(f"[zPattern] Failed to load '{fname}': {exc}")
            continue
        if isinstance(data, dict):
            for key, val in data.items():
                if key == "zMeta":
                    continue
                registry[key] = val
    return registry


def expand_components(tree: Any, zos: Any, registry: Dict[str, Any] = None) -> Any:
    """Expand every ``%<component>`` invocation in ``tree`` (returns a new tree).

    ``registry`` is optional (injected for tests); otherwise loaded from zLoom/patterns/.
    No components declared → the original tree is returned untouched (fast path).
    """
    if registry is None:
        registry = load_component_registry(zos)
    if not registry:
        return tree
    return _expand_node(tree, registry, zos, 0)


def _expand_node(node: Any, registry: Dict[str, Any], zos: Any, depth: int) -> Any:
    if isinstance(node, dict):
        out: Dict[str, Any] = {}
        for key, val in node.items():
            name = key[1:] if isinstance(key, str) and key.startswith("%") else None
            if name is not None and name in registry:
                produced = _render_component(name, val, registry, zos, depth + 1)
                if isinstance(produced, dict):
                    out.update(produced)  # merge component body into parent (in place)
                else:
                    out[key] = produced
            elif name is not None:
                zos.logger.framework.warning(
                    f"[zPattern] Unknown component '%{name}' (not in zLoom/patterns/) — left as-is"
                )
                out[key] = _expand_node(val, registry, zos, depth)
            else:
                out[key] = _expand_node(val, registry, zos, depth)
        return out
    if isinstance(node, list):
        return [_expand_node(item, registry, zos, depth) for item in node]
    return node


def _render_component(
    name: str, slots: Any, registry: Dict[str, Any], zos: Any, depth: int
) -> Any:
    """Fill a component definition's slots, then expand any nested components."""
    if depth > _MAX_DEPTH:
        zos.logger.framework.error(
            f"[zPattern] Max expansion depth ({_MAX_DEPTH}) hit at '%{name}' — cycle? aborting."
        )
        return {}
    import copy
    slot_map = slots if isinstance(slots, dict) else {}
    filled = _fill_slots(copy.deepcopy(registry[name]), slot_map)
    # Nested components inside the produced body expand now (depth-guarded).
    return _expand_node(filled, registry, zos, depth)


def _fill_slots(node: Any, slots: Dict[str, Any]) -> Any:
    if isinstance(node, str):
        return _sub_str(node, slots)
    if isinstance(node, dict):
        return {k: _fill_slots(v, slots) for k, v in node.items()}
    if isinstance(node, list):
        return [_fill_slots(v, slots) for v in node]
    return node


def _sub_str(text: str, slots: Dict[str, Any]) -> Any:
    # Exact match "%param" → slot value verbatim (may be a non-string subtree).
    if text.startswith("%") and text[1:] in slots:
        return slots[text[1:]]
    # Embedded "%param" → textual substitution (word-boundary guarded so %body
    # never clobbers %bodytext). Only declared slots are touched — render tokens
    # like %session.* are left for render time.
    for pname, pval in slots.items():
        text = re.sub(r"%" + re.escape(pname) + r"(?![A-Za-z0-9_])", str(pval), text)
    return text
