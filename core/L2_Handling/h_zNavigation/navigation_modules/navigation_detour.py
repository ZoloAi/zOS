# zOS/core/L2_Handling/h_zNavigation/navigation_modules/navigation_detour.py

"""
Detour — the zModal call/return engine (zNavigation-owned).

zAlpha / zDelta are GOTOs: the route moves, the trail records, coming back is
zBack's job. ``zModal:`` is zOS's first CALL verb: walk INTO a block, complete
it, and auto-RETURN to the firing point — the walk resumes exactly where it
was. A modal is a glance, not a move, so the detour contract is:

    * trail-invisible — the nested run gets NO navigation callbacks, so the
      modal's internals write no crumbs; the route (zVaFolder/zVaFile/zBlock)
      never mutates; zBack after return acts as if the detour never happened
    * completion = the target block finishes (a zDialog's onSubmit returns, or
      plain content falls off its last key) → control returns to the caller
    * dismiss — a zBack raised INSIDE the modal closes it (same return path);
      pure-content modals gate on a "close" pause so they have presence in the
      terminal instead of scrolling past
    * signal pass-through — "exit"/"stop" (user ends the session from inside),
      "navigate" (a REPLACE hop staged inside the modal: the modal dies and the
      trampoline takes over), and "$Block" (delta pick) all propagate untouched

Ownership split (mirrors the zLink/zDelta seams): zDispatch RECOGNIZES the
``zModal`` key and RESOLVES its target forms to a block dict
(handler_navigation.handle_zmodal); THIS module owns the run semantics; the
walker's engine loop resumes the caller naturally when the nested run returns.

Bifrost: the SAME staging pattern navigation uses (_zPendingNavigate). A
dispatch runs synchronously inside the bridge and cannot send WS frames, so
the detour stages the resolved (already zLoom-woven) block under
session["_zPendingModal"] and returns; the bridge seam that already flushes
pending navigations pops it, runs the block through the shared chunk
enrichment pipeline, and ships a ``render_modal`` message — the client
renders the declarative block into a floating overlay and owns dismissal
(backdrop/ESC/×) locally. The server never moved the route, so closing needs
no round-trip: trail-invisible by construction, exactly the zCLI contract.
"""

from zOS import Any, Dict, Optional

from zOS.zVocabulary import CONTROL_RETURN_ZBACK, CONTROL_RETURN_STOP

# Signals the detour must NOT swallow — they outlive the modal. "navigate" is
# the walker trampoline signal (zWalker.NAV_SIGNAL) staged by a REPLACE hop
# fired inside the modal; "exit"/"stop" end the session from inside it.
_SIGNAL_NAVIGATE = "navigate"
_SIGNAL_EXIT = "exit"
_PASS_THROUGH_SIGNALS = (_SIGNAL_NAVIGATE, _SIGNAL_EXIT, CONTROL_RETURN_STOP)

# The complex completion result. Being a dict (not a str/int/bool/None) it
# trips the engine's anchor-loop check, so a modal fired from a ``~Menu*``
# anchor returns the user to that menu — drill-in/step-out, like a sub-wizard.
MODAL_COMPLETED: Dict[str, str] = {"zModal": "completed"}

# Top-level marks that make a modal SELF-GATING in zCLI (it already waits for
# the user), so the close pause would be a second, annoying Enter. Menus (the
# ``*`` modifier or longhand zMenu) and dialogs gate; plain content does not.
_SELF_GATING_KEYS = frozenset({"zDialog", "zMenu"})

_LOG = "[zModal]"


class Detour:
    """The modal detour runner — one responsibility: run a block as a CALL."""

    def __init__(self, navigation: Any) -> None:
        self.navigation = navigation
        self.zos = navigation.zos
        self.logger = navigation.logger

    def run_modal(
        self,
        block_dict: Dict[str, Any],
        walker: Any,
        source_key: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Run ``block_dict`` as a modal detour and return to the caller.

        The caller (dispatch's NavigationHandler) has already resolved the
        authored form (inline dict / ``$Block`` / ``@.zPath``) to a block dict
        and pre-woven its zLoom bindings into ``context``. This method owns
        only the call/return contract described in the module docstring.
        Returns MODAL_COMPLETED on normal completion/dismiss, or the
        pass-through signal when the modal was left via a real move.
        """
        if not isinstance(block_dict, dict) or not block_dict:
            self.logger.warning(f"{_LOG} empty/invalid modal content — nothing to run")
            return None

        self.logger.framework.debug(
            f"{_LOG} open (source={source_key or '?'}, keys={list(block_dict)[:6]})"
        )

        # zBifrost: stage-and-flush (never run execute_loop here — in Bifrost it
        # returns a chunked GENERATOR whose frames this sync seam cannot send).
        # The bridge pops _zPendingModal at its flush seam and ships the block
        # as a render_modal message; the client overlay owns display + dismiss.
        if self.zos.session.get("zMode") == "zBifrost":
            self.zos.session["_zPendingModal"] = {
                "block": block_dict,
                "context": context,
                "source": source_key,
            }
            self.logger.framework.debug(f"{_LOG} staged for bridge flush (Bifrost)")
            return dict(MODAL_COMPLETED)

        # Trail-invisible nested run: NO navigation callbacks → no crumbs, no
        # scope seed, no session route mutation (the zDelegate precedent).
        result = walker.execute_loop(items_dict=block_dict, context=context)

        # A real move fired inside the modal outlives it — propagate untouched.
        if isinstance(result, str):
            if result in _PASS_THROUGH_SIGNALS:
                self.logger.framework.debug(f"{_LOG} pass-through signal: {result}")
                return result
            if result.startswith("$"):
                self.logger.framework.debug(f"{_LOG} delta pick escapes modal: {result}")
                return result
            if result == CONTROL_RETURN_ZBACK:
                # zBack inside the modal = dismiss. The detour absorbs it: the
                # caller's own trail was never touched, so there is nothing to pop.
                self.logger.framework.debug(f"{_LOG} dismissed (zBack)")
                return dict(MODAL_COMPLETED)

        # zCLI presence gate: plain content would scroll past without a beat.
        # Self-gating modals (dialog/menu inside) already waited for the user.
        if self._needs_close_gate(block_dict):
            try:
                self.zos.display.text(
                    "", indent=1, pause=True, break_message="Press Enter to close..."
                )
            except Exception as err:  # pylint: disable=broad-except
                self.logger.framework.debug(f"{_LOG} close gate skipped: {err}")

        self.logger.framework.debug(f"{_LOG} closed (completed)")
        return dict(MODAL_COMPLETED)

    def _needs_close_gate(self, block_dict: Dict[str, Any]) -> bool:
        """True when the modal is pure content (nothing inside gated the user).

        Only meaningful in zCLI — Bifrost renders (no blocking prompt), and its
        overlay skin will own dismissal client-side.
        """
        if self.zos.session.get("zMode") == "zBifrost":
            return False
        for key, value in block_dict.items():
            if not isinstance(key, str):
                continue
            if key.rstrip("!").endswith("*"):  # a menu key gates
                return False
            if key in _SELF_GATING_KEYS:
                return False
            if isinstance(value, dict) and any(k in value for k in _SELF_GATING_KEYS):
                return False
        return True
