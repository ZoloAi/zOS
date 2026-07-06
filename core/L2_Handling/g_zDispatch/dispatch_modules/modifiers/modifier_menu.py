# zOS/core/L2_Handling/g_zDispatch/dispatch_modules/modifiers/modifier_menu.py

"""
Menu Modifier Implementation for zDispatch Subsystem.

This module provides the MenuModifier class, which implements the asterisk (*)
modifier behavior for creating navigation menus from data.

Extracted from dispatch_modifiers.py as part of Phase 4 refactoring.

Modifier Behavior:
    * (asterisk) - "Menu" modifier
    - Creates navigation menu via zNavigation.create()
    - Respects ~ (tilde) anchor modifier to disable back button
    - Applies RBAC filtering for navbar menus (~zNavBar*)
    - Tracks menu appearance in breadcrumbs (POP semantics)
    - Re-dispatches dict results (e.g., zLink navigation)

Usage Example:
    modifier = MenuModifier(dispatch, zos, logger)
    
    # Simple menu
    result = modifier.process(["*"], "menu*", menu_dict, walker)
    
    # Anchored menu (no back button)
    result = modifier.process(["~", "*"], "~menu*", menu_dict, walker)
    
    # Navbar menu (RBAC filtered)
    result = modifier.process(["~", "*"], "~zNavBar*", navbar_items, walker)

Integration:
    - zNavigation: Menu creation via zos.navigation.create()
    - zAuth: RBAC filtering for navbar menus
    - zCrumbs: Breadcrumb tracking via handle_zCrumbs()
    - CommandLauncher: Re-dispatch dict results

Thread Safety:
    - Stateless operations (no instance state mutation)
    - Safe for concurrent execution
"""

from zOS import Any, List, Optional, Union

# Import dispatch constants. The `*` modifier is now a thin classifier that
# delegates BOTH flavors (plain + navbar) to NavigationHandler.handle_zmenu —
# the menu engine, crumbs, navbar RBAC/Done/STOP all live there (SSOT).
from ..dispatch_constants import (
    MOD_TILDE,
    KEY_ZMENU,
    _LOG_MSG_MENU_DETECTED,
)


class MenuModifier:
    """
    Implements menu creation modifier (*) for navigation.
    
    This class handles the asterisk modifier, which creates navigation
    menus from horizontal data structures (lists or dicts).
    
    Attributes:
        dispatch: Parent zDispatch instance
        zos: zOS framework instance (provides navigation subsystem)
        logger: Logger instance for debug output
    
    Methods:
        process(): Main entry point for menu modifier processing
    
    Example:
        modifier = MenuModifier(dispatch, zos, logger)
        result = modifier.process(["*"], "menu*", menu_dict, walker)
    """

    def __init__(self, dispatch: Any, zos: Any, logger: Any) -> None:
        """
        Initialize menu modifier.
        
        Args:
            dispatch: Parent zDispatch instance
            zos: zOS framework instance (provides navigation subsystem)
            logger: Logger instance for debug output
        
        Example:
            modifier = MenuModifier(dispatch, zos, logger)
        """
        self.dispatch = dispatch
        self.zos = zos
        self.logger = logger

    # ========================================================================
    # PUBLIC API
    # ========================================================================

    def process(
        self,
        modifiers: List[str],
        zKey: str,
        zHorizontal: Any,
        walker: Optional[Any]
    ) -> Optional[Union[str, Any]]:
        """
        Process menu modifier (*) - creates menu via zNavigation.
        
        Args:
            modifiers: List of detected modifier symbols
            zKey: Original key with modifiers
            zHorizontal: Menu items (list or dict)
            walker: Optional walker instance
        
        Returns:
            Menu navigation result
        
        Notes:
            - Checks for anchor (~) modifier to disable back button
            - Tracks menu appearance in breadcrumbs (POP semantics)
            - Applies RBAC filtering for navbar menus
            - Re-dispatches dict results (e.g., zLink navigation)
        """
        is_anchor = MOD_TILDE in modifiers
        is_navbar = zKey.startswith("~zNavBar")
        self.logger.debug(_LOG_MSG_MENU_DETECTED, zKey, is_anchor)

        # The `*` key is sugar for a zMenu block — build the spec and route it
        # through the ONE engine path (NavigationHandler.handle_zmenu). BOTH
        # flavors now live in that shared core (SSOT):
        #   - plain   Name*     → crumb APPEND + nested re-show loop (crumb_key)
        #   - navbar  ~zNavBar* → RBAC filter + Done row + terminal STOP (navbar_key)
        # Title stays unset for the shorthand (the longhand form spells it out).
        # ~zNavBar is innately anchored.
        handler = self.dispatch.launcher.navigation_handler
        if is_navbar:
            spec = {"options": zHorizontal, "zAnchor": True}
            return handler.handle_zmenu({KEY_ZMENU: spec}, walker, navbar_key=zKey)

        spec = {"options": zHorizontal, "zAnchor": is_anchor}
        return handler.handle_zmenu({KEY_ZMENU: spec}, walker, crumb_key=zKey)
