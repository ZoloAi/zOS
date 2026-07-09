# zOS/core/L2_Core/d_zAuth/zAuth_modules/auth_logout.py
"""
Built-in zLogout Action - Declarative Logout (v1.6.0+)

═══════════════════════════════════════════════════════════════════════════════
OVERVIEW
═══════════════════════════════════════════════════════════════════════════════

This module provides a built-in zLogout action for declarative logout
without requiring application-specific plugin code. It's the sister action
of zLogin and handles session cleanup and context switching.

Key Features:
    - Session cleanup: Removes app from session[zAuth][applications]
    - Context switching: Auto-switches to zSession if available, otherwise anonymous
    - Cache invalidation: Regenerates session_hash for frontend updates
    - Dual-mode aware: Handles transitions between contexts
    - Declarative: Works in both Terminal and Bifrost modes

Usage:
    # In zUI.logout.yaml
    Logout_Action!:
        - zLogout: "zCloud"  # App name to logout from

    Session Changes:
    Before:
        session[zAuth][applications] = {
            "zCloud": { authenticated: True, ... }
        }
        session[zAuth][active_context] = "application"
        session[zAuth][active_app] = "zCloud"
    
    After:
        session[zAuth][applications] = {}  # zCloud removed
        session[zAuth][active_context] = None  # Or "zsession" if available
        session[zAuth][active_app] = None

═══════════════════════════════════════════════════════════════════════════════
"""

from zOS import Any, Dict
from zOS.L1_Foundation.a_zConfig.zConfig_modules import (
    SESSION_KEY_ZVISITOR,
    SESSION_KEY_ZMODE,
    ZMODE_ZBIFROST,
    ZAUTH_KEY_AUTHENTICATED,
    ZAUTH_KEY_ID,
    ZAUTH_KEY_USERNAME,
    ZAUTH_KEY_ROLE,
    ZAUTH_KEY_API_KEY,
)
from zOS.L1_Foundation.a_zConfig.zConfig_modules.session.config_session import SessionConfig

# Constants
LOG_PREFIX = "[zLogout]"


def _clear_cookie_identity(zos: Any) -> None:
    """Drop the session_store identity bound to this caller's zsid (best-effort).

    The logout counterpart to action_login._persist_cookie_identity: clears the
    durable slice so a hard reload / new tab / WS resume carrying the same cookie
    rehydrates as guest, not signed-in.
    """
    try:
        zsid = zos.session.get("_zsid")
        if zsid:
            from zOS.L1_Foundation.a_zConfig.zConfig_modules.session import (  # type: ignore[reportMissingImports]
                session_cookie as _sc,
            )
            _sc.clear_identity(zos, zsid)
    except Exception:  # pylint: disable=broad-except
        pass


def handle_zLogout(
    app_name: str,
    _zConv: Dict[str, Any],
    _zContext: Dict[str, Any],
    zos: Any
) -> Dict[str, Any]:
    """
    Built-in zLogout handler - clears app session and switches context.
    
    This is the sister action of zLogin. It removes the specified app from
    the authenticated apps list and automatically switches to the appropriate
    context (zSession if available, otherwise anonymous).
    
    Args:
        app_name: Application name to logout from (e.g., "zCloud")
        _zConv: Form data (not used for logout, but required for consistency)
        _zContext: Dialog context (not used for logout, but required for consistency)
        zos: zOS instance (provides session, logger access)
    
    Returns:
        Dict[str, Any]: Response dict for gate completion
            - success (bool): True if logout successful
            - message (str): Success message for user feedback
    
    Examples:
        # Logout from zCloud app
        >>> result = handle_zLogout("zCloud", {}, {}, zos)
        >>> # Removes: session[zAuth][applications]["zCloud"]
        >>> # Switches context to: "zsession" or "anonymous"
    
    Session Cleanup Process:
        1. Check if zAuth structure exists (graceful if missing)
        2. Remove app from session[zAuth][applications][app_name]
        3. Check if other apps are still authenticated
        4. If zSession is authenticated, switch to CONTEXT_ZSESSION
        5. If no zSession, set active_context to None (anonymous)
        6. Update dual_mode flag accordingly
        7. Clear active_app
        8. Regenerate session_hash for frontend cache invalidation
    
    Notes:
        - Gracefully handles logout from non-authenticated apps (success anyway)
        - Always regenerates session_hash to trigger frontend updates
        - Preserves zSession authentication if present
        - Works in both Terminal and Bifrost modes
    """
    logger = zos.logger
    logger.info(f"{LOG_PREFIX} Logout request for app: {app_name}")

    # One zOS instance = one signed-in caller — sign-out clears the single
    # session["zVisitor"] back to its anonymous shape (graceful if absent).
    zos.session[SESSION_KEY_ZVISITOR] = {
        ZAUTH_KEY_AUTHENTICATED: False,
        ZAUTH_KEY_ID: None,
        ZAUTH_KEY_USERNAME: None,
        ZAUTH_KEY_ROLE: None,
        ZAUTH_KEY_API_KEY: None,
    }
    logger.info(f"{LOG_PREFIX} Cleared signed-in identity")

    # Cookie-bound identity must die too, else a reconnect/reload carrying the
    # same zsid rehydrates the just-cleared identity from the session_store (the
    # login write-through in action_login._persist_cookie_identity). Without this,
    # signing out leaves authed-only chrome (e.g. the Logout item) visible after
    # the next WS resume. Mirror of the login persist seam.
    _clear_cookie_identity(zos)

    # v1.6.0: Regenerate session_hash for frontend cache invalidation
    new_hash = SessionConfig.regenerate_session_hash(zos.session)
    logger.debug(f"{LOG_PREFIX} Session hash regenerated: {new_hash}")

    # Success! Display message and return
    success_msg = f"[ok] You have been successfully logged out from {app_name}"
    logger.info(f"{LOG_PREFIX} Logout successful for {app_name}")

    if _is_bifrost_mode(zos):
        return {"success": True, "message": success_msg, "app": app_name}

    # Terminal mode: Display success message and return truthy value for ! modifier
    zos.display.success(success_msg)
    return True  # Return True (truthy) to indicate success for ! modifier


# ============================================================================
# zLogout BLOCK PRIMITIVE (new declarative form — sister of zLogin block)
# ============================================================================

def handle_zLogout_block(
    logout_config: Dict[str, Any],
    zos: Any,
    walker: Any = None,
) -> Any:
    """
    Handle the zLogout block dispatch event (sister of the zLogin block).

    zLogout is a zForm with nothing to collect, so it is much simpler than
    zLogin — it composes only:
        1. AUTH      — clear the app session (existing zAuth `zLogout` action)
        2. FOLLOW-UP — dispatch onSuccess (navigation) once logged out

    App identity is resolved via the same SSOT used by zLogin
    (`_resolve_block_app_name`, anchored on zSpark `zApp`) so the author never
    hardcodes the app name.

    CLI: clears the session, then dispatches the onSuccess zEvent inline.
    Bifrost: the gate auto-executor sends success + a `navigate` instruction
    built from onSuccess, so onSuccess is NOT dispatched here for that mode.
    """
    # Reuse the zLogin block helpers — single source of truth for app
    # resolution and onSuccess dispatch (DRY across the auth zForms).
    from .action_login import _resolve_block_app_name, _dispatch_on_success  # pylint: disable=import-outside-toplevel

    logger = zos.logger if hasattr(zos, "logger") else None
    app_name = _resolve_block_app_name(logout_config.get("zApp"), zos)

    # AUTH: clear the app session (existing, mode-agnostic zAuth action).
    result = handle_zLogout(app_name=app_name, _zConv={}, _zContext={}, zos=zos)

    # FOLLOW-UP: in CLI, dispatch onSuccess inline — and PROPAGATE its result.
    # Same trampoline contract as zLogin (action_login.py): a zLink onSuccess
    # stages a navigate signal that the sequential walker only honors when
    # it's the value returned for THIS step; swallowing it here falls through
    # to the next sibling key instead of landing on the target block.
    # In Bifrost the gate sender emits the navigate instruction (no inline render).
    if not _is_bifrost_mode(zos):
        on_success = logout_config.get("onSuccess")
        if on_success is not None:
            nav_result = _dispatch_on_success(on_success, zos, walker, logger)
            if nav_result is not None:
                return nav_result
    return result


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _is_bifrost_mode(zos: Any) -> bool:
    """
    Check if current mode is Bifrost (GUI).
    
    Args:
        zos: zOS instance
        
        Returns:
        bool: True if Bifrost mode, False if Terminal mode
    """
    return zos.session.get(SESSION_KEY_ZMODE) == ZMODE_ZBIFROST
