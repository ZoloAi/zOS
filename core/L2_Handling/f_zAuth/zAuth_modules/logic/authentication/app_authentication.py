"""
App Authentication Manager - Handles application user authentication

Extracted from monolithic Authentication class for better separation of concerns.
"""

from zOS import Dict, Optional, Any
from zOS.L1_Foundation.a_zConfig.zConfig_modules import (
    SESSION_KEY_ZVISITOR,
    ZAUTH_KEY_AUTHENTICATED,
    ZAUTH_KEY_ID,
    ZAUTH_KEY_USERNAME,
    ZAUTH_KEY_ROLE,
    ZAUTH_KEY_API_KEY,
)

from ...auth_constants import (
    STATUS_SUCCESS,
    STATUS_ERROR,
    KEY_STATUS,
    DEFAULT_USER_MODEL,
    DEFAULT_ID_FIELD,
    DEFAULT_USERNAME_FIELD,
    DEFAULT_ROLE_FIELD,
    DEFAULT_API_KEY_FIELD,
    DEFAULT_ROLE,
    _LOG_PREFIX_AUTH,
    _LOG_LEVEL_INFO,
    _LOG_LEVEL_ERROR,
    _LOG_APP_AUTH_SUCCESS,
    _LOG_APP_AUTH_ERROR,
    _ERR_NO_SESSION,
    _ERR_INVALID_CREDS,
)

LOG_PREFIX = _LOG_PREFIX_AUTH


class AppAuthenticationManager:
    """Token-verifies a caller and writes the single signed-in identity.

    Tier-2 (application/token) auth now writes the same session["zVisitor"] as
    every other sign-in — there is one identity per zOS instance. ``app_name`` is
    informational only (kept in the response for callers like bifrost).
    """

    @property
    def session(self):
        """Live per-caller session — resolves via the live holder (§19 Phase 2)."""
        return self.zos.session

    def __init__(self, zos: Any, context_manager: Any) -> None:
        """Initialize with zOS instance and dependencies."""
        self.zos = zos
        self.logger = zos.logger
        self.context_manager = context_manager

    def _log(self, level: str, message: str) -> None:
        """Centralized logging with LOG_PREFIX."""
        if level == _LOG_LEVEL_INFO:
            self.logger.info(message)
        elif level == _LOG_LEVEL_ERROR:
            self.logger.error(message)

    def _check_session(self) -> bool:
        """Validate that session exists."""
        return self.session is not None

    def _create_status_response(self, status: str, **kwargs: Any) -> Dict[str, Any]:
        """Create standardized status response dictionary."""
        response = {KEY_STATUS: status}
        response.update(kwargs)
        return response

    def authenticate_app_user(
        self,
        app_name: str,
        token: str,
        config: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Authenticate user to a specific application (Layer 2 auth)."""
        if not self._check_session():
            return self._create_status_response(STATUS_ERROR, reason=_ERR_NO_SESSION)

        auth_config = self._configure_app_auth(config)

        try:
            user_data = self._authenticate_app_user_data(app_name, token, auth_config)
            self._store_app_authentication(app_name, user_data)
            self._log_app_auth_success(app_name, user_data)

            return self._create_status_response(
                STATUS_SUCCESS,
                app_name=app_name,
                user=user_data,
            )

        except Exception as e:
            self._log(_LOG_LEVEL_ERROR, f"{_LOG_APP_AUTH_ERROR} for {app_name}: {e}")
            return self._create_status_response(
                STATUS_ERROR,
                app_name=app_name,
                reason=str(e)
            )

    def _configure_app_auth(self, config: Optional[Dict[str, str]]) -> Dict[str, str]:
        """Configure authentication settings with defaults."""
        default_config = {
            "user_model": DEFAULT_USER_MODEL,
            DEFAULT_ID_FIELD: DEFAULT_ID_FIELD,
            DEFAULT_USERNAME_FIELD: DEFAULT_USERNAME_FIELD,
            DEFAULT_ROLE_FIELD: DEFAULT_ROLE_FIELD,
            DEFAULT_API_KEY_FIELD: DEFAULT_API_KEY_FIELD
        }
        return {**default_config, **(config or {})}

    def _authenticate_app_user_data(
        self,
        app_name: str,
        token: str,
        auth_config: Dict[str, str]
    ) -> Dict[str, Any]:
        """Verify the app token against the user ledger and return the real identity.

        Tier-2 (application) auth is **ecosystem auth (Type A2)**: the authority for
        "is this token valid for this user" is the zCloud user ledger, and PAT
        verification (sha256(token) ↦ user row) is sealed in zGuard via
        ``api_key_auth.verify_api_key``. This path **fails closed** — it never
        fabricates an identity:

          - token does not match a ledger row -> ``ValueError`` (caller -> STATUS_ERROR)
          - zGuard binary absent (open-core)   -> ``ImportError`` "…z patch"
                                                   (caller -> STATUS_ERROR)

        With the zGuard binary present, this works whether or not the operator is
        logged in — the binary does the verifying; login is a separate trust tier.
        """
        from .api_key_auth import verify_api_key

        model = auth_config.get("user_model") if auth_config else None
        user_row = verify_api_key(self.zos, token, model)
        if not user_row:
            raise ValueError(f"{_ERR_INVALID_CREDS} for {app_name}")

        id_field = auth_config.get(DEFAULT_ID_FIELD, DEFAULT_ID_FIELD)
        username_field = auth_config.get(DEFAULT_USERNAME_FIELD, DEFAULT_USERNAME_FIELD)
        role_field = auth_config.get(DEFAULT_ROLE_FIELD, DEFAULT_ROLE_FIELD)
        return {
            ZAUTH_KEY_AUTHENTICATED: True,
            ZAUTH_KEY_ID: user_row.get(id_field),
            ZAUTH_KEY_USERNAME: user_row.get(username_field),
            ZAUTH_KEY_ROLE: user_row.get(role_field) or DEFAULT_ROLE,
            ZAUTH_KEY_API_KEY: token,
        }

    def _store_app_authentication(self, app_name: str, user_data: Dict[str, Any]) -> None:
        """Write the verified identity into the single session["zVisitor"]."""
        self.session[SESSION_KEY_ZVISITOR] = user_data

    def _log_app_auth_success(self, app_name: str, user_data: Dict[str, Any]) -> None:
        """Log successful authentication."""
        self._log(
            _LOG_LEVEL_INFO,
            f"{_LOG_APP_AUTH_SUCCESS}: {app_name} "
            f"(username={user_data[ZAUTH_KEY_USERNAME]})"
        )
