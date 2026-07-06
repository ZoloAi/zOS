# zOS/core/L2_Handling/h_zNavigation/navigation_modules/navigation_linking.py

"""
Inter-File Linking (zLink) for zNavigation - Navigation Flow Component.

This module provides the Linking class, which handles inter-file navigation via
zLink expressions. It parses zLink syntax, validates RBAC permissions, loads
target files, and orchestrates navigation to the linked block.

Architecture
------------
The Linking class is a Tier 1 (Foundation) component that manages zLink navigation:

1. **Parse zLink Expression** (parse_zLink_expression)
   - Extracts file path and optional permission requirements
   - Supports: zLink(path) or zLink(path, {"role": "admin"})
   - Uses zParser.zExpr_eval() for permission dict parsing

2. **Check RBAC Permissions** (check_zLink_permissions)
   - Validates user permissions against required permissions
   - Reads from session[SESSION_KEY_ZVISITOR]
   - Denies access if permissions don't match

3. **Execute Navigation** (handle)
   - Orchestrates the full linking flow
   - Updates session with new file/block context
   - Delegates to zLoader for file loading
   - Delegates to zWalker for block execution

zLink Syntax
------------
Basic link (no permissions)::

    zLink(@.zUI.settings.NetworkSettings)

Link with permission requirements::

    zLink(@.zUI.admin.UserManagement, {"role": "admin"})
    zLink(@.zUI.finance.Reports, {"role": "finance", "level": "manager"})

Path Format:
- @ = Base path (workspace root)
- zUI = UI directory
- filename = YAML file name (without extension)
- BlockName = Target block within file

RBAC Integration
----------------
Permission checking uses the zAuth subsystem:

1. Retrieves user auth data from session[SESSION_KEY_ZVISITOR]
2. Compares user attributes with required permissions (exact match)
3. Denies access if any required permission doesn't match
4. Allows access if no permissions specified (public link)

Example::

    # User in session
    session[SESSION_KEY_ZVISITOR] = {"role": "admin", "level": "manager"}
    
    # Required permissions
    required = {"role": "admin"}
    
    # Check: user["role"] == required["role"] → True (access granted)

Session Updates
---------------
The linking process updates the following session keys:

- SESSION_KEY_ZVAFOLDER: Folder containing the file
- SESSION_KEY_ZVAFILE: Filename (without extension)
- SESSION_KEY_ZBLOCK: Target block name

These session keys are used by zLoader and zWalker to maintain navigation context.

Layer Position
--------------
Layer 1, Position 4 (zNavigation) - Tier 1 (Foundation)

Integration
-----------
- Called by: zNavigation facade, dispatch_launcher (3 call sites)
- Uses: zParser (zExpr_eval), zLoader (file loading), zWalker (block execution)
- Session: Reads SESSION_KEY_ZVISITOR, writes SESSION_KEY_ZVAFOLDER, etc.
- Logging: Debug for flow, info for parsing, warning for permission denials

Forward Dependencies
--------------------
This module depends on:

1. **zParser (Week 6.8):**
   - zExpr_eval() for parsing permission dict strings
   
2. **zLoader (Week 6.9):**
   - loader.handle() for loading target YAML files
   
3. **zWalker (Week 6.11):**
   - walker.display for UI declarations
   - walker.loader for file loading
   - walker.zCrumbs for breadcrumb management
   - walker.zBlock_loop() for executing target block

Usage Examples
--------------
Parse a basic zLink::

    linking = Linking(navigation_system)
    path, perms = linking.parse_zLink_expression(walker, "zLink(@.zUI.settings.Main)")
    # path = "@.zUI.settings.Main"
    # perms = {}

Parse a zLink with permissions::

    path, perms = linking.parse_zLink_expression(
        walker,
        'zLink(@.zUI.admin.Users, {"role": "admin"})'
    )
    # path = "@.zUI.admin.Users"
    # perms = {"role": "admin"}

Check permissions::

    has_access = linking.check_zLink_permissions(walker, {"role": "admin"})
    # Returns True if user has admin role, False otherwise

Execute full linking flow::

    result = linking.handle(walker, 'zLink(@.zUI.settings.Network)')
    # Navigates to Network block in settings file

Module Constants
----------------
DISPLAY_* : str
    Display settings (color, styles, indents)
STATUS_* : str
    Status values for navigation results
MSG_* : str
    Message strings for permission denials and errors
LOG_* : str
    Log message templates
PARSE_* : str
    Parsing literals for zLink expression syntax
PATH_* : str
    Path parsing constants
"""

from zOS import Any, Dict, List, Optional, Tuple
from zOS.L1_Foundation.a_zConfig.zConfig_modules.config_constants import (
    SESSION_KEY_ZVAFOLDER,
    SESSION_KEY_ZVAFILE,
    SESSION_KEY_ZBLOCK,
    SESSION_KEY_ZCRUMBS,
)

from .navigation_helpers import reload_current_file
from .resolvers.resolver_zlink import ZLinkResolver, NAV_VERB_ZLINK, LINK_TYPE_EXTERNAL
from .navigation_constants import (
    DISPLAY_COLOR_ZLINK,
    _DISPLAY_STYLE_FULL,
    _DISPLAY_INDENT_HANDLE,
    _DISPLAY_MSG_HANDLE_ZLINK,
    STATUS_STOP,
    _MSG_PERMISSION_DENIED,
    _MSG_NO_WALKER,
    _LOG_INCOMING_REQUEST,
    _LOG_ZLINK_PATH,
    _LOG_REQUIRED_PERMS,
    _LOG_ZFILE_PARSED,
    _PATH_SEPARATOR,
    _PATH_INDEX_FILENAME_START,
    _PATH_PARTS_MIN,
    _PATH_PARTS_BASE_OFFSET,
    _PATH_DEFAULT_BASE,
)


# ============================================================================
# Linking Class
# ============================================================================

class Linking:
    """
    Inter-file linking manager for zNavigation.
    
    Handles zLink expressions for navigating between files and blocks. Parses
    zLink syntax, validates RBAC permissions, loads target files, and orchestrates
    navigation flow via zWalker.
    
    Attributes
    ----------
    navigation : Any
        Reference to parent navigation system
    zcli : Any
        Reference to zOS instance
    logger : Any
        Logger instance for linking operations
    zSession : Dict[str, Any]
        Direct reference to zcli.session (for convenience)
    
    Methods
    -------
    handle(walker, zHorizontal)
        Execute full zLink navigation flow
    parse_zLink_expression(walker, expr)
        Parse zLink expression to extract path and permissions
    check_zLink_permissions(walker, required)
        Check if user has required permissions
    
    Private Methods
    ---------------
    _update_session_path(zLink_path, selected_zBlock)
        Update session with new file/block context
    
    Examples
    --------
    Execute a zLink::
    
        linking = Linking(navigation_system)
        result = linking.handle(walker, 'zLink(@.zUI.settings.Network)')
    
    Parse and check permissions::
    
        path, perms = linking.parse_zLink_expression(
            walker,
            'zLink(@.zUI.admin.Users, {"role": "admin"})'
        )
        has_access = linking.check_zLink_permissions(walker, perms)
    
    Integration
    -----------
    - Parent: zNavigation system
    - Session: Reads SESSION_KEY_ZVISITOR, writes SESSION_KEY_ZVAFOLDER/ZVAFILENAME/ZBLOCK
    - Walker: Passed as parameter for display, loader, zCrumbs, zBlock_loop access
    - Logging: Debug for flow, info for parsing, warning for denials
    
    Forward Dependencies
    --------------------
    - zParser: zExpr_eval() for permission dict parsing
    - zLoader: walker.loader.handle() for file loading
    - zWalker: walker.display, walker.zCrumbs, walker.zBlock_loop()
    """

    # Class-level type declarations
    navigation: Any  # Navigation system reference
    zos: Any  # zOS instance
    logger: Any  # Logger instance
    zSession: Dict[str, Any]  # Direct reference to session
    resolver: ZLinkResolver  # zLink resolver component

    def __init__(self, navigation: Any) -> None:
        """
        Initialize linking manager.
        
        Args
        ----
        navigation : Any
            Parent navigation system instance that provides access to zos and logger
        
        Notes
        -----
        Stores references to the parent navigation system, zcli core, logger, and
        session for use during linking operations. The zSession reference is stored
        for convenience to avoid repeated `self.zos.session` lookups.
        
        Session Dependencies
        --------------------
        This module manages the following session keys:
        - SESSION_KEY_ZVISITOR: Read for permission checking
        - SESSION_KEY_ZVAFOLDER: Written during navigation
        - SESSION_KEY_ZVAFILE: Written during navigation
        - SESSION_KEY_ZBLOCK: Written during navigation
        """
        self.navigation = navigation
        self.zos = navigation.zos
        self.logger = navigation.logger
        self.zSession = self.zos.session  # Store for convenience

        # Initialize zLink resolver (extracted)
        self.resolver = ZLinkResolver(self.logger)

    # ========================================================================
    # Private Helper Methods (extracted from handle() for decomposition)
    # ========================================================================

    def _handle_http_route_detection(
        self,
        walker: Any,
        zLink_path: str
    ) -> Optional[Any]:
        """
        Handle HTTP route detection for Web mode.
        
        Detects if zLink is an HTTP route (starts with "/") and handles it
        appropriately for Web mode (return redirect metadata) or zCLI mode
        (show warning and stop).
        
        Args:
            walker: zWalker instance with session and display
            zLink_path: Parsed zLink path
        
        Returns:
            - Redirect metadata dict if Web mode HTTP route
            - STATUS_STOP if zCLI mode HTTP route (invalid)
            - None if not an HTTP route (continue normal processing)
        """
        # HTTP ROUTE DETECTION (v1.5.4 Phase 3 - Demo 4)
        if not zLink_path.startswith("/"):
            return None  # Not an HTTP route, continue normal processing

        self.logger.info(f"[zLink] HTTP route detected: {zLink_path}")

        # Read the display mode from the canonical session (SSOT). The passed-in
        # walker may be a fallback instance whose session defaults to zCLI; the
        # engine's own session carries the authoritative mode set by the runtime.
        from zOS.L1_Foundation.a_zConfig.zConfig_modules.config_constants import (
            SESSION_KEY_ZMODE,
            ZMODE_ZBIFROST,
            ZMODE_ZCLI,
            ZMODE_WEB,
        )
        mode = self.zos.session.get(SESSION_KEY_ZMODE, ZMODE_ZCLI)

        if mode == ZMODE_WEB:
            # WEB MODE: Return metadata for HTML link rendering
            self.logger.debug("[zLink] Web mode - returning redirect metadata")
            return {
                "type": "http_redirect",
                "url": zLink_path,
                "mode": "web"
            }
        elif mode == ZMODE_ZBIFROST:
            # BIFROST MODE: a zLink that resolves to an HTTP route during a
            # server-side block render becomes a deferred client navigate. The
            # message walker flushes it as a navigate_back(url) event once the
            # block completes — the same SSOT navigation used by zLogin/zLogout.
            self.logger.info(f"[zLink] Bifrost mode - deferring client navigate to {zLink_path}")
            self.zos.session["_zPendingNavigate"] = zLink_path
            return STATUS_STOP
        else:
            # TERMINAL MODE: HTTP routes don't make sense here
            self.logger.warning(f"[zLink] HTTP route '{zLink_path}' in zCLI mode - skipping navigation")
            walker.display.handle({
                "event": "warning",
                "content": f"HTTP route '{zLink_path}' cannot be navigated in zCLI mode",
                "indent": 1
            })
            return STATUS_STOP

    def _handle_bifrost_zpath_navigate(self, zLink_path: str) -> Optional[Any]:
        """Defer an @-zPath zLink to a client route navigate in Bifrost mode.

        SSOT parity with zURL hrefs: a zBtn ``action: zLink(@.zPath)`` clicked in
        Bifrost is dispatched over the WS bridge. Running ``execute_loop`` there
        returns a lazy display-event generator that the bridge cannot JSON-
        serialize. Instead we resolve the zPath to its canonical route (the SAME
        resolver zURL uses) and stash it on ``_zPendingNavigate``; the dispatch
        bridge pops it and emits a ``navigate_back`` event so the client loads the
        target page by route.

        Returns
        -------
        STATUS_STOP
            When a route was resolved and the navigate was deferred (Bifrost).
        None
            Not Bifrost mode, or no registered route for the zPath — caller falls
            through to the normal server-side render (zCLI execute_loop).
        """
        from zOS.L1_Foundation.a_zConfig.zConfig_modules.config_constants import (
            SESSION_KEY_ZMODE,
            ZMODE_ZBIFROST,
        )
        if self.zos.session.get(SESSION_KEY_ZMODE) != ZMODE_ZBIFROST:
            return None

        # resolve_href_to_route is idempotent: a zPath with a registered route →
        # the route URL; anything else (no route, non-zPath) → the input unchanged.
        route = self.resolver.resolve_href_to_route(self.zos, zLink_path)
        if not route or route == zLink_path:
            self.logger.warning(
                f"[zLink] Bifrost: no route for zPath '{zLink_path}' — "
                "falling through to server-side render"
            )
            return None

        self.logger.info(f"[zLink] Bifrost mode - deferring client navigate to {route}")
        self.zos.session["_zPendingNavigate"] = route
        return STATUS_STOP

    def _capture_source_breadcrumb(
        self,
        walker: Any,
        is_navbar_navigation: bool
    ) -> None:
        """
        Capture SOURCE context breadcrumb BEFORE navigation.
        
        Records the source location (where we're navigating FROM) by adding
        a breadcrumb for the calling key. Skips this if navbar navigation
        (will be cleared by OP_RESET anyway).
        
        Args:
            walker: zWalker instance with session and navigation
            is_navbar_navigation: Whether this is a navbar navigation (skip recording)
        """
        # Get crumbs dict (handle enhanced format)
        crumbs_dict = walker.session.get(SESSION_KEY_ZCRUMBS, {})

        # Get trails from enhanced format or use old format
        if 'trails' in crumbs_dict:
            trails = crumbs_dict['trails']
        else:
            trails = crumbs_dict

        source_block_path = next(reversed(trails)) if trails else None

        # NAVBAR NAVIGATION: Skip source breadcrumb recording
        if is_navbar_navigation:
            self.logger.debug("[zLink] Skipping source breadcrumb (navbar navigation will RESET)")
            return

        # REGULAR NAVIGATION: Record source breadcrumb
        if source_block_path and source_block_path in trails:
            source_trail = trails[source_block_path]
            source_zKey = source_trail[-1] if source_trail else None

            if source_zKey:
                walker.navigation.breadcrumbs.record_zStride(source_zKey, walker=walker)
                self.logger.debug(f"Recorded source breadcrumb: {source_block_path}[{source_zKey}]")

    def _reset_navbar_trail(self, walker: Any) -> None:
        """
        Reset the crumb trail for navbar navigation (the only RESET in zOS).

        Clears every scope so the navbar target becomes the new root, then drops
        the one-shot ``_navbar_navigation`` flag so the next ordinary navigation
        APPENDs normally. walker_dispatch records the target block fresh after
        this, making the picked item the sole/first crumb.

        Args:
            walker: zWalker instance with session
        """
        # SSOT: delegate the only trail RESET in zOS to zNavigation. The reset
        # logic (clear scopes + drop the one-shot navbar marker) lives in one
        # place — Breadcrumbs.reset_trail — so zLink never reimplements it.
        self.navigation.breadcrumbs.reset_trail()

    def _get_or_discover_block(
        self,
        walker: Any,
        zFile_parsed: Dict[str, Any],
        selected_zBlock: str,
        zFile_path: str
    ) -> Tuple[Dict[str, Any], List[str]]:
        """
        Get block from loaded file or auto-discover from separate file.
        
        Implements fallback chain:
        1. Try finding block in loaded file
        2. If not found, try loading from zUI.{blockName}.yaml
        
        Strips navigation modifiers (^ ~) from block name for file path
        since file names don't have modifiers.
        
        Args:
            walker: zWalker instance with loader
            zFile_parsed: Loaded file content
            selected_zBlock: Target block name (may have modifiers)
            zFile_path: Original file path
        
        Returns:
            Tuple of (block_dict, block_keys)
        
        Raises:
            Returns STATUS_STOP on failure (logs error)
        """
        # Try finding block in loaded file
        if selected_zBlock in zFile_parsed:
            active_zBlock_dict = zFile_parsed[selected_zBlock]
            self.logger.debug(f"[zLink] Block '{selected_zBlock}' found in loaded file")
            return active_zBlock_dict, list(active_zBlock_dict.keys())

        # AUTO-DISCOVERY: Try loading from separate file
        self.logger.debug(f"[zLink] Block '{selected_zBlock}' not in file, trying auto-discovery...")

        # Strip navigation modifiers from block name for file path
        file_block_name = selected_zBlock.lstrip("^~")

        # Construct fallback zPath
        if zFile_path.startswith("@"):
            path_parts = zFile_path.split(".")
            fallback_path_parts = path_parts[:-1] + [file_block_name]
            fallback_zPath = ".".join(fallback_path_parts)
        else:
            fallback_zPath = f"@.zViews.zUI.{file_block_name}"

        self.logger.debug(f"[zLink] Trying fallback: {fallback_zPath} (stripped modifiers from '{selected_zBlock}')")

        try:
            fallback_zFile = walker.loader.handle(fallback_zPath)
            if fallback_zFile and isinstance(fallback_zFile, dict):
                if selected_zBlock in fallback_zFile:
                    active_zBlock_dict = fallback_zFile[selected_zBlock]
                    self.logger.info(f"[ok] [zLink] Auto-discovered block '{selected_zBlock}' from: {fallback_zPath}")
                    return active_zBlock_dict, list(active_zBlock_dict.keys())
                else:
                    raise KeyError(f"Block '{selected_zBlock}' not found in {fallback_zPath}")
            else:
                raise ValueError(f"Failed to load {fallback_zPath}")
        except Exception as e:
            self.logger.error(
                f"Block '{selected_zBlock}' not found:\n"
                f"  - Not in loaded file: {zFile_path}\n"
                f"  - Fallback failed: {fallback_zPath}\n"
                f"  - Error: {e}\n"
                f"  - Hint: a navbar/zLink target must be a REAL block — a TOP-LEVEL "
                f"block in the current file, or a cross-file @path. A nested "
                f"sub-section (a key inside another block) is not addressable; "
                f"promote it to a top-level block or target it with an explicit zLink."
            )
            raise  # Re-raise to be caught by caller

    def _setup_bounce_back_snapshot(
        self,
        walker: Any,
        selected_zBlock: str,
        source_folder: str,
        source_file: str,
        source_block: str
    ) -> Optional[Dict[str, Any]]:
        """
        Setup bounce-back snapshot if block has ^ modifier.
        
        Detects if block name starts with ^ (bounce-back modifier) and
        saves a deep copy of current breadcrumb state for later restoration.
        Also stores the source location to enable bounce-back even with no history.
        
        Args:
            walker: zWalker instance with session
            selected_zBlock: Target block name (may have ^ prefix)
            source_folder: Source folder path before navigation
            source_file: Source file name before navigation
            source_block: Source block name before navigation
        
        Returns:
            Deep copy of breadcrumb state with source location if bounce-back enabled, None otherwise
        """
        # RETIRED: prefix `^Block` block-level bounce-back. The caret is now a
        # SUFFIX modifier (`<key>^: <zPath>`) that mints a zCrumbs bulk-rewind —
        # no snapshot/restore needed. Kept as a no-op so the call site is stable.
        should_bounce_back = False
        self.logger.debug(f"[zNavigation] Block name: '{selected_zBlock}', bounce-back retired (no-op)")

        if not should_bounce_back:
            return None

        self.logger.info(f"[zNavigation] ⬅️  Block-level bounce-back enabled for: {selected_zBlock}")

        # Save deep copy of current breadcrumb state
        import copy
        breadcrumb_snapshot = copy.deepcopy(walker.zcli.session.get(SESSION_KEY_ZCRUMBS, {}))

        # Store source location for bounce-back (needed when there's no history)
        breadcrumb_snapshot['_bounce_back_source'] = {
            'folder': source_folder,
            'file': source_file,
            'block': source_block
        }

        self.logger.debug(
            f"[zNavigation] 📸 Saved breadcrumb snapshot with source: "
            f"{source_folder}.{source_file}.{source_block}"
        )

        return breadcrumb_snapshot

    def _restore_bounce_back(
        self,
        walker: Any,
        result: Any,
        breadcrumb_snapshot: Optional[Dict[str, Any]]
    ) -> Any:
        """
        Restore breadcrumb state after bounce-back block execution.
        
        Restores the saved breadcrumb snapshot and continues walker execution
        from the original location. Skips restoration if user already navigated
        away (zBack, exit, etc.).
        
        Args:
            walker: zWalker instance with session and loader
            result: Result from block execution
            breadcrumb_snapshot: Saved breadcrumb state (None = skip restoration)
        
        Returns:
            Result from continued walker execution, or original result
        """
        if breadcrumb_snapshot is None:
            self.logger.warning("[zNavigation] No breadcrumb snapshot to restore!")
            return result

        # Skip bounce-back if user already navigated away
        if isinstance(result, dict) or result in ["zBack", "exit", "stop"]:
            self.logger.debug(f"[zNavigation] Skipping bounce-back restoration, result: {result}")
            return result

        self.logger.info("[zNavigation] ⬅️  Restoring breadcrumbs from snapshot!")

        # Clear _navbar_navigation flag before restoration
        if '_navbar_navigation' in breadcrumb_snapshot:
            del breadcrumb_snapshot['_navbar_navigation']
            self.logger.debug("[zNavigation] Cleared _navbar_navigation flag from snapshot")

        # Restore breadcrumb state
        walker.zcli.session[SESSION_KEY_ZCRUMBS] = breadcrumb_snapshot
        self.logger.debug(f"[zNavigation] ✅ Restored breadcrumbs: {breadcrumb_snapshot}")

        # Get active crumb from restored snapshot
        if 'trails' in breadcrumb_snapshot:
            trail_keys = list(breadcrumb_snapshot['trails'].keys())
        else:
            trail_keys = [k for k in breadcrumb_snapshot.keys() if not k.startswith('_')]

        active_zCrumb = trail_keys[-1] if trail_keys else None

        # If no history, use the source location stored in snapshot
        if not active_zCrumb:
            # Extract source location from snapshot
            source_info = breadcrumb_snapshot.get('_bounce_back_source', {})
            source_folder = source_info.get('folder', '')
            source_file = source_info.get('file', '')
            source_block = source_info.get('block', '')

            if not source_file:
                # No history and no source info - this shouldn't happen but handle gracefully
                self.logger.warning("[zNavigation] No history to restore and no source info - bounce-back complete")
                return result

            # Navbar/root navigation - bounce back to source location
            self.logger.info(
                f"[zNavigation] ⬅️  No history, bouncing back to source: "
                f"{source_folder}.{source_file}.{source_block}"
            )

            # Build source zPath
            if source_folder:
                zPath = f"{source_folder}.{source_file}"
            else:
                zPath = f"@.{source_file}"

            # Update session to source location
            walker.zcli.session[SESSION_KEY_ZVAFOLDER] = source_folder
            walker.zcli.session[SESSION_KEY_ZVAFILE] = source_file
            walker.zcli.session[SESSION_KEY_ZBLOCK] = source_block

            # Load source file
            self.logger.debug(f"[zNavigation] Reloading source file: {zPath}")
            zFile_parsed = reload_current_file(walker)

            # Get source block
            source_zBlock_dict = zFile_parsed.get(source_block, {})
            source_zBlock_keys = list(source_zBlock_dict.keys())

            if not source_zBlock_keys:
                self.logger.warning(f"[zNavigation] Source block '{source_block}' has no keys - cannot continue")
                return result

            # Continue execution from source block
            self.logger.info(f"[zNavigation] ⏯  Continuing execution in source block: {source_block}")
            result = walker.execute_loop(items_dict=source_zBlock_dict)
            return result

        # Parse active crumb to get file/block info
        crumb_parts = active_zCrumb.split(".")
        if len(crumb_parts) < 3:
            self.logger.warning(f"[zNavigation] Invalid crumb format: {active_zCrumb}")
            return result

        # Extract path, filename, and block
        zVaFolder = ".".join(crumb_parts[:-2])
        zVaFile = ".".join(crumb_parts[-2:-1])
        zBlock = crumb_parts[-1]

        # Construct zPath and reload file
        zPath = f"{zVaFolder}.{zVaFile}"
        self.logger.debug(f"[zNavigation] Reloading file for bounce-back: {zPath}")

        # Load file and get block
        raw_zFile = walker.loader.handle(zPath=zPath)
        if zBlock not in raw_zFile:
            self.logger.warning(f"[zNavigation] Block '{zBlock}' not found in {zPath}")
            return result

        block_dict = raw_zFile[zBlock]

        # Get start key from restored trail
        if 'trails' in breadcrumb_snapshot:
            trail = breadcrumb_snapshot['trails'].get(active_zCrumb, [])
        else:
            trail = breadcrumb_snapshot.get(active_zCrumb, [])
        start_key = trail[-1] if trail else None

        self.logger.debug(f"[zNavigation] Continuing from: {zBlock}, start_key: {start_key}")

        # Re-execute block to continue walker
        bounce_result = walker.execute_loop(items_dict=block_dict, start_key=start_key)

        # Convert soft exit dict to signal string
        if isinstance(bounce_result, dict) and bounce_result.get("exit") == "completed":
            self.logger.debug("[zNavigation] User exited after bounce-back - converting to signal")
            return "exit"

        return bounce_result

    # ========================================================================
    # Public API
    # ========================================================================

    def handle(self, walker: Any, zHorizontal: str) -> str:
        """
        Handle zLink navigation request.
        
        Orchestrates the full linking flow: display declaration, parsing, permission
        checking, file loading, session updates, breadcrumb tracking, and block execution.
        
        Args
        ----
        walker : Any
            Walker instance providing display, loader, zCrumbs, and zBlock_loop access
        zHorizontal : str
            zLink expression to execute (e.g., 'zLink(@.zUI.settings.Network)')
        
        Returns
        -------
        str
            Navigation result:
            - STATUS_STOP if permission denied or walker is None
            - Result from walker.zBlock_loop() on success
        
        Examples
        --------
        Basic zLink (no permissions)::
        
            result = linking.handle(walker, 'zLink(@.zUI.settings.Main)')
            # Navigates to Main block in settings file
        
        zLink with permissions::
        
            result = linking.handle(
                walker,
                'zLink(@.zUI.admin.Users, {"role": "admin"})'
            )
            # Checks permissions, then navigates if allowed
        
        Handle permission denial::
        
            result = linking.handle(walker, 'zLink(@.zUI.admin.Users, {"role": "admin"})')
            if result == STATUS_STOP:
                print("Permission denied or error occurred")
        
        Notes
        -----
        - **Display Declaration**: Shows "Handle zLink" banner
        - **Parsing**: Extracts path and permissions from expression
        - **Permission Check**: Validates RBAC if permissions specified
        - **File Loading**: Uses walker.loader.handle() to load target file
        - **Session Update**: Updates file path, filename, and block in session
        - **Breadcrumb Tracking**: Calls walker.zCrumbs.handle_zCrumbs()
        - **Block Execution**: Returns result from walker.zBlock_loop()
        
        Algorithm
        ---------
        1. Display "Handle zLink" declaration
        2. Log incoming request
        3. Parse zLink expression (path + permissions)
        4. Log parsed values
        5. If permissions required and check fails, deny access (return STATUS_STOP)
        6. Load target file via walker.loader.handle()
        7. Extract target block name from path
        8. Update session with new file/block context
        9. Validate walker instance exists
        10. Track breadcrumb (walker.zCrumbs.handle_zCrumbs)
        11. Execute target block (walker.zBlock_loop)
        12. Return result
        """
        # ====================================================================
        # ORCHESTRATOR: Simplified handle() method using extracted helpers
        # ====================================================================

        # Display declaration
        walker.display.zDeclare(
            _DISPLAY_MSG_HANDLE_ZLINK,
            color=DISPLAY_COLOR_ZLINK,
            indent=_DISPLAY_INDENT_HANDLE,
            style=_DISPLAY_STYLE_FULL
        )

        # Log incoming request
        self.logger.debug(_LOG_INCOMING_REQUEST, zHorizontal)

        # Extract the zLink event value (string shorthand or {target, zPsi} dict)
        if isinstance(zHorizontal, dict):
            zLink_value = zHorizontal.get('zLink', '')
        else:
            zLink_value = zHorizontal

        # Compile to the canonical nav IR (SSOT). One compiler unifies every
        # authored form — imperative zLink(...), bare zPath, and the
        # {target, zPsi, permissions} dict — lifting target/zPsi/perms in a
        # single place shared with zDelta and (the compiler) zURL. zPsi sets the
        # walker start_key in the landed block (a menu-pick start line, by
        # address; zUI.zMenu Option A vs B). Stateless.
        intent = self.resolver.compile_intent(zLink_value, verb=NAV_VERB_ZLINK)
        zpsi_anchor = intent.zpsi

        # Bare anchor (no target): in-page jump within the CURRENT block — no file
        # change, no crumb push. Re-run the current block from the anchored key.
        if not intent.target:
            return self._handle_inpage_zpsi(walker, zpsi_anchor)

        zLink_path = intent.target
        required_perms = intent.perms
        self.logger.debug(_LOG_ZLINK_PATH, zLink_path)
        self.logger.debug(_LOG_REQUIRED_PERMS, required_perms)

        # EXTERNAL URL (http/https): a zLink target pointing OUTSIDE the app —
        # most often a navbar item funneled through {zLink: url}. classify_href
        # still tags intent.kind=external even with the verb pinned to zLink, so
        # honor it via the zOpen SSOT (the SAME authority zURL uses) instead of
        # trying to load a URL as a file. This is what lets external links cascade
        # on the terminal exactly as they now do in Bifrost (where a navbar
        # external item renders as a real <a target=_blank>).
        if intent.kind == LINK_TYPE_EXTERNAL and zLink_path:
            self.logger.info("[zLink] External target -> zOpen: %s", zLink_path)
            self.zos.open.handle(f"zOpen({zLink_path})")
            return STATUS_STOP

        # HTTP ROUTE DETECTION: Handle Web mode routes early
        http_result = self._handle_http_route_detection(walker, zLink_path)
        if http_result is not None:
            return http_result  # Either redirect metadata or STATUS_STOP

        # FILE-BASED NAVIGATION: Continue with normal flow

        # Check permissions if required - delegate to resolver
        if required_perms and not self.resolver.check_permissions(walker.session, required_perms):
            print(_MSG_PERMISSION_DENIED)
            return STATUS_STOP

        # BIFROST zPATH NAVIGATION (parity with zURL hrefs): in Bifrost a zLink to
        # an @-zPath must become a CLIENT route navigate — NOT a server-side
        # execute_loop whose lazy generator can't be JSON-serialized across the WS
        # bridge (that raised "Object of type generator is not JSON serializable" on
        # a zBtn action: zLink). Resolve the zPath to its canonical route and defer:
        # the dispatch bridge flushes _zPendingNavigate as a navigate_back event,
        # the same SSOT used by the /-route branch and zLogin/zLogout. RBAC is
        # already enforced above. zCLI falls through and runs execute_loop below.
        bifrost_nav = self._handle_bifrost_zpath_navigate(zLink_path)
        if bifrost_nav is not None:
            return bifrost_nav

        # Extract target block name and file path - delegate to resolver
        selected_zBlock, zFile_path = self.resolver.extract_block_from_path(zLink_path)

        # Load target file
        zFile_parsed = walker.loader.handle(zFile_path)
        self.logger.debug(_LOG_ZFILE_PARSED, zFile_parsed)

        # BREADCRUMB FIX: Capture SOURCE context before navigation.
        # SSOT: the navbar reset marker is read through zNavigation, not by
        # reaching into the raw crumbs dict.
        is_navbar_navigation = self.navigation.breadcrumbs.is_navbar_pending()

        # Store source location BEFORE navigation (needed for bounce-back)
        source_folder = walker.session.get(SESSION_KEY_ZVAFOLDER, '')
        source_file = walker.session.get(SESSION_KEY_ZVAFILE, '')
        source_block = walker.session.get(SESSION_KEY_ZBLOCK, '')

        if is_navbar_navigation:
            self.logger.info("[zLink] Navbar navigation detected → will trigger OP_RESET")

        self._capture_source_breadcrumb(walker, is_navbar_navigation)

        # Update session to TARGET location
        self._update_session_path(zLink_path, selected_zBlock)

        # NAVBAR OP_RESET: zNavBar is the ONLY navigation in zOS that resets the
        # crumb trail — the chosen item becomes the new root, discarding the prior
        # trail (user model: a navbar pick jumps to a new first node). Source
        # capture is already skipped above; here we actually clear the trail so
        # walker_dispatch records the target block fresh as the sole scope.
        if is_navbar_navigation:
            self._reset_navbar_trail(walker)

        # Get block dict with auto-discovery fallback
        try:
            active_zBlock_dict, _ = self._get_or_discover_block(
                walker, zFile_parsed, selected_zBlock, zFile_path
            )
        except Exception:
            return STATUS_STOP

        # Validate walker instance
        if walker is None:
            self.logger.error(_MSG_NO_WALKER)
            return STATUS_STOP

        # Seed the target breadcrumb scope via the SSOT seeder so a zBack raised
        # inside the landed block (e.g. a zBtn action: zBack) has a real parent
        # scope to transition back to. Without this the target had no scope key
        # in the enhanced trails map, so handle_zBack saw a single scope, never
        # transitioned, and re-rendered the current page. Session path keys were
        # already updated by _update_session_path above. Navbar navigation just
        # cleared the trail (target becomes new root), so it is seeded here too.
        self.navigation.breadcrumbs.seed_scope(walker=walker, arrival=True)
        self.logger.debug(f"Navigating to target block: {zLink_path}")

        # BLOCK-LEVEL BOUNCE-BACK: Setup snapshot if ^ modifier present
        breadcrumb_snapshot = self._setup_bounce_back_snapshot(
            walker, selected_zBlock, source_folder, source_file, source_block
        )
        should_bounce_back = breadcrumb_snapshot is not None

        # Pre-resolve data bindings so template %data.* variables are available.
        # zLoom SSOT: bindings are declared at the FILE ROOT zMeta (`zSpool: [..]`)
        # and resolved ONCE per render into %data.*. The root is the binding site —
        # `zFile_parsed[block]` (active_zBlock_dict) drops it. `prepare_block_render`
        # is the ONE seam (shared with the boot path zWalker.run and the route path):
        # it builds the root binding, merges block-level literal `_data`, resolves to
        # %data.*, and loop-expands any zList/zShuttle in place — all before dispatch.
        block_context = self.zos.zloom.prepare_block_render(zFile_parsed, active_zBlock_dict)

        # zPsi: resolve the #anchor to a real block key and start the run there.
        # Like a menu pick, the walker runs from start_key to the end of the block.
        start_key = self.resolver.resolve_anchor_key(active_zBlock_dict, zpsi_anchor)
        if zpsi_anchor and not start_key:
            self.logger.warning(
                f"[zPsi] Anchor '#{zpsi_anchor}' not found in block "
                f"'{selected_zBlock}' — starting at top"
            )

        # Execute target block.
        # SSOT navigation: hand the walker's own navigation callbacks to the nested
        # loop so the landed block honors zCrumbs. Without them a zBack raised inside
        # the target (e.g. a zBtn action: zBack) had no on_back to pop the trail and
        # was silently swallowed — the engine never returned to the source page.
        # zBifrost runs the chunked executor (callbacks unused there), so this only
        # affects the zCLI path, which is exactly where the gap lived.
        nav_callbacks = (
            walker._create_navigation_callbacks()
            if hasattr(walker, "_create_navigation_callbacks")
            else None
        )
        # Bounce-back (^) is a CALL/RESUME hop: it must run the target to completion
        # and then restore the source snapshot in THIS frame, so it keeps the direct
        # (bounded) recursive call. A plain zLink is a REPLACE hop → trampoline in
        # zCLI (stage + NAV_SIGNAL → flat stack); zBifrost keeps the direct call.
        if should_bounce_back:
            result = walker.execute_loop(
                items_dict=active_zBlock_dict,
                context=block_context,
                start_key=start_key,
                navigation_callbacks=nav_callbacks,
            )
            self.logger.debug(f"[zNavigation] Block execution result: {result}, should_bounce_back: {should_bounce_back}")
            return self._restore_bounce_back(walker, result, breadcrumb_snapshot)

        if hasattr(walker, "navigate_or_recurse"):
            return walker.navigate_or_recurse(
                items_dict=active_zBlock_dict,
                context=block_context,
                start_key=start_key,
                navigation_callbacks=nav_callbacks,
            )
        return walker.execute_loop(
            items_dict=active_zBlock_dict,
            context=block_context,
            start_key=start_key,
            navigation_callbacks=nav_callbacks,
        )

    def _handle_inpage_zpsi(self, walker: Any, anchor: Optional[str]) -> str:
        """Jump the walker to a sub-key WITHIN the current block (bare ``#anchor``).

        Same-page / in-page navigation (TOC). Reloads the current block and
        re-runs it from the anchored key — no session mutation, no breadcrumb
        push. If the anchor is missing/unknown the block runs from the top.
        """
        if not anchor:
            self.logger.debug("[zPsi] Empty in-page anchor — no-op")
            return STATUS_STOP

        folder = walker.session.get(SESSION_KEY_ZVAFOLDER, "")
        vafile = walker.session.get(SESSION_KEY_ZVAFILE)
        block = walker.session.get(SESSION_KEY_ZBLOCK)
        if not vafile or not block:
            self.logger.warning("[zPsi] In-page anchor with no current file/block — skipping")
            return STATUS_STOP

        zPath = f"{folder}.{vafile}" if folder else vafile
        raw_zFile = walker.loader.handle(zPath)
        block_dict = raw_zFile.get(block, {}) if isinstance(raw_zFile, dict) else {}
        if not block_dict:
            self.logger.warning(f"[zPsi] In-page anchor: block '{block}' not found in {zPath}")
            return STATUS_STOP

        start_key = self.resolver.resolve_anchor_key(block_dict, anchor)
        if not start_key:
            self.logger.warning(
                f"[zPsi] In-page anchor '#{anchor}' not found in block '{block}' — starting at top"
            )

        self.logger.debug(f"[zPsi] In-page jump → block '{block}' start_key='{start_key}'")
        # REPLACE navigation: zCLI trampolines (flat stack), zBifrost direct.
        if hasattr(walker, "navigate_or_recurse"):
            return walker.navigate_or_recurse(items_dict=block_dict, start_key=start_key)
        return walker.execute_loop(items_dict=block_dict, start_key=start_key)

    # ========================================================================
    # Private Helper Methods
    # ========================================================================

    def _update_session_path(
        self,
        zLink_path: str,
        selected_zBlock: str
    ) -> None:
        """
        Update session with new file/block context.
        
        Parses the zLink path to extract base path, filename, and block name,
        then updates the session accordingly.
        
        Args
        ----
        zLink_path : str
            Full zLink path (e.g., "@.zUI.settings.NetworkSettings")
        selected_zBlock : str
            Target block name (e.g., "NetworkSettings")
        
        Notes
        -----
        DRY Helper: Centralizes session path updates.
        
        Session Keys Updated:
        - SESSION_KEY_ZVAFOLDER: Folder path (e.g., "")
        - SESSION_KEY_ZVAFILE: Filename (e.g., "zUI.settings")
        - SESSION_KEY_ZBLOCK: Block name (e.g., "NetworkSettings")
        
        Algorithm
        ---------
        1. Extract path to file (everything except last part)
        2. Split path into parts by "."
        3. If >= 2 parts:
           a. Extract base path (all parts except last 2)
           b. Set zVaFolder to joined base path (or "" if empty)
           c. Set zVaFile to last 2 parts joined
        4. Else (< 2 parts):
           a. Set zVaFolder to ""
           b. Set zVaFile to entire path
        5. Set zBlock to selected_zBlock
        """
        # Extract path to file (without block name)
        path_to_file = zLink_path.rsplit(_PATH_SEPARATOR, 1)[0]
        parts = path_to_file.split(_PATH_SEPARATOR)

        # Parse path components
        if len(parts) >= _PATH_PARTS_MIN:
            base_path_parts = parts[:_PATH_PARTS_BASE_OFFSET]
            self.zSession[SESSION_KEY_ZVAFOLDER] = (
                _PATH_SEPARATOR.join(base_path_parts) if base_path_parts else _PATH_DEFAULT_BASE
            )
            self.zSession[SESSION_KEY_ZVAFILE] = _PATH_SEPARATOR.join(
                parts[_PATH_INDEX_FILENAME_START:]
            )
        else:
            self.zSession[SESSION_KEY_ZVAFOLDER] = _PATH_DEFAULT_BASE
            self.zSession[SESSION_KEY_ZVAFILE] = path_to_file

        # Set block name
        self.zSession[SESSION_KEY_ZBLOCK] = selected_zBlock
