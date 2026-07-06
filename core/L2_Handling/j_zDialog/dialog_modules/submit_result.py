# zOS/core/L2_Handling/j_zDialog/dialog_modules/submit_result.py

"""
SSOT for zDialog onSubmit feedback.

The submit leaf — not Bifrost, not zCLI — owns the answer to "did this submit
succeed, and what should the user be told?". Both renderers consume the SAME
``ZResult`` so the signal can never drift between terminal and browser:

    zCLI    → render_submit_signal()  → ONE display.success / display.error line
    Bifrost → zresult_ws_fields()      → WS success / message / errors

Action handling (the only place that knows each action's return contract):

    • zData returns a bare bool (True = ok). Field-level errors are stashed in
      ``session['_zdata_errors']`` by crud_insert / crud_update, so a failure
      is read from there — not guessed.
    • zFunc / zLogin / any other action already return a ZResult-coercible
      envelope, so ``ZResult.coerce`` trusts the action's own ok/message/error.

Kept import-light on purpose (only a lazy ``zos_plugin.ZResult``) so the
Bifrost bridge and the zDataSandbox probe can both import the mapper without
dragging in zDispatch.
"""

from typing import Any, Dict, List, Optional

__all__ = ["coerce_submit_result", "render_submit_signal"]

# Per-action success headline. Falls back to "Done" for anything else.
_ZDATA_VERBS = {"insert": "Saved", "update": "Updated", "delete": "Deleted"}


def coerce_submit_result(
    submit_dict: Dict[str, Any],
    raw_result: Any,
    session: Optional[Dict[str, Any]] = None,
):
    """Normalise an onSubmit outcome into ONE ``ZResult`` (SSOT)."""
    from zos_plugin import ZResult  # local — keeps this module import-light

    if isinstance(submit_dict, dict) and "zData" in submit_dict:
        action = (submit_dict.get("zData") or {}).get("action") or "save"
        if raw_result is True:
            return ZResult.success(message=_ZDATA_VERBS.get(action, "Done"))

        # Failure — surface the field-level errors crud stashed, if any.
        errors: Any = None
        if isinstance(session, dict):
            errors = session.pop("_zdata_errors", None)
        errors = _normalise_errors(errors)
        if errors:
            # error (singular) is the zCLI headline; data carries the full list
            # so Bifrost can render every field error in response.errors.
            return ZResult.failure("; ".join(errors), data=errors)
        return ZResult.failure("Action failed. Please try again.")

    # zFunc / zLogin / other — trust the action's own envelope.
    return ZResult.coerce(raw_result)


def render_submit_signal(display: Any, zr: Any) -> None:
    """zCLI: surface a submit ``ZResult`` as ONE signal (mirrors zFunc._display_result)."""
    if display is None:
        return
    if zr.ok:
        display.success(zr.message or "Done")
    else:
        display.error(zr.error or "Action failed.")


def _normalise_errors(errors: Any) -> List[str]:
    """Flatten whatever crud stashed into a list of human strings."""
    if not errors:
        return []
    if isinstance(errors, dict):
        return [f"{field}: {msg}" for field, msg in errors.items()]
    if isinstance(errors, list):
        return [str(e) for e in errors]
    return [str(errors)]
