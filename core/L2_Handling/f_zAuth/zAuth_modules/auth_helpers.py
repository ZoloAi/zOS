"""
Authentication Helper Utilities - Shared DRY session access (single identity)

zOS runs ONE app per instance, so there is ONE signed-in caller: the flat dict
at ``session["zVisitor"]`` (root, sibling of zCrumbs). These helpers are the SSOT
read path for that identity — every reader (RBAC, parser %auth, display, bifrost)
goes through ``get_zvisitor`` instead of reaching into the session layout.

Usage:
    from .auth_helpers import get_zvisitor

    visitor = get_zvisitor(self.session)
    if visitor.get(ZAUTH_KEY_AUTHENTICATED):
        role = visitor.get(ZAUTH_KEY_ROLE)
"""

from zOS import Dict, Any

from zOS.L1_Foundation.a_zConfig.zConfig_modules.config_constants import (
    SESSION_KEY_ZVISITOR,
)


def get_zvisitor(session: Dict[str, Any]) -> Dict[str, Any]:
    """Return the single signed-in caller identity dict (empty if none).

    SSOT read for ``session["zVisitor"]`` — the flat authenticated-identity dict
    ({authenticated, id, username, role, api_key}).
    """
    if not session:
        return {}
    return session.get(SESSION_KEY_ZVISITOR, {})


# Back-compat alias for the pre-collapse name (some call sites used the
# "zsession_data" wording). Identical behavior — the single zVisitor identity.
def get_zsession_data(session: Dict[str, Any]) -> Dict[str, Any]:
    """Deprecated alias of :func:`get_zvisitor` (single identity)."""
    return get_zvisitor(session)
