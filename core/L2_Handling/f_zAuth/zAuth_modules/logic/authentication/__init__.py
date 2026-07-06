"""
Authentication Facade - Maintains backward compatibility

This facade delegates to specialized manager classes while preserving the
original Authentication class interface.
"""

from zOS import Any, Dict, Optional

from .remote_authentication import RemoteAuthenticationManager
from .login_manager import LoginManager
from .logout_manager import LogoutManager
from .context_manager import ContextManager
from .credential_manager import CredentialManager
from .app_authentication import AppAuthenticationManager


class Authentication:
    """
    CORE authentication module implementing three-tier authentication model.
    
    This is a facade class that delegates to specialized managers:
    - RemoteAuthenticationManager: Remote API authentication
    - LoginManager: zSession login operations
    - LogoutManager: Logout operations across contexts
    - ContextManager: Context switching and state
    - CredentialManager: Credential queries
    - AppAuthenticationManager: Application user authentication
    
    Maintains full backward compatibility with the original monolithic class.
    """
    
    zos: Any
    session: Dict[str, Any]
    logger: Any
    
    @property
    def session(self):
        """Live per-caller session — resolves via the live holder (§19 Phase 2)."""
        return self.zos.session

    def __init__(self, zos: Any) -> None:
        """Initialize authentication module with manager delegation."""
        self.zos = zos
        self.logger = zos.logger
        
        # Initialize managers (order matters for dependencies)
        self._context_manager = ContextManager(zos)
        self._credential_manager = CredentialManager(zos)
        self._remote_auth_manager = RemoteAuthenticationManager(zos)
        self._login_manager = LoginManager(zos, self._remote_auth_manager, self._context_manager)
        self._logout_manager = LogoutManager(zos, self._credential_manager)
        self._app_auth_manager = AppAuthenticationManager(zos, self._context_manager)
    
    # =========================================================================
    # PUBLIC API - Delegated to managers
    # =========================================================================
    
    # Layer 1: zSession Authentication
    def login(self, username: Optional[str] = None, password: Optional[str] = None,
              server_url: Optional[str] = None, persist: bool = True) -> Dict[str, Any]:
        """Authenticate zOS/Zolo user to zSession context."""
        return self._login_manager.login(username, password, server_url, persist)
    
    def logout(self, context: str = "zSession", app_name: Optional[str] = None,
               delete_persistent: bool = False) -> Dict[str, Any]:
        """Clear session authentication (context-aware)."""
        return self._logout_manager.logout(context, app_name, delete_persistent)
    
    def status(self) -> Dict[str, Any]:
        """Show current zSession authentication status."""
        return self._credential_manager.status()
    
    def is_authenticated(self) -> bool:
        """Check if user is currently authenticated in ANY context."""
        return self._credential_manager.is_authenticated()
    
    def get_credentials(self) -> Optional[Dict[str, Any]]:
        """Get current zSession authentication data."""
        return self._credential_manager.get_credentials()
    
    # Application Authentication (degenerate — single signed-in identity).
    # The multi-app surface is retained for callers (e.g. bifrost token auth) but
    # now writes/reads the one session["zVisitor"]; app_name is informational only.
    def authenticate_app_user(self, app_name: str, token: str,
                               config: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Authenticate the caller via token → writes the single zVisitor identity."""
        return self._app_auth_manager.authenticate_app_user(app_name, token, config)

    def get_app_user(self, app_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Return the single signed-in identity (app_name ignored)."""
        return self._context_manager.get_active_user()

    def switch_app(self, app_name: str) -> bool:
        """No-op: single identity, nothing to switch to."""
        return True

    # Context Management — single identity, no contexts to switch.
    def set_active_context(self, context: str) -> bool:
        """No-op: single identity, no active-context concept."""
        return True

    def get_active_user(self) -> Optional[Dict[str, Any]]:
        """Get the single signed-in caller identity."""
        return self._context_manager.get_active_user()
    
    # Remote Authentication
    def authenticate_remote(self, username: str, password: str,
                            server_url: Optional[str] = None) -> Dict[str, Any]:
        """Authenticate via Flask API (remote server)."""
        return self._remote_auth_manager.authenticate_remote(username, password, server_url)


__all__ = ['Authentication']
