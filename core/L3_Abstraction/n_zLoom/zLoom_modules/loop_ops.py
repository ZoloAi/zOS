# zOS/core/L3_Abstraction/n_zLoom/zLoom_modules/loop_ops.py
"""zLoom LOOP ops — expand ``zList`` directives into concrete keyed blocks.

Runs at the data-binding layer (the SSOT shared by CLI zDash panels and Bifrost
zWizard chunks) BEFORE the render split, so no render-time loop primitive or
``%item`` awareness leaks downstream. Mixed into the ``zLoom`` facade.
"""

from zOS import Any, Dict

from .token_resolver import LOOP_FRAME_KEY


class LoopOps:
    """zList expansion methods for zLoom (expects ``self.zos``)."""

    zos: Any

    def _push_row(self, context: Any, row: Any) -> Dict[str, Any]:
        """Push ``row`` onto the render-scoped loop-frame stack and return the context
        dict actually used. The stack lives in ``context[LOOP_FRAME_KEY]`` (never in
        session): a list used LIFO so nested loops (a shuttle inside a shuttle) each see
        their own row via the top frame. Creates the context dict + stack on first use;
        wraps a non-dict row as ``{"value": str(row)}`` (matching the resolver contract).
        """
        frame = row if isinstance(row, dict) else {"value": str(row)}
        ctx = context if isinstance(context, dict) else {}
        ctx.setdefault(LOOP_FRAME_KEY, []).append(frame)
        return ctx

    def _pop_row(self, context: Any) -> None:
        """Pop the current row off the loop-frame stack (end of one iteration)."""
        if isinstance(context, dict):
            stack = context.get(LOOP_FRAME_KEY)
            if isinstance(stack, list) and stack:
                stack.pop()

    def expand_list_bindings(
        self,
        block: Dict[str, Any],
        resolved_data: Dict[str, Any],
        context: Any = None
    ) -> Dict[str, Any]:
        """Expand every ``zList: {source: %data.<name>, each: {…}}`` into one
        resolved each-block per row (``%item.*`` bound to that row). Mutates
        ``block`` in place and returns it; a no-op when no zList is present.
        """
        if isinstance(block, dict):
            self._expand_node(block, resolved_data if isinstance(resolved_data, dict) else {}, context)
        return block

    def _expand_node(self, node: Dict[str, Any], resolved_data: Dict[str, Any], context: Any) -> None:
        """Depth-first walk: recurse into children, then expand a zList on this node."""
        for key, val in list(node.items()):
            if key == "zList":
                continue
            if isinstance(val, dict):
                self._expand_node(val, resolved_data, context)
            elif isinstance(val, list):
                for item in val:
                    if isinstance(item, dict):
                        self._expand_node(item, resolved_data, context)

        cfg = node.get("zList")
        if isinstance(cfg, dict):
            self._expand_zlist_into(node, cfg, resolved_data, context)

    def _expand_zlist_into(
        self,
        parent: Dict[str, Any],
        cfg: Dict[str, Any],
        resolved_data: Dict[str, Any],
        context: Any
    ) -> None:
        """Replace ``parent``'s zList directive with one resolved each-block per row."""
        import copy

        rows = self._lookup_list_source(cfg.get("source", ""), resolved_data)
        each_tmpl = cfg.get("each", {})
        gate = cfg.get("zGate")  # optional per-row filter (jinja `{% for … if … %}`)
        # Consume the directive regardless, so no render-time loop primitive leaks.
        parent.pop("zList", None)
        if not isinstance(rows, list) or not isinstance(each_tmpl, dict) or not each_tmpl:
            return

        # Weave each row through the render-scoped loop-frame stack (LoopOps-owned, in
        # context — never session). _push_row returns the context carrying the frame;
        # both the per-row gate and the token resolver read %item.* off the top of it.
        # The stack is self-restoring (push/pop per row), so the old zVars["item"] +
        # prev_item save/restore dance is gone, and nested shuttles are safe by design.
        out_idx = 0
        for row in rows:
            row_ctx = self._push_row(context, row)
            try:
                # Denied row is simply not woven (contiguous output keys).
                if gate is not None and not self._row_passes_gate(gate, row_ctx):
                    continue
                woven = self._resolve_item_tokens(copy.deepcopy(each_tmpl), row_ctx)
                # Collapse per-row zKnots WHILE the %item frame is live (so a card's
                # computed value / ternary sees this row). Same engine as page-scope
                # (KnotOps.expand_knots) — sibling mixin on the zLoom facade; guarded so
                # LoopOps stays usable in isolation (unit smokes).
                expand_knots = getattr(self, "expand_knots", None)
                if expand_knots is not None:
                    expand_knots(woven, row_ctx)
                parent[f"zListItem__{out_idx}"] = woven
                out_idx += 1
            finally:
                self._pop_row(row_ctx)

    def _row_passes_gate(self, gate: Any, context: Any) -> bool:
        """Ask zGate whether the current row (``%item.*`` on the loop-frame stack) passes.

        Delegates to the zGate SSOT — the loop never decides inline. If the engine
        is unavailable (misconfiguration, not a trust gate), the row is KEPT and a
        warning is logged: a shuttle filter is a BUSINESS predicate, so failing open
        surfaces the gap without silently blanking the list."""
        zgate = getattr(self.zos, "zgate", None)
        if zgate is None or not hasattr(zgate, "evaluate"):
            self.zos.logger.framework.warning(
                "[zShuttle] zGate engine unavailable — row filter skipped (row kept)"
            )
            return True
        granted, _reason = zgate.evaluate(gate, context)
        return bool(granted)

    def _lookup_list_source(self, source_ref: Any, resolved_data: Dict[str, Any]) -> Any:
        """Resolve a ``%data.<key>`` zList source to a list of rows.

        Reads the binding result first, then falls back to
        session["_current_block_data"] (the CLI panel stash). A limit=1 dict is
        wrapped to a single-row list so callers iterate uniformly.
        """
        if not isinstance(source_ref, str) or not source_ref.startswith("%data."):
            return None
        key = source_ref[len("%data."):]
        val = resolved_data.get(key) if isinstance(resolved_data, dict) else None
        if val is None and hasattr(self.zos, "session"):
            block_data = self.zos.session.get("_current_block_data")
            if isinstance(block_data, dict):
                val = block_data.get(key)
        if isinstance(val, dict):
            return [val]
        return val if isinstance(val, list) else None

    def resolve_list_source(self, source_ref: Any, context: Any = None) -> list:
        """Public SSOT: resolve a ``%data.<key>`` reference to a list of rows.

        Thin context-unwrapping wrapper around ``_lookup_list_source`` for callers
        outside the zList expansion path (e.g. a zMenu's dynamic ``options:``) that
        only hold a dispatch context, not an already-extracted resolved_data map.
        Always returns a list (empty on miss) so callers never branch on None.
        """
        resolved_data = context.get("_resolved_data") if isinstance(context, dict) else None
        val = self._lookup_list_source(source_ref, resolved_data if isinstance(resolved_data, dict) else {})
        return val if isinstance(val, list) else []

    def _resolve_item_tokens(self, node: Any, context: Any) -> Any:
        """Deep-resolve %tokens (esp. ``%item.*``) in a copied each-block against the
        current row (top of the loop-frame stack in ``context``). Non-string leaves pass through.

        Knot IR is left INTACT here (its ``%item.*`` operands bake to literals, but the
        op/condition keys survive) — the per-row ``expand_knots`` pass in
        ``_expand_zlist_into`` collapses it to a scalar while the frame is still live."""
        from zOS.L2_Handling.d_zParser.parser_modules.parser_functions import resolve_variables

        if isinstance(node, str):
            return resolve_variables(node, self.zos, context) if "%" in node else node
        if isinstance(node, dict):
            return {k: self._resolve_item_tokens(v, context) for k, v in node.items()}
        if isinstance(node, list):
            return [self._resolve_item_tokens(v, context) for v in node]
        return node
