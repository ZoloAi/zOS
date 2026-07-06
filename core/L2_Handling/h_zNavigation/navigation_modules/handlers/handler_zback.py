# zOS/core/L2_Handling/h_zNavigation/navigation_modules/handlers/handler_zback.py

"""
Backward Navigation Handler for zNavigation Subsystem.

This module provides the ZBackHandler class, which manages backward navigation
through breadcrumb trails with scope transitions and file reloading. Extracted
from navigation_breadcrumbs.py to follow the approved modular pattern.

Architecture
------------
The ZBackHandler encapsulates all zBack (backward navigation) operations:

1. **Trail Popping** (handle_trail_pop)
   - Pop last key from current trail
   - Handle empty trail scope transitions
   - Cascade empty scope removal

2. **Session Updates** (parse_crumb_and_update)
   - Parse crumb to extract folder, file, block
   - Update session path keys
   - Return resolved resume key

3. **File Reloading** (reload_file_after_back)
   - Reload file using loader
   - Validate block and keys
   - Prepare navigation context

Backward Navigation Flow
------------------------
1. Get active crumb and trail from session
2. Pop last key from trail (or transition to parent scope)
3. Parse active crumb to get file/block context
4. Update session with parsed values
5. Reload file via loader
6. Return (block_dict, block_keys, start_key)

Layer Position
--------------
Layer 1, Position 4 (zNavigation) - Handler (Tier 2)

Integration
-----------
- Called by: Breadcrumbs class for zBack operations
- Uses: navigation_helpers for file reload
- Session: Read/write SESSION_KEY_ZCRUMBS, path keys
"""

from zOS import Any, Dict, List, Optional, Tuple

from zOS.L1_Foundation.a_zConfig.zConfig_modules.config_constants import (
    SESSION_KEY_ZCRUMBS,
    SESSION_KEY_ZVAFOLDER,
    SESSION_KEY_ZVAFILE,
    SESSION_KEY_ZBLOCK,
)

from ..navigation_helpers import reload_current_file
from ..breadcrumb_marker import is_arrival

# Constants from navigation_constants
_SEPARATOR_DOT = "."
_SEPARATOR_EMPTY = ""
_PREFIX_DEFAULT_PATH = "@."
# A zOS scope key is {folder}.{file}.{block} where {file} is a two-segment
# "zUI.<name>" filename (the zOS file-naming convention). So a valid crumb is
# at minimum 4 parts: folder(≥1) + file(2) + block(1). The filename occupies
# the two segments immediately before the block; everything earlier is folder.
_CRUMB_PARTS_MIN = 4
# History-SSOT duplicate-frame suffix. Revisited scopes are stored as
# "{scope}::dupN" so zBack can unwind the true traversal; the suffix must be
# stripped before a key is parsed into {folder}.{file}.{block}. Keep in sync
# with navigation_breadcrumbs.Breadcrumbs._DUP_SEP.
_DUP_SEP = "::dup"
_INDEX_FOLDER_END = -3
_INDEX_FILENAME_START = -3
_INDEX_FILENAME_END = -1
_INDEX_LAST_PART = -1
_KEY_TRAILS = "trails"

# Operation constants
OP_POP = "POP"
NAV_SEQUENTIAL = "SEQUENTIAL"

# Log messages
_LOG_TRAIL_AFTER_POP = "[ZBackHandler] Trail after pop for '%s': %s"
_LOG_POPPED_SCOPE = "[ZBackHandler] Popped scope '%s': %s"
_LOG_ACTIVE_CRUMB_PARENT = "[ZBackHandler] Moved to parent scope: '%s'"
_LOG_PARENT_TRAIL_BEFORE = "[ZBackHandler] Parent trail before pop: %s"
_LOG_PARENT_TRAIL_AFTER = "[ZBackHandler] Parent trail after pop: %s"
_LOG_ROOT_EMPTY = "[ZBackHandler] At root with empty trail - nothing to pop"
_LOG_POST_POP_EMPTY = "[ZBackHandler] Popped empty scope '%s': %s"
_LOG_PARENT_TRAIL_PRE_SECOND = "[ZBackHandler] Parent trail before second pop: %s"
_LOG_PARENT_TRAIL_POST_SECOND = "[ZBackHandler] Parent trail after second pop: %s"
_LOG_ACTIVE_PARTS = "[ZBackHandler] Active crumb parts: %s (len=%d)"
_LOG_PARSED_SESSION = "[ZBackHandler] Parsed session - folder:'%s', file:'%s', block:'%s'"
_LOG_RELOADING_PATH = "[ZBackHandler] Reloading file: %s"
_LOG_WARN_INVALID_KEY = "[ZBackHandler] Invalid key '%s' not in block '%s', using None"
_LOG_ERR_INVALID_CRUMB = "[ZBackHandler] Invalid crumb format: %s"
_ERR_EMPTY_FILENAME = "[ZBackHandler] Empty filename after parsing - cannot reload"
_ERR_NO_KEYS_AFTER_BACK = "[ZBackHandler] No keys found in block after zBack"


class ZBackHandler:
    """
    Backward navigation handler for breadcrumb trail.
    
    Manages zBack operations including trail popping, scope transitions,
    crumb parsing, session updates, and file reloading.
    
    Attributes
    ----------
    logger : Any
        Logger instance for zBack operations
    
    Methods
    -------
    handle_trail_pop_and_scope_transition(session, active_crumb, root_crumb, trail)
        Pop from trail and handle scope transitions
    parse_crumb_and_update_session(session, active_crumb, trail)
        Parse crumb and update session path keys
    reload_file_after_back(session, resolved_key, walker)
        Reload file and prepare navigation context
    """

    # Class-level type declarations
    logger: Any  # Logger instance

    def __init__(self, logger: Any) -> None:
        """
        Initialize zBack handler.
        
        Args
        ----
        logger : Any
            Logger instance for zBack operations
        """
        self.logger = logger

    def handle_trail_pop_and_scope_transition(
        self,
        session: Dict[str, Any],
        active_crumb: str,
        root_crumb: str,
        trail: List[str]
    ) -> Tuple[str, List[str]]:
        """
        Handle trail popping and scope transitions for zBack navigation.
        
        Implements multi-step algorithm:
        - Step 1: Pop from current trail
        - Step 2: Handle empty trail (scope transition to parent)
        - Step 3: Cascade empty scope removal
        
        Args
        ----
        session : Dict[str, Any]
            Session dict containing breadcrumb state
        active_crumb : str
            Current active breadcrumb scope
        root_crumb : str
            Root breadcrumb scope (original starting point)
        trail : List[str]
            Current trail (list of navigation keys)
        
        Returns
        -------
        Tuple[str, List[str]]
            Updated (active_crumb, trail) after popping
        
        Examples
        --------
        Pop from trail::
        
            active, trail = handler.handle_trail_pop_and_scope_transition(
                session,
                "@.zUI.settings.Network",
                "@.zUI.main.MainMenu",
                ["WiFi", "DNS", "Proxy"]
            )
            # Returns: ("@.zUI.settings.Network", ["WiFi", "DNS"])
        
        Scope transition::
        
            active, trail = handler.handle_trail_pop_and_scope_transition(
                session,
                "@.zUI.settings.Network",
                "@.zUI.main.MainMenu",
                []  # Empty trail
            )
            # Transitions to parent scope
            # Returns: ("@.zUI.main.MainMenu", [...])
        
        Notes
        -----
        Algorithm:
        1. If trail has items: pop last item
        2. If trail is empty and not at root:
           a. Pop current scope
           b. Move to parent scope
           c. Get parent's trail
           d. Pop from parent's trail
        3. If trail still empty after step 2:
           a. Remove now-empty scope
           b. Move to grandparent
           c. Pop from grandparent's trail
        """
        # STEP 0: Arrival-scope short-circuit (linked/delta pages).
        # A scope whose first trail entry is an "α<block>" arrival marker represents
        # one page reached by zLink/zDelta. zBack on it must leave the ENTIRE page
        # in a single press — not unwind the page's display keys one at a time —
        # so we skip per-key popping and fall straight into the scope transition.
        # The arrival marker is set by Breadcrumbs.seed_scope(arrival=True) (SSOT);
        # is_arrival is the ONE reader of the glyph (breadcrumb_marker SSOT).
        _is_arrival_scope = (
            bool(trail)
            and is_arrival(trail[0])
            and active_crumb != root_crumb
        )
        if _is_arrival_scope:
            trail = []  # collapse the page unit; scope transition below leaves it

        # STEP 1: Pop from Current Trail
        if trail:
            trail.pop()
            self.logger.debug(_LOG_TRAIL_AFTER_POP, active_crumb, trail)

            # Update context for POP operation
            self._update_context_for_pop(session, active_crumb)
        else:
            # STEP 2: Handle Empty Trail (Scope Transition)
            if active_crumb != root_crumb:
                # Not at root - can move to parent
                popped_scope = self._pop_scope(session, active_crumb)
                self.logger.debug(_LOG_POPPED_SCOPE, active_crumb, popped_scope)

                # Move to parent scope
                active_crumb = self._get_active_crumb(session)
                self.logger.debug(_LOG_ACTIVE_CRUMB_PARENT, active_crumb)

                # Get parent's trail
                trail = self._get_crumbs_dict(session)[active_crumb]
                self.logger.debug(_LOG_PARENT_TRAIL_BEFORE, trail)

                # Pop the parent's last key
                if trail:
                    trail.pop()
                    self.logger.debug(_LOG_PARENT_TRAIL_AFTER, trail)
            else:
                # At root with empty trail - nothing to pop
                self.logger.debug(_LOG_ROOT_EMPTY)

        # STEP 3: Cascade Empty Scope Removal
        if not trail and active_crumb != root_crumb:
            # Current scope is now empty and not root - remove it
            popped_scope = self._pop_scope(session, active_crumb)
            self.logger.debug(_LOG_POST_POP_EMPTY, active_crumb, popped_scope)

            # Move to parent scope
            active_crumb = self._get_active_crumb(session)
            self.logger.debug(_LOG_ACTIVE_CRUMB_PARENT, active_crumb)

            # Get parent's trail
            trail = self._get_crumbs_dict(session)[active_crumb]
            self.logger.debug(_LOG_PARENT_TRAIL_PRE_SECOND, trail)

            # Pop parent's last key
            if trail:
                trail.pop()
                self.logger.debug(_LOG_PARENT_TRAIL_POST_SECOND, trail)

        return active_crumb, trail

    def parse_crumb_and_update_session(
        self,
        session: Dict[str, Any],
        active_crumb: str,
        trail: List[str]
    ) -> Optional[str]:
        """
        Parse active crumb and update session with file context.
        
        Extracts folder, file, and block from crumb path and updates session
        keys for navigation context.
        
        Args
        ----
        session : Dict[str, Any]
            Session dict to update
        active_crumb : str
            Active breadcrumb scope to parse
        trail : List[str]
            Current trail (for resolving resume key)
        
        Returns
        -------
        Optional[str]
            Resolved zBack key (where to resume), or None if trail empty
        
        Examples
        --------
        Parse crumb::
        
            key = handler.parse_crumb_and_update_session(
                session,
                "@.zUI.settings.Network",
                ["WiFi", "DNS"]
            )
            # Updates session:
            #   SESSION_KEY_ZVAFOLDER = "@"
            #   SESSION_KEY_ZVAFILE = "zUI.settings"
            #   SESSION_KEY_ZBLOCK = "Network"
            # Returns: "DNS" (last key in trail)
        
        Notes
        -----
        - Crumb format: {folder}.{file}.{block}
        - Minimum 3 parts required
        - Invalid crumbs log error and skip session update
        """
        # Parse crumb parts. Strip any history-SSOT "::dupN" suffix first so a
        # revisited-page frame resolves to the same {folder}.{file}.{block} path
        # as its first visit.
        canonical_crumb = active_crumb.split(_DUP_SEP)[0]
        parts = canonical_crumb.split(_SEPARATOR_DOT)
        self.logger.debug(_LOG_ACTIVE_PARTS, parts, len(parts))

        if len(parts) >= _CRUMB_PARTS_MIN:
            # Extract: {folder}.{zUI.filename}.{BlockName} — the filename is the
            # two segments before the block (zOS "zUI.<name>" convention), so the
            # folder is everything up to that two-segment filename.
            base_path_parts = parts[:_INDEX_FOLDER_END]
            session[SESSION_KEY_ZVAFOLDER] = (
                _SEPARATOR_DOT.join(base_path_parts) if base_path_parts else _SEPARATOR_EMPTY
            )
            session[SESSION_KEY_ZVAFILE] = _SEPARATOR_DOT.join(
                parts[_INDEX_FILENAME_START:_INDEX_FILENAME_END]
            )
            session[SESSION_KEY_ZBLOCK] = parts[_INDEX_LAST_PART]
            self.logger.debug(
                _LOG_PARSED_SESSION,
                session[SESSION_KEY_ZVAFOLDER],
                session[SESSION_KEY_ZVAFILE],
                session[SESSION_KEY_ZBLOCK]
            )
        else:
            # Invalid crumb format
            self.logger.error(_LOG_ERR_INVALID_CRUMB, active_crumb)

        # Return resolved zBack key
        return trail[_INDEX_LAST_PART] if trail else None

    def reload_file_after_back(
        self,
        session: Dict[str, Any],
        resolved_zback_key: Optional[str],
        walker: Optional[Any]
    ) -> Tuple[Dict[str, Any], List[str], Optional[str]]:
        """
        Reload file after zBack navigation and prepare return context.
        
        Loads file via walker, extracts block dict and keys, validates
        resume key, and prepares navigation context for resumption.
        
        Args
        ----
        session : Dict[str, Any]
            Session dict with updated path keys
        resolved_zback_key : Optional[str]
            Key to resume from (or None for start of block)
        walker : Optional[Any]
            Walker instance for file loading
        
        Returns
        -------
        Tuple[Dict[str, Any], List[str], Optional[str]]
            Tuple of (block_dict, block_keys, start_key)
        
        Examples
        --------
        Reload file::
        
            block_dict, keys, start_key = handler.reload_file_after_back(
                session,
                "DNS",
                walker
            )
            # Returns:
            #   block_dict: {WiFi: {...}, DNS: {...}, Proxy: {...}}
            #   keys: ["WiFi", "DNS", "Proxy"]
            #   start_key: "DNS"
        
        Notes
        -----
        - Uses reload_current_file helper for actual loading
        - Validates start_key exists in block
        - Returns None start_key if validation fails
        - Returns empty results if file load fails
        """
        # Get path from session
        folder = session.get(SESSION_KEY_ZVAFOLDER, _SEPARATOR_EMPTY)
        file = session.get(SESSION_KEY_ZVAFILE, _SEPARATOR_EMPTY)

        if not file:
            self.logger.error(_ERR_EMPTY_FILENAME)
            return {}, [], None

        # Build zPath
        if folder:
            zpath = f"{folder}{_SEPARATOR_DOT}{file}"
        else:
            zpath = f"{_PREFIX_DEFAULT_PATH}{file}"

        self.logger.debug(_LOG_RELOADING_PATH, zpath)

        # Load file
        zfile_parsed = reload_current_file(walker)

        # Extract block dict and keys
        active_block_dict = zfile_parsed.get(session[SESSION_KEY_ZBLOCK], {})
        block_keys = list(active_block_dict.keys())

        # Validate
        if not block_keys:
            self.logger.error(_ERR_NO_KEYS_AFTER_BACK)
            return active_block_dict, [], None

        # Normalize start key
        if resolved_zback_key and resolved_zback_key in block_keys:
            start_key = resolved_zback_key
        else:
            if resolved_zback_key:
                self.logger.warning(
                    _LOG_WARN_INVALID_KEY,
                    resolved_zback_key,
                    session[SESSION_KEY_ZBLOCK]
                )
            start_key = None

        return active_block_dict, block_keys, start_key

    # Private helper methods

    def _update_context_for_pop(self, _session: Dict[str, Any], current_file: str) -> None:
        """Update context tracking for POP operation."""
        # This would call context update if needed
        # For now, just log
        self.logger.debug(f"[ZBackHandler] Context updated for POP in {current_file}")

    def _pop_scope(self, session: Dict[str, Any], scope: str) -> Optional[List[str]]:
        """Pop (remove) a scope from breadcrumb trails."""
        crumbs_dict = session.get(SESSION_KEY_ZCRUMBS, {})
        trails = crumbs_dict.get(_KEY_TRAILS, crumbs_dict)
        return trails.pop(scope, None)

    def _get_active_crumb(self, session: Dict[str, Any]) -> str:
        """Get active (most recent) crumb from session."""
        crumbs_dict = session.get(SESSION_KEY_ZCRUMBS, {})
        trails = crumbs_dict.get(_KEY_TRAILS, crumbs_dict)
        return next(reversed(trails)) if trails else ""

    def _get_crumbs_dict(self, session: Dict[str, Any]) -> Dict[str, List[str]]:
        """Get breadcrumb trails dict from session."""
        crumbs_dict = session.get(SESSION_KEY_ZCRUMBS, {})
        return crumbs_dict.get(_KEY_TRAILS, crumbs_dict)
