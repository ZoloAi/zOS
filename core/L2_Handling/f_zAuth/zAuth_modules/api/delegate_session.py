# zOS/core/L2_Handling/d_zAuth/zAuth_modules/api/delegate_session.py

"""
Session Authentication Delegate for zAuth Facade.

This module provides zSession (Layer 1) authentication delegate methods,
following zDisplay's delegate pattern for clean facade composition.

Methods:
    - login: Authenticate zOS/Zolo user
    - logout: Clear session authentication
    - status: Show authentication status
    - is_authenticated: Check if authenticated
    - get_credentials: Get current user credentials

Pattern:
    All methods delegate to self.authentication module instance.
"""

import os

from zOS import Any, Optional, Dict

# Import constants for method implementation
from ..auth_constants import (
    CONTEXT_ZSESSION,
    KEY_STATUS,
    KEY_CREDENTIALS,
    KEY_USERNAME,
    FIELD_USER_ID,
    KEY_ROLE,
    STATUS_SUCCESS,
    STATUS_FAIL,
    DEFAULT_ROLE,
    ENV_USE_REMOTE_API,
    ENV_TRUE,
)
from zOS.L1_Foundation.a_zConfig.zConfig_modules import (
    SESSION_KEY_ZVISITOR,
    ZAUTH_KEY_ID,
    ZAUTH_KEY_USERNAME,
    ZAUTH_KEY_ROLE,
    ZAUTH_KEY_API_KEY,
)


class DelegateSession:  # pylint: disable=no-member
    """Mixin providing zSession authentication delegate methods.
    
    These methods provide the primary Layer 1 (zSession) authentication API,
    delegating to the Authentication module for core logic and SessionPersistence
    for persistent storage.
    
    Note:
        This is a mixin class. The authentication, session_persistence, logger,
        and zos attributes are provided by the subclass (zAuth). Pylint warnings
        about missing members are expected and suppressed.
    """

    # Layer 1: zSession Authentication Delegates

    def login(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
        server_url: Optional[str] = None,
        persist: bool = True
    ) -> Dict[str, Any]:
        """
        Authenticate a platform (zSession / Tier-1) user and persist the identity.

        Two paths, one SSOT verification:
          - Local (dev/default): verify against the user ledger via
            ``authenticate_zolo_credentials`` (same path as ``zLogin: zolo`` and
            ``zolo login``).
          - Remote (ZOLO_USE_REMOTE_API=true): delegate to the remote authority
            through ``authentication.login()``.

        On success the identity is written to session[zAuth][zSession] and, when
        ``persist`` is True, to the local identity file (zConfig.identity.zolo) —
        the git-like "already logged in" record read by the boot cascade. No
        SQLite session store is involved.

        Args:
            username: Email or username (prompted if None).
            password: Password (prompted if None).
            server_url: Optional remote authority URL (remote path only).
            persist: Persist the identity to disk (default: True).

        Returns:
            Dict: {"status": "success"|"fail", "user": {...}}
        """
        # ── Remote authority path (production) ───────────────────────────────
        if os.getenv(ENV_USE_REMOTE_API, "false").lower() == ENV_TRUE:
            result = self.authentication.login(username, password, server_url, persist)
            if result.get(KEY_STATUS) == STATUS_SUCCESS and persist:
                self._persist_zsession_identity()
            result.pop("password", None)
            result.pop("persist", None)
            return result

        # ── Local ledger path (dev / single-machine default) ─────────────────
        if not username:
            username = self.zos.display.zPrimitives.read_string("Username: ")
        if not password:
            password = self.zos.display.zPrimitives.read_password("Password: ")
        if not username or not password:
            self.zos.display.error("[FAIL] Authentication failed: missing credentials")
            return {KEY_STATUS: STATUS_FAIL}

        field = "email" if "@" in username else "username"
        role = self.authenticate_zolo_credentials({field: username, "password": password})
        if not role:
            self.zos.display.error("[FAIL] Authentication failed: invalid credentials")
            return {KEY_STATUS: STATUS_FAIL}

        zsess = self._zsession()
        if persist:
            self._persist_zsession_identity()
        self.zos.display.success(
            f"[OK] Logged in as: {zsess.get(ZAUTH_KEY_USERNAME)} ({role})"
        )
        return {
            KEY_STATUS: STATUS_SUCCESS,
            "user": {
                KEY_USERNAME: zsess.get(ZAUTH_KEY_USERNAME),
                FIELD_USER_ID: zsess.get(ZAUTH_KEY_ID),
                KEY_ROLE: role or DEFAULT_ROLE,
            },
        }

    def _zsession(self) -> Dict[str, Any]:
        """Current signed-in caller identity (session["zVisitor"], or empty)."""
        return self.session.get(SESSION_KEY_ZVISITOR, {}) or {}

    def _persist_zsession_identity(self) -> bool:
        """Write the in-memory zSession to the zOwnership file (git-like).

        NOTE (zOwnership boundary): this mirrors a RUNTIME zSession into the
        zMachine zOwnership record — the save_zownership name makes that
        cross-boundary write visible; behavior unchanged.
        """
        z = self._zsession()
        return self.save_zownership({
            "username": z.get(ZAUTH_KEY_USERNAME),
            "user_id": z.get(ZAUTH_KEY_ID),
            "role": z.get(ZAUTH_KEY_ROLE, DEFAULT_ROLE),
            "api_key": z.get(ZAUTH_KEY_API_KEY),
        })

    def logout(
        self,
        context: str = CONTEXT_ZSESSION,
        app_name: Optional[str] = None,
        delete_persistent: bool = True
    ) -> Dict[str, str]:
        """
        Clear session authentication and optionally delete persistent session.
        
        Delegates to: authentication.logout() + session_persistence cleanup
        
        Supports context-aware logout for all three authentication tiers:
        - "zSession": Logout from zSession only
        - "application": Logout from specific app (requires app_name)
        - "all_apps": Logout from all authenticated apps
        - "all": Logout from everything (zSession + all apps)
        
        Args:
            context: Authentication context to logout from (default: "zSession")
                    - "zSession": Logout zOS/Zolo user
                    - "application": Logout specific app user (requires app_name)
                    - "all_apps": Logout from all apps
                    - "all": Logout from zSession and all apps
            app_name: App name for "application" context logout (optional)
            delete_persistent: If True, delete SQLite session entry (default: True)
        
        Returns:
            Dict: {"status": "success", "cleared": ["zSession", "app1", ...]}
        
        Integration:
            - Uses zDisplay generic events for logout feedback
            - Uses zData to delete persistent session (if delete_persistent=True)
            - Clears session[SESSION_KEY_ZVISITOR] based on context
        
        Context Behavior:
            After logout, active_context is updated:
            - "zSession" logout: context → "application" (if app exists) or None
            - "application" logout: context → "zSession" (if exists) or None
            - "all" logout: context → None
        
        Examples:
            # Logout from zSession only
            zos.auth.logout()
            
            # Logout from specific app
            zos.auth.logout(context="application", app_name="my_store")
            
            # Logout from all apps but keep zSession
            zos.auth.logout(context="all_apps")
            
            # Logout from everything
            zos.auth.logout(context="all", delete_persistent=True)
        """
        self.authentication.logout(
            context=context,
            app_name=app_name,
            delete_persistent=delete_persistent
        )

        # Clear the zOwnership identity (git-like sign-out) when the zSession tier
        # is being torn down. NOTE (zOwnership boundary): a runtime logout reaching
        # into the zMachine owner record — clear_zownership makes that visible.
        if delete_persistent and context in (CONTEXT_ZSESSION, "all"):
            try:
                self.clear_zownership()
            except Exception as e:  # pylint: disable=broad-except
                self.logger.error(f"[zAuth] Error clearing zOwnership identity: {e}")

        return {KEY_STATUS: STATUS_SUCCESS}

    def status(self) -> Dict[str, Any]:
        """
        Show current authentication status for all tiers.
        
        Delegates to: authentication.status()
        
        Returns comprehensive authentication status including:
        - zSession authentication (username, role)
        - Application authentications (all apps)
        - Active context (zSession, application, dual)
        - Dual mode status
        
        Returns:
            Dict: {
                "status": "authenticated"|"not_authenticated",
                "user": {...},  # Current user based on active_context
                "zsession": {...},  # zSession auth data
                "applications": {...},  # All app auth data
                "active_context": "zSession"|"application"|"dual",
                "dual_mode": bool
            }
        
        Integration:
            - Uses zDisplay generic events for status display
            - Reads from session[SESSION_KEY_ZVISITOR]
        
        Example:
            status = zos.auth.status()
            print(f"Authenticated: {status['status']}")
            print(f"Current user: {status['user']}")
            print(f"Active context: {status['active_context']}")
        """
        return self.authentication.status()

    def is_authenticated(self) -> bool:
        """
        Check if user is currently authenticated in ANY context.
        
        Delegates to: authentication.is_authenticated()
        
        Returns True if:
        - zSession is authenticated, OR
        - At least one application is authenticated
        
        Returns:
            bool: True if authenticated in any context, False otherwise
        
        Context Awareness:
            This checks for ANY authentication. For context-specific checks,
            use get_credentials() or get_app_user(app_name).
        
        Example:
            if zos.auth.is_authenticated():
                print("User is logged in")
            else:
                print("No authentication")
        """
        return self.authentication.is_authenticated()

    def get_credentials(self) -> Optional[Dict[str, Any]]:
        """
        Get zSession credentials for the currently authenticated user.
        
        Delegates to: authentication.get_credentials()
        
        Returns zSession (Layer 1) credentials only. For application credentials,
        use get_app_user(app_name).
        
        Returns:
            Optional[Dict]: {
                "username": str,
                "user_id": str,
                "role": str
            } if authenticated, None otherwise
        
        Integration:
            - Reads from session[SESSION_KEY_ZVISITOR][ZLOBBY_KEY_ZVISITOR]
            - Returns None if not authenticated
        
        Example:
            creds = zos.auth.get_credentials()
            if creds:
                print(f"Logged in as: {creds['username']}")
                print(f"Role: {creds['role']}")
        """
        return self.authentication.get_credentials()
