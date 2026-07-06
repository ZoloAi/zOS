# zOS/core/L2_Handling/h_zNavigation/navigation_modules/breadcrumb_classify.py

"""zStride passivity classifier — the SSOT for "pre-order vs commit-on-success".

A crumb is a recorded zStride. WHEN a zStride records depends on whether its key
can FAIL:

  • PASSIVE structure (organizational containers, display leaves) cannot
    false-positive — entering a group / rendering a leaf always succeeds — so it
    stamps on ENTRY (pre-order), making the trail read parent-before-child
    (``Greeting > zH0``).
  • CONDITIONAL keys commit ON SUCCESS — they keep the engine's post-dispatch
    path so a blocked key never leaves a false-positive crumb. The ``!`` gate is
    the canonical case: recorded only AFTER it passes. Conditional = a modifier
    (gate ``!`` / menu ``*`` / bounce ``^`` / anchor ``~``), the ``zCrumbs``
    display directive, a routed/gated VALUE key (``zLink``/``zURL``/``zDelta``/
    ``zMenu``/``zBack``/…/``if``), or a commit-on-success leaf EVENT
    (``url``/``button``/inputs/``selection``).

Why this lives alone
--------------------
This ONE predicate replaces three hand-spelled copies that had ~70% overlap and
drifted apart (e.g. a nested ``zURL`` leaf was treated as passive in one site
and conditional in another):

  • zGuard  ``SequentialExecutor._is_passive_container``  (engine loop)
  • zOS     ``OrganizationalHandler._zStride_passive``    (nested walk)
  • zOS     ``CommandLauncher._zStride_hoisted_leaf``     (single-leaf hoist)

Each site feeds only what it has — the key, optionally its value dict (engine
container test), optionally an already-resolved leaf event (hoisted leaf) — and
the verdict is identical. Mirrors ``breadcrumb_marker``: **no imports from the
navigation package**, so both the zOS dispatch handlers (direct import) and the
zGuard wizard (try-import with a literal fallback, like its other zOS SSOT
borrows) share the single definition. The modifier glyphs are the ONE canonical
set from ``dispatch_constants`` — never re-spelled here.
"""

from typing import Any, Optional

try:  # the canonical modifier SSOT (zOS dispatch) — never a second copy
    from zOS.L2_Handling.g_zDispatch.dispatch_modules.dispatch_constants import (  # type: ignore[reportMissingImports]
        PREFIX_MODIFIERS as _PREFIX_MODIFIERS,
        SUFFIX_MODIFIERS as _SUFFIX_MODIFIERS,
    )
except Exception:  # noqa: BLE001 - defensive: keep importable in isolation
    _PREFIX_MODIFIERS = ["^", "~"]
    _SUFFIX_MODIFIERS = ["!", "*"]

# A routed / gated / leaf VALUE key — its presence makes a dict CONDITIONAL (the
# key commits on success, never pre-stamped). SSOT for the engine's
# passive-container test (was SequentialExecutor._NON_PASSIVE_VALUE_KEYS).
CONDITIONAL_VALUE_KEYS = frozenset({
    'zDisplay', 'zLink', 'zURL', 'zDelta', 'zMenu', 'zBack', 'zExit',
    'zStop', 'zNavBar', 'zDash', 'action', 'if',
})

# A leaf EVENT that commits on success (input prompts + click-through links /
# menus) — recorded by the engine's commit path, never pre-stamped as passive
# structure. SSOT for the hoisted-leaf test (was CommandLauncher._CONDITIONAL_EVENTS).
CONDITIONAL_EVENTS = frozenset({
    'url', 'button', 'read_string', 'read_password', 'selection',
})

# The display directive that opens a window onto the trail — itself never a nav key.
_ZCRUMBS = 'zCrumbs'


def is_passive_zStride(
    key: Any,
    value: Any = None,
    event: Optional[str] = None,
) -> bool:
    """True iff ``key`` is a PASSIVE zStride (record pre-order, on entry).

    ``False`` ⇒ the key is CONDITIONAL and must keep the commit-on-success path
    (so a blocked ``!`` gate, a denied nav, or a refused input never records).

    Feed whatever the call site has:
      - ``key``    — always (the step / container / leaf name, modifiers intact).
      - ``value``  — the key's dict value, for the engine container test (a dict
                     carrying a routed/gated key is conditional).
      - ``event``  — an already-resolved leaf event, for the hoisted-leaf test
                     (a commit-on-success event is conditional).
    """
    if not isinstance(key, str) or not key:
        return False
    # Modifier (gate ! / menu * / bounce ^ / anchor ~) → conditional.
    if key[0] in _PREFIX_MODIFIERS or key[-1] in _SUFFIX_MODIFIERS:
        return False
    # zCrumbs is a display directive (a window onto the trail), not a nav key.
    if key.lstrip('_') == _ZCRUMBS:
        return False
    # A routed / gated / leaf value key → commit-on-success.
    if isinstance(value, dict) and any(k in value for k in CONDITIONAL_VALUE_KEYS):
        return False
    # A commit-on-success leaf event → never pre-stamped.
    if event is not None and event in CONDITIONAL_EVENTS:
        return False
    return True
