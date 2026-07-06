# zOS/core/L2_Handling/g_zDispatch/dispatch_modules/modifiers/modifier_crumbs.py

"""
Crumbs-Rewind Modifier for zDispatch Subsystem.

Implements the caret (^) SUFFIX modifier — the authoring sugar for a zCrumbs
bulk-rewind:

    <key>^: <zPath>            # sugar
    zCrumbs: {show: none, zBack: <zPath>}   # equivalent longhand

Both forms collapse to the single bulk-back signal ``{ZCRUMB_SIGNAL: <zPath>}``
which the walker already consumes (zNavigation.handle_zCrumb_back → pop_to_scope
+ re-walk, with a zLink-forward fallback when the target is not on the trail).

This modifier performs NO execution and NO mode branching: the rewind is a pure
trail operation owned by zNavigation. It only mints the signal — the mechanic,
the mode-agnostic unwind, and the navigation all live in the existing SSOT.

History:
    Replaces the retired BounceModifier (prefix ``^action`` "execute-then-back").
    The genuine multi-level "return to a point and prune the dead-end" need is
    served honestly by the zCrumbs rewind; the old bounce primitive is gone.
"""

from zOS import Any, Dict, Union

from ..dispatch_constants import ZCRUMB_SIGNAL


class CrumbsRewindModifier:
    """Mint the bulk-back signal for the caret (^) suffix modifier."""

    def __init__(self, dispatch: Any, zos: Any, logger: Any) -> None:
        self.dispatch = dispatch
        self.zos = zos
        self.logger = logger

    def process(self, zHorizontal: Any) -> Union[Dict[str, Any], Any]:
        """Return the bulk-back signal for ``<key>^: <zPath>``.

        Args:
            zHorizontal: the key's value — a zPath naming the trail scope to
                rewind to. The author owns trail correctness (per design); an
                off-trail target falls forward to zLink downstream.

        Returns:
            {ZCRUMB_SIGNAL: <zPath>} when the value is a usable target, else the
            raw value untouched (defensive — nothing to rewind to).
        """
        if not isinstance(zHorizontal, str) or not zHorizontal.strip():
            self.logger.framework.debug(
                "[CrumbsRewind] ^ modifier got non-path value %r — passthrough", zHorizontal
            )
            return zHorizontal
        target = zHorizontal.strip()
        self.logger.framework.debug("[CrumbsRewind] ^ → bulk-back to %r", target)
        return {ZCRUMB_SIGNAL: target}
