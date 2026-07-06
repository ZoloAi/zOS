# zOS/core/L2_Handling/h_zNavigation/navigation_modules/handlers/handler_breadcrumbs_ops.py

"""
Breadcrumb Operations Handler for zNavigation Subsystem.

This module provides the BreadcrumbsOpsHandler class, which manages breadcrumb
trail operations (RESET, APPEND, REPLACE, POP_TO, POP). Extracted from
navigation_breadcrumbs.py to follow the approved modular pattern.

Architecture
------------
The BreadcrumbsOpsHandler encapsulates all breadcrumb trail manipulation:

1. **Operation Handlers** (4 operation types)
   - RESET: Clear trail and restart from new key
   - APPEND: Add key to trail (default)
   - REPLACE: Replace last key in trail
   - POP_TO: Pop back to specific key

2. **Context Tracking** (_update_context_and_depth)
   - Track navigation type (navbar, menu, sequential, etc.)
   - Track block type (root, panel, menu, etc.)
   - Update depth maps for panel navigation

Operation Types
---------------
- RESET: Navbar navigation, clears trail
- APPEND: Normal forward navigation
- REPLACE: Update current position
- POP_TO: Jump back to specific point
- POP: Backward navigation (handled by ZBackHandler)

Layer Position
--------------
Layer 1, Position 4 (zNavigation) - Handler (Tier 2)

Integration
-----------
- Called by: Breadcrumbs class for trail operations
- Session: Read/write SESSION_KEY_ZCRUMBS trails, context, depth maps
"""

from zOS import Any, Dict, List

from zOS.L1_Foundation.a_zConfig.zConfig_modules.config_constants import SESSION_KEY_ZCRUMBS

# Operation constants
OP_RESET = "RESET"
OP_APPEND = "APPEND"
OP_REPLACE = "REPLACE"
OP_POP_TO = "POP_TO"
OP_POP = "POP"
OP_NEW_KEY = "NEW_KEY"

# Navigation type constants
NAV_NAVBAR = "NAVBAR"
NAV_DELTA = "DELTA"
NAV_DASHBOARD = "DASHBOARD"
NAV_MENU = "MENU"
NAV_SEQUENTIAL = "SEQUENTIAL"
NAV_ZLINK = "ZLINK"

# Block type constants
TYPE_ROOT = "ROOT"
TYPE_PANEL = "PANEL"
TYPE_MENU = "MENU"
TYPE_SELECTION = "SELECTION"
TYPE_SEQUENTIAL = "SEQUENTIAL"

# Keys for enhanced format
_KEY_TRAILS = "trails"
_KEY_CONTEXT = "context"
_KEY_DEPTH_MAP = "depth_map"

# Log messages
_LOG_RESET_OPERATION = "[BreadcrumbsOps] RESET operation - clearing trail and starting fresh"
_LOG_POP_TO_OPERATION = "[BreadcrumbsOps] POP_TO operation - popping to key: %s"
_LOG_REPLACE_OPERATION = "[BreadcrumbsOps] REPLACE operation - replacing last key"
_LOG_APPEND_OPERATION = "[BreadcrumbsOps] APPEND operation - adding key to trail"
_LOG_CONTEXT_UPDATE = "[BreadcrumbsOps] Context updated: operation=%s, nav_type=%s, block_type=%s"
_LOG_DEPTH_UPDATE = "[BreadcrumbsOps] Depth map updated for: %s -> depth=%d"


class BreadcrumbsOpsHandler:
    """
    Breadcrumb trail operations handler.
    
    Manages breadcrumb trail manipulation with support for RESET, APPEND,
    REPLACE, and POP_TO operations. Tracks navigation context and depth.
    
    Attributes
    ----------
    logger : Any
        Logger instance for operations
    
    Methods
    -------
    handle_reset_operation(session, trail, key)
        Clear trail and start fresh with new key
    handle_pop_to_operation(session, trail, key)
        Pop trail back to specific key
    handle_replace_operation(session, trail, key)
        Replace last key in trail
    handle_append_operation(session, trail, key)
        Append key to trail
    update_context_and_depth(session, operation, nav_type, block_type, block, key, trail)
        Update context tracking and depth maps
    """

    # Class-level type declarations
    logger: Any  # Logger instance

    def __init__(self, logger: Any) -> None:
        """
        Initialize breadcrumb operations handler.
        
        Args
        ----
        logger : Any
            Logger instance for operations
        """
        self.logger = logger

    def handle_reset_operation(
        self,
        _session: Dict[str, Any],
        trail: List[str],
        key: str
    ) -> None:
        """
        Handle RESET operation - clear trail and start fresh.
        
        Used for navbar navigation to reset breadcrumb trail.
        
        Args
        ----
        session : Dict[str, Any]
            Session dict containing breadcrumb state
        trail : List[str]
            Current trail (will be cleared)
        key : str
            New key to start trail with
        
        Examples
        --------
        Reset trail::
        
            handler.handle_reset_operation(
                session,
                ["Old", "Keys"],
                "NewStart"
            )
            # Trail is now: ["NewStart"]
        """
        trail.clear()
        trail.append(key)
        self.logger.debug(_LOG_RESET_OPERATION)

    def handle_pop_to_operation(
        self,
        _session: Dict[str, Any],
        trail: List[str],
        key: str
    ) -> None:
        """
        Handle POP_TO operation - pop trail back to specific key.
        
        Removes all keys after the specified key in trail.
        
        Args
        ----
        session : Dict[str, Any]
            Session dict containing breadcrumb state
        trail : List[str]
            Current trail
        key : str
            Key to pop back to
        
        Examples
        --------
        Pop to key::
        
            handler.handle_pop_to_operation(
                session,
                ["A", "B", "C", "D"],
                "B"
            )
            # Trail is now: ["A", "B"]
        """
        if key in trail:
            index = trail.index(key)
            del trail[index + 1:]
        self.logger.debug(_LOG_POP_TO_OPERATION, key)

    def handle_replace_operation(
        self,
        _session: Dict[str, Any],
        trail: List[str],
        key: str
    ) -> None:
        """
        Handle REPLACE operation - replace last key in trail.
        
        Updates the current position without adding to history.
        
        Args
        ----
        session : Dict[str, Any]
            Session dict containing breadcrumb state
        trail : List[str]
            Current trail
        key : str
            New key to replace with
        
        Examples
        --------
        Replace last key::
        
            handler.handle_replace_operation(
                session,
                ["A", "B", "C"],
                "NewC"
            )
            # Trail is now: ["A", "B", "NewC"]
        """
        if trail:
            trail[-1] = key
        else:
            trail.append(key)
        self.logger.debug(_LOG_REPLACE_OPERATION)

    def handle_append_operation(
        self,
        _session: Dict[str, Any],
        trail: List[str],
        key: str
    ) -> None:
        """
        Handle APPEND operation - add key to trail.
        
        Default operation for forward navigation.
        
        Args
        ----
        session : Dict[str, Any]
            Session dict containing breadcrumb state
        trail : List[str]
            Current trail
        key : str
            Key to append
        
        Examples
        --------
        Append key::
        
            handler.handle_append_operation(
                session,
                ["A", "B"],
                "C"
            )
            # Trail is now: ["A", "B", "C"]
        """
        if trail and trail[-1] == key:
            self.logger.debug(f"[BreadcrumbsOps] APPEND skipped — '{key}' already at end of trail")
            return
        trail.append(key)
        self.logger.debug(_LOG_APPEND_OPERATION)

    def handle_append_raw_operation(
        self,
        _session: Dict[str, Any],
        trail: List[str],
        key: str
    ) -> None:
        """
        Handle APPEND_RAW operation - append verbatim, NO consecutive-dup guard.

        APPEND drops a key equal to the immediately-preceding one (a re-render
        guard for sequential zCLI traversal). The click-origin ancestry chain
        wants the OPPOSITE: an airtight, verbatim echo where a legitimate repeat
        (a chain key equal to the departing scope's current tail, or two equal
        adjacent ancestry keys) MUST survive — ``show: session`` is the engine
        X-ray, not a curated breadcrumb. This path appends unconditionally.

        Args
        ----
        session : Dict[str, Any]
            Session dict containing breadcrumb state
        trail : List[str]
            Current trail
        key : str
            Key to append verbatim
        """
        trail.append(key)
        self.logger.debug("[BreadcrumbsOps] APPEND_RAW — appended '%s' verbatim", key)

    def update_context_and_depth(
        self,
        session: Dict[str, Any],
        operation: str,
        nav_type: str,
        block_type: str,
        block: str,
        _key: str,
        trail: List[str]
    ) -> None:
        """
        Update context tracking and depth maps.
        
        Tracks navigation patterns for analytics and panel depth tracking.
        
        Args
        ----
        session : Dict[str, Any]
            Session dict containing breadcrumb state
        operation : str
            Operation type (RESET, APPEND, etc.)
        nav_type : str
            Navigation type (NAVBAR, MENU, etc.)
        block_type : str
            Block type (ROOT, PANEL, etc.)
        block : str
            Block identifier
        key : str
            Current key
        trail : List[str]
            Current trail
        
        Examples
        --------
        Update context::
        
            handler.update_context_and_depth(
                session,
                OP_APPEND,
                NAV_MENU,
                TYPE_MENU,
                "MainMenu",
                "Settings",
                ["Dashboard", "Settings"]
            )
        """
        # Update context
        self._update_context(
            session,
            operation=operation,
            nav_type=nav_type,
            block_type=block_type,
            current_file=block
        )

        # Update depth map (for panel navigation)
        if block_type == TYPE_PANEL:
            self._update_depth_map(session, block, len(trail))

        self.logger.debug(
            _LOG_CONTEXT_UPDATE,
            operation,
            nav_type,
            block_type
        )

    def _update_context(
        self,
        session: Dict[str, Any],
        operation: str,
        nav_type: str,
        block_type: str | None = None,
        current_file: str | None = None
    ) -> None:
        """Update context tracking in session."""
        crumbs_dict = session.get(SESSION_KEY_ZCRUMBS, {})

        # Ensure enhanced format
        if _KEY_TRAILS not in crumbs_dict:
            crumbs_dict = {
                _KEY_TRAILS: crumbs_dict if isinstance(crumbs_dict, dict) and crumbs_dict else {},
                _KEY_CONTEXT: {},
                _KEY_DEPTH_MAP: {}
            }
            session[SESSION_KEY_ZCRUMBS] = crumbs_dict

        # Update context
        context = crumbs_dict.get(_KEY_CONTEXT, {})
        context.update({
            "operation": operation,
            "nav_type": nav_type,
            "block_type": block_type,
            "current_file": current_file
        })
        crumbs_dict[_KEY_CONTEXT] = context

    def _update_depth_map(
        self,
        session: Dict[str, Any],
        panel_key: str,
        depth: int
    ) -> None:
        """Update depth map for panel navigation."""
        crumbs_dict = session.get(SESSION_KEY_ZCRUMBS, {})

        # Ensure enhanced format
        if _KEY_DEPTH_MAP not in crumbs_dict:
            crumbs_dict[_KEY_DEPTH_MAP] = {}

        # Update depth
        crumbs_dict[_KEY_DEPTH_MAP][panel_key] = depth
        self.logger.debug(_LOG_DEPTH_UPDATE, panel_key, depth)
