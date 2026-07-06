"""
Context Helpers - Resolves authentication context for RBAC

Extracted from monolithic RBAC class for better separation of concerns.
"""

from zOS import Optional, Any
from zOS.L1_Foundation.a_zConfig.zConfig_modules.config_constants import (
    ZAUTH_KEY_ROLE,
    ZAUTH_KEY_ID,
    ZAUTH_KEY_AUTHENTICATED,
)

from ...auth_constants import (
    DB_LABEL_AUTH,
    SCHEMA_META_KEY,
    SCHEMA_LABEL_KEY,
    _LOG_PREFIX_RBAC,
)

from ...auth_helpers import get_zvisitor

from .acting_principal import (
    get_acting_principal,
    P_AUTHENTICATED,
    P_ROLE,
    P_USER_ID,
)

LOG_PREFIX = _LOG_PREFIX_RBAC


class ContextHelpers:
    """Resolves authentication context for RBAC operations."""

    @property
    def session(self):
        """Live per-caller session — resolves via the live holder (§19 Phase 2)."""
        return self.zos.session

    def __init__(self, zos: Any) -> None:
        """Initialize with zOS instance."""
        self.zos = zos
        self.logger = zos.logger

    def _log(self, level: str, message: str) -> None:
        """Centralized logging with LOG_PREFIX."""
        full_message = f"{LOG_PREFIX} {message}"

        if level == "debug":
            self.logger.debug(full_message)
        elif level == "warning":
            self.logger.warning(full_message)

    def _get_current_role(self) -> Optional[str]:
        """Role of the signed-in caller (acting-principal override wins)."""
        principal = get_acting_principal()
        if principal is not None:
            return principal.get(P_ROLE)
        return get_zvisitor(self.session).get(ZAUTH_KEY_ROLE)

    def _get_current_user_id(self) -> Optional[str]:
        """ID of the signed-in caller (acting-principal override wins)."""
        principal = get_acting_principal()
        if principal is not None:
            return principal.get(P_USER_ID)
        return get_zvisitor(self.session).get(ZAUTH_KEY_ID)

    def _is_authenticated(self) -> bool:
        """Whether the caller is signed in (acting-principal override wins)."""
        principal = get_acting_principal()
        if principal is not None:
            return bool(principal.get(P_AUTHENTICATED))
        return bool(get_zvisitor(self.session).get(ZAUTH_KEY_AUTHENTICATED, False))

    def _is_db_ready(self) -> bool:
        """Check if zData handler is ready and auth schema is loaded."""
        return (
            self.zos.data.adapter is not None and
            self.zos.data.schema.get(SCHEMA_META_KEY, {}).get(SCHEMA_LABEL_KEY) == DB_LABEL_AUTH
        )
