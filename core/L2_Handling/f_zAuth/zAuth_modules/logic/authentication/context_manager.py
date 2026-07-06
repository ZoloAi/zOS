"""
Context Manager - single signed-in identity (zVisitor)

The multi-context / multi-app switching machinery is gone: one zOS instance has
one signed-in caller. This thin manager just exposes that identity.
"""

from zOS import Dict, Optional, Any

from ...auth_constants import _LOG_PREFIX_AUTH
from ...auth_helpers import get_zvisitor

LOG_PREFIX = _LOG_PREFIX_AUTH


class ContextManager:
    """Exposes the single signed-in caller identity (session["zVisitor"])."""

    @property
    def session(self):
        """Live per-caller session — resolves via the live holder (§19 Phase 2)."""
        return self.zos.session

    def __init__(self, zos: Any) -> None:
        """Initialize with zOS instance."""
        self.zos = zos
        self.logger = zos.logger

    def get_active_user(self) -> Optional[Dict[str, Any]]:
        """Return the signed-in caller identity dict, or None if not present."""
        if self.session is None:
            return None
        return get_zvisitor(self.session) or None
