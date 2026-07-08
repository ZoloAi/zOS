# zOS/core/L2_Handling/g_zDispatch/dispatch_modules/zprobe.py

"""
zProbe — the denominator oracle for zProgress.

When `zProgress` is declared on (or beside) an action, zOS needs ONE answer to
the same question regardless of context: *how many stops does this journey
have?* zProbe is that single source of truth. It is a READ-ONLY twin of the
dispatch router — it routes by the same keys the launcher routes by, but its
verb is *count*, not *execute*. No side effects, ever.

A "stop" is a user-legible journey stage (a wizard step, a confirm gate, an
execute) — NOT an internal microsecond pipeline phase. Counting those phases
would resurrect the fake-% trap; zProbe deliberately does not.

Visibility horizon: zProbe sees DECLARED structure only. It cannot see inside an
opaque plugin body, nor traverse runtime-data-dependent branches. So its total
is the honest *initial* denominator; the live run may reconcile it (e.g. a `!`
retry adds a stop). Callers should tolerate a denominator that grows.

Scope (v1, zCLI): zFunc (direct), zBtn with a plugin action (longer journey),
zWizard (one stop per declared step). New contexts register a counter here —
this is the generalization seam of PROGRESS_ACTION_KEYS.
"""

from zOS import Any, Optional, List

from .dispatch_constants import KEY_ZFUNC, KEY_ZWIZARD, PLUGIN_PREFIX

# Literal UI key — zBtn has no KEY_ constant (it is a shorthand element, detected
# by literal name before expansion). Kept local to the probe.
_KEY_ZBTN = "zBtn"

# ── Stage vocabularies (SSOT) ────────────────────────────────────────────────
# A "stop" is an INTERNAL zOS wiring stage the event passes through — not a
# function detail. Every event is first routed by zDispatch, so that is always
# the first stop; the LAST stop is the subsystem that does the real work. This is
# why even a bare zFunc has >1 stop: the bar genuinely progresses (dispatch →
# execute) instead of jumping 0→100.
STAGES_ZFUNC = ("zDispatch", "zFunc")                 # routed, then executed
STAGES_ZBTN = ("zDispatch", "zDialog", "zFunc")       # routed, confirmed, executed

# Keys that are wizard chrome / metadata, not steps.
_WIZARD_META = {
    "_zClass", "_zStyle", "_zId", "zId", "zProgress",
    "zMode", "zRaven", "zScripts",
}


class ProbeResult:
    """The oracle's answer: how many stops, what they're called, which context."""

    __slots__ = ("total", "stops", "kind")

    def __init__(self, total: int, stops: List[str], kind: str) -> None:
        self.total = max(1, int(total))
        self.stops = list(stops) if stops else ["executing"]
        self.kind = kind

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"ProbeResult(kind={self.kind!r}, total={self.total}, stops={self.stops})"


def probe(scope: Any, zos: Optional[Any] = None) -> ProbeResult:
    """Discover the progress denominator for `scope` (read-only).

    `scope` is the parsed block dict the zProgress is attached to. Routes by the
    same keys the dispatch launcher routes by, deepest-known context wins.
    """
    if not isinstance(scope, dict):
        return ProbeResult(len(STAGES_ZFUNC), list(STAGES_ZFUNC), "unknown")

    # zWizard is the richest structural case — count its declared steps.
    if KEY_ZWIZARD in scope:
        return _probe_wizard(scope[KEY_ZWIZARD])

    # A button whose action is a plugin call has the longer (gated) journey.
    if _KEY_ZBTN in scope:
        return _probe_btn(scope[_KEY_ZBTN])

    # A direct function call — one opaque execute.
    if KEY_ZFUNC in scope:
        return ProbeResult(len(STAGES_ZFUNC), list(STAGES_ZFUNC), "zFunc")

    return ProbeResult(len(STAGES_ZFUNC), list(STAGES_ZFUNC), "unknown")


def _probe_wizard(wiz: Any) -> ProbeResult:
    """One stop per declared step (strip `!` modifiers, drop chrome).

    Step enumeration uses the shared ``semantic_keys`` primitive (parser_utils) —
    the same "structure vs. chrome" definition the renderer/reload twin uses — so
    what counts as a real child lives in one place. Wizard chrome (``_WIZARD_META``
    + underscore-prefixed keys) is the exclusion set for this context.
    """
    if not isinstance(wiz, dict):
        return ProbeResult(len(STAGES_ZFUNC), list(STAGES_ZFUNC), "zWizard")
    from zOS.L2_Handling.d_zParser.parser_modules.parser_utils import semantic_keys
    steps = [k.replace("!", "") for k in semantic_keys(wiz, exclude=_WIZARD_META, drop_underscored=True)]
    return ProbeResult(len(steps), steps or ["step"], "zWizard")


def _probe_btn(btn: Any) -> ProbeResult:
    """A plugin-backed button journeys confirm → resolve → execute; a bare
    button (no plugin action) is a single stop."""
    action = btn.get("action") if isinstance(btn, dict) else None
    if isinstance(action, str) and action.startswith(PLUGIN_PREFIX):
        return ProbeResult(len(STAGES_ZBTN), list(STAGES_ZBTN), "zBtn")
    return ProbeResult(len(STAGES_ZFUNC), list(STAGES_ZFUNC), "zBtn")
