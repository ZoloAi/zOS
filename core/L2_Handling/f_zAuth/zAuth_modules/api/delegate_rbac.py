# zOS/core/L2_Handling/d_zAuth/zAuth_modules/api/delegate_rbac.py

"""
RBAC Delegate for zAuth Facade.

This module provides Role-Based Access Control delegate methods,
following zDisplay's delegate pattern for clean facade composition.

Methods:
    - has_role: Check if user has required role
    - is_authenticated_in_context: Context-aware auth check (DUAL requires both)
    - get_current_role: Resolve the active user's role as a single string

Pattern:
    All methods delegate to self.rbac module instance.
"""

from zOS import Optional, Union, List, Dict, Any, Tuple

from ..logic.rbac.acting_principal import (
    acting_as as _acting_as,
    make_principal as _make_principal,
)


class DelegateRBAC:  # pylint: disable=no-member
    """Mixin providing RBAC delegate methods.
    
    These methods provide context-aware role and permission checks,
    delegating to the RBAC module for access control logic.
    
    Note:
        This is a mixin class. The rbac attribute is provided by
        the subclass (zAuth). Pylint warnings about missing members are expected
        and suppressed.
    """

    # RBAC Delegates

    def has_role(self, required_role: Union[str, List[str], None]) -> bool:
        """
        Check if the current user has the required role (context-aware).
        
        Delegates to: rbac.has_role()
        
        Checks roles based on active_context:
        - "zSession": Checks zSession user's role
        - "application": Checks active app user's role
        - "dual": Checks BOTH with OR logic (either context can grant)
        
        Args:
            required_role: Role name (str), list of roles (list), or None
                         - str: User must have this exact role
                         - list: User must have ANY of these roles (OR logic)
                         - None: Public access (always returns True)
        
        Returns:
            bool: True if user has the required role(s), False otherwise
        
        Integration:
            - Used by zWizard for zVaF menu access control
            - Reads role from session[SESSION_KEY_ZVISITOR] based on active_context
        
        Dual-Mode Behavior:
            In dual mode, returns True if user has role in EITHER context:
            - zSession user has "admin" OR
            - Active app user has "admin"
        
        Examples:
            # Single role check
            if zos.auth.has_role("admin"):
                print("User is admin")
            
            # Multiple roles (OR logic)
            if zos.auth.has_role(["admin", "moderator"]):
                print("User is admin OR moderator")
            
            # Public access
            if zos.auth.has_role(None):
                print("Always True - public access")
        """
        return self.rbac.has_role(required_role)

    def is_authenticated_in_context(self) -> bool:
        """
        Context-aware authentication check (delegates to rbac).

        Unlike is_authenticated() (True if ANY context is authenticated), this
        reflects the ACTIVE context: zSession/application check that context;
        DUAL requires BOTH to be authenticated.

        Returns:
            bool: True if authenticated in the active context.
        """
        return self.rbac.is_authenticated_in_context()

    def get_current_role(self) -> Optional[str]:
        """
        Resolve the active user's role as a single string (delegates to rbac).

        In DUAL context the application role is preferred over the zSession role.
        Returns None when unauthenticated or no role is set.

        Returns:
            Optional[str]: The resolved role, or None.
        """
        return self.rbac.get_current_role()

    def check_zrbac(
        self, rbac: Optional[Dict[str, Any]]
    ) -> Tuple[bool, Optional[str]]:
        """
        Evaluate a declarative ``zRBAC`` requirement block → (granted, reason).

        Delegates to: rbac.check_zrbac()

        The single SSOT decision the wizard render-gate and `if:` evaluator call:
        callers hand the parsed ``zRBAC`` block and act only on the boolean
        verdict + denial reason. All auth/role/session logic stays in zRBAC.
        """
        return self.rbac.check_zrbac(rbac)

    def check_data_access(
        self,
        table_meta: Optional[Dict[str, Any]],
        schema_meta: Optional[Dict[str, Any]] = None,
        action: Optional[str] = None,
        category: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Authoritatively evaluate declarative ``zRBAC`` for a data action.

        Delegates to: rbac.check_data_access()

        Resolves the effective zRBAC block (table-level over schema-level
        ``zMeta`` default, with optional per-action / per-category overrides)
        and evaluates it context-aware. This is the SSOT the zData access guard
        calls so reads/mutations are gated by the same contract the wizard
        render-gate uses.

        Args:
            table_meta: The target table's schema definition dict (or None).
            schema_meta: The schema-level ``zMeta`` dict (default fallback).
            action: The data action verb (e.g. "insert", "read", "delete").
            category: Action category bucket ("read" / "write") for overrides.

        Returns:
            (granted, reason) — reason is None when granted, else a short
            denial reason suitable for audit logging.
        """
        return self.rbac.check_data_access(table_meta, schema_meta, action, category)

    @staticmethod
    def acting_as(principal: Optional[Dict[str, Any]]):
        """
        Bind a request-scoped acting principal for an RBAC evaluation block.

        Intended for multi-client front doors (e.g. zBifrost WS) that share a
        single zOS instance across concurrent connections: each dispatched
        request runs under the connection's authenticated identity instead of
        the ambient (shared) session, so the zData access guard and wizard
        render-gate enforce per-request RBAC. Thread/async-safe via contextvars.

        Use as a context manager:

            with zos.auth.acting_as(zos.auth.make_principal(True, "admin", "u1")):
                handle_zDispatch(...)

        Passing ``None`` clears any inherited principal for the block (the
        correct fail-closed choice for an unauthenticated/guest connection).

        Returns:
            A context manager restoring the prior principal on exit.
        """
        return _acting_as(principal)

    @staticmethod
    def make_principal(
        authenticated: bool,
        role: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Build a normalized principal dict for :meth:`acting_as`."""
        return _make_principal(authenticated, role, user_id)
