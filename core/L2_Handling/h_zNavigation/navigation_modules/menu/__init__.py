"""
Menu module for zNavigation subsystem.

This package contains menu-related components for building, rendering,
and handling user interaction with navigation menus.

Components:
- menu_builder: Menu construction from various input formats
- menu_renderer: Menu display and formatting
- menu_interaction: User input and selection handling
- menu_search: Interactive search/filter functionality

Architecture:
- Composition pattern (MenuSystem orchestrates components)
- Mode-agnostic (supports zCLI and Bifrost)
- Clean separation of concerns (build, render, interact)
"""

__all__ = []
