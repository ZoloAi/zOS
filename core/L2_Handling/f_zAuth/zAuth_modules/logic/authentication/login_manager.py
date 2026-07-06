"""
Login Manager - Handles zSession login operations

Extracted from monolithic Authentication class for better separation of concerns.
"""

from zOS import os, Dict, Optional, Any, Tuple
from zOS.L1_Foundation.a_zConfig.zConfig_modules import (
    ZAUTH_KEY_AUTHENTICATED,
    ZAUTH_KEY_ID,
    ZAUTH_KEY_USERNAME,
    ZAUTH_KEY_ROLE,
    ZAUTH_KEY_API_KEY,
)

from ...auth_constants import (
    STATUS_SUCCESS,
    STATUS_FAIL,
    STATUS_PENDING,
    KEY_STATUS,
    KEY_CREDENTIALS,
    KEY_USERNAME,
    KEY_PERSIST,
    KEY_PASSWORD,
    FIELD_ROLE,
    FIELD_API_KEY,
    DEFAULT_PERSIST,
    ENV_USE_REMOTE_API,
    ENV_TRUE,
    _LOG_PREFIX_AUTH,
    _LOG_LEVEL_WARNING,
    _LOG_AUTH_FAILED,
    _ERR_INVALID_CREDS,
    _MSG_AWAITING_GUI,
)

from ...auth_helpers import get_zsession_data

LOG_PREFIX = _LOG_PREFIX_AUTH


class LoginManager:
    """Manages zSession login operations."""

    @property
    def session(self):
        """Live per-caller session — resolves via the live holder (§19 Phase 2)."""
        return self.zos.session

    def __init__(self, zos: Any, remote_auth_manager: Any, context_manager: Any) -> None:
        """Initialize with zOS instance and manager dependencies."""
        self.zos = zos
        self.logger = zos.logger
        self.remote_auth_manager = remote_auth_manager
        self.context_manager = context_manager

    def _log(self, level: str, message: str) -> None:
        """Centralized logging with LOG_PREFIX."""
        if level == _LOG_LEVEL_WARNING:
            self.logger.warning(message)

    def _create_status_response(self, status: str, **kwargs: Any) -> Dict[str, Any]:
        """Create standardized status response dictionary."""
        response = {KEY_STATUS: status}
        response.update(kwargs)
        return response

    def login(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
        server_url: Optional[str] = None,
        persist: bool = DEFAULT_PERSIST
    ) -> Dict[str, Any]:
        """Authenticate zOS/Zolo user to zSession context (Layer 1)."""
        username, password, pending_response = self._get_login_credentials(username, password)
        if pending_response:
            return pending_response

        if os.getenv(ENV_USE_REMOTE_API, "false").lower() == ENV_TRUE:
            result = self.remote_auth_manager.authenticate_remote(username, password, server_url)
            if result.get(KEY_STATUS) == STATUS_SUCCESS:
                return self._handle_successful_login(result, persist, password)

        return self._handle_failed_login()

    def _get_login_credentials(
        self,
        username: Optional[str],
        password: Optional[str]
    ) -> Tuple[Optional[str], Optional[str], Optional[Dict[str, Any]]]:
        """Get login credentials, prompting if not provided."""
        if username and password:
            return username, password, None

        pending_response = self._try_gui_login_prompt(username, password)
        if pending_response:
            return None, None, pending_response

        if not username:
            username = self.zos.display.zPrimitives.read_string("Username: ")
        if not password:
            # TODO(ssot): replace with self.zos.display.read_password("Password: ")
            # to use tier-2 event API instead of calling primitive directly.
            # Audit in context of zAuth testing — do not change before zAuth test coverage exists.
            password = self.zos.display.zPrimitives.read_password("Password: ")

        return username, password, None

    def _try_gui_login_prompt(
        self,
        username: Optional[str],
        password: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        """Try to send GUI login prompt."""
        if self.zos.display.zPrimitives.send_gui_event("auth_login_prompt", {
            "username": username,
            "password": password,
            "fields": ["username", "password"]
        }):
            return self._create_status_response(STATUS_PENDING, reason=_MSG_AWAITING_GUI)
        return None

    def _handle_successful_login(
        self,
        result: Dict[str, Any],
        persist: bool,
        password: str
    ) -> Dict[str, Any]:
        """Handle successful remote authentication."""
        credentials = result.get(KEY_CREDENTIALS)
        if not credentials or not self.session:
            return result

        self._update_zsession_with_credentials(credentials)
        self._display_login_success(credentials)

        result[KEY_PERSIST] = persist
        result[KEY_PASSWORD] = password

        return result

    def _update_zsession_with_credentials(self, credentials: Dict[str, Any]) -> None:
        """Update zSession in session dict with credentials."""
        get_zsession_data(self.session).update({
            ZAUTH_KEY_AUTHENTICATED: True,
            ZAUTH_KEY_ID: credentials.get("user_id"),
            ZAUTH_KEY_USERNAME: credentials.get(KEY_USERNAME),
            ZAUTH_KEY_ROLE: credentials.get(FIELD_ROLE),
            ZAUTH_KEY_API_KEY: credentials.get(FIELD_API_KEY)
        })

    def _display_login_success(self, credentials: Dict[str, Any]) -> None:
        """Display successful login message."""
        username = credentials.get(KEY_USERNAME)
        role = credentials.get(FIELD_ROLE)
        user_id = credentials.get("user_id")
        api_key = credentials.get(FIELD_API_KEY)

        self.zos.display.success(f"[OK] Logged in as: {username} ({role})")
        self.zos.display.text(f"     User ID: {user_id}", indent=0, pause=False)

        if api_key:
            truncated_key = api_key[:20] + "..." if len(api_key) > 20 else api_key
            self.zos.display.text(f"     API Key: {truncated_key}", indent=0, pause=False)

    def _handle_failed_login(self) -> Dict[str, Any]:
        """Handle failed authentication."""
        self._log(_LOG_LEVEL_WARNING, _LOG_AUTH_FAILED)
        self.zos.display.error(f"[FAIL] Authentication failed: {_ERR_INVALID_CREDS}")
        return self._create_status_response(STATUS_FAIL, reason=_ERR_INVALID_CREDS)
