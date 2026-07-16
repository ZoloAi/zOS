# zOS/core/L3_Abstraction/n_zLoom/zGate.py
"""zGate — the gating layer, folded into the zLoom subsystem (Layer 3).

Every yes/no gate in zOS — auth (``zRBAC``), conditional (wizard ``if:``), and value
comparisons — is answered here, in one grammar, with one contract:
``(granted, reason)``. zGate does not invent auth or query logic; it *composes*
existing SSOTs — it delegates trust to ``zos.auth.check_zrbac`` and reads live values
through ``zos.zloom.resolve_value``, reusing zData's comparator vocabulary
(``zAbove``/``zBelow``/``zIN``/``zBetween``/``zNull``). The only new grammar is the
combinators ``zAll``/``zAny``/``zNot``.

Public surface (attached at boot as ``zos.zgate``):

    evaluate(predicate, context)  — answer a predicate → (granted, reason)
    lower_zrbac(block)            — a resolved zRBAC block → lean zGate IR
    lower_if(expression)          — a wizard if: string   → zGate IR

TRUST BOUNDARY (why this is public, not in the zGuard wheel): zGate is decision
GRAMMAR, not trust ESTABLISHMENT. Identity, ownership, and watermark verification
live in the private ``zguard.auth`` wheel and are reached only via
``check_zrbac``. zGate holds no secrets and makes no identity decision inline, so
hiding it would add nothing but obscurity while breaking the open language surface
(zLSP, zAgents, scaffold, tests). The security guarantee is the invariant that
every ``authed``/``role``/``require`` predicate delegates to that auth SSOT.

Layering note: L2 consumers (zDispatch, zNavigation, zAuth gates, routes) and
zGuard (wizard) call into ``zos.zgate`` via the runtime ``zos`` handle — a runtime
attribute access, not an import — so there is no import-time layer inversion.
"""

from zOS import Any

from .zLoom_modules.gate_evaluator import evaluate_gate
from .zLoom_modules.gate_lowering import lower_zrbac, lower_if, GateLoweringError

__all__ = ["zGate", "GateLoweringError"]


class zGate:  # noqa: N801 — subsystem facade
    """Public zGate facade — attached at boot as ``zos.zgate``."""

    def __init__(self, zos: Any) -> None:
        self.zos = zos
        self._warned_legacy: set = set()  # transitional: warn once per legacy key

    def evaluate(self, predicate: Any, context: Any = None):
        """Answer a zGate predicate against the live session → (granted, reason)."""
        return evaluate_gate(predicate, self.zos, context)

    def gate_predicate(self, container: Any) -> Any:
        """Extract the authored gate predicate from a block — the ONE place that
        knows the authored key name.

        End state: the gate is authored under ``zGate:`` and its value IS the IR,
        so we return it verbatim (no lowering — authored == evaluated).

        TRANSITIONAL (Phase 3 migration bridge — DELETED in 3E): if a block still
        carries the retired ``zRBAC:`` key, we lower it and log a one-time
        deprecation warning so a not-yet-migrated file is LOUD, never a silent
        fail-open. ``if:`` is handled by the wizard (it needs a zHat resolver), not
        here. Returns None when no gate is present (→ open).
        """
        if not isinstance(container, dict):
            return None
        if "zGate" in container:
            return container["zGate"]
        # noqa: transitional bridge — remove in Phase 3E. A None-valued zRBAC is
        # NOT a gate: the server-file parser stamps `zRBAC: None` on every route
        # entry (vafile_server), so key-presence alone would mark ALL routes as
        # gated (empty gate {} evaluates open, but public/gated discrimination —
        # e.g. the sitemap projection — would see everything as private).
        if container.get("zRBAC") is not None:
            self._warn_legacy("zRBAC")
            return self.lower_zrbac(container["zRBAC"])
        return None

    def check(self, container: Any, context: Any = None):
        """Convenience: extract the authored gate from a block and evaluate it."""
        return self.evaluate(self.gate_predicate(container), context)

    @staticmethod
    def references_zhat(predicate: Any) -> bool:
        """Does this gate predicate reference a ``%zHat.*`` token anywhere?

        The discriminator that partitions ONE authored ``zGate:`` on a wizard step:
          * references zHat  → a wizard-local *conditional-inclusion* gate. Only the
            wizard (with a live zHat resolver) can answer it; a False verdict SKIPS
            the step. The general render gate must leave it alone (real zloom can't
            resolve zHat → would wrongly deny).
          * no zHat          → auth / ``%data`` / ``%session`` gate answerable by the
            real engine → the render gate (check_zrbac / zloom) owns it.
        """
        if isinstance(predicate, str):
            return predicate.startswith("%zHat.")
        if isinstance(predicate, dict):
            return any(
                zGate.references_zhat(k) or zGate.references_zhat(v)
                for k, v in predicate.items()
            )
        if isinstance(predicate, (list, tuple)):
            return any(zGate.references_zhat(item) for item in predicate)
        return False

    def _warn_legacy(self, key: str) -> None:
        if key in self._warned_legacy:
            return
        self._warned_legacy.add(key)
        log = getattr(self.zos, "logger", None)
        if log is not None and hasattr(log, "framework"):
            log.framework.warning(
                f"[zGate] authored '{key}:' is deprecated and will be removed — "
                f"migrate to 'zGate:' (transitional bridge active)"
            )

    def lower_zrbac(self, block: Any) -> Any:
        """Lower a resolved zRBAC block into the lean zGate IR."""
        return lower_zrbac(block)

    def lower_if(self, expression: Any) -> Any:
        """Lower a wizard ``if:`` expression string into the zGate IR."""
        return lower_if(expression)
