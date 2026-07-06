"""
RBAC Facade — Flask-style gating.

Two gates only, both decided from the live session (populated once at login):
  - require_auth : authenticated in the active context?
  - require_role : exact role match?

zRBAC is schema-agnostic. It never queries a permissions/roles table at
decision-time — the session is the SSOT.
"""

from zOS import Any, Dict, Optional, Union, List, Tuple

from .context_helpers import ContextHelpers
from .role_checker import RoleChecker
from ...auth_constants import (
    ZRBAC_KEY,
    ZRBAC_ZGUEST,
    ZRBAC_AUTHENTICATED,
    ZRBAC_REQUIRE_AUTH,
    ZRBAC_REQUIRE_ROLE,
    ZRBAC_REQUIRE,
    ZRBAC_REQUIRE_PREDICATE,
    ZRBAC_ACTIONS,
    _DENY_GUEST_ONLY,
    _DENY_AUTH_REQUIRED,
    _DENY_ROLE_REQUIRED,
    _DENY_ATTR_REQUIRED,
    _DENY_GATE_UNAVAILABLE,
    _LOG_PREDICATE_DEPRECATED,
)


class RBAC:
    """
    Context-aware, session-only access control.

    Delegates to:
    - ContextHelpers: resolves the active authentication context
    - RoleChecker: exact role match (context-aware, dual-OR)
    """

    zos: Any
    session: Dict[str, Any]
    logger: Any

    @property
    def session(self):
        """Live per-caller session — resolves via the live holder (§19 Phase 2)."""
        return self.zos.session

    def __init__(self, zos: Any) -> None:
        """Initialize RBAC module with manager delegation."""
        self.zos = zos
        self.logger = zos.logger
        self._context_helpers = ContextHelpers(zos)
        self._role_checker = RoleChecker(zos, self._context_helpers)

    # =========================================================================
    # PUBLIC API
    # =========================================================================

    # Role Checking
    def has_role(self, required_role: Optional[Union[str, List[str]]]) -> bool:
        """Check if the current user has the required role (context-aware)."""
        return self._role_checker.has_role(required_role)

    # Context Identity (resolved through the context-aware helpers — SSOT)
    def is_authenticated_in_context(self) -> bool:
        """
        Whether the user is authenticated in the ACTIVE context.

        Context-aware — distinct from the tier-agnostic zAuth.is_authenticated()
        (which is True if ANY context is authenticated). Here: zSession/application
        check that context; DUAL requires BOTH to be authenticated.
        """
        return self._context_helpers._is_authenticated()  # pylint: disable=protected-access

    def get_current_role(self) -> Optional[str]:
        """
        Resolve the active user's role as a single string (SSOT for callers).

        Reads the live role from the active context. In DUAL context the helper
        returns a (zsession_role, app_role) tuple; the application role is
        preferred, falling back to the zSession role. Returns None when
        unauthenticated or no role is set.
        """
        role = self._context_helpers._get_current_role()  # pylint: disable=protected-access
        if isinstance(role, tuple):
            role = next((r for r in (role[1], role[0]) if r), None)
        return role

    # =========================================================================
    # zRBAC EVALUATION — authoritative decision over a declarative zRBAC block.
    # SSOT for BOTH the wizard render-gate and the zData access guard.
    # =========================================================================

    def check_zrbac(self, rbac: Optional[Dict[str, Any]]) -> Tuple[bool, Optional[str]]:
        """
        Authoritatively evaluate a resolved ``zRBAC`` requirement block.

        Flask-style short-circuit order, decided from the session only:
          1. No requirement       → granted (public).
          2. ``zGuest`` + authed  → denied (guest-only resource).
          3. ``require_auth``     → denied if not authenticated.
          4. ``require_role``     → implies auth; denied on exact-role mismatch.
          5. ``require`` (map)     → implies auth; attribute-agnostic — each
             selector resolves through the zLoom value SSOT against the live
             caller and must match its expected value (AND; list = membership).

        The ``authenticated`` alias folds into the explicit flags so ONE word
        behaves identically everywhere it appears:
          authenticated: true  → require_auth (signed-in only)
          authenticated: false → zGuest       (signed-out only)

        ``require_role`` values may be literal (``admin``) or a ``%zloom.*``
        expression resolved against the caller before the match. zRBAC stays a
        dumb bool gate: it never invents permission/predicate vocabulary —
        builders gate on ANY attribute via ``require`` (the rock&roll-band case).

        Authentication is context-aware (DUAL requires both). No auth calls are
        made when ``rbac`` is empty, so unprotected resources pay zero cost.

        Returns:
            (granted, reason) — reason is None when granted, else a short
            human-readable denial reason for audit/UX.
        """
        if not rbac:
            return True, None

        authed = self.is_authenticated_in_context()

        auth_alias = rbac.get(ZRBAC_AUTHENTICATED)
        if isinstance(auth_alias, str):
            auth_alias = {"true": True, "false": False}.get(auth_alias.strip().lower())
        want_guest = bool(rbac.get(ZRBAC_ZGUEST)) or (auth_alias is False)
        want_auth = bool(rbac.get(ZRBAC_REQUIRE_AUTH)) or (auth_alias is True)

        # Deprecated predicate gate: never wired. Warn + degrade to require_auth
        # (a security improvement over the prior silent allow-all) rather than
        # breaking authored views; migrate to `require:` for true attribute gating.
        if rbac.get(ZRBAC_REQUIRE_PREDICATE) is not None:
            self.logger.framework.warning(_LOG_PREDICATE_DEPRECATED)
            want_auth = True

        if want_guest and authed:
            return False, _DENY_GUEST_ONLY

        if want_auth and not authed:
            return False, _DENY_AUTH_REQUIRED

        required_role = rbac.get(ZRBAC_REQUIRE_ROLE)
        if required_role is not None:
            if not authed:
                return False, _DENY_AUTH_REQUIRED
            required_role = self._resolve_rbac_value(required_role)
            if not self.has_role(required_role):
                return False, _DENY_ROLE_REQUIRED % (required_role,)

        require = rbac.get(ZRBAC_REQUIRE)
        if isinstance(require, dict) and require:
            if not authed:
                return False, _DENY_AUTH_REQUIRED
            resolver = self._zloom_resolver()
            if resolver is None:
                return False, _DENY_GATE_UNAVAILABLE  # fail closed — no resolver
            for selector, expected in require.items():
                expr = selector if str(selector).startswith("%") else f"%zloom.zVisitor.{selector}"
                actual = resolver.resolve_value(expr)
                if not self._attr_match(actual, expected):
                    return False, _DENY_ATTR_REQUIRED % (selector,)

        return True, None

    # ---- attribute-agnostic gate helpers (consume the zLoom value SSOT) ----

    def _zloom_resolver(self) -> Optional[Any]:
        """The zLoom value SSOT (``zos.zloom``) via the runtime handle, or None.

        Runtime attribute access — NOT an import — so zAuth keeps no static
        dependency on the zLoom subsystem. A gate that can't resolve fails closed.
        """
        resolver = getattr(self.zos, "zloom", None)
        return resolver if resolver is not None and hasattr(resolver, "resolve_value") else None

    def _resolve_rbac_value(self, value: Any) -> Any:
        """Resolve a ``%zloom.*`` requirement value to a literal; pass others through."""
        if isinstance(value, str) and value.startswith("%"):
            resolver = self._zloom_resolver()
            if resolver is not None:
                return resolver.resolve_value(value)
        return value

    @staticmethod
    def _attr_match(actual: Any, expected: Any) -> bool:
        """True if the caller's resolved ``actual`` satisfies ``expected``.

        - expected is a list → membership (string-coerced) of actual, or any
          overlap when actual is itself a list.
        - otherwise → string-coerced equality.
        A None ``actual`` (missing attribute) never matches → gate fails closed.
        """
        if actual is None:
            return False
        if isinstance(expected, (list, tuple)):
            wanted = {str(e) for e in expected}
            if isinstance(actual, (list, tuple)):
                return any(str(a) in wanted for a in actual)
            return str(actual) in wanted
        if isinstance(actual, (list, tuple)):
            return str(expected) in {str(a) for a in actual}
        return str(actual) == str(expected)

    def resolve_data_rbac(
        self,
        table_meta: Optional[Dict[str, Any]],
        schema_meta: Optional[Dict[str, Any]] = None,
        action: Optional[str] = None,
        category: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Resolve the effective ``zRBAC`` block for a data action.

        Precedence: table-level ``zRBAC`` wins over the schema-level (``zMeta``)
        default. An optional ``zRBAC.actions`` map provides per-action overrides
        keyed by the exact action verb (e.g. ``delete``) or by category bucket
        (``read`` / ``write``); a matching override fully governs that action.
        """
        base = None
        if isinstance(table_meta, dict):
            base = table_meta.get(ZRBAC_KEY)
        if not isinstance(base, dict) and isinstance(schema_meta, dict):
            base = schema_meta.get(ZRBAC_KEY)
        if not isinstance(base, dict):
            return None

        actions = base.get(ZRBAC_ACTIONS)
        if isinstance(actions, dict):
            override = None
            if action and isinstance(actions.get(action), dict):
                override = actions.get(action)
            elif category and isinstance(actions.get(category), dict):
                override = actions.get(category)
            if override is not None:
                return override

        if ZRBAC_ACTIONS in base:
            return {k: v for k, v in base.items() if k != ZRBAC_ACTIONS}
        return base

    def check_data_access(
        self,
        table_meta: Optional[Dict[str, Any]],
        schema_meta: Optional[Dict[str, Any]] = None,
        action: Optional[str] = None,
        category: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        """Resolve + evaluate zRBAC for a data action (one call for the zData guard)."""
        rbac = self.resolve_data_rbac(table_meta, schema_meta, action, category)
        return self.check_zrbac(rbac)


__all__ = ['RBAC']
