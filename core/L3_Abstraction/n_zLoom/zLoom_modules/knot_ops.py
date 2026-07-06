# zOS/core/L3_Abstraction/n_zLoom/zLoom_modules/knot_ops.py
"""zLoom KNOT ops — collapse ``zKnot`` value-dicts to scalars before render.

A **zKnot** ties `%` threads into ONE computed value (jinja `{{ a+b }}` / ternary).
The pure engine lives in ``knot_eval`` (the value math + zGate-delegated ternary); this
mixin is the facade surface + the structure pass that walks a bound block and collapses
every authored knot to its scalar, mirroring ``expand_list_bindings`` (LoopOps) and
component expansion. Runs at the binding seam (``prepare_block_render`` + the Bifrost
``_bind_root_zinja`` mirror) so NO render-time knot awareness leaks downstream, and CLI ⇄
Bifrost stay identical by construction. Mixed into the ``zLoom`` facade.

TWO authored forms (a grammar constraint, not a preference): in zUI files ``content`` /
``label`` are AUTO-MULTILINE prose slots — the parser slurps any nested value there into
a STRING, so a knot cannot live directly under ``content:``. Hence:
  • **element-child form** (for the prose case) — a ``zKnot:`` KEY inside a UI element;
    it computes the element's ``content`` (siblings like ``_zClass`` are preserved)::

        zText:
            _zClass: zc-eyebrow
            zKnot: { zMul: [%item.price_usd, 2] }   # → content = <scalar>

  • **value form** (for non-multiline slots) — a bare op IR as the value itself::

        label: { zAdd: [%a, %b] }                   # → label = <scalar>
"""

from zOS import Any, Dict

from .knot_eval import evaluate_knot, is_op_ir


class KnotOps:
    """zKnot resolution methods for zLoom (expects ``self.zos``)."""

    zos: Any

    def resolve_knot(self, expr: Any, context: Any = None) -> Any:
        """Evaluate ONE knot IR → scalar (facade SSOT entry). ``None`` on any invalid
        input (bad op / div-by-zero / missing operand) — fail safe, never raises."""
        return evaluate_knot(expr, self.zos, context)

    def expand_knots(self, block: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
        """Collapse every authored knot in ``block`` to its scalar, in place.

        Walks the bound block depth-first, handling both authored forms (see module
        docstring). A no-op when no knot is present. Loop-scoped knots (``%item.*``
        inside a zShuttle each-block) are collapsed per-row by LoopOps against the live
        loop frame; this pass finishes page-scoped knots (``%data.* / %route.* / zVars``).
        """
        if isinstance(block, dict):
            self._expand_knot_node(block, context)
        return block

    def _expand_knot_node(self, node: Any, context: Any) -> None:
        """Depth-first: element-child ``zKnot`` → ``content``; bare-op values → scalar;
        recurse into everything else. An op IR is collapsed WHOLE (never recursed into —
        the engine owns operand/nesting resolution)."""
        if isinstance(node, dict):
            # element-child form: a zKnot KEY computes this element's content (keeps siblings)
            if "zKnot" in node:
                node["content"] = self.resolve_knot(node.pop("zKnot"), context)
            for key, val in list(node.items()):
                if is_op_ir(val):
                    node[key] = self.resolve_knot(val, context)
                elif isinstance(val, (dict, list)):
                    self._expand_knot_node(val, context)
        elif isinstance(node, list):
            for i, item in enumerate(node):
                if is_op_ir(item):
                    node[i] = self.resolve_knot(item, context)
                elif isinstance(item, (dict, list)):
                    self._expand_knot_node(item, context)
