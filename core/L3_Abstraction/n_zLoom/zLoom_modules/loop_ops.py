# zOS/core/L3_Abstraction/n_zLoom/zLoom_modules/loop_ops.py
"""zLoom LOOP ops — expand ``zList`` directives into concrete keyed blocks.

Runs at the data-binding layer (the SSOT shared by CLI zDash panels and Bifrost
zWizard chunks) BEFORE the render split, so no render-time loop primitive or
``%item`` awareness leaks downstream. Mixed into the ``zLoom`` facade.
"""

import json

from zOS import Any, Dict

from .token_resolver import LOOP_FRAME_KEY

# Private stash key for a zList's ORIGINAL directive, surviving past its own
# expansion. `raw_zFile[block_name]` (handler_navigation._resolve_delta_target_
# block) hands out a LIVE reference into the loader's cached parse, not a copy
# — a block revisited via zDelta within the same process re-expands the SAME
# dict. Popping `zList` outright (the render contract: the walker/dispatcher
# have no primitive for a raw zList key, only baked zListItem__N children) is
# fine for a page rendered ONCE, but a page revisited later would find no
# `zList` left to re-expand and freeze at whatever its FIRST visit saw — e.g.
# an empty history list on first render never grows even after a real insert.
#
# Stored as a JSON STRING, never a dict: every metadata key that ever existed
# before this one (`_zClass`, `_zStyle`, ...) held a scalar, so more than one
# render path skips organizational recursion with a bare `isinstance(val,
# dict)` check rather than an explicit key allow-list — a dict-valued stash
# would silently render as one more phantom child block (its raw `each`
# template, unresolved %item tokens and all) under any such path. A string
# value is inert everywhere without needing every one of those paths found +
# patched.
_ZLIST_SOURCE_KEY = "__zListSource"


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
        """Depth-first walk: recurse into children, then expand every zList on this node."""
        for key, val in list(node.items()):
            if self._zlist_ordinal(key) is not None:
                continue
            if isinstance(val, dict):
                self._expand_node(val, resolved_data, context)
            elif isinstance(val, list):
                for item in val:
                    if isinstance(item, dict):
                        self._expand_node(item, resolved_data, context)

        # A never-yet-expanded list sits at a `zList` key (or a parser/shuttle
        # suffixed `zList__dupN` when the block carries MORE than one list —
        # zOS#50); a node REVISITED later in the same process only has the
        # stashed original (see _ZLIST_SOURCE_KEY). Either is a valid cfg to
        # re-weave against this call's fresh data. Snapshot the keys FIRST:
        # each expansion rebuilds the node in place, and a stash minted by this
        # very pass must not be re-expanded within it.
        for key in list(node.keys()):
            if key not in node:
                continue  # consumed by an earlier expansion's rebuild
            ordinal = self._zlist_ordinal(key)
            if ordinal is not None and isinstance(node.get(key), dict):
                self._expand_zlist_into(node, node[key], resolved_data, context, key, ordinal)
                continue
            ordinal = self._stash_ordinal(key)
            if ordinal is not None:
                cfg = self._load_zlist_source(node.get(key))
                if isinstance(cfg, dict):
                    self._expand_zlist_into(node, cfg, resolved_data, context, key, ordinal)

    @staticmethod
    def _zlist_ordinal(key: Any) -> Any:
        """``zList`` → '' | ``zList__dupN`` → 'dupN' | anything else → None."""
        if key == "zList":
            return ""
        if isinstance(key, str) and key.startswith("zList__"):
            return key[len("zList__"):]
        return None

    @staticmethod
    def _stash_ordinal(key: Any) -> Any:
        """``__zListSource`` → '' | ``__zListSource__dupN`` → 'dupN' | else None."""
        if key == _ZLIST_SOURCE_KEY:
            return ""
        prefix = _ZLIST_SOURCE_KEY + "__"
        if isinstance(key, str) and key.startswith(prefix):
            return key[len(prefix):]
        return None

    @staticmethod
    def _row_belongs(key: Any, ordinal: str) -> bool:
        """True when a ``zListItem__…`` key was woven by THE list with this ordinal.

        Default list ('' ordinal) owns ``zListItem__<digits>``; an ordinal list
        owns ``zListItem__<ordinal>_<digits>`` — so two lists on one block never
        claim (or clean up) each other's rows.
        """
        if not isinstance(key, str) or not key.startswith("zListItem__"):
            return False
        rest = key[len("zListItem__"):]
        if ordinal:
            return rest.startswith(f"{ordinal}_")
        return rest.isdigit()

    @staticmethod
    def _load_zlist_source(stashed: Any) -> Any:
        """Deserialize a JSON-string ``_ZLIST_SOURCE_KEY`` stash back to a dict."""
        if not isinstance(stashed, str):
            return None
        try:
            return json.loads(stashed)
        except (TypeError, ValueError):
            return None

    def _expand_zlist_into(
        self,
        parent: Dict[str, Any],
        cfg: Dict[str, Any],
        resolved_data: Dict[str, Any],
        context: Any,
        anchor_key: str = "zList",
        ordinal: str = ""
    ) -> None:
        """Replace ``parent``'s zList directive with one resolved each-block per row.

        Rows are woven AT THE DIRECTIVE'S DECLARED POSITION (zOS#50 — they used
        to append at the dict tail, so "list above a details panel" rendered
        below it). ``anchor_key`` is the key being consumed (``zList`` /
        ``zList__dupN`` first pass, the stash on a revisit); ``ordinal``
        namespaces this list's rows + stash so several lists on one block never
        clean up or overwrite each other's output.
        """
        import copy

        rows = self._lookup_list_source(cfg.get("source", ""), resolved_data)
        if rows is None:
            # zOS#42: an unresolvable source weaves ZERO rows (the directive is
            # still consumed below, so the raw each-template can never render as
            # a phantom row) — and it SAYS so, because a nonsense reel/name is
            # otherwise indistinguishable from "my CSS/reel is broken".
            # session_framework, NOT framework: the latter is the GLOBAL
            # zos-framework.log (session-agnostic, often handler-less in app
            # runs) — this is an app-authoring fault, it belongs in the
            # <title>.framework.log trace the developer actually reads.
            log = getattr(self.zos.logger, "session_framework", None) \
                or self.zos.logger.framework
            log.warning(
                f"[zLoom] zList source '{cfg.get('source', '')}' did not resolve "
                f"to a list (reel missing, zVars name, or non-%data ref) — weaving 0 rows"
            )
        each_tmpl = cfg.get("each", {})
        gate = cfg.get("zGate")  # optional per-row filter (jinja `{% for … if … %}`)

        # Weave each row through the render-scoped loop-frame stack (LoopOps-owned, in
        # context — never session). _push_row returns the context carrying the frame;
        # both the per-row gate and the token resolver read %item.* off the top of it.
        # The stack is self-restoring (push/pop per row), so the old zVars["item"] +
        # prev_item save/restore dance is gone, and nested shuttles are safe by design.
        row_prefix = f"zListItem__{ordinal}_" if ordinal else "zListItem__"
        woven_rows: Dict[str, Any] = {}
        out_idx = 0
        if isinstance(rows, list) and isinstance(each_tmpl, dict) and each_tmpl:
            for row in rows:
                row_ctx = self._push_row(context, row)
                try:
                    # Denied row is simply not woven (contiguous output keys).
                    if gate is not None and not self._row_passes_gate(gate, row_ctx):
                        continue
                    row_copy = copy.deepcopy(each_tmpl)
                    # A NESTED zGate (e.g. an "owner actions" child block gated on
                    # `%item.<field>: %session.<field>`) must be settled HERE, while
                    # the %item frame is still live — _resolve_item_tokens below only
                    # does STRING interpolation (a resolver miss is left as the
                    # literal token, per token_resolver.py's display contract), so a
                    # denied comparison would otherwise survive as two now-unresolvable
                    # literal tokens once the loop frame pops, silently comparing
                    # None == None (always "equal") for every later walk. Pruning first
                    # means the gate is answered with the SAME live %item/%session
                    # values the row-level `zList.zGate` filter already uses above.
                    self._prune_denied_subtrees(row_copy, row_ctx)
                    woven = self._resolve_item_tokens(row_copy, row_ctx)
                    # Collapse per-row zKnots WHILE the %item frame is live (so a card's
                    # computed value / ternary sees this row). Same engine as page-scope
                    # (KnotOps.expand_knots) — sibling mixin on the zLoom facade; guarded so
                    # LoopOps stays usable in isolation (unit smokes).
                    expand_knots = getattr(self, "expand_knots", None)
                    if expand_knots is not None:
                        expand_knots(woven, row_ctx)
                    woven_rows[f"{row_prefix}{out_idx}"] = woven
                    out_idx += 1
                finally:
                    self._pop_row(row_ctx)

        # Consume the PUBLIC directive (no render-time loop primitive leaks) and
        # stash the original AT ITS POSITION so THIS SAME node — a live reference
        # a revisit within the process shares (see _ZLIST_SOURCE_KEY) — can be
        # re-woven against fresh data next time instead of freezing forever.
        # The rebuild drops THIS list's prior rows (count/content may have
        # changed since) and re-emits stash + fresh rows exactly where the
        # directive was declared; other lists' rows/stashes pass through.
        stash_key = f"{_ZLIST_SOURCE_KEY}__{ordinal}" if ordinal else _ZLIST_SOURCE_KEY
        try:
            stash_val = json.dumps(cfg)
        except TypeError:
            stash_val = None  # non-JSON-safe cfg (shouldn't happen for parsed zolo)
        rebuilt: Dict[str, Any] = {}
        for key, val in list(parent.items()):
            if key == anchor_key:
                if stash_val is not None:
                    rebuilt[stash_key] = stash_val
                rebuilt.update(woven_rows)
                continue
            if key == stash_key or self._row_belongs(key, ordinal):
                continue  # this list's prior stash/rows — superseded by the rebuild
            rebuilt[key] = val
        parent.clear()
        parent.update(rebuilt)

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

    def _prune_denied_subtrees(self, node: Any, context: Any) -> None:
        """Depth-first: drop any child block whose own ``zGate`` denies (an
        action_row-scoped gate NESTED inside a row template, distinct from the
        whole-row filter on ``zList`` itself). A passing block has its now-spent
        ``zGate`` key stripped so it never reaches the renderer."""
        if not isinstance(node, dict):
            return
        for key in list(node.keys()):
            val = node.get(key)
            if not isinstance(val, dict):
                continue
            child_gate = val.get("zGate")
            if child_gate is not None:
                if not self._row_passes_gate(child_gate, context):
                    del node[key]
                    continue
                val.pop("zGate", None)
            self._prune_denied_subtrees(val, context)

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
        from .token_resolver import resolve_whole_token

        if isinstance(node, str):
            if "%" not in node:
                return node
            # A WHOLE-value token bakes to its RAW value so the native type
            # survives the row copy: `readonly: %item.locked` stays a real bool
            # (not the truthy string "False" — zOS#92), `options: %item.tags`
            # stays a list (zOS#57). A miss (None) falls through to the display
            # path below, which keeps the literal token — visible and debuggable.
            is_whole, raw = resolve_whole_token(node, self.zos, context)
            if is_whole and raw is not None and not isinstance(raw, str):
                return raw
            return resolve_variables(node, self.zos, context)
        if isinstance(node, dict):
            return {k: self._resolve_item_tokens(v, context) for k, v in node.items()}
        if isinstance(node, list):
            return [self._resolve_item_tokens(v, context) for v in node]
        return node
