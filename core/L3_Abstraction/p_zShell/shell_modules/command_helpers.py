# zOS/core/L3_Abstraction/p_zShell/shell_modules/command_helpers.py

"""
Shared helpers for zShell command executors.

Two pieces of boilerplate were copy-pasted across nearly every executor:

    1. Unpacking the parsed-command dict (``action`` / ``args`` / ``options``),
       each file re-declaring its own key constants with subtly different
       defaults.
    2. A subsystem-availability guard (``hasattr(zos, "x") or zos.x is None``)
       that errors + logs + bails.

This module is the single source of truth for both. Executors with genuinely
different contracts (e.g. lazy-init in ``shell_cmd_comm`` or the typed
error-dict validators in ``shell_cmd_func``/``shell_cmd_data``) keep their own
logic; everything else should route through here.
"""

from zOS import Any, Dict, List, Optional, Tuple

from .executor_constants import KEY_ACTION, KEY_ARGS, KEY_OPTIONS


def get_command_parts(
    parsed: Dict[str, Any],
    *,
    action_default: Optional[str] = None,
) -> Tuple[Optional[str], List[Any], Dict[str, Any]]:
    """Unpack a parsed command into ``(action, args, options)``.

    ``args`` defaults to a fresh list and ``options`` to a fresh dict so callers
    never alias a shared mutable. ``action_default`` lets callers preserve their
    prior contract (some used ``""``, others ``None``).
    """
    return (
        parsed.get(KEY_ACTION, action_default),
        parsed.get(KEY_ARGS, []) or [],
        parsed.get(KEY_OPTIONS, {}) or {},
    )


def require_subsystem(zos: Any, attr: str, error_msg: Optional[str] = None) -> bool:
    """Return ``True`` if ``zos.<attr>`` exists and is initialized.

    On failure: emits ``error_msg`` via zDisplay (when provided), logs, and
    returns ``False`` so the caller can ``if not require_subsystem(...): return``.
    """
    if not hasattr(zos, attr) or getattr(zos, attr) is None:
        if error_msg:
            zos.display.error(error_msg)
        zos.logger.error("%s subsystem not available", attr)
        return False
    return True
