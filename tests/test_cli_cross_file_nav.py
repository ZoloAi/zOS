"""zOS#19 — zCLI cross-file navigation dead-ends.

Two seams used to swallow a staged cross-file hop in zCLI:

1. ``NavigationHandler._run_menu`` (navbar flavor): a pick's zLink dispatch
   STAGES the target and returns NAV_SIGNAL for the walker trampoline — the
   menu loop returned CONTROL_RETURN_STOP instead, so the staged page was
   never walked ("Walker session completed" right after the pick).

2. ``SelectionCollector.collect_button_confirmation``: the action-string
   ladder knew ``zLink(`` / ``zDelta(`` but not ``zAlpha(`` — the first-class
   Greek name the docs teach for cross-file buttons — so the action fell
   through to the step-jump return and was silently dropped.

These tests pin the trampoline signal SSOT and both propagation paths.
"""

import sys
import types
from pathlib import Path

import pytest

ZOS_ROOT = Path(__file__).resolve().parents[1]
if str(ZOS_ROOT) not in sys.path:
    sys.path.insert(0, str(ZOS_ROOT))


# ---------------------------------------------------------------------------
# Signal SSOT — the three copies of "navigate" must never drift.
# ---------------------------------------------------------------------------

def test_nav_signal_ssot_matches_walker():
    from zOS.L2_Handling.h_zNavigation.navigation_modules.navigation_constants import (
        NAV_SIGNAL,
    )
    from zOS.L4_Orchestration.q_zWalker.zWalker import NAV_SIGNAL as WALKER_SIGNAL

    assert NAV_SIGNAL == "navigate"
    assert WALKER_SIGNAL is NAV_SIGNAL


def test_nav_signal_matches_zguard_engine():
    zguard = pytest.importorskip("zguard.zengine.zengine_modules.zengine_constants")
    from zOS.L2_Handling.h_zNavigation.navigation_modules.navigation_constants import (
        NAV_SIGNAL,
    )

    assert zguard._SIGNAL_NAVIGATE == NAV_SIGNAL


# ---------------------------------------------------------------------------
# Seam 1 — _run_menu must bubble NAV_SIGNAL, not clobber it with STOP.
# ---------------------------------------------------------------------------

class _Logger:
    def __init__(self):
        self.framework = self

    def debug(self, *a, **k): pass
    def info(self, *a, **k): pass
    def warning(self, *a, **k): pass
    def error(self, *a, **k): pass


def _make_handler(launch_result):
    """Build a NavigationHandler with everything _run_menu touches stubbed."""
    from zOS.L2_Handling.g_zDispatch.dispatch_modules.handlers.handler_navigation import (
        NavigationHandler,
    )

    zos = types.SimpleNamespace()
    zos.session = {"zMode": "zCLI"}
    zos.logger = _Logger()

    # navigation.create → the menu render; return the nav dict a $-pick yields.
    nav = types.SimpleNamespace()
    nav.create = lambda options, title=None, allow_back=True, walker=None: (
        {"zLink": "@.zViews.zUI.Gallery.Gallery"}
    )
    nav.breadcrumbs = types.SimpleNamespace(
        clear_navbar_pending=lambda: None,
        set_navbar_pending=lambda *a, **k: None,
    )
    zos.navigation = nav

    # launcher.launch → the zLink dispatch result under test.
    launcher = types.SimpleNamespace(launch=lambda *a, **k: launch_result)
    zos.dispatch = types.SimpleNamespace(launcher=launcher)

    handler = NavigationHandler.__new__(NavigationHandler)
    handler.zos = zos
    handler.logger = _Logger()
    # Navbar RBAC filter is exercised elsewhere; identity here.
    handler._apply_navbar_rbac = lambda zKey, options: list(options)
    return handler


def test_navbar_pick_bubbles_nav_signal():
    from zOS.L2_Handling.h_zNavigation.navigation_modules.navigation_constants import (
        NAV_SIGNAL,
    )

    handler = _make_handler(launch_result=NAV_SIGNAL)
    result = handler._run_menu(
        ["$Gallery"], title=None, anchored=True, walker=None,
        navbar_key="~zNavBar*",
    )
    assert result == NAV_SIGNAL, (
        "a staged zCLI hop must bubble to the walker trampoline — "
        "STOP here ends the session with the landed page never walked (zOS#19)"
    )


def test_navbar_pick_direct_render_still_stops():
    """zBifrost / direct-call dispatches (no staged hop) keep the STOP contract."""
    from zOS.zVocabulary import CONTROL_RETURN_STOP

    handler = _make_handler(launch_result=None)
    result = handler._run_menu(
        ["$Gallery"], title=None, anchored=True, walker=None,
        navbar_key="~zNavBar*",
    )
    assert result == CONTROL_RETURN_STOP


def test_plain_menu_pick_bubbles_nav_signal():
    """The non-navbar dict-pick path must also propagate the signal."""
    from zOS.L2_Handling.h_zNavigation.navigation_modules.navigation_constants import (
        NAV_SIGNAL,
    )

    handler = _make_handler(launch_result=NAV_SIGNAL)
    result = handler._run_menu(
        ["$Gallery"], title=None, anchored=True, walker=None,
    )
    assert result == NAV_SIGNAL


# ---------------------------------------------------------------------------
# Seam 2 — the button action ladder must know zAlpha( (first-class zLink name).
# ---------------------------------------------------------------------------

def _collect_with_action(monkeypatch, action):
    from zOS.L2_Handling.e_zDisplay.zDisplay_modules.compounds.inputs import (
        selection_collector as sc,
    )

    collector = sc.SelectionCollector.__new__(sc.SelectionCollector)
    collector.display = types.SimpleNamespace(zos=None)

    # Confirm gate answers y; renderer feedback is a no-op.
    monkeypatch.setattr(
        "zOS.L2_Handling.e_zDisplay.zDisplay_modules.utils.confirm_gate.confirm_gate",
        lambda display, kind, label=None, color=None: True,
    )
    renderer = types.SimpleNamespace(display_feedback=lambda *a, **k: None)
    return collector.collect_button_confirmation(
        label="Go", color="info", action=action, renderer=renderer,
    )


def test_zalpha_action_returns_zlink_dict(monkeypatch):
    result = _collect_with_action(
        monkeypatch, "zAlpha(@.zViews.zUI.Gallery.Gallery)"
    )
    assert result == {"zLink": "@.zViews.zUI.Gallery.Gallery"}, (
        "zAlpha( must normalize to the zLink dict the wizard engine navigates "
        "on — the raw string is mistaken for a step-jump key and dropped (zOS#19)"
    )


def test_zlink_action_unchanged(monkeypatch):
    result = _collect_with_action(monkeypatch, "zLink(@.zViews.zUI.Gallery.Gallery)")
    assert result == {"zLink": "@.zViews.zUI.Gallery.Gallery"}


def test_zdelta_action_unchanged(monkeypatch):
    result = _collect_with_action(monkeypatch, "zDelta($Details)")
    assert result == {"zDelta": "$Details"}
