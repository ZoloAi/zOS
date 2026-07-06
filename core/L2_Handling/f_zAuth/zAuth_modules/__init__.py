"""
zAuth Modules Package - Modular Three-Tier Authentication System (v1.5.4+)

PACKAGE OVERVIEW

This package contains the four core modules that implement zOS's sophisticated
three-tier authentication system. Each module is designed with clear separation
of concerns and follows the Facade pattern, exposing clean APIs while hiding
implementation complexity.

MODULE ARCHITECTURE

The package follows a layered directory structure with clear dependency hierarchy:

    security/                          # Layer 1: Security Primitives
        password_security.py
        └── Provides: bcrypt password hashing and verification
        └── Dependencies: None (foundation)
        └── Used by: persistence/

    persistence/                       # Layer 2: Data Persistence
        session_persistence.py
        └── Provides: SQLite-based persistent session management
        └── Dependencies: security/password_security
        └── Used by: core/ (indirectly via zAuth facade)

    core/                              # Layer 3: Core Authentication Logic
        authentication.py (CORE)
        └── Provides: Three-tier authentication (zSession, Application, Dual)
        └── Dependencies: security/ (indirectly), zConfig, zDisplay, zComm
        └── Used by: zAuth.py (facade), actions/

        rbac.py
        └── Provides: Context-aware Role-Based Access Control
        └── Dependencies: zConfig (for session/auth constants)
        └── Used by: zAuth.py (facade), zWizard (for access control)

    actions/                           # Layer 3: Declarative Actions
        action_login.py, action_logout.py
        └── Provides: Built-in zLogin and zLogout action handlers
        └── Dependencies: logic/authentication
        └── Used by: zDispatch, zBifrost (for declarative auth)

MODULE DESCRIPTIONS

**security/password_security.py** (PasswordSecurity class):
    Purpose:
        - Secure password hashing using bcrypt algorithm
        - Password verification with timing-safe comparison
        - Handles 72-byte bcrypt limit with truncation and logging
    
    Key Features:
        - Bcrypt with 12 rounds (2^12 = 4096 iterations)
        - Random salting (built into bcrypt)
        - Timing-safe comparison (prevents timing attacks)
        - Optional logging integration
    
    API:
        - hash_password(password: str) -> str
        - verify_password(password: str, hashed: str) -> bool

**persistence/session_persistence.py** (SessionPersistence class):
    Purpose:
        - Persistent session storage using SQLite database
        - 7-day session expiry with automatic cleanup
        - Integration with zData subsystem for database operations
    
    Key Features:
        - Declarative zData operations (no raw SQL)
        - Session tokens generated with secrets.token_urlsafe()
        - Automatic password hashing via PasswordSecurity
        - Session cleanup on login/logout
    
    API:
        - ensure_sessions_db() -> bool
        - load_session(identifier: str, identifier_type: str) -> Optional[Dict]
        - save_session(auth_data: Dict, password: str) -> bool
        - cleanup_expired() -> int

**logic/authentication.py** (Authentication class) - CORE:
    Purpose:
        - CORE three-tier authentication implementation
        - zSession Auth (Internal zOS/Zolo users)
        - Application Auth (External users of zOS-built apps)
        - Dual-Mode Auth (Both contexts active simultaneously)
    
    Key Features:
        - Multi-app simultaneous authentication
        - Context-aware session management (active_context)
        - Local and remote authentication (via zComm)
        - Integration with zDisplay for all UI feedback
        - 100% SESSION_KEY_ZVISITOR modernization (64 replacements)
    
    API:
        Layer 1 (zSession):
            - login(username, password, server_url, persist) -> Dict
            - logout(context, app_name, delete_persistent) -> Dict
            - status() -> Dict
            - is_authenticated() -> bool
            - get_credentials() -> Optional[Dict]
        
        Layer 2 (Application):
            - authenticate_app_user(app_name, token, config) -> Dict
            - switch_app(app_name) -> bool
            - get_app_user(app_name) -> Optional[Dict]
        
        Context Management:
            - set_active_context(context) -> bool
            - get_active_user() -> Optional[Dict]
        
        Remote:
            - authenticate_remote(username, password, server_url) -> Dict

**logic/rbac.py** (RBAC class):
    Purpose:
        - Context-aware Role-Based Access Control
        - Supports all three authentication tiers (zSession, Application, Dual)
        - Dynamic role/permission checks based on active_context
        - Dual-mode uses OR logic (either context can grant access)
    
    Key Features:
        - Context-aware role checks (_get_current_role helper)
        - Dual-mode OR logic (_check_role_match helper)
        - Flask-style: session-only, exact role match, no permissions/schema reads

    API:
        - has_role(role: Union[str, List[str]]) -> bool
        - check_zrbac(rbac: dict) -> (granted: bool, reason: Optional[str])

THREE-TIER AUTHENTICATION MODEL

This package implements zOS's three-tier authentication model:

**Tier 1 - zSession Authentication (Internal Users):**
    - Authenticates zOS/Zolo platform users
    - Used for premium features, plugins, cloud services
    - Session key: session[SESSION_KEY_ZVISITOR][ZLOBBY_KEY_ZVISITOR]

**Tier 2 - Application Authentication (External Users):**
    - Authenticates end-users of applications BUILT with zOS
    - Each app maintains independent user database and credentials
    - Multi-app support: Multiple simultaneous authentications
    - Session key: session[SESSION_KEY_ZVISITOR][ZAUTH_KEY_APPLICATIONS][app_name]

**Tier 3 - Dual-Mode Authentication (Both Contexts):**
    - Both zSession AND application authenticated simultaneously
    - Example: Store owner analyzing their store (zOS user + store user)
    - RBAC uses OR logic: Either context can grant access
    - Session key: session[SESSION_KEY_ZVISITOR][ZAUTH_KEY_DUAL_MODE] = True

INTEGRATION WITH ZOS SUBSYSTEMS

**zConfig (config_session.py):**
    - Provides all session/auth constants:
      SESSION_KEY_ZVISITOR, ZAUTH_KEY_*, CONTEXT_*
    - Maintains consistent session structure across subsystems
    - All modules import constants from zConfig (Week 6.2)

**zDisplay:**
    - All authentication feedback uses generic zDisplay events
    - Methods: success(), error(), warning(), text(), header()
    - Dual-mode compatible (Terminal + Bifrost)

**zComm (comm_http.py):**
    - Remote authentication uses zComm.http_post() for API calls
    - Secure HTTPS communication with Zolo authentication server

**zData (data_operations.py):**
    - Session persistence uses declarative zData operations
    - No raw SQL - all operations go through zData subsystem

**zWizard (wizard.py):**
    - RBAC integration: checkzRBAC_access() delegates to auth.check_zrbac
    - Access control for all zVaF menu items
    - Supports zGuest, require_auth, require_role (authenticated alias)

USAGE EXAMPLE

    from zOS.L2_Handling.f_zAuth.zAuth_modules import (
        PasswordSecurity,
        SessionPersistence,
        Authentication,
        RBAC
    )

    # Example 1: Password hashing
    pwd_security = PasswordSecurity(logger=zos.logger)
    hashed = pwd_security.hash_password("my_password")
    is_valid = pwd_security.verify_password("my_password", hashed)

    # Example 2: Session persistence
    session_mgr = SessionPersistence(zos, session_duration_days=7)
    session_mgr.ensure_sessions_db()
    session_data = session_mgr.load_session("user@example.com", "username")
    
    # Example 3: Three-tier authentication
    auth = Authentication(zos)
    
    # zSession authentication (Tier 1)
    result = auth.login("user@zolo.com", "password")
    
    # Application authentication (Tier 2)
    result = auth.authenticate_app_user("my_store", "token", config)
    
    # Context switching
    auth.set_active_context("dual")  # Tier 3
    
    # Example 4: RBAC
    rbac = RBAC(zos)

    if rbac.has_role("admin"):
        print("User is admin")

    granted, reason = rbac.check_zrbac({"require_role": "admin"})

THREAD SAFETY

All modules operate on the zOS session object, which is NOT thread-safe by design.
Each zOS instance maintains a single session dictionary.

For multi-threaded applications:
- Each thread should use its own zOS instance
- Multi-app authentication within a SINGLE session is fully supported and isolated
"""

# Package Metadata
__version__ = "1.5.4"
__author__ = "Zolo"
__description__ = "Modular three-tier authentication system for zOS framework"

# Module Imports (Dependency Order)

# Layer 0: Constants (Foundation)
from .auth_constants import *  # Centralized constants for all auth modules

# Layer 0.5: Session Access Helpers (single signed-in identity)
from .auth_helpers import (
    get_zvisitor,
    get_zsession_data,  # deprecated alias of get_zvisitor
)

# Layer 1: Foundation (Password Security)
from .security.password_security import PasswordSecurity  # bcrypt hashing/verification

# Layer 2: zOwnership (instance-owner identity at rest — git-like, file-based,
# SEPARATE from the runtime session)
from .persistence.zownership_store import (  # zConfig.identity.zolo read/write/clear
    save_zownership,
    load_zownership,
    clear_zownership,
)

# Layer 3: Authentication Logic (Authentication + RBAC)
from .logic.authentication import Authentication  # Three-tier auth (zSession, App, Dual)
from .logic.rbac import RBAC  # Context-aware Role-Based Access Control

# Layer 4: API Delegates (Public Facade Methods)
from .auth_delegates import zAuthDelegates  # Composed delegate mixins for zAuth facade

# Layer 3: Built-in Actions (zLogin, zLogout)
from .actions.action_login import handle_zLogin    # Built-in declarative login action
from .actions.action_logout import handle_zLogout  # Built-in declarative logout action

# Public API Exports
__all__ = [
    'PasswordSecurity',      # Layer 1: bcrypt password hashing and verification
    'save_zownership',       # Layer 2: persist zOwnership identity (zConfig.identity.zolo)
    'load_zownership',       # Layer 2: read persisted zOwnership identity
    'clear_zownership',      # Layer 2: clear persisted zOwnership identity
    'Authentication',        # Layer 3: CORE three-tier authentication implementation
    'RBAC',                  # Layer 3: Context-aware Role-Based Access Control
    'zAuthDelegates',        # Layer 4: API delegate composition for zAuth facade
    'handle_zLogin',         # Layer 3: Built-in declarative login action
    'handle_zLogout'         # Layer 3: Built-in declarative logout action
]
