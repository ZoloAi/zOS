# zOS/core/L2_Handling/d_zAuth/zAuth_modules/auth_delegates.py

"""
zAuth Delegate Composition - Primary User-Facing API

This module provides the main interface for all authentication operations in the
zOS framework. The delegate methods are the PRIMARY way to interact with zAuth,
following the proven pattern established by zDisplay.

Architecture:
    zAuthDelegates uses the Mixin pattern to compose the zAuth public API from
    multiple focused delegate classes, each in its own module under api/:
    
    - DelegatePassword: 2 methods (password hashing/verification)
    - DelegateSession: 5 methods (login/logout/status/is_authenticated/get_credentials)
    - DelegateApplication: 3 methods (multi-app authentication)
    - DelegateContext: 2 methods (context switching)
    - DelegateRBAC: 4 methods (role/permission checks)
    
    This separation allows:
    - Clean main zAuth class focused on core orchestration
    - Optimal file sizes (each delegate ~80-220 lines)
    - Clear single responsibility per module
    - Easy addition/removal of API methods
    - Perfect pattern consistency with zDisplay architecture

Delegation Chain:
    Every method in the delegate classes follows a clear delegation pattern:
    
    1. User calls delegate:     zos.auth.login("user", "pass")
    2. Delegate routes:         DelegateSession.login()
    3. Calls core module:       self.authentication.login()
    4. Core module executes:    Authentication class logic
    5. Returns result:          Dict with status and user data
    
    Key Point: Delegates are thin wrappers that provide clean public API
    while keeping the actual business logic in logic/ modules.

Method Categories:
    The delegate methods are organized into 5 logical categories:

    1. Password Security (2): hash_password, verify_password
    2. Session Auth (5): login, logout, status, is_authenticated, get_credentials
    3. Application Auth (3): authenticate_app_user, switch_app, get_app_user
    4. Context Management (2): set_active_context, get_active_user
    5. RBAC (2): has_role, check_zrbac

    These delegate methods provide the primary user API.

Usage Pattern:
    ```python
    # Throughout zOS subsystems:
    zos.auth.login("user@zolo.com", "password")
    zos.auth.has_role("admin")
    zos.auth.authenticate_app_user("store", "token", config)
    zos.auth.set_active_context("dual")
    ```

Mixin Pattern Notes:
    This is a mixin class designed to be inherited by zAuth. It does not
    initialize any state and relies entirely on the parent class's module
    instances (password_security, authentication, rbac). Linter warnings about
    missing members are expected and safe to ignore.

Industry-Grade Refactoring:
    This delegate pattern was successfully proven in zDisplay, where it:
    - Reduced main file from monolithic to focused core
    - Organized 25 methods into 5 focused delegates
    - Improved maintainability and navigation
    - Provided clear extension points
    
    The same pattern is now applied to zAuth for consistency across L2 subsystems.
"""

from .api import (
    DelegatePassword,
    DelegateSession,
    DelegateApplication,
    DelegateContext,
    DelegateRBAC
)


class zAuthDelegates(
    DelegatePassword,
    DelegateSession,
    DelegateApplication,
    DelegateContext,
    DelegateRBAC
):
    """Mixin class providing primary user-facing API for zAuth.
    
    This class composes all delegate categories using multiple inheritance:
    - DelegatePassword: 2 methods (password hashing/verification)
    - DelegateSession: 5 methods (zSession authentication)
    - DelegateApplication: 3 methods (multi-app authentication)
    - DelegateContext: 2 methods (context switching)
    - DelegateRBAC: 4 methods (role/permission checks)
    
    All methods are thin wrappers that delegate to appropriate core modules:
    - password_security: PasswordSecurity instance
    - authentication: Authentication instance
    - rbac: RBAC instance
    
    These module instances are initialized by the zAuth class and accessed
    via self.* in each delegate method.
    
    Public API Surface (16 methods):
        Password Security:
            - hash_password(plain_password) → str
            - verify_password(plain_password, hashed) → bool
        
        zSession Authentication:
            - login(username, password, server_url, persist) → Dict
            - logout(context, app_name, delete_persistent) → Dict
            - status() → Dict
            - is_authenticated() → bool
            - get_credentials() → Optional[Dict]
        
        Application Authentication:
            - authenticate_app_user(app_name, token, config) → Dict
            - switch_app(app_name) → bool
            - get_app_user(app_name) → Optional[Dict]
        
        Context Management:
            - set_active_context(context) → bool
            - get_active_user() → Optional[Dict]
        
        RBAC:
            - has_role(required_role) → bool
            - check_zrbac(rbac) → (granted: bool, reason: Optional[str])
    
    Pattern follows zDisplay's zDisplayDelegates architecture for consistency.
    """
    pass  # All methods provided by mixin classes
