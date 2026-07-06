"""
Resolvers module for zNavigation subsystem.

This package contains data resolver modules that parse and validate
navigation-related data structures.

Resolvers:
- resolver_navbar: Navbar configuration resolution
- resolver_zlink: zLink expression parsing and RBAC validation

Architecture:
- Resolvers are pure functions with no side effects
- No session mutation (read-only operations)
- Focused on data transformation and validation
"""

__all__ = []
