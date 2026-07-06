# zOS/core/L2_Handling/h_zNavigation/navigation_modules/handlers/handler_panels.py

"""
Panel Management Handler for zNavigation Subsystem.

This module provides the PanelManager class, which manages panel-specific
breadcrumb keys and session state for wizard-style navigation flows.
Extracted from navigation_breadcrumbs.py to follow the approved handler pattern.

Architecture
------------
The PanelManager encapsulates panel-related breadcrumb operations:

1. **Panel Key Creation** (create_panel_key)
   - Generates unique breadcrumb keys for wizard panels
   - Format: "{panel_name}_panel_crumb"
   - Session-scoped uniqueness

2. **Panel Key Cleanup** (clear_other_panel_keys)
   - Removes breadcrumb keys from inactive panels
   - Ensures only active panel has breadcrumb state
   - Prevents navigation conflicts

Panel Pattern
-------------
Panels are wizard-style navigation flows where each panel has isolated
breadcrumb state. When switching panels, previous panel keys are cleared
to prevent cross-contamination.

Example Flow:
1. User enters "config_wizard" panel
2. PanelManager creates "config_wizard_panel_crumb" key
3. User navigates within panel (keys stored under panel crumb)
4. User switches to "setup_wizard" panel
5. PanelManager clears "config_wizard_panel_crumb"
6. PanelManager creates "setup_wizard_panel_crumb" key

Layer Position
--------------
Layer 1, Position 4 (zNavigation) - Handler (Tier 2)

Integration
-----------
- Called by: Breadcrumbs handler for panel operations
- Session: Read/write SESSION_KEY_ZCRUMBS for panel keys
"""

from zOS import Any, Dict

from zOS.L1_Foundation.a_zConfig.zConfig_modules.config_constants import SESSION_KEY_ZCRUMBS

# Panel constants
_PANEL_KEY_SUFFIX = "_panel_crumb"
_PANEL_KEY_SEARCH = "_panel"

_LOG_CREATED_PANEL_KEY = "[PanelManager] Created panel key '%s' for panel '%s'"
_LOG_CLEARING_PANEL_KEYS = "[PanelManager] Clearing other panel keys (current: '%s')"
_LOG_REMOVED_PANEL_KEY = "[PanelManager] Removed panel key '%s'"
_LOG_NO_PANEL_KEYS_FOUND = "[PanelManager] No other panel keys found to clear"


class PanelManager:
    """
    Panel management for wizard-style navigation.
    
    Manages panel-specific breadcrumb keys and ensures clean panel transitions
    by clearing inactive panel state.
    
    Attributes
    ----------
    logger : Any
        Logger instance for panel operations
    
    Methods
    -------
    create_panel_key(panel_name, session)
        Generate unique breadcrumb key for panel
    clear_other_panel_keys(current_panel, session)
        Remove breadcrumb keys from inactive panels
    """

    # Class-level type declarations
    logger: Any  # Logger instance
    breadcrumbs: Any  # Parent Breadcrumbs (SSOT scope removal)

    def __init__(self, logger: Any, breadcrumbs: Any = None) -> None:
        """
        Initialize panel manager.
        
        Args
        ----
        logger : Any
            Logger instance for panel operations
        breadcrumbs : Any, optional
            Parent Breadcrumbs instance. Used so panel cleanup removes scopes via
            the SSOT ``Breadcrumbs.remove_scope`` instead of mutating the trails
            dict directly (keeps crumb manipulation in one place).
        """
        self.logger = logger
        self.breadcrumbs = breadcrumbs

    def create_panel_key(self, panel_name: str, _session: Dict) -> str:
        """
        Create unique breadcrumb key for a panel.
        
        Generates a panel-specific breadcrumb key using the format
        "{panel_name}_panel_crumb". This key is used to scope breadcrumbs
        within wizard flows.
        
        Args
        ----
        panel_name : str
            Name of the panel (e.g., "config_wizard", "setup_wizard")
        session : Dict
            Session dictionary containing breadcrumb state
        
        Returns
        -------
        str
            Generated panel key (e.g., "config_wizard_panel_crumb")
        
        Examples
        --------
        Create panel key::
        
            key = panel_mgr.create_panel_key("config_wizard", session)
            # Returns: "config_wizard_panel_crumb"
        
        Notes
        -----
        - Key Format: "{panel_name}_panel_crumb"
        - Used as breadcrumb trail key in session
        - Scopes breadcrumbs to specific wizard panel
        """
        panel_key = f"{panel_name}{_PANEL_KEY_SUFFIX}"
        self.logger.debug(_LOG_CREATED_PANEL_KEY, panel_key, panel_name)
        return panel_key

    def clear_other_panel_keys(self, current_panel: str, session: Dict) -> None:
        """
        Clear breadcrumb keys from other panels.
        
        Removes breadcrumb keys from panels that are not the current panel.
        This prevents navigation conflicts when switching between wizard panels.
        
        Args
        ----
        current_panel : str
            Current active panel name
        session : Dict
            Session dictionary containing breadcrumb state
        
        Examples
        --------
        Clear other panels::
        
            # Switch to config_wizard panel
            panel_mgr.clear_other_panel_keys("config_wizard", session)
            # Removes: setup_wizard_panel_crumb, onboarding_panel_crumb, etc.
            # Keeps: config_wizard_panel_crumb
        
        Notes
        -----
        - Searches for keys containing "_panel" suffix
        - Removes all panel keys except current panel
        - Prevents cross-panel breadcrumb contamination
        - Logs each removal for debugging
        
        Algorithm
        ---------
        1. Get breadcrumb trails dict from session
        2. Generate current panel key
        3. Find all keys containing "_panel"
        4. For each panel key (except current):
           a. Remove key from trails dict
           b. Log removal
        5. Update session with modified trails
        """
        # Get breadcrumb trails from session
        crumbs_dict = session.get(SESSION_KEY_ZCRUMBS, {})
        trails = crumbs_dict.get('trails', crumbs_dict)

        # Generate current panel key
        current_panel_key = self.create_panel_key(current_panel, session)

        self.logger.debug(_LOG_CLEARING_PANEL_KEYS, current_panel)

        # Find and remove other panel keys
        panel_keys_to_remove = [
            key for key in trails.keys()
            if _PANEL_KEY_SEARCH in key and key != current_panel_key
        ]

        if panel_keys_to_remove:
            for key in panel_keys_to_remove:
                # SSOT scope removal when wired to the parent Breadcrumbs;
                # fall back to a direct delete only if constructed standalone.
                if self.breadcrumbs is not None:
                    self.breadcrumbs.remove_scope(key)
                else:
                    del trails[key]
                self.logger.debug(_LOG_REMOVED_PANEL_KEY, key)
        else:
            self.logger.debug(_LOG_NO_PANEL_KEYS_FOUND)

        # Update session
        if 'trails' in crumbs_dict:
            crumbs_dict['trails'] = trails
        else:
            crumbs_dict = trails
        session[SESSION_KEY_ZCRUMBS] = crumbs_dict

    def is_panel_key(self, key: str) -> bool:
        """
        Check if a breadcrumb key is a panel key.
        
        Args
        ----
        key : str
            Breadcrumb key to check
        
        Returns
        -------
        bool
            True if key is a panel key (contains "_panel"), False otherwise
        
        Examples
        --------
        Check panel key::
        
            is_panel = panel_mgr.is_panel_key("config_wizard_panel_crumb")
            # Returns: True
            
            is_panel = panel_mgr.is_panel_key("users.menu.list")
            # Returns: False
        """
        return _PANEL_KEY_SEARCH in key
