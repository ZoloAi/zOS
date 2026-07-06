# zOS/core/L2_Handling/h_zNavigation/navigation_modules/navigation_breadcrumbs.py

"""
Breadcrumb Trail Management for zNavigation - Session State Component.

This module provides the Breadcrumbs class, which manages hierarchical navigation
trails stored in the zSession. It supports adding breadcrumbs, navigating backward
through the trail, and formatting breadcrumbs for display.

Architecture
------------
The Breadcrumbs class is a Tier 1 (Foundation) component that directly manages
zSession state for navigation history. It implements a scope-based breadcrumb model
where each scope (file + block path) maintains its own trail of navigation keys.

Breadcrumb Data Model (Session-based):

    session[SESSION_KEY_ZCRUMBS] = {
        "@.zUI.main.MainMenu": ["Dashboard", "Settings", "Profile"],
        "@.zUI.settings.Network": ["Wi-Fi", "DNS", "Proxy"]
    }

**Structure:**
- **Key (Scope)**: Full path to a zUI block (e.g., "@.zUI.main.MainMenu")
- **Value (Trail)**: Ordered list of navigation keys within that block

**Scope Format**: `{path}.{filename}.{BlockName}`
- `path`: Base path or "@" for default
- `filename`: e.g., "zUI.main"
- `BlockName`: Top-level block name

This model supports:
- **Hierarchical Navigation**: Parent/child scope relationships
- **Multi-level Back**: Navigate up through nested scopes
- **State Persistence**: Trails preserved in zSession
- **File Reloading**: Automatic reload of correct file after zBack

Core Methods
------------
1. handle_zCrumbs(zBlock, zKey, walker=None)
   - Adds a navigation key to the current block's trail
   - Prevents duplicate consecutive keys
   - Creates new scopes as needed

2. handle_zBack(show_banner=True, walker=None) -> Tuple[Dict, List, Optional[str]]
   - Navigates backward through the breadcrumb trail
   - Manages parent/child scope transitions
   - Reloads the appropriate file after navigation
   - Returns: (block_dict, block_keys, start_key)

3. zCrumbs_banner() -> Dict[str, str]
   - Formats breadcrumbs for display
   - Returns dict of {scope: formatted_trail}

zBack Algorithm (Complex - 113 lines)
--------------------------------------
The zBack algorithm handles multi-level navigation with sophisticated scope management:

**Step 1: Identify Active Scope**
- Get the last (most recent) scope from session[SESSION_KEY_ZCRUMBS]
- Get the trail (list of keys) for this scope

**Step 2: Pop from Current Trail**
- If trail has items → pop the last key
- This moves back one step within the current block

**Step 3: Handle Empty Trail (Scope Transition)**
- If trail is empty and we're not at root:
  a. Remove the empty child scope from session
  b. Move to parent scope (now the last scope)
  c. Pop parent's last key (the link that opened the child)

**Step 4: Cascade Empty Scope Removal**
- If after popping, the current scope is now empty and not root:
  - Repeat the scope transition (step 3)
  - This handles cases where navigating back empties multiple levels

**Step 5: Parse Active Crumb for File Context**
- Split the active crumb by "." to extract:
  - Base path (everything before last 3 parts)
  - Filename (2nd and 3rd parts from end)
  - Block name (last part)
- Update session keys: zVaFolder, zVaFile, zBlock

**Step 6: Reload File**
- Construct zPath from session values
- Load file using zLoader
- Extract the active block dict and its keys

**Step 7: Return Context**
- Return (block_dict, block_keys, start_key)
- start_key is the current position in the trail (or None if trail is empty)

Session Integration (Critical)
-------------------------------
This module is a **CORE session management component** that directly reads and writes
multiple session keys:

**Primary Session Keys (from zConfig):**
- SESSION_KEY_ZCRUMBS: The breadcrumb trail dict
- SESSION_KEY_ZVAFOLDER: Folder containing current file
- SESSION_KEY_ZVAFILE: Current file name
- SESSION_KEY_ZBLOCK: Current block name

**Session Dependencies:**
- zWalker: Relies on breadcrumbs for navigation state
- zLoader: Used to reload files after navigation
- zDisplay: Uses zCrumbs_banner() for UI display

**CRITICAL**: All session keys MUST use centralized SESSION_KEY_* constants from
zConfig.zConfig_modules.config_session to ensure system-wide consistency.

Layer Position
--------------
Layer 1, Position 4 (zNavigation) - Tier 1 (Foundation)

Integration
-----------
- Called by: MenuSystem, zWalker
- Uses: zSession (state management), zLoader (file reloading), zDisplay (output)
- Thread Safety: Not thread-safe (relies on session state)

Usage Examples
--------------
Add breadcrumb to trail::

    breadcrumbs = Breadcrumbs(navigation_system)
    breadcrumbs.handle_zCrumbs(
        zBlock="@.zUI.main.MainMenu",
        zKey="Settings",
        walker=current_walker
    )

Navigate backward::

    block_dict, block_keys, start_key = breadcrumbs.handle_zBack(
        show_banner=True,
        walker=current_walker
    )
    
    if start_key:
        # Resume from start_key in block_keys
        index = block_keys.index(start_key)
    else:
        # Start from beginning
        index = 0

Format breadcrumbs for display::

    breadcrumbs_dict = breadcrumbs.zCrumbs_banner()
    # {"@.zUI.main.MainMenu": "Dashboard > Settings > Profile"}

Module Constants
----------------
COLOR_* : str
    Display colors for breadcrumb operations
STYLE_* : str
    Display styles (full, single, etc.)
INDENT_* : int
    Indentation levels for display
SEPARATOR_* : str
    String separators for formatting
PREFIX_* : str
    Path prefixes for default locations
MSG_* : str
    Display messages for operations
LOG_* : str
    Logging message templates
ERR_* : str
    Error messages for validation failures
CRUMB_* : int
    Magic numbers for crumb parsing (minimum parts, indices)
"""

from zOS import Any, Dict, List, Optional, Tuple
from zSys import zpath
from zOS.L1_Foundation.a_zConfig.zConfig_modules.config_constants import (
    SESSION_KEY_ZCRUMBS,
    SESSION_KEY_ZVAFOLDER,
    SESSION_KEY_ZVAFILE,
    SESSION_KEY_ZBLOCK,
)

_SEPARATOR_DOT = "."

from .navigation_helpers import get_display as get_display_helper
from .breadcrumb_marker import make_arrival, is_arrival, strip_arrival, ARRIVAL_MARK
from .handlers.handler_panels import PanelManager
from .handlers.handler_zback import ZBackHandler
from .handlers.handler_breadcrumbs_ops import BreadcrumbsOpsHandler
from .navigation_constants import (
    COLOR_ZCRUMB,
    _STYLE_FULL,
    _INDENT_ZBACK,
    _SEPARATOR_CRUMB,
    _SEPARATOR_EMPTY,
    _MSG_HANDLE_ZBACK,
    _KEY_TRAILS,
    _KEY_CONTEXT,
    _KEY_DEPTH_MAP,
    KEY_NAVBAR_PENDING,
    KEY_NAVBAR_SCOPED,
)


# ============================================================================
# Breadcrumbs Class
# ============================================================================

class Breadcrumbs:
    """
    Breadcrumb trail manager for zNavigation.
    
    Manages hierarchical navigation trails stored in zSession, supporting adding
    breadcrumbs, navigating backward through history, and formatting trails for display.
    
    Attributes
    ----------
    navigation : Any
        Reference to parent navigation system
    zos : Any
        Reference to zOS instance
    logger : Any
        Logger instance for breadcrumb operations
    
    Methods
    -------
    handle_zCrumbs(zBlock, zKey, walker=None)
        Add navigation key to breadcrumb trail
    handle_zBack(show_banner=True, walker=None)
        Navigate backward through trail, reload file
    zCrumbs_banner()
        Format breadcrumbs for display
    
    Private Methods
    ---------------
    _get_display(walker)
        Get display adapter (DRY helper)
    _get_active_crumb(session)
        Get active (most recent) crumb from session (DRY helper)
    _get_crumbs_dict(session)
        Get crumbs dict with validation (DRY helper)
    _pop_scope(session, scope)
        Pop (remove) a scope from crumbs dict (DRY helper)
    
    Examples
    --------
    Initialize and add breadcrumb::
    
        breadcrumbs = Breadcrumbs(navigation_system)
        breadcrumbs.handle_zCrumbs("@.zUI.main.Menu", "Settings", walker)
    
    Navigate backward::
    
        block_dict, keys, start_key = breadcrumbs.handle_zBack(True, walker)
    
    Format for display::
    
        trails = breadcrumbs.zCrumbs_banner()
    
    Integration
    -----------
    - Parent: zNavigation system
    - Session: Reads/writes SESSION_KEY_ZCRUMBS, SESSION_KEY_ZVAFOLDER, etc.
    - Display: Uses zDisplay for output (mode-agnostic)
    - Loader: Uses zLoader for file reloading
    """

    # Class-level type declarations
    navigation: Any  # Navigation system reference
    zos: Any  # zOS instance
    logger: Any  # Logger instance
    panel_manager: PanelManager  # Panel management component
    zback_handler: ZBackHandler  # zBack navigation handler
    ops_handler: BreadcrumbsOpsHandler  # Operations handler

    def __init__(self, navigation: Any) -> None:
        """
        Initialize breadcrumbs manager.
        
        Args
        ----
        navigation : Any
            Parent navigation system instance that provides access to zos and logger
        
        Notes
        -----
        Stores references to the parent navigation system, zos instance, and logger
        for use during breadcrumb operations. No state is maintained beyond these
        references - all navigation state is stored in zSession.
        
        Session Dependencies
        --------------------
        This module relies on zSession having the following keys initialized:
        - SESSION_KEY_ZCRUMBS: Dict of scopes and trails (or enhanced format)
        - SESSION_KEY_ZVAFOLDER: Current file folder
        - SESSION_KEY_ZVAFILE: Current file name
        - SESSION_KEY_ZBLOCK: Current block name
        
        Enhanced Format (Phase 0.5)
        ---------------------------
        SESSION_KEY_ZCRUMBS now supports enhanced format:
        {
            'trails': {scope: [keys...]},
            '_context': {last_operation, last_nav_type, current_file, timestamp},
            '_depth_map': {file: {block: {depth, type}}}
        }
        Old format (flat dict) is auto-migrated for backward compatibility.
        """
        self.navigation = navigation
        self.zos = navigation.zos
        self.logger = navigation.logger

        # Initialize handlers (extracted). PanelManager gets a back-ref so panel
        # cleanup removes scopes via the SSOT Breadcrumbs.remove_scope.
        self.panel_manager = PanelManager(self.logger, breadcrumbs=self)
        self.zback_handler = ZBackHandler(self.logger)
        self.ops_handler = BreadcrumbsOpsHandler(self.logger)

    def _create_panel_key(self, panel_name: str, session: Dict) -> str:
        """Delegates to PanelManager."""
        return self.panel_manager.create_panel_key(panel_name, session)

    def _clear_other_panel_keys(self, current_panel: str, session: Dict) -> None:
        """Delegates to PanelManager."""
        return self.panel_manager.clear_other_panel_keys(current_panel, session)

    def handle_zCrumbs(
        self,
        zKey: str,
        _walker: Optional[Any] = None,
        operation: str = "APPEND"
    ) -> None:
        """
        Add or replace navigation key in breadcrumb trail.
        
        Delegates to BreadcrumbsOpsHandler for implementation.
        See handler_breadcrumbs_ops.py for full details.
        """
        # Get active block path from session
        session = self.zos.session
        z_block = self._get_active_crumb(session)  # Use helper

        # Get or create trail
        trails = self._get_crumbs_dict(session)
        if z_block not in trails:
            trails[z_block] = []
        trail = trails[z_block]

        # Delegate operation to handler
        if operation == "RESET":
            self.ops_handler.handle_reset_operation(session, trail, zKey)
        elif operation == "REPLACE":
            self.ops_handler.handle_replace_operation(session, trail, zKey)
        elif operation == "POP_TO":
            self.ops_handler.handle_pop_to_operation(session, trail, zKey)
        elif operation == "APPEND_RAW":
            self.ops_handler.handle_append_raw_operation(session, trail, zKey)
        else:  # APPEND (default)
            self.ops_handler.handle_append_operation(session, trail, zKey)

        # Update context and depth
        self.ops_handler.update_context_and_depth(
            session, operation, "SEQUENTIAL", "SEQUENTIAL",
            z_block, zKey, trail
        )

    def handle_zBack(
        self,
        show_banner: bool = True,
        walker: Optional[Any] = None
    ) -> Tuple[Dict[str, Any], List[str], Optional[str]]:
        """
        Navigate backward through breadcrumb trail.
        
        Delegates to ZBackHandler for all backward navigation operations.
        
        Args
        ----
        show_banner : bool, default=True
            Whether to display "zBack" banner
        walker : Optional[Any], default=None
            Optional walker instance for context
        
        Returns
        -------
        Tuple[Dict[str, Any], List[str], Optional[str]]
            Tuple of (block_dict, block_keys, start_key)
        
        Notes
        -----
        - Delegates to self.zback_handler methods
        - See ZBackHandler for full implementation details
        """
        # Display banner if requested
        if show_banner:
            display = self._get_display(walker)
            display.zDeclare(
                _MSG_HANDLE_ZBACK,
                color=COLOR_ZCRUMB,
                indent=_INDENT_ZBACK,
                style=_STYLE_FULL
            )

        # Get initial state.
        # active_crumb = newest scope (top of stack, where we are now).
        # root_crumb  = oldest scope (bottom of stack, the origin we must never
        #   pop past). These were previously BOTH set to the active scope, which
        #   made `active_crumb != root_crumb` always false and silently disabled
        #   every cross-scope transition — so any zBack landing in a scope opened
        #   by zLink/zDelta could never return to its parent. Deriving root from
        #   the FIRST trail key restores multi-scope back-navigation (SSOT).
        active_crumb = self._get_active_crumb(self.zos.session)
        _scope_keys = list(self._get_crumbs_dict(self.zos.session).keys())
        root_crumb = _scope_keys[0] if _scope_keys else active_crumb
        trail = self._get_crumbs_dict(self.zos.session).get(active_crumb, [])

        # Guard: active_crumb not in trails means truly no navigation context — signal exit.
        # Use `in` directly so falsy-but-valid "" scope is treated as present.
        _trails = self._get_crumbs_dict(self.zos.session)
        if active_crumb not in _trails:
            self.logger.debug("[ZBackHandler] No active crumb - at top-level, no parent to navigate to")
            return {}, [], None

        # Step 1-4: Handle trail popping and scope transitions (delegate to handler)
        active_crumb, trail = self.zback_handler.handle_trail_pop_and_scope_transition(
            self.zos.session,
            active_crumb,
            root_crumb,
            trail
        )

        # Step 5: Parse crumb and update session (delegate to handler)
        resolved_key = self.zback_handler.parse_crumb_and_update_session(
            self.zos.session,
            active_crumb,
            trail
        )

        # Step 6-8: Reload file and prepare context (delegate to handler)
        return self.zback_handler.reload_file_after_back(
            self.zos.session,
            resolved_key,
            walker
        )

    def handle_zCrumb_back(
        self,
        target: str,
        walker: Optional[Any] = None
    ) -> Optional[Tuple[Dict[str, Any], List[str], Optional[str]]]:
        """zCrumb click → BULK-back to ``target`` (the lone POP_TO render path).

        Sibling to ``handle_zBack`` but unwinds an ARBITRARY depth in one step:
        ``pop_to_scope`` drops every scope opened after ``target`` (vs zBack's
        single hop), then the SAME reload contract reloads the landed page so the
        walker re-walks it. Mode-agnostic — the trail is backend state, so zCLI
        and Bifrost share this unwind. The click's *omega* (in-scope section
        anchor) is NOT consumed here: it rides the render intent and only Bifrost
        acts on it (scroll to section); zCLI has no viewport, so the scope half is
        all it needs.

        Returns
        -------
        Optional[Tuple[Dict, List, Optional[str]]]
            ``(block_dict, block_keys, start_key)`` to re-walk the target page
            when ``target`` was on the trail. ``None`` when it was not — the
            caller then treats the click as ordinary FORWARD navigation (zLink).
        """
        # CONTRACT: a bare target (no @/~ sigil) is a STRICT in-block rewind — it
        # may only name a key in the CURRENT zBlock tree (the omega/in-page case).
        # Crossing the block requires a zPath, handled below via pop_to_scope.
        if target and not str(target).startswith((zpath.SIGIL_WORKSPACE, zpath.SIGIL_HOME)):
            return self._rewind_in_block(str(target), walker)

        if not self.pop_to_scope(target):
            return None  # not on the trail → caller forwards as zLink

        session = self.zos.session
        active = self._get_active_crumb(session)
        trails = self._get_crumbs_dict(session)

        # Rebuild the landed page's trail from its seed so the upcoming re-walk
        # records a CLEAN trail rather than double-appending onto the frame we
        # just unwound to. Preserve a leading arrival marker (page reached by
        # zLink/zDelta) so a subsequent zBack still treats it as one unit.
        seed = trails.get(active, [])
        trails[active] = [seed[0]] if seed and is_arrival(seed[0]) else []

        # Point the session at the landed scope (reuse the zBack parser) and
        # re-render the WHOLE page (start_key=None) — "bring me back to that crumb".
        self.zback_handler.parse_crumb_and_update_session(session, active, [])
        return self.zback_handler.reload_file_after_back(session, None, walker)

    def _rewind_in_block(
        self,
        key: str,
        walker: Optional[Any] = None
    ) -> Optional[Tuple[Dict[str, Any], List[str], Optional[str]]]:
        """STRICT in-block rewind for a bare ``<key>^`` target (the omega case).

        Prune the active scope's key-trail back to ``key`` (drop everything deeper)
        and re-walk the CURRENT block from it. A bare key NEVER crosses the zBlock:
        ``pop_trail_to_before`` is a no-op if ``key`` isn't on the in-block trail,
        and ``reload_file_after_back`` validates ``key`` against THIS block's keys —
        an unknown key just re-renders the block from the top, it can never leak
        forward to another page (that is what a zPath is for). Mode-agnostic — the
        trail is backend state, so zCLI and Bifrost share this unwind.
        """
        session = self.zos.session
        self.pop_trail_to_before(key)
        return self.zback_handler.reload_file_after_back(session, key, walker)

    def zCrumbs_banner(self) -> Dict[str, str]:
        """
        Format breadcrumbs for display.
        
        Converts the session breadcrumb dict into a display-friendly format
        where each scope's trail is joined into a readable string.
        
        Returns
        -------
        Dict[str, str]
            Dictionary mapping scope names to formatted trail strings.
            Empty trails are represented as empty strings.
        
        Examples
        --------
        Format all breadcrumbs::
        
            trails = breadcrumbs.zCrumbs_banner()
            # {
            #     "@.zUI.main.MainMenu": "Dashboard > Settings > Profile",
            #     "@.zUI.settings.Network": "Wi-Fi > DNS"
            # }
        
        Handle empty trails::
        
            trails = breadcrumbs.zCrumbs_banner()
            # {
            #     "@.zUI.main.MainMenu": "",
            #     "@.zUI.settings.Network": "Wi-Fi"
            # }
        
        Notes
        -----
        - **Separator**: Trails are joined with " > " (_SEPARATOR_CRUMB)
        - **Empty Trails**: Represented as empty strings (not None)
        - **Read-Only**: Does not modify session state
        - **Display Integration**: Typically called by zDisplay.zCrumbs() for UI output
        
        Format
        ------
        - Input: {"scope1": ["key1", "key2"], "scope2": []}
        - Output: {"scope1": "key1 > key2", "scope2": ""}
        """
        # zCLI is a thin RENDERER over the SSOT projector — it does not invent its
        # own trail meaning. project_trail() is the ONE place the session trail is
        # turned into hops (shared with Bifrost), so the two runtimes can't drift.
        # Here we flatten the canonical hops back into the {scope: "key > key"} shape
        # the zCLI display loop expects.
        self._ensure_enhanced_format(self.zos.session)
        return {
            hop["path"]: (_SEPARATOR_CRUMB.join(hop["keys"]) if hop["keys"] else _SEPARATOR_EMPTY)
            for hop in self.project_trail()
        }

    # ========================================================================
    # SSOT Trail Projection — the ONE projector both runtimes read
    # ========================================================================

    def project_trail(self) -> List[Dict[str, Any]]:
        """Echo the live session crumb trail as canonical hops (THE SSOT).

        ``show: session`` is a FAITHFUL, UNFILTERED echo of ``zSession``'s crumb
        state — it is innate engine output (the zWizard trail), not a curated UI
        breadcrumb. This is the single source of truth both surfaces read, so the
        ONLY reason zCLI and Bifrost can differ is what the RECORDER put in
        session (sync zCLI zStrides every key; chunk Bifrost zStrides only the
        clicked nav-origin — see ``record_zStride``). The display NEVER filters:

          - zCLI    : ``zCrumbs_banner`` flattens these hops into ``key > key``
                      strings for the terminal renderer.
          - Bifrost : ``message_utils._slim_session_trail`` ships these hops over
                      the wire verbatim (the client skin is zMode-aware).

        Canonical hop::

            {"path":    <scope zPath, ::dupN and #N stripped → navigable>,
             "label":   <leaf label, min-depth-unique across the hop set>,
             "keys":    [<every entry recorded in this scope, verbatim — no
                          filter, including the α<block> arrival sentinel>],
             "arrival": <bool — keys[0] is the α arrival sentinel; lets a clean
                          surface drop the engine glyph without knowing it>}

        Only two normalizations touch the data, both non-lossy display concerns:
        ``_``-prefixed METADATA scopes (_context/_depth_map) are skipped, and the
        navigable ``path`` is de-suffixed (``::dupN``/``#N``) — the human ``label``
        still disambiguates revisits. Insertion order IS visit order. ``[]`` ⇒ no
        history. (Real webapp breadcrumbs use ``show: manual``/``structure``;
        ``session`` is the raw engine mirror — mostly CLI + backend debugging.)
        """
        trails = self._get_crumbs_dict(self.zos.session)
        if not isinstance(trails, dict) or not trails:
            return []

        hops: List[Dict[str, Any]] = []
        paths: List[str] = []
        for scope, trail in trails.items():
            if not isinstance(scope, str) or scope.startswith('_'):
                continue
            path = self.canonical_scope(scope).split('#')[0]
            # No filter — echo every recorded entry verbatim (density is the
            # recorder's job, not the display's). The arrival sentinel (α<block>)
            # rides in `keys` for zCLI's raw X-ray; `arrival` flags it so a clean
            # surface (Bifrost GUI) can drop the engine glyph and lead with the
            # human `label` WITHOUT re-implementing the sentinel detection.
            keys = [k for k in trail if isinstance(k, str)] if isinstance(trail, list) else []
            arrival = bool(keys and is_arrival(keys[0]))
            hops.append({"path": path, "label": path, "keys": keys, "arrival": arrival})
            paths.append(path)

        for label, hop in zip(self.derive_labels(paths), hops):
            hop["label"] = label
        return hops

    @staticmethod
    def derive_labels(paths: List[str]) -> List[str]:
        """Min-depth-unique display labels for a set of scope zPaths (SSOT rule).

        Depth 1 = the block leaf (``scope.rsplit('.',1)[-1]``); escalate the depth
        ONLY when leaves collide; fall back to the full path minus the root sigil.
        This is the one rule mirrored by the zCLI display helper and the Bifrost JS
        renderer — same algorithm, single definition of "what a crumb is called".
        """
        if not paths:
            return []
        parts_list = [p.split('#')[0].split('.') for p in paths]
        max_depth = max(len(p) for p in parts_list)
        for depth in range(1, max_depth):
            labels = ['.'.join(p[-depth:]) for p in parts_list]
            if len(set(labels)) == len(labels):
                return labels
        return ['.'.join(p[1:]) for p in parts_list]

    # ========================================================================
    # SSOT Recorder Contract — the ONE way a key enters the active scope trail
    # ========================================================================

    def record_zStride(self, key: str, walker: Optional[Any] = None, raw: bool = False) -> None:
        """Record ONE **zStride** into the active scope's trail (SSOT contract).

        A *zStride* is the engine atom: one key the zWalk touches. zWalker
        zWalks; at every key it zStrides; **a crumb is a recorded zStride**.
        (``step``/``zHat`` are event-altitude words — a user-authored
        ``zWizard:`` step is just a zStride wearing user control — and never
        leak into this recorder.) Every key that lands in a scope trail funnels
        through here so trail DENSITY is a DECLARED contract instead of an
        accident of each runtime's mechanics. The contract:

          - **zCLI** (synchronous wizard): the zWalk passes through keys in
            order and zStrides each, so the trail is dense — that is what lets
            ``handle_zBack`` step back key-by-key inside a page.
          - **Bifrost** (async chunk render): never walks intermediate keys; it
            zStrides via ``record_nav_origin`` with the clicked element's
            ANCESTRY CHAIN (block-top → leaf), each key recorded in order — the
            spatial analog of zCLI's temporal traversal.

        Density therefore differs by medium BY DESIGN; the HOP (scope) is the
        canonical interchangeable unit that ``project_trail`` exposes. A zStride
        is a forward advance only — backward motion goes through ``handle_zBack``,
        navbar resets through ``reset_trail``.

        ``raw`` selects the append policy. Default (``False``) keeps the
        consecutive-duplicate guard — correct for sequential zCLI / menu
        recording where a re-render must not double a key. ``True`` appends
        verbatim (no guard) for the airtight click-origin chain, where a
        legitimate repeat MUST survive the ``show: session`` echo.
        """
        self.handle_zCrumbs(key, _walker=walker, operation="APPEND_RAW" if raw else "APPEND")

    # ========================================================================
    # SSOT Nav-Origin Crumb (first-class primitive — every nav verb feeds it)
    # ========================================================================

    def record_nav_origin(
        self,
        origin: Optional[Any],
        walker: Optional[Any] = None
    ) -> None:
        """Record the click-origin ANCESTRY CHAIN onto the departing scope (SSOT).

        This is the chunk-mode equivalent of zCLI's sequential ``on_continue``
        recording. In zCLI the wizard walks keys in TIME, so by the time the user
        reaches a nav verb (zLink / zDelta / zURL / zMenu) every preceding key is
        already on the trail. Bifrost renders whole sections as chunks and never
        walks them — so the faithful record is the SPATIAL path of what was
        clicked: the ordered ``data-zkey`` ancestry from the departing block's
        top section down to the clicked leaf (e.g.
        ``["Events_Section", "Inner", "Grid", "Navigation_Card", "zURL"]``).
        Every nav verb routes its click-origin through this one method
        (verb-agnostic SSOT) so the departing scope carries "how the click was
        reached" BEFORE the destination scope is seeded. ``handle_zBack`` stays
        TRUE to the session trail, and ``show: session`` echoes it verbatim.

        Args
        ----
        origin : Optional[str | list[str]]
            The click-origin. A list is the ordered ancestry chain (preferred,
            outer→inner); a bare str is a single legacy origin key. No-op when
            falsy/empty.
        walker : Optional[Any]
            Walker for call-site symmetry; Breadcrumbs is self-aware.
        """
        if not origin:
            return
        # Only attribute the click to an EXISTING departing scope. With no active
        # scope this is a root/boot navigation — there is nothing to come back to.
        trails = self._get_crumbs_dict(self.zos.session)
        if not trails:
            return
        chain = origin if isinstance(origin, (list, tuple)) else [origin]
        # Airtight, verbatim, in order — RAW append so legitimate repeats survive
        # (the chain is the engine X-ray for `show: session`, not a curated UX trail).
        for key in chain:
            if isinstance(key, str) and key:
                self.record_zStride(key, walker=walker, raw=True)
        self.logger.debug(
            "[zCrumbs] record_nav_origin → appended chain %r to active scope", list(chain)
        )

    # ========================================================================
    # Public Trail Helpers (for the zBack ladder / navigation callbacks)
    # ========================================================================

    def get_active_trail(self) -> List[str]:
        """Return a copy of the current active trail (keys visited in this scope)."""
        session = self.zos.session
        trails = self._get_crumbs_dict(session)
        active_scope = self._get_active_crumb(session)
        # active_scope can be "" (empty string) when block name is unknown —
        # use `in` directly so falsy-but-valid scopes still work.
        if active_scope in trails:
            return list(trails[active_scope])
        return []

    def pop_trail_to_before(self, key: str) -> None:
        """
        Truncate the active trail so that ``key`` and everything after it is removed.
        The key will be re-appended by the menu modifier when it renders again.
        """
        session = self.zos.session
        trails = self._get_crumbs_dict(session)
        active_scope = self._get_active_crumb(session)
        if active_scope not in trails:
            return
        trail = trails[active_scope]
        if key in trail:
            idx = trail.index(key)
            del trail[idx + 1:]  # keep key itself; remove only what's deeper
            self.logger.debug(f"[zCrumbs] pop_trail_to_before('{key}'): trail now {trail}")

    # ========================================================================
    # Private Helper Methods (DRY)
    # ========================================================================

    def _get_active_crumb(self, session: Dict[str, Any]) -> str:
        """
        Get active (most recent) crumb from session.

        Args
        ----
        session : Dict[str, Any]
            zSession dict

        Returns
        -------
        str
            Active crumb (last key in trails dict)
        """
        trails = self._get_crumbs_dict(session)
        if trails:
            # Return the last key from trails (most recent)
            return list(trails.keys())[-1]
        return ""

    def _get_crumbs_dict(self, session: Dict[str, Any]) -> Dict[str, List[str]]:
        """
        Get crumbs dict (trails) from session with validation.

        Args
        ----
        session : Dict[str, Any]
            zSession dict

        Returns
        -------
        Dict[str, List[str]]
            Trails dictionary
        """
        self._ensure_enhanced_format(session)
        crumbs_dict = session.get(SESSION_KEY_ZCRUMBS, {})
        return crumbs_dict.get(_KEY_TRAILS, {})

    def _pop_scope(self, session: Dict[str, Any], scope: str) -> None:
        """
        Pop (remove) a scope from crumbs dict.

        Args
        ----
        session : Dict[str, Any]
            zSession dict
        scope : str
            Scope key to remove
        """
        trails = self._get_crumbs_dict(session)
        if scope in trails:
            del trails[scope]

    # ========================================================================
    # SSOT Navbar Reset Marker (zNavBar is the ONLY trail RESET in zOS)
    # ========================================================================

    def set_navbar_pending(self, scoped: bool = False) -> None:
        """
        Mark that the user's NEXT navigation is a navbar pick (zCLI one-shot).

        SSOT for the navbar reset marker. Previously modifier_menu wrote
        ``session[zCrumbs]["_navbar_navigation"] = True`` directly from the
        dispatch layer — a cross-subsystem reach into crumb state. Now the menu
        modifier calls this and zNavigation owns the marker. The flag lives at
        the top level of the crumbs map (beside ``trails``) and is consumed by
        the next zLink via ``is_navbar_pending`` + ``reset_trail``.

        Args
        ----
        scoped : bool, default=False
            False → GLOBAL navbar: the pick resets to the absolute root (full
            clear of every scope). True → INLINE navbar: capture the current
            active scope as the HOST and reset only DOWN TO it, so a nested host
            (e.g. a zDash page reached via a menu drill-in) survives the pick
            instead of being wiped. The host scope is the active scope at render
            time — the block the inline bar lives in.
        """
        session = self.zos.session
        self._ensure_enhanced_format(session)
        crumbs = session[SESSION_KEY_ZCRUMBS]
        crumbs[KEY_NAVBAR_PENDING] = True
        if scoped:
            host_scope = self._get_active_crumb(session)
            crumbs[KEY_NAVBAR_SCOPED] = host_scope
            self.logger.debug(
                "[zCrumbs] navbar pending set (SCOPED → host '%s') — next nav RESETs down to host",
                host_scope
            )
        else:
            crumbs.pop(KEY_NAVBAR_SCOPED, None)
            self.logger.debug("[zCrumbs] navbar pending set (FULL) — next navigation will RESET trail to root")

    def is_navbar_pending(self) -> bool:
        """Return True if the next navigation should RESET the trail (navbar pick)."""
        crumbs_dict = self.zos.session.get(SESSION_KEY_ZCRUMBS, {})
        if not isinstance(crumbs_dict, dict):
            return False
        return bool(crumbs_dict.get(KEY_NAVBAR_PENDING, False))

    def clear_navbar_pending(self) -> None:
        """
        Drop the one-shot navbar reset markers WITHOUT touching the trail.

        The pending flag is armed at navbar RENDER time (before the user picks),
        on the assumption the next navigation is an item hop that consumes it via
        ``reset_trail``. When the user instead picks **Done** (the navbar's
        exit-forward affordance) no navigation happens, so the armed flag would
        leak onto the next unrelated zLink and wrongly RESET its trail. modifier_menu
        calls this on a Done pick to disarm the markers and continue the block flow.
        """
        crumbs_dict = self.zos.session.get(SESSION_KEY_ZCRUMBS, {})
        if isinstance(crumbs_dict, dict):
            crumbs_dict.pop(KEY_NAVBAR_PENDING, None)
            crumbs_dict.pop(KEY_NAVBAR_SCOPED, None)
        self.logger.debug("[zCrumbs] navbar pending cleared (Done — no navigation)")

    def reset_trail(self) -> None:
        """
        Reset the crumb trail for a navbar pick — the ONLY trail RESET in zOS.

        Two depths, selected by the marker set in ``set_navbar_pending``:

        - **FULL** (global navbar, no host marker): clear every scope so the
          target becomes the absolute new root.
        - **SCOPED** (inline navbar, host marker present): keep the host scope
          and its ancestors, dropping only scopes opened *below* the host. The
          inline bar's host page (e.g. a zDash reached via a drill-in) survives
          the pick — the target seeds beneath it rather than replacing the world.

        Also drops the one-shot navbar markers so the following ordinary
        navigation APPENDs normally.
        """
        session = self.zos.session
        trails = self._get_crumbs_dict(session)
        crumbs_dict = session.get(SESSION_KEY_ZCRUMBS, {})
        host_scope = crumbs_dict.get(KEY_NAVBAR_SCOPED) if isinstance(crumbs_dict, dict) else None

        if host_scope and isinstance(trails, dict) and host_scope in trails:
            # SCOPED: drop every scope inserted AFTER the host (deeper), keep the
            # host scope (with its trail intact) and everything above it.
            scopes = list(trails.keys())
            cut = scopes.index(host_scope)
            dropped = scopes[cut + 1:]
            for scope in dropped:
                del trails[scope]
            self.logger.debug(
                "[zCrumbs] reset_trail (SCOPED) — kept down to host '%s', dropped %d deeper scope(s)",
                host_scope, len(dropped)
            )
        elif isinstance(trails, dict):
            # FULL: navbar target becomes the absolute new root.
            trails.clear()
            self.logger.debug("[zCrumbs] reset_trail (FULL) — navbar target becomes new root")

        if isinstance(crumbs_dict, dict):
            crumbs_dict.pop(KEY_NAVBAR_PENDING, None)
            crumbs_dict.pop(KEY_NAVBAR_SCOPED, None)

    def remove_scope(self, scope: str) -> None:
        """Public SSOT scope removal (e.g. zDash panel cleanup) — delegates to _pop_scope."""
        self._pop_scope(self.zos.session, scope)

    def pop_to_scope(self, target: str) -> bool:
        """Bulk-back to ``target`` — the ONE deliberate exception to append-everywhere.

        Forward navigation always APPENDs; a **zCrumb click** is the lone verb
        that travels backward by an arbitrary depth in a single step. This is its
        SSOT and the only live caller of the POP_TO operation. Mode-agnostic: the
        trail is backend state, so zCLI and Bifrost share this exact unwind. The
        click's *omega* (in-scope section anchor) is NOT consumed here — it rides
        the render intent and only Bifrost acts on it (scroll to section); zCLI
        has no viewport, so the scope half is all it needs.

        Resolution
        ----------
        - **Exact frame** — ``target`` is a literal trail key (the session echo
          carries the raw ``::dupN`` frame, so a specific revisit is honoured).
        - **Canonical** — else the LAST scope whose ``::dupN``-stripped form equals
          target's canonical form (a manual/structure crumb zPath → its live
          frame, preferring the most recent if revisited).

        Every scope opened *after* the matched frame is dropped, leaving it active.

        Returns
        -------
        bool
            True if ``target`` was on the trail and we unwound to it (caller
            re-renders that scope). False if ``target`` is not on the trail — the
            caller treats the click as ordinary FORWARD navigation (e.g. a manual
            crumb pointing at a never-visited block).
        """
        trails = self._get_crumbs_dict(self.zos.session)
        if not isinstance(trails, dict) or not trails or not target:
            return False
        scopes = list(trails.keys())
        if target in trails:
            idx = scopes.index(target)
        else:
            tgt_canon = self.canonical_scope(target)
            idx = None
            for i, scope in enumerate(scopes):
                if self.canonical_scope(scope) == tgt_canon:
                    idx = i  # keep scanning — prefer the most recent frame
            if idx is None:
                return False
        dropped = scopes[idx + 1:]
        for scope in dropped:
            del trails[scope]
        self.logger.debug(
            "[zCrumbs] pop_to_scope — bulk back to '%s', dropped %d deeper scope(s)",
            scopes[idx], len(dropped)
        )
        return True

    # ========================================================================
    # SSOT Scope Seeding (used by every navigation verb: zLink, zDelta, ...)
    # ========================================================================

    def build_scope_key(
        self,
        folder: str,
        file: str,
        block: str
    ) -> str:
        """
        Build the canonical breadcrumb scope key (SSOT).

        Every navigation verb that opens a new block (zLink, zDelta, zMenu,
        zNavBar, zDash, ...) MUST derive its scope key from this one place so
        the format never drifts. The format mirrors what ``handle_zBack`` parses
        back out: ``{folder}.{file}.{block}``.

        Args
        ----
        folder : str
            Base folder (e.g. "@.UI"). May be empty.
        file : str
            File path component (e.g. "zUI.btnlink"). May already include folder.
        block : str
            Target block name (e.g. "PageA").

        Returns
        -------
        str
            Canonical scope key, e.g. "@.UI.zUI.btnlink.PageA".
        """
        prefix = _SEPARATOR_DOT.join(p for p in (folder, file) if p)
        return f"{prefix}{_SEPARATOR_DOT}{block}" if prefix else block

    # History-SSOT disambiguator. Revisiting a scope that is already on the trail
    # must push a NEW frame (so zBack unwinds the true traversal) rather than
    # collapsing onto the first visit. Duplicate frames therefore get a unique
    # key "{scope}::dupN". Everything that turns a key back into a navigable
    # {folder}.{file}.{block} path MUST strip this suffix first via
    # canonical_scope(). Keep _DUP_SEP in sync with handler_zback._DUP_SEP.
    _DUP_SEP = "::dup"

    @staticmethod
    def canonical_scope(key: str) -> str:
        """Strip the history-SSOT ``::dupN`` suffix from a scope key (SSOT)."""
        return key.split(Breadcrumbs._DUP_SEP)[0] if key else key

    # Arrival-sentinel helpers — thin pass-throughs to the dep-free SSOT
    # (breadcrumb_marker) so zGuard surfaces (message_walker, wizard exec) reach
    # the ONE glyph at runtime via zos.navigation.breadcrumbs.* without importing
    # a deep core path. See breadcrumb_marker for why the glyph is 'α', not '$'.
    make_arrival = staticmethod(make_arrival)
    is_arrival = staticmethod(is_arrival)
    strip_arrival = staticmethod(strip_arrival)
    ARRIVAL_MARK = ARRIVAL_MARK

    def _unique_scope_key(self, scope: str, trails: Dict[str, Any]) -> str:
        """Return ``scope`` if free, else the next free ``scope::dupN`` key."""
        if scope not in trails:
            return scope
        n = 1
        while f"{scope}{self._DUP_SEP}{n}" in trails:
            n += 1
        return f"{scope}{self._DUP_SEP}{n}"

    def seed_scope(
        self,
        walker: Optional[Any] = None,
        folder: Optional[str] = None,
        file: Optional[str] = None,
        block: Optional[str] = None,
        arrival: bool = False
    ) -> str:
        """
        Create (if absent) the breadcrumb scope for a freshly-entered block.

        SSOT seeder. When folder/file/block are omitted they are read from the
        canonical session path keys (already updated by the caller, e.g.
        zLink._update_session_path). The scope is created in the enhanced
        ``trails`` map so all readers (handle_zBack, zCrumbs_banner) see it —
        unlike the legacy zDelta seeder, which wrote the flat top-level form and
        was silently ignored by every reader.

        Args
        ----
        walker : Optional[Any]
            Walker instance (unused for seeding; kept for call-site symmetry).
        folder, file, block : Optional[str]
            Explicit scope parts; fall back to session path keys when None.
        arrival : bool, default=False
            When True, seed the new scope with an ``α<block>`` arrival marker as
            its first trail entry. Cross-scope verbs (zLink, zDelta) set this so
            the landed page is treated as one navigable unit: a single zBack pops
            the whole scope back to its parent instead of unwinding the page's
            display keys one at a time. The boot/root scope leaves it False.

        Returns
        -------
        str
            The scope key that was created (or already present).
        """
        session = self.zos.session
        folder = folder if folder is not None else session.get(SESSION_KEY_ZVAFOLDER, "")
        file = file if file is not None else session.get(SESSION_KEY_ZVAFILE, "")
        block = block if block is not None else session.get(SESSION_KEY_ZBLOCK, "")
        scope = self.build_scope_key(folder, file, block)
        trails = self._get_crumbs_dict(session)

        # HISTORY-SSOT: seed_scope fires once per navigation event (zLink/zDelta/
        # boot), never on a plain re-render — so we can safely push a frame here.
        #   • Re-seeding the page we are ALREADY on (boot double-seed, self-nav,
        #     anchor jump) is idempotent: keep the current frame, do not grow.
        #   • Navigating to any OTHER page pushes a NEW frame, even if that page
        #     was visited earlier — revisits get a unique "{scope}::dupN" key so
        #     zBack unwinds the true traversal instead of collapsing repeats.
        keys = list(trails.keys())
        active_key = keys[-1] if keys else None
        if active_key is not None and self.canonical_scope(active_key) == scope:
            self.logger.debug(f"[zCrumbs] seed_scope → '{active_key}' (re-seed, no-op)")
            return active_key

        key = self._unique_scope_key(scope, trails)
        trails[key] = [make_arrival(block)] if arrival else []
        self.logger.debug(f"[zCrumbs] seed_scope → '{key}' (arrival={arrival})")
        return key

    def _create_trail_key(self, scope: str, session: Dict[str, Any]) -> None:
        """
        Create a new trail key if it doesn't exist.

        Args
        ----
        scope : str
            Scope key to create (e.g., "@.zUI.main.MainMenu")
        session : Dict[str, Any]
            zSession dict

        Returns
        -------
        None

        Notes
        -----
        DRY Helper: Centralizes trail key creation for zWalker orchestration.
        Ensures enhanced format and only creates if key doesn't already exist.
        Used by zWalker for session initialization and multi-block execution.

        Phase 0.5: Creates empty trail in enhanced format 'trails' dict.
        """
        self._ensure_enhanced_format(session)
        trails = self._get_crumbs_dict(session)
        if scope not in trails:
            trails[scope] = []

    def _ensure_enhanced_format(self, session: Dict[str, Any]) -> None:
        """
        Ensure breadcrumbs are in enhanced format.

        Args
        ----
        session : Dict[str, Any]
            zSession dict
        """
        crumbs_dict = session.get(SESSION_KEY_ZCRUMBS, {})

        # Check if already in enhanced format
        if _KEY_TRAILS in crumbs_dict:
            return

        # Migrate to enhanced format
        session[SESSION_KEY_ZCRUMBS] = {
            _KEY_TRAILS: crumbs_dict if isinstance(crumbs_dict, dict) else {},
            _KEY_CONTEXT: {},
            _KEY_DEPTH_MAP: {}
        }

    def _get_display(self, walker: Optional[Any] = None) -> Any:
        """
        Get display instance for banner rendering.

        Args
        ----
        walker : Optional[Any], default=None
            Optional walker instance for context

        Returns
        -------
        Any
            Display instance
        """
        return get_display_helper(self.zos, walker)
