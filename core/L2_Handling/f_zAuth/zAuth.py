# zOS/core/L2_Core/d_zAuth/zAuth.py
"""
zAuth - Three-Tier Authentication Facade (v1.5.4+)

Facade Pattern orchestrating 3 modules: PasswordSecurity, Authentication, RBAC.
Provides unified API for bcrypt passwords, three-tier auth (zSession/Application/
Dual), and context-aware RBAC. The zOS instance OWNER (zOwnership) persists git-like
to a local config file (zConfig.identity.zolo) via persistence.zownership_store —
SEPARATE from the runtime session, no SQLite session DB.

THREE-TIER MODEL
  Tier 1 (zSession): Internal zOS/Zolo users -> login/logout/is_authenticated/
                     get_credentials/status
  Tier 2 (Application): External app users -> authenticate_app_user/switch_app/
                        get_app_user (multi-app simultaneous auth supported)
  Tier 3 (Dual): Both contexts active -> set_active_context/get_active_user
                 (RBAC uses OR logic)

DELEGATION (18 methods via zAuthDelegates mixins)
  Password: hash_password, verify_password -> password_security
  Session: login, logout, status, is_authenticated, get_credentials -> authentication
  App: authenticate_app_user, switch_app, get_app_user -> authentication
  Context: set_active_context, get_active_user -> authentication
  RBAC: has_role, is_authenticated_in_context, get_current_role -> rbac

MODULE RESPONSIBILITIES
  PasswordSecurity: bcrypt (12 rounds), timing-safe verification, 72-byte truncation
  zownership_store: persist/read/clear the zOwnership identity (zConfig.identity.zolo)
  Authentication: Three-tier logic, multi-app, remote auth (zComm), zDisplay UI
  RBAC: Context-aware roles/permissions, dual-mode OR logic, SQLite persistence

INTEGRATION: zConfig (constants), zDisplay (UI), zComm (remote), zData (storage),
             zWizard (RBAC)

EXAMPLES
  # Basic: zos.auth.login("user@zolo.com", "pass"); zos.auth.has_role("admin")
  # Multi-app: zos.auth.authenticate_app_user("store", token, config)
  # Dual: zos.auth.set_active_context("dual")  # RBAC checks both contexts

THREAD SAFETY: NOT thread-safe. Each thread needs own zOS instance.
               Multi-app auth within single session is fully supported.
"""


__version__ = "1.0.0"
from zOS import Any, Optional, Dict
from zOS.L1_Foundation.a_zConfig.zConfig_modules.config_constants import SESSION_KEY_ZVISITOR

from .zAuth_modules import PasswordSecurity, Authentication, RBAC
from .zAuth_modules.auth_delegates import zAuthDelegates
from .zAuth_modules.auth_constants import (
    DEFAULT_ROLE,
)

# Module-specific constants
COLOR_ZAUTH: str = "ZAUTH"
MSG_READY: str = "zAuth Ready"


class zAuth(zAuthDelegates):
    """
    Authentication Facade - Three-Tier Auth System (v1.5.4+)
    
    Orchestrates 3 modules (PasswordSecurity, Authentication, RBAC) via Facade
    Pattern. Inherits 16 public methods from zAuthDelegates mixins.
    
    Modules: password_security, authentication, rbac
    Methods: See zAuthDelegates (api/delegate_*.py) - Password(2), Session(5), 
             Application(3), Context(2), RBAC(6)
    Integration: zConfig (constants), zDisplay (UI), zComm (remote), zData (storage)
    Thread Safety: NOT thread-safe (use separate zOS per thread)
    
    BREAKING (v1.5.4): bcrypt only, no plaintext passwords
    """

    # Class-level type declarations
    zos: Any
    session: Dict[str, Any]
    logger: Any
    mycolor: str
    password_security: PasswordSecurity
    authentication: Authentication
    rbac: RBAC

    @property
    def session(self):
        """Live per-caller session — resolves via the live holder (§19 Phase 2)."""
        return self.zos.session

    def __init__(self, zos: Any) -> None:
        """Initialize auth modules (password_security, authentication, rbac)."""
        self.zos = zos
        self.logger = zos.logger
        self.mycolor = COLOR_ZAUTH  # Orange-brown bg (Authentication)

        # Initialize modular components (all require zos instance)
        self.password_security = PasswordSecurity(logger=self.logger)
        self.authentication = Authentication(zos)
        self.rbac = RBAC(zos)

        # Display ready message via zDisplay facade
        self.zos.display.zDeclare(MSG_READY, color=self.mycolor, indent=0, style="full")

        # Note: Database initialization is deferred until after zParser/zLoader are ready
        # Will be called automatically on first use (lazy initialization)


    # ════════════════════════════════════════════════════════════════════════════
    # BOOT IDENTITY (Tier-1 cascade)
    # ════════════════════════════════════════════════════════════════════════════

    def resolve_boot_identity(self) -> Dict[str, Any]:
        """Resolve the runtime's platform (Tier-1 / zSession) identity at boot.

        Precedence cascade (most-secure → least): persistent session token →
        environment (ZOLO_USER/ZOLO_PASSWORD) → zSpark policy (zGuest /
        auth: required). Auth logic lives in zAuth; zConfig only surfaces the
        raw sources. Returns a status dict and never raises. See
        zAuth_modules.logic.authentication.boot_identity.
        """
        from .zAuth_modules.logic.authentication.boot_identity import resolve_boot_identity
        return resolve_boot_identity(self.zos)

    # ════════════════════════════════════════════════════════════════════════════
    # TRUST WATERMARK (instance-level — zOS License §3.2, the visible identity half)
    # ════════════════════════════════════════════════════════════════════════════

    def instance_registered(self) -> bool:
        """True when this instance has a verifiable OWNER identity (watermark OFF).

        Reads the persistent/env owner WITHOUT mutating the session — distinct
        from the per-connection web session, which stays anonymous in server mode
        (multi-tenant). Verdict + mark are sealed in zGuard; no-op without it. See
        zAuth_modules.logic.authentication.watermark.
        """
        from .zAuth_modules.logic.authentication.watermark import is_registered
        return is_registered(self.zos)

    def watermark_html(self) -> str:
        """Served-page trust-watermark badge for an unregistered instance
        (``""`` when registered). Emitted by zGuard (sealed); no-op without it."""
        from .zAuth_modules.logic.authentication.watermark import watermark_html
        return watermark_html(self.zos)

    def watermark_banner(self) -> str:
        """CLI boot-banner trust-watermark line for an unregistered instance
        (``""`` when registered). Emitted by zGuard (sealed); no-op without it."""
        from .zAuth_modules.logic.authentication.watermark import watermark_banner
        return watermark_banner(self.zos)

    # ════════════════════════════════════════════════════════════════════════════
    # API KEYS (Personal Access Tokens — non-interactive Tier-1 auth)
    # ════════════════════════════════════════════════════════════════════════════

    # ════════════════════════════════════════════════════════════════════════════
    # MACHINE IDENTITY (Tier-1 persistence — git/ssh-style, zConfig.identity.zolo)
    # ════════════════════════════════════════════════════════════════════════════

    def save_zownership(self, identity: Dict[str, Any]) -> bool:
        """Persist the zOS instance OWNER to the local config dir
        (zConfig.identity.zolo). The git-like 'this machine is owned by X' record.
        zOwnership is SEPARATE from the runtime session — never poured into it."""
        from .zAuth_modules.persistence.zownership_store import save_zownership
        return save_zownership(self.zos, identity)

    def load_zownership(self) -> Optional[Dict[str, Any]]:
        """Read the persisted zOwnership identity (or None if no owner)."""
        from .zAuth_modules.persistence.zownership_store import load_zownership
        return load_zownership(self.zos)

    def clear_zownership(self) -> bool:
        """Remove the persisted zOwnership identity (sign out the owner)."""
        from .zAuth_modules.persistence.zownership_store import clear_zownership
        return clear_zownership(self.zos)

    def authenticate_zolo_credentials(
        self, credentials: Dict[str, Any], model: Optional[str] = None
    ) -> Optional[str]:
        """Headless Tier-1 (zSession) sign-in against the user ledger.

        Verify ``credentials`` ({email|username, password}) and, on success, write
        the platform identity into session[zAuth][zSession]. Returns the resolved
        role, or None on failure. The SSOT verification path shared with the
        declarative ``zLogin: zolo`` handler — used by `zolo login` and the boot
        cascade. No display side-effects.
        """
        from .zAuth_modules.actions.action_login import authenticate_zolo_credentials
        return authenticate_zolo_credentials(credentials, self.zos, model)

    def issue_api_key(self, identity: str, model: Optional[str] = None) -> Optional[str]:
        """Mint a revocable PAT for a user (by email/username). Stores sha256(token)
        in the ledger and returns the plaintext ONCE (None if no such user)."""
        from .zAuth_modules.logic.authentication.api_key_auth import issue_api_key
        return issue_api_key(self.zos, identity, model)

    def verify_api_key(self, token: str, model: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Return the user row whose stored api_key matches sha256(token), else None."""
        from .zAuth_modules.logic.authentication.api_key_auth import verify_api_key
        return verify_api_key(self.zos, token, model)

    def authenticate_api_key(self, token: str, model: Optional[str] = None) -> Optional[str]:
        """Verify a PAT and establish the Tier-1 zSession (headless). Returns role/None."""
        from .zAuth_modules.logic.authentication.api_key_auth import authenticate_api_key
        return authenticate_api_key(self.zos, token, model)

    def revoke_api_key(self, identity: str, model: Optional[str] = None) -> bool:
        """Revoke a user's PAT (clear the stored hash). Returns False if no such user."""
        from .zAuth_modules.logic.authentication.api_key_auth import revoke_api_key
        return revoke_api_key(self.zos, identity, model)

    # ════════════════════════════════════════════════════════════════════════════
    # PUBLIC API METHODS (Delegated to zAuthDelegates mixins)
    # ════════════════════════════════════════════════════════════════════════════

    # All public API methods (16 total) are now provided by zAuthDelegates
    # mixins via multiple inheritance. See zAuth_modules/auth_delegates.py for
    # the complete implementation and individual delegate modules in zAuth_modules/api/.
    #
    # From DelegatePassword (2 methods):
    #   - hash_password(plain_password) -> str
    #   - verify_password(plain_password, hashed_password) -> bool
    #
    # From DelegateSession (5 methods):
    #   - login(username, password, server_url, persist) -> Dict
    #   - logout(context, app_name, delete_persistent) -> Dict
    #   - status() -> Dict
    #   - is_authenticated() -> bool
    #   - get_credentials() -> Optional[Dict]
    #
    # From DelegateApplication (3 methods):
    #   - authenticate_app_user(app_name, token, config) -> Dict
    #   - switch_app(app_name) -> bool
    #   - get_app_user(app_name) -> Optional[Dict]
    #
    # From DelegateContext (2 methods):
    #   - set_active_context(context) -> bool
    #   - get_active_user() -> Optional[Dict]
    #
    # From DelegateRBAC (1 method):
    #   - has_role(required_role) -> bool

    # ════════════════════════════════════════════════════════════════════════════
    # DEPRECATED METHODS (Backwards Compatibility)
    # ════════════════════════════════════════════════════════════════════════════

    def _authenticate_remote(self, username: str, password: str, server_url: Optional[str] = None) -> Dict[str, Any]:
        """DEPRECATED v1.5.4 - v1.6.0: Use authentication.authenticate_remote(username, password, server_url)"""
        return self.authentication.authenticate_remote(username, password, server_url)
