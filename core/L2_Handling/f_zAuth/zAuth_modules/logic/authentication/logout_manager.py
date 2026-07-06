"""
Logout Manager - Handles logout operations across contexts

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
    CONTEXT_ZSESSION,
)
from zOS.L1_Foundation.a_zConfig.zConfig_modules.session.config_session import SessionConfig

from ...auth_constants import (
    STATUS_SUCCESS,
    STATUS_ERROR,
    KEY_STATUS,
    DEFAULT_DELETE_PERSISTENT,
    _LOG_PREFIX_AUTH,
    _LOG_LEVEL_INFO,
    _LOG_LEVEL_DEBUG,
    _LOG_SESSION_DELETE,
    _LOG_SESSION_DELETE_FAIL,
    _ERR_NO_SESSION,
)

from ...auth_helpers import get_zvisitor

LOG_PREFIX = _LOG_PREFIX_AUTH


class LogoutManager:
    """Manages logout operations across all authentication contexts."""

    @property
    def session(self):
        """Live per-caller session — resolves via the live holder (§19 Phase 2)."""
        return self.zos.session

    def __init__(self, zos: Any, credential_manager: Any) -> None:
        """Initialize with zOS instance and dependencies."""
        self.zos = zos
        self.logger = zos.logger
        self.credential_manager = credential_manager

    def _log(self, level: str, message: str) -> None:
        """Centralized logging with LOG_PREFIX."""
        if level == _LOG_LEVEL_INFO:
            self.logger.info(message)
        elif level == _LOG_LEVEL_DEBUG:
            self.logger.debug(message)

    def _create_status_response(self, status: str, **kwargs: Any) -> Dict[str, Any]:
        """Create standardized status response dictionary."""
        response = {KEY_STATUS: status}
        response.update(kwargs)
        return response

    def _check_session(self) -> bool:
        """Validate that session exists."""
        return self.session is not None

    def logout(
        self,
        context: str = CONTEXT_ZSESSION,
        app_name: Optional[str] = None,
        delete_persistent: bool = DEFAULT_DELETE_PERSISTENT
    ) -> Dict[str, Any]:
        """Clear the single signed-in identity (context/app_name are vestigial)."""
        if not self._check_session():
            return self._create_status_response(STATUS_ERROR, reason=_ERR_NO_SESSION)

        cleared = []
        is_logged_in = self.credential_manager.is_authenticated()
        self._logout_zvisitor(cleared, delete_persistent)
        self._display_logout_feedback(is_logged_in)

        new_hash = SessionConfig.regenerate_session_hash(self.session)
        self._log(_LOG_LEVEL_DEBUG, f"Session hash regenerated on logout: {new_hash}")

        return self._create_status_response(
            STATUS_SUCCESS,
            context=context,
            cleared=cleared,
            delete_persistent=delete_persistent,
        )

    def _logout_zvisitor(self, cleared: list, delete_persistent: bool) -> Optional[str]:
        """Reset session["zVisitor"] to its anonymous shape."""
        username = get_zvisitor(self.session).get(ZAUTH_KEY_USERNAME)

        self.session[SESSION_KEY_ZVISITOR] = {
            ZAUTH_KEY_AUTHENTICATED: False,
            ZAUTH_KEY_ID: None,
            ZAUTH_KEY_USERNAME: None,
            ZAUTH_KEY_ROLE: None,
            ZAUTH_KEY_API_KEY: None,
        }

        cleared.append(f"{CONTEXT_ZSESSION} ({username})")

        if delete_persistent and username:
            self._delete_persistent_session(username)

        # Cookie-bound identity (ZAUTH_INSTANCE.notes.md §19.L): drop the stored
        # identity so a lingering zsid cookie can't rehydrate a signed-out user.
        try:
            zsid = self.session.get("_zsid")
            if zsid:
                from zOS.L1_Foundation.a_zConfig.zConfig_modules.session import (  # type: ignore[reportMissingImports]
                    session_cookie as _sc,
                )
                _sc.clear_identity(self.zos, zsid)
        except Exception:  # pylint: disable=broad-except
            pass

        return username

    def _delete_persistent_session(self, username: str) -> None:
        """Clear the persisted zOwnership identity (git-like sign-out).

        NOTE (zOwnership boundary): this is a RUNTIME logout reaching into the
        zMachine zOwnership record (zConfig.identity.zolo). The zownership_store
        call name makes that cross-boundary touch visible; behavior unchanged.
        """
        try:
            from ...persistence.zownership_store import clear_zownership
            clear_zownership(self.zos)
            self._log(_LOG_LEVEL_DEBUG, f"{_LOG_SESSION_DELETE}: {username}")
        except Exception as e:  # pylint: disable=broad-except
            self._log(_LOG_LEVEL_DEBUG, f"{_LOG_SESSION_DELETE_FAIL}: {e}")

    def _display_logout_feedback(self, is_logged_in: bool) -> None:
        """Display logout feedback to user."""
        if is_logged_in:
            self.zos.display.success("[OK] Logged out successfully")
        else:
            self.zos.display.warning("[WARN] Not currently logged in")
