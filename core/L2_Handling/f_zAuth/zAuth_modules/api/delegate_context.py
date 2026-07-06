# zOS/core/L2_Handling/d_zAuth/zAuth_modules/api/delegate_context.py

"""
Context Management Delegate for zAuth Facade.

This module provides authentication context switching delegate methods,
following zDisplay's delegate pattern for clean facade composition.

Methods:
    - set_active_context: Switch between zSession, application, or dual contexts
    - get_active_user: Get current user based on active context

Pattern:
    All methods delegate to self.authentication module instance.
"""

from zOS import Any, Optional, Dict


class DelegateContext:  # pylint: disable=no-member
    """Mixin providing context management delegate methods.
    
    These methods provide context switching for the three-tier authentication
    system, delegating to the Authentication module for context management.
    
    Note:
        This is a mixin class. The authentication attribute is provided by
        the subclass (zAuth). Pylint warnings about missing members are expected
        and suppressed.
    """

    # Context Management Delegates

    def set_active_context(self, context: str) -> bool:
        """
        Set the active authentication context (zSession, application, or dual).
        
        Delegates to: authentication.set_active_context()
        
        Controls which authentication tier is considered "active" for RBAC checks
        and get_active_user() calls. In dual mode, RBAC uses OR logic (either
        context can grant access).
        
        Args:
            context: Context to activate
                    - "zSession": Use zSession auth for RBAC
                    - "application": Use app auth for RBAC (requires authenticated app)
                    - "dual": Use both (OR logic - either can grant access)
        
        Returns:
            bool: True if context set successfully, False if requested context unavailable
                 (e.g., trying to set "application" when no apps authenticated)
        
        Integration:
            - Updates session[SESSION_KEY_ZVISITOR][ZAUTH_KEY_ACTIVE_CONTEXT]
            - Updates session[SESSION_KEY_ZVISITOR][ZAUTH_KEY_DUAL_MODE] for "dual"
            - Affects RBAC checks (rbac.has_role / rbac.check_zrbac)
        
        RBAC Behavior:
            - "zSession": Only zSession user's role checked
            - "application": Only active app user's role checked
            - "dual": BOTH checked with OR logic (either grants access)
        
        Example:
            # Login as Zolo user
            zos.auth.login("admin@zolo.com", "password")
            
            # Authenticate as store owner
            zos.auth.authenticate_app_user("store", "owner_token", config)
            
            # Set dual mode (both contexts active)
            zos.auth.set_active_context("dual")
            
            # RBAC now checks both contexts with OR logic
            if zos.auth.has_role("admin"):  # True if admin in EITHER context
                print("Admin access granted")
        """
        return self.authentication.set_active_context(context)

    def get_active_user(self) -> Optional[Dict[str, Any]]:
        """
        Get the currently active user based on active_context.
        
        Delegates to: authentication.get_active_user()
        
        Returns the user data for the currently active authentication context:
        - "zSession": Returns zSession user
        - "application": Returns active app user
        - "dual": Returns zSession user (by convention)
        
        Returns:
            Optional[Dict]: Current active user data, or None if not authenticated
                          Structure depends on active_context:
                          - zSession: {"username", "user_id", "role", ...}
                          - application: {"user_id", "role", ...app-specific...}
        
        Integration:
            - Reads from session[SESSION_KEY_ZVISITOR] based on active_context
        
        Example:
            zos.auth.set_active_context("application")
            user = zos.auth.get_active_user()
            print(f"Active user: {user['user_id']}")
            
            zos.auth.set_active_context("zSession")
            user = zos.auth.get_active_user()
            print(f"Active user: {user['username']}")
        """
        return self.authentication.get_active_user()
