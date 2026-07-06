"""
Role Checker - Flask-style exact role matching (context-aware)

Extracted from the RBAC facade for separation of concerns. Roles are compared
by exact name against the live session — no schema reads, no hierarchy/levels.
"""

from zOS import Optional, Any, Union, List

from ...auth_constants import (
    _LOG_PREFIX_RBAC,
    _LOG_NOT_AUTHENTICATED,
    _LOG_NO_ROLE,
    _LOG_INVALID_ROLE_TYPE,
)

LOG_PREFIX = _LOG_PREFIX_RBAC


class RoleChecker:
    """Context-aware exact role matching (no hierarchy)."""

    def __init__(self, zos: Any, context_helpers: Any) -> None:
        """Initialize with zOS instance and dependencies."""
        self.zos = zos
        self.logger = zos.logger
        self.context_helpers = context_helpers

    def _log(self, level: str, message: str) -> None:
        """Centralized logging with LOG_PREFIX."""
        full_message = f"{LOG_PREFIX} {message}"

        if level == "debug":
            self.logger.debug(full_message)
        elif level == "warning":
            self.logger.warning(full_message)

    def has_role(self, required_role: Optional[Union[str, List[str]]]) -> bool:
        """Check if the current user has the required role (context-aware)."""
        if required_role is None:
            return True

        if not self.context_helpers._is_authenticated():  # pylint: disable=protected-access
            self._log("debug", _LOG_NOT_AUTHENTICATED)
            return False

        user_role = self.context_helpers._get_current_role()  # pylint: disable=protected-access

        if not user_role:
            self._log("debug", _LOG_NO_ROLE)
            return False

        if self._check_role_match(user_role, required_role):
            return True

        if not isinstance(required_role, (str, list)):
            self._log("warning", f"{_LOG_INVALID_ROLE_TYPE}: {type(required_role)}")

        return False

    def _check_role_match(
        self,
        user_role: Optional[str],
        required_role: Union[str, List[str]]
    ) -> bool:
        """Exact match of the caller's single role against the requirement(s)."""
        if not user_role:
            return False

        if isinstance(required_role, str):
            return self._roles_match(user_role, required_role)

        if isinstance(required_role, list):
            return any(self._roles_match(user_role, req) for req in required_role)

        return False

    def _roles_match(self, user_role_name: str, required_role_name: str) -> bool:
        """Exact role match (Flask-style). No schema/hierarchy reads at gate time."""
        return user_role_name == required_role_name
