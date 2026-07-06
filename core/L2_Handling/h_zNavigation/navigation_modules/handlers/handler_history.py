# zOS/core/L2_Handling/h_zNavigation/navigation_modules/handlers/handler_history.py

"""
Navigation History Handler for zNavigation Subsystem.

This module provides the HistoryManager class, which manages navigation history
tracking with FIFO overflow management. Extracted from navigation_state.py to
follow the approved handler pattern from e_zDispatch.

Architecture
------------
The HistoryManager encapsulates all history-related logic that was previously
in the Navigation class. It provides:

1. **History Addition** (add_to_history)
   - Appends location to history list
   - Enforces FIFO overflow (max 50 items)
   - Session state updates

2. **History Retrieval** (get_history)
   - Safely reads history from session
   - Returns empty list if no history exists

3. **History Clearing** (clear_history)
   - Removes all history from session
   - Preserves current location

Session Management
------------------
This handler manages the SESSION_KEY_NAVIGATION_HISTORY session key:

History Structure:
    session[SESSION_KEY_NAVIGATION_HISTORY] = [
        {"target": "prev_1", "context": {...}, "timestamp": "..."},
        {"target": "prev_2", "context": {...}, "timestamp": "..."},
        ...  # Up to 50 items (FIFO overflow)
    ]

FIFO Overflow Strategy:
- Size Limit: 50 items (configurable via _HISTORY_MAX_SIZE)
- Overflow: When limit reached, oldest item (index 0) is removed
- Preservation: Current location stored separately, not in history

Layer Position
--------------
Layer 1, Position 4 (zNavigation) - Handler (Tier 2)

Integration
-----------
- Called by: Navigation (navigation_state.py) for history operations
- Session: Read/write SESSION_KEY_NAVIGATION_HISTORY
"""

from zOS import Any, Dict, List

# Session key constant (SSOT: navigation_constants — do not re-declare the literal)
from ..navigation_constants import SESSION_KEY_NAVIGATION_HISTORY

# History size limit
_HISTORY_MAX_SIZE = 50
_HISTORY_FIRST_INDEX = 0


class HistoryManager:
    """
    Navigation history manager for zNavigation subsystem.
    
    Manages navigation history tracking with FIFO overflow management.
    Extracted from Navigation class for better separation of concerns.
    
    Attributes
    ----------
    zos : Any
        Reference to zOS instance for session access
    logger : Any
        Logger instance for history operations
    
    Methods
    -------
    add_to_history(location)
        Add location to history with FIFO overflow
    get_history()
        Get full history list from session
    clear_history()
        Clear all history from session
    """

    # Class-level type declarations
    zos: Any  # zOS instance
    logger: Any  # Logger instance

    def __init__(self, zos: Any, logger: Any) -> None:
        """
        Initialize history manager.
        
        Args
        ----
        zos : Any
            zOS instance for session access
        logger : Any
            Logger instance for history operations
        """
        self.zos = zos
        self.logger = logger

    def add_to_history(self, location: Dict[str, Any]) -> None:
        """
        Add location to navigation history.
        
        Appends location to history and enforces FIFO overflow when limit is reached.
        
        Args
        ----
        location : Dict[str, Any]
            Location dict to add to history (contains target, context, timestamp)
        
        Examples
        --------
        Add location to history::
        
            location = {
                "target": "users.menu.list",
                "context": {"filter": "active"},
                "timestamp": "2025-10-31 12:34:56"
            }
            history_manager.add_to_history(location)
        
        Notes
        -----
        Algorithm:
        1. Get current history from session
        2. Append new location
        3. If history exceeds _HISTORY_MAX_SIZE, remove oldest (index 0)
        4. Update session with modified history
        
        Overflow Strategy:
        FIFO (First In, First Out): When history reaches _HISTORY_MAX_SIZE items,
        the oldest item (at index 0) is removed before adding the new item.
        """
        # Get history using helper
        history = self.get_history()

        # Add location to history
        history.append(location)

        # Enforce size limit with FIFO overflow
        if len(history) > _HISTORY_MAX_SIZE:
            removed = history.pop(_HISTORY_FIRST_INDEX)
            self.logger.debug(
                f"[HistoryManager] FIFO overflow: removed oldest entry "
                f"(target: {removed.get('target', 'unknown')})"
            )

        # Update session with modified history
        self.zos.session[SESSION_KEY_NAVIGATION_HISTORY] = history
        self.logger.debug(
            f"[HistoryManager] Added to history: {location.get('target', 'unknown')} "
            f"(total: {len(history)} entries)"
        )

    def get_history(self) -> List[Dict[str, Any]]:
        """
        Get history list from session.
        
        Returns
        -------
        List[Dict[str, Any]]
            Navigation history list from session, or empty list if no history exists
        
        Examples
        --------
        Get all history::
        
            history = history_manager.get_history()
            for entry in history:
                print(f"Visited: {entry['target']} at {entry['timestamp']}")
        
        Notes
        -----
        - Returns [] if SESSION_KEY_NAVIGATION_HISTORY doesn't exist in session
        - Does not modify session state (read-only)
        - Limited to _HISTORY_MAX_SIZE entries (FIFO overflow)
        """
        return self.zos.session.get(SESSION_KEY_NAVIGATION_HISTORY, [])

    def clear_history(self) -> None:
        """
        Clear all navigation history.
        
        Removes all history entries from session while preserving current location.
        
        Examples
        --------
        Clear history::
        
            history_manager.clear_history()
            # history is now empty, current location unchanged
        
        Notes
        -----
        - Sets SESSION_KEY_NAVIGATION_HISTORY to empty list
        - Does NOT affect current location (stored separately)
        - Useful for session cleanup or privacy features
        """
        self.zos.session[SESSION_KEY_NAVIGATION_HISTORY] = []
        self.logger.info("[HistoryManager] Navigation history cleared")

    def get_history_size(self) -> int:
        """
        Get current history size.
        
        Returns
        -------
        int
            Number of entries in history
        
        Examples
        --------
        Check history size::
        
            size = history_manager.get_history_size()
            if size > 40:
                print("History nearly full")
        """
        return len(self.get_history())

    def get_max_size(self) -> int:
        """
        Get maximum history size.
        
        Returns
        -------
        int
            Maximum number of history entries (_HISTORY_MAX_SIZE)
        
        Examples
        --------
        Check max size::
        
            max_size = history_manager.get_max_size()
            print(f"History limit: {max_size} entries")
        """
        return _HISTORY_MAX_SIZE
