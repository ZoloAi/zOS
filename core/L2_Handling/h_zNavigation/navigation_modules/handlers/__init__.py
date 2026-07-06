"""
Handlers module for zNavigation subsystem.

This package contains focused handler modules that implement specific
navigation responsibilities following the approved zDispatch pattern.

Handlers:
- handler_navbar: Navigation bar resolution and RBAC filtering
- handler_breadcrumbs: Breadcrumb trail management
- handler_zback: Back navigation algorithm
- handler_panels: Dashboard panel management
- handler_linking: Inter-file navigation (zLink)
- handler_state: Navigation state tracking
- handler_history: Navigation history management

Architecture:
- Each handler is focused on a single responsibility
- Handlers delegate to shared utilities in navigation_helpers
- Clean separation from facade layer (zNavigation.py)
"""

__all__ = []
