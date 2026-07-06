"""
Credential Manager - Handles credential queries

Extracted from monolithic Authentication class for better separation of concerns.
"""

from zOS import Dict, Optional, Any
from zOS.L1_Foundation.a_zConfig.zConfig_modules import (
    ZAUTH_KEY_AUTHENTICATED,
    ZAUTH_KEY_ID,
    ZAUTH_KEY_USERNAME,
    ZAUTH_KEY_ROLE,
    ZAUTH_KEY_API_KEY,
)

from ...auth_constants import (
    KEY_STATUS,
    _MSG_NOT_AUTHENTICATED,
)

from ...auth_helpers import get_zvisitor

class CredentialManager:
    """Manages credential queries and authentication status."""

    @property
    def session(self):
        """Live per-caller session — resolves via the live holder (§19 Phase 2)."""
        return self.zos.session

    def __init__(self, zos: Any) -> None:
        """Initialize with zOS instance."""
        self.zos = zos
    def _check_session(self) -> bool:
        """Validate that session exists."""
        return self.session is not None

    def _create_status_response(self, status: str, **kwargs: Any) -> Dict[str, Any]:
        """Create standardized status response dictionary."""
        response = {KEY_STATUS: status}
        response.update(kwargs)
        return response

    def is_authenticated(self) -> bool:
        """Check if the single signed-in caller is authenticated."""
        if not self._check_session():
            return False

        visitor = get_zvisitor(self.session)
        return bool(
            visitor.get(ZAUTH_KEY_AUTHENTICATED, False)
            and visitor.get(ZAUTH_KEY_USERNAME) is not None
        )

    def get_credentials(self) -> Optional[Dict[str, Any]]:
        """Get the signed-in caller's identity data."""
        if self.is_authenticated():
            return get_zvisitor(self.session)
        return None

    def get_app_user(self, app_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Return the single signed-in identity (app_name ignored)."""
        return self.get_credentials()

    def status(self) -> Dict[str, Any]:
        """Show current authentication status."""
        if self.is_authenticated():
            auth_data = get_zvisitor(self.session)
            self.zos.display.header("[*] Authentication Status")
            self.zos.display.text(f"Username:   {auth_data.get(ZAUTH_KEY_USERNAME)}", indent=1, pause=False)
            self.zos.display.text(f"Role:       {auth_data.get(ZAUTH_KEY_ROLE)}", indent=1, pause=False)
            self.zos.display.text(f"User ID:    {auth_data.get(ZAUTH_KEY_ID)}", indent=1, pause=False)
            if api_key := auth_data.get(ZAUTH_KEY_API_KEY):
                truncated_key = api_key[:20] + "..." if len(api_key) > 20 else api_key
                self.zos.display.text(f"API Key:    {truncated_key}", indent=1, pause=False)
            return self._create_status_response("authenticated", user=auth_data)
        else:
            self.zos.display.warning("[WARN] Not authenticated. Run 'auth login' to authenticate.")
            return self._create_status_response(_MSG_NOT_AUTHENTICATED)
