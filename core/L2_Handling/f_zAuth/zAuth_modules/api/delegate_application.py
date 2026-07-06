# zOS/core/L2_Handling/d_zAuth/zAuth_modules/api/delegate_application.py

"""
Application Authentication Delegate for zAuth Facade.

This module provides Application (Layer 2) authentication delegate methods,
following zDisplay's delegate pattern for clean facade composition.

Methods:
    - authenticate_app_user: Authenticate external app user
    - switch_app: Switch active application context
    - get_app_user: Get specific app's user data

Pattern:
    All methods delegate to self.authentication module instance.
"""

from zOS import Any, Optional, Dict


class DelegateApplication:  # pylint: disable=no-member
    """Mixin providing application authentication delegate methods.
    
    These methods provide the Layer 2 (Application) authentication API,
    delegating to the Authentication module for multi-app user management.
    
    Note:
        This is a mixin class. The authentication attribute is provided by
        the subclass (zAuth). Pylint warnings about missing members are expected
        and suppressed.
    """

    # Layer 2: Application Authentication Delegates

    def authenticate_app_user(
        self,
        app_name: str,
        token: str,
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Authenticate external user for application BUILT with zOS.
        
        Delegates to: authentication.authenticate_app_user()
        
        This method handles Layer 2 (Application) authentication for end-users of apps
        BUILT with zOS. Each app maintains independent user identities and
        credentials. Multiple apps can be authenticated simultaneously.
        
        Args:
            app_name: Application identifier (e.g., "my_store", "admin_panel")
            token: Application-specific authentication token
            config: Optional authentication configuration
                   {"auth_endpoint": str, "verify_ssl": bool, ...}
        
        Returns:
            Dict: {
                "status": "success"|"fail",
                "user": {
                    "user_id": str,
                    "role": str,
                    "username": str (optional),
                    ...app-specific fields...
                },
                "app_name": str
            }
        
        Integration:
            - Uses zComm for remote app authentication (comm_http.py)
            - Updates session[SESSION_KEY_ZVISITOR][ZAUTH_KEY_APPLICATIONS][app_name]
            - If zSession also authenticated, sets dual_mode = True
        
        Context Behavior:
            After successful app authentication:
            - If zSession also authenticated: active_context → "dual"
            - If zSession not authenticated: active_context → "application"
        
        Example:
            # Authenticate store customer
            result = zos.auth.authenticate_app_user(
                app_name="my_store",
                token="customer_token_123",
                config={"auth_endpoint": "https://store.com/api/auth"}
            )
            
            if result["status"] == "success":
                print(f"App user: {result['user']['user_id']}")
        """
        return self.authentication.authenticate_app_user(app_name, token, config)

    def switch_app(self, app_name: str) -> bool:
        """
        Switch active application context.
        
        Delegates to: authentication.switch_app()
        
        Changes the active_context to focus on a specific authenticated app.
        The app must already be authenticated via authenticate_app_user().
        
        Args:
            app_name: Application name to switch to
        
        Returns:
            bool: True if switch successful, False if app not authenticated
        
        Integration:
            - Updates session[SESSION_KEY_ZVISITOR][ZAUTH_KEY_ACTIVE_CONTEXT]
            - RBAC checks will now use this app's user for role/permission checks
        
        Example:
            # Authenticate multiple apps
            zos.auth.authenticate_app_user("store", token1, config1)
            zos.auth.authenticate_app_user("admin", token2, config2)
            
            # Switch between apps
            zos.auth.switch_app("store")
            # RBAC now checks store user's roles
            
            zos.auth.switch_app("admin")
            # RBAC now checks admin user's roles
        """
        return self.authentication.switch_app(app_name)

    def get_app_user(self, app_name: str) -> Optional[Dict[str, Any]]:
        """
        Get authentication data for a specific application.
        
        Delegates to: authentication.get_app_user()
        
        Returns the authenticated user data for the specified app.
        Returns None if the app is not currently authenticated.
        
        Args:
            app_name: Application name to get user data for
        
        Returns:
            Optional[Dict]: {
                "user_id": str,
                "role": str,
                "username": str (optional),
                ...app-specific fields...
            }
            Returns None if app not authenticated.
        
        Integration:
            - Reads from session[SESSION_KEY_ZVISITOR][ZAUTH_KEY_APPLICATIONS][app_name]
        
        Example:
            store_user = zos.auth.get_app_user("my_store")
            if store_user:
                print(f"Store user: {store_user['user_id']}")
                print(f"Store role: {store_user['role']}")
            else:
                print("Not authenticated with store")
        """
        return self.authentication.get_app_user(app_name)
