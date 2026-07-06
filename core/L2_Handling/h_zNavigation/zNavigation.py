# zOS/core/L2_Handling/h_zNavigation/zNavigation.py

"""
zNavigation - Unified Navigation System Subsystem for zOS.

This module provides the zNavigation facade class, which serves as the primary
interface for navigation operations in zCLI mode. It orchestrates four specialized
components to deliver menu creation, breadcrumb management, navigation state
tracking, and inter-file linking.

Facade Pattern
--------------
The zNavigation class implements the Facade pattern, providing a simplified
interface to the complex navigation subsystem. It delegates all operations to
specialized components while maintaining a clean, consistent public API.

**Key Design Principles:**
- Pure delegation (no business logic in facade)
- Clean public API for external clients
- Component encapsulation (internal structure hidden)
- Backward compatibility (standalone functions for Walker)

Component Architecture
----------------------
The zNavigation facade orchestrates four specialized components:

1. **MenuSystem** (navigation_menu_system.py)
   - Menu creation and display (create, select)
   - Orchestrates builder, renderer, and interaction components
   - Supports static, dynamic, and function-based menus
   - Integration: Called by zDispatch for * (menu) modifier

2. **Breadcrumbs** (navigation_breadcrumbs.py)
   - Navigation trail management (zCrumbs)
   - "Back" functionality (zBack)
   - Session breadcrumb storage and retrieval
   - UI file reloading based on breadcrumb state

3. **Navigation** (navigation_state.py)
   - Current navigation location tracking
   - Navigation history management (FIFO overflow)
   - Session state storage with timestamps
   - Location metadata management

4. **Linking** (navigation_linking.py)
   - Inter-file linking (zLink expressions)
   - RBAC permission checking for links
   - Session context updates (zVaFolder, zVaFile, zBlock)
   - Integration: zParser (expression eval), zLoader (file loading)

Public API
----------
The facade exposes 10 methods organized by functional area:

**Menu System (2 methods):**
- create(options, title, allow_back, walker) → str
- select(options, prompt, walker) → str

**Breadcrumbs (2 methods):**
- handle_zCrumbs(zBlock, zKey, walker) → Any
- handle_zBack(show_banner, walker) → str

**Navigation State (3 methods):**
- navigate_to(target, context) → Dict
- get_current_location() → Dict
- get_navigation_history() → List

**Inter-file Linking (1 method):**
- handle_zLink(zHorizontal, walker) → str

Backward Compatibility
----------------------
Two standalone functions maintain backward compatibility with Walker:

- handle_zLink(zHorizontal, walker) → Delegates to facade
- handle_zCrumbs(zBlock, zKey, walker) → Delegates to facade

These functions ensure legacy code continues to work while encouraging
migration to the modern facade API.

Layer Position
--------------
Layer 1, Position 4 (zNavigation) - Facade

Integration
-----------
- Parent: zCLI core (zCLI.py)
- Used By: zDispatch (menu system), zWalker (navigation), external clients
- Uses: MenuSystem, Breadcrumbs, Navigation, Linking components

Usage Examples
--------------
Via facade (recommended)::

    # Initialize zCLI (done automatically)
    zcli = zCLI()
    
    # Create navigation menu
    choice = zcli.navigation.create(
        ["Settings", "Profile", "Logout"],
        title="Main Menu",
        allow_back=True,
        walker=walker
    )
    
    # Handle breadcrumb trail
    zcli.navigation.handle_zCrumbs("menu_block", "option_key", walker)
    
    # Navigate to location
    zcli.navigation.navigate_to("users.menu.list_users")
    
    # Handle inter-file linking
    result = zcli.navigation.handle_zLink("zLink(path.to.file.block)", walker)

Via standalone functions (backward compatibility)::

    # Legacy Walker integration
    from zOS.L2_Handling.h_zNavigation import handle_zLink, handle_zCrumbs
    
    # These delegate to the facade internally
    result = handle_zLink("zLink(path)", walker)
    handle_zCrumbs("block", "key", walker)

See Also
--------
- navigation_modules/ : Component implementations
- zDispatch : Menu system integration (* modifier)
- zWalker : Navigation orchestration
"""

from zOS import Any, Dict, List, Optional, Tuple

from .navigation_modules.menu.navigation_menu_system import MenuSystem
from .navigation_modules.navigation_breadcrumbs import Breadcrumbs
from .navigation_modules.navigation_state import Navigation
from .navigation_modules.navigation_linking import Linking
from .navigation_modules.handlers.handler_navbar import NavbarHandler
from .navigation_modules.navigation_constants import (
    COLOR_MENU,
    _DISPLAY_MSG_READY,
    _DISPLAY_INDENT_INIT,
    _DISPLAY_STYLE_INIT,
    _ERROR_MSG_NO_ZCLI,
    _ERROR_MSG_NO_WALKER,
    _LOG_MSG_READY,
)


# ============================================================================
# zNavigation Facade Class
# ============================================================================

class zNavigation:
    """
    Unified navigation system facade for zOS.
    
    Provides a clean, consistent interface to the navigation subsystem by
    orchestrating four specialized components: MenuSystem, Breadcrumbs,
    Navigation, and Linking. Implements the Facade pattern with pure
    delegation (no business logic in facade).
    
    Attributes
    ----------
    zcli : Any
        Reference to zCLI core instance
    session : Dict
        Session dictionary for state management
    logger : Any
        Logger instance for navigation operations
    mycolor : str
        Display color for navigation messages (default: "MENU")
    menu : MenuSystem
        Menu creation and interaction component
    breadcrumbs : Breadcrumbs
        Navigation trail management component
    navigation : Navigation
        Navigation state and history component
    linking : Linking
        Inter-file linking component
    
    Methods
    -------
    create(options, title, allow_back, walker)
        Create and display a menu, return user choice
    select(options, prompt, walker)
        Simple selection menu without complex navigation
    handle_zCrumbs(zBlock, zKey, walker)
        Handle breadcrumb trail management
    handle_zBack(show_banner, walker)
        Handle back navigation
    navigate_to(target, context)
        Navigate to a specific target
    get_current_location()
        Get current navigation location
    get_navigation_history()
        Get navigation history
    handle_zLink(zHorizontal, walker)
        Handle inter-file linking
    
    Examples
    --------
    Create navigation menu::
    
        nav = zNavigation(zcli)
        choice = nav.create(
            ["Settings", "Profile", "Logout"],
            title="Main Menu",
            walker=walker
        )
    
    Handle breadcrumbs::
    
        nav.handle_zCrumbs("menu_block", "option_key", walker)
        result = nav.handle_zBack(show_banner=True, walker=walker)
    
    Navigate to location::
    
        nav.navigate_to("users.menu.list_users")
        location = nav.get_current_location()
    
    Integration
    -----------
    - Initialized by: zCLI.py core
    - Used by: zDispatch, zWalker, external clients
    - Delegates to: MenuSystem, Breadcrumbs, Navigation, Linking
    """

    # Class-level type declarations
    zos: Any  # zOS instance
    session: Dict[str, Any]  # Session dictionary
    logger: Any  # Logger instance
    mycolor: str  # Display color
    menu: MenuSystem  # Menu system component
    breadcrumbs: Breadcrumbs  # Breadcrumbs component
    navigation: Navigation  # Navigation component
    linking: Linking  # Linking component
    navbar_handler: NavbarHandler  # Navbar handler component

    @property
    def session(self):
        """Live per-caller session — resolves via the live holder (§19 Phase 2)."""
        return self.zos.session

    def __init__(self, zos: Any) -> None:
        """
        Initialize zNavigation subsystem with component orchestration.
        
        Args
        ----
        zos : Any
            zOS instance (required)
        
        Raises
        ------
        ValueError
            If zos parameter is None
        
        Notes
        -----
        Initialization sequence:
        1. Validate zos parameter
        2. Store references (zos, session, logger)
        3. Set display color (backward compatibility)
        4. Initialize 4 specialized components
        5. Display ready message
        6. Log initialization
        """
        if zos is None:
            raise ValueError(_ERROR_MSG_NO_ZCLI)

        self.zos = zos
        self.logger = zos.logger
        self.mycolor = COLOR_MENU  # Keep MENU color for backward compatibility

        # Initialize navigation modules (component composition)
        self.menu = MenuSystem(self)
        self.breadcrumbs = Breadcrumbs(self)
        self.navigation = Navigation(self)
        self.linking = Linking(self)
        self.navbar_handler = NavbarHandler(self)  # Navbar handler (extracted)

        # Display ready message using modern zDisplay
        self.zos.display.zDeclare(
            _DISPLAY_MSG_READY,
            color=self.mycolor,
            indent=_DISPLAY_INDENT_INIT,
            style=_DISPLAY_STYLE_INIT
        )

        self.logger.framework.debug(_LOG_MSG_READY)

    def resolve_navbar(
        self, raw_zFile: Dict[str, Any],
        route_meta: Optional[Dict[str, Any]] = None
    ) -> Optional[List[str]]:
        """
        Resolve navigation bar for a given zVaFile based on meta.zNavBar with route fallback.
        
        Delegates to NavbarHandler for all navbar resolution logic following the
        approved handler pattern from e_zDispatch.
        
        Args
        ----
        raw_zFile : Dict[str, Any]
            Parsed YAML dictionary from zVaFile
        route_meta : Optional[Dict[str, Any]], default=None
            Optional route metadata from zServer.routes.yaml (for fallback)
        
        Returns
        -------
        Optional[List[str]]
            Resolved navbar items or None
        
        Notes
        -----
        - Delegates to self.navbar_handler.resolve()
        - See NavbarHandler for full resolution logic
        """
        return self.navbar_handler.resolve(raw_zFile, route_meta)

    def reload_navbar(self) -> None:
        """SSOT hook: refresh the cached global navbar after a zEnv reload.

        Called by zServer's soft reload AFTER zConfig re-injects zEnv into
        os.environ, so an edited ZNAVBAR (renamed/retargeted item) takes effect
        without a cold restart. Delegates to the handler — the facade owns no
        navbar parsing of its own.
        """
        self.navbar_handler.reload()

    def parse_zpsi_value(self, value: Any) -> "Tuple[str, Optional[str]]":
        """Normalize a zLink/zDelta value into ``(target, zPsi_anchor)`` (SSOT passthrough).

        zPsi is the shared property (dict form) of zLink/zDelta — it sets the
        walker start_key in the landed block (a menu-pick start line, by address).
        """
        return self.linking.resolver.parse_zpsi_value(value)

    def resolve_anchor_key(self, block_dict: Any, anchor: Optional[str]) -> Optional[str]:
        """Resolve a zPsi anchor to the real (modifier-bearing) block key (SSOT passthrough)."""
        return self.linking.resolver.resolve_anchor_key(block_dict, anchor)

    def compile_intent(self, value: Any, verb: Optional[str] = None) -> Any:
        """Compile any navigation value into a canonical NavIntent (SSOT passthrough).

        The single nav "compiler": explicit ``verb`` (zLink/zDelta dispatch) or
        href-classified verb (zURL). Returns a NavIntent(verb, target, zpsi,
        perms, kind) — see ZLinkResolver.compile_intent.
        """
        return self.linking.resolver.compile_intent(value, verb=verb)

    def _filter_navbar_byzRBAC(self, navbar_items: List[Any]) -> List[Any]:
        """
        Filter navbar items based on RBAC rules and authentication state.

        Delegates to NavbarHandler for RBAC filtering logic.

        Args
        ----
        navbar_items : List[Any]
            Raw navbar items (strings or dicts with RBAC metadata)

        Returns
        -------
        List[Any]
            Filtered list of navbar items

        Notes
        -----
        - Delegates to self.navbar_handler.filter_by_rbac()
        - See NavbarHandler for full filtering logic
        """
        return self.navbar_handler.filter_by_rbac(navbar_items)

    # ========================================================================
    # Menu System Methods
    # ========================================================================

    def create(
        self,
        options: Any,
        title: Optional[str] = None,
        allow_back: bool = True,
        walker: Optional[Any] = None
    ) -> str:
        """
        Create and display a menu, return user choice.
        
        Delegates to MenuSystem for full-featured menu creation with navigation
        support. Integrates with breadcrumb system and supports "Back" option.
        
        Args
        ----
        options : Any
            List of menu options or dict with options
        title : Optional[str], default=None
            Optional menu title
        allow_back : bool, default=True
            Whether to add "Back" option
        walker : Optional[Any], default=None
            Optional walker instance for context
        
        Returns
        -------
        str
            Selected option string (or "zBack" if back chosen)
        
        Examples
        --------
        Basic menu::
        
            choice = nav.create(
                ["Settings", "Profile", "Logout"],
                title="Main Menu",
                walker=walker
            )
        
        Anchor menu (no back)::
        
            choice = nav.create(
                ["Yes", "No"],
                title="Confirm",
                allow_back=False,
                walker=walker
            )
        
        Notes
        -----
        - Called by zDispatch for * (menu) modifier
        - Delegates to MenuSystem.create()
        - Mode-agnostic (zCLI/Bifrost)
        """
        return self.menu.create(options, title=title, allow_back=allow_back, walker=walker)

    def select(
        self,
        options: List[str],
        prompt: str = "Select option",
        walker: Optional[Any] = None
    ) -> str:
        """
        Simple selection menu without complex navigation.
        
        Delegates to MenuSystem for simplified menu without "Back" option or
        navigation features. Used for quick selections.
        
        Args
        ----
        options : List[str]
            List of options to select from
        prompt : str, default="Select option"
            Prompt text to display
        walker : Optional[Any], default=None
            Optional walker instance for context
        
        Returns
        -------
        str
            Selected option string
        
        Examples
        --------
        Color selection::
        
            color = nav.select(
                ["Red", "Green", "Blue"],
                prompt="Choose a color",
                walker=walker
            )
        
        Quick yes/no::
        
            answer = nav.select(["Yes", "No"], walker=walker)
        
        Notes
        -----
        - No "Back" option (hardcoded allow_back=False)
        - Delegates to MenuSystem.select()
        - Simpler display than create()
        """
        return self.menu.select(options, prompt=prompt, walker=walker)

    # ========================================================================
    # Breadcrumbs Methods
    # ========================================================================

    def handle_zCrumbs(
        self,
        zKey: str,
        walker: Optional[Any] = None,
        operation: str = "APPEND"
    ) -> Any:
        """
        Handle breadcrumb trail management.
        
        Delegates to Breadcrumbs for adding navigation crumbs to session,
        enabling "Back" functionality and navigation trail display.
        Self-aware: reads session state to determine active block path.
        
        Args
        ----
        zKey : str
            Key identifier for breadcrumb
        walker : Optional[Any], default=None
            Optional walker instance for context
        operation : str, default="APPEND"
            Breadcrumb operation: "APPEND" or "REPLACE"
        
        Returns
        -------
        Any
            Breadcrumb operation result
        
        Examples
        --------
        Add breadcrumb::
        
            nav.handle_zCrumbs("users_menu", "list_users_key", walker)
        
        Notes
        -----
        - Stores breadcrumb in session (zCrumbs key)
        - Enables zBack functionality
        - Delegates to Breadcrumbs.handle_zCrumbs()
        - Breadcrumbs reads session state to determine block path
        - Supports APPEND (default) and REPLACE operations
        """
        return self.breadcrumbs.handle_zCrumbs(zKey, _walker=walker, operation=operation)

    def record_zStride(self, key: str, walker: Optional[Any] = None, raw: bool = False) -> None:
        """Record ONE **zStride** into the active scope trail (SSOT contract).

        A zStride is the engine atom (one key the zWalk touches); a crumb is a
        recorded zStride. The single sanctioned recorder entry point — every key
        that enters a scope trail (menu picks, zLink source, nav-origin) funnels
        through here so trail density is a DECLARED contract, not incidental.
        ``raw`` skips the consecutive-dup guard for the airtight click-origin
        chain. Delegates to Breadcrumbs.record_zStride (SSOT owner); see it for
        the per-medium density contract (zCLI dense / Bifrost click-ancestry chain).
        """
        return self.breadcrumbs.record_zStride(key, walker=walker, raw=raw)

    def record_nav_origin(
        self,
        origin: Optional[Any],
        walker: Optional[Any] = None
    ) -> None:
        """Record the click-origin ANCESTRY CHAIN onto the departing scope (SSOT).

        First-class nav-origin recorder used by EVERY navigation verb (zLink,
        zDelta, zURL, zMenu). In Bifrost's chunked render the click is the only
        signal, so verbs pass the clicked element's ordered ``data-zkey``
        ancestry (block-top → leaf) and this appends it verbatim to the departing
        scope — the spatial analog of zCLI's sequential on_continue recording.
        Accepts a list (chain) or a bare str (legacy single key). Delegates to
        Breadcrumbs (SSOT owner).
        """
        return self.breadcrumbs.record_nav_origin(origin, walker=walker)

    def pop_to_scope(self, target: str) -> bool:
        """Bulk-back to ``target`` — SSOT facade for the zCrumb click (POP_TO).

        The lone backward-by-arbitrary-depth verb: a crumb click unwinds the
        trail to ``target`` in one step instead of appending. Mode-agnostic
        (trail is backend state — zCLI and Bifrost share the unwind). Returns
        True when it popped (target was on the trail → caller re-renders that
        scope), False when absent (caller forwards as ordinary navigation).
        Delegates to Breadcrumbs.pop_to_scope (SSOT owner).
        """
        return self.breadcrumbs.pop_to_scope(target)

    def handle_zCrumb_back(
        self,
        target: str,
        walker: Optional[Any] = None
    ) -> Optional[Tuple[Dict[str, Any], List[str], Optional[str]]]:
        """zCrumb click → bulk-back render path (SSOT facade).

        Returns the ``(block_dict, block_keys, start_key)`` tuple to re-walk the
        target page when ``target`` is on the trail, else None (caller forwards
        the click as ordinary zLink). Delegates to Breadcrumbs.handle_zCrumb_back.
        """
        return self.breadcrumbs.handle_zCrumb_back(target, walker=walker)

    def handle_zBack(
        self,
        show_banner: bool = True,
        walker: Optional[Any] = None
    ) -> Tuple[Dict[str, Any], List[str], Optional[str]]:
        """
        Handle back navigation.
        
        Delegates to Breadcrumbs for navigating back in the breadcrumb trail,
        reloading the previous UI file and restoring navigation state.
        
        Args
        ----
        show_banner : bool, default=True
            Whether to display "zBack" banner
        walker : Optional[Any], default=None
            Optional walker instance for context
        
        Returns
        -------
        Tuple[Dict[str, Any], List[str], Optional[str]]
            A tuple containing:
            - block_dict: Dict of the active block's content
            - block_keys: List of all keys in the active block
            - start_key: The key to resume from (or None if trail is empty)
        
        Examples
        --------
        Navigate back with banner::
        
            result = nav.handle_zBack(show_banner=True, walker=walker)
        
        Silent back navigation::
        
            result = nav.handle_zBack(show_banner=False, walker=walker)
        
        Notes
        -----
        - Pops breadcrumb from session trail
        - Reloads previous UI file
        - Delegates to Breadcrumbs.handle_zBack()
        """
        return self.breadcrumbs.handle_zBack(show_banner=show_banner, walker=walker)

    # ========================================================================
    # Navigation Methods
    # ========================================================================

    def navigate_to(
        self,
        target: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Navigate to a specific target.
        
        Delegates to Navigation for updating current location and adding to
        navigation history with optional context metadata.
        
        Args
        ----
        target : str
            Navigation target (file, block, key, etc.)
        context : Optional[Dict[str, Any]], default=None
            Optional navigation context metadata
        
        Returns
        -------
        Dict[str, Any]
            Navigation result with status and target
        
        Examples
        --------
        Navigate to file/block::
        
            result = nav.navigate_to("users.menu.list_users")
        
        Navigate with context::
        
            result = nav.navigate_to(
                "users.detail",
                context={"user_id": 123}
            )
        
        Notes
        -----
        - Updates session current_location
        - Adds to navigation_history (FIFO overflow)
        - Delegates to Navigation.navigate_to()
        """
        return self.navigation.navigate_to(target, context=context)

    def get_current_location(self) -> Dict[str, Any]:
        """
        Get current navigation location.
        
        Delegates to Navigation for retrieving current location from session,
        including target and context metadata.
        
        Returns
        -------
        Dict[str, Any]
            Current location dict with target, context, timestamp
        
        Examples
        --------
        Get current location::
        
            location = nav.get_current_location()
            print(f"Current: {location['target']}")
        
        Notes
        -----
        - Reads from session (current_location key)
        - Returns empty dict if no location set
        - Delegates to Navigation.get_current_location()
        """
        return self.navigation.get_current_location()

    def get_navigation_history(self) -> List[Dict[str, Any]]:
        """
        Get navigation history.
        
        Delegates to Navigation for retrieving full navigation history from
        session, limited to last 50 entries (FIFO overflow).
        
        Returns
        -------
        List[Dict[str, Any]]
            List of navigation history entries
        
        Examples
        --------
        Get history::
        
            history = nav.get_navigation_history()
            for entry in history:
                print(f"Visited: {entry['target']}")
        
        Notes
        -----
        - Reads from session (navigation_history key)
        - Limited to 50 entries (FIFO overflow)
        - Delegates to Navigation.get_navigation_history()
        """
        return self.navigation.get_navigation_history()

    # ========================================================================
    # Linking Methods
    # ========================================================================

    def handle_zLink(
        self,
        zHorizontal: str,
        walker: Optional[Any] = None
    ) -> str:
        """
        Handle inter-file linking.
        
        Delegates to Linking for parsing zLink expressions, checking RBAC
        permissions, loading target files, and updating session context.
        
        Args
        ----
        zHorizontal : str
            zLink expression (e.g., "zLink(path.to.file.block)")
        walker : Optional[Any], default=None
            Optional walker instance for context
        
        Returns
        -------
        str
            Result of link navigation
        
        Examples
        --------
        Basic link::
        
            result = nav.handle_zLink(
                "zLink(users.menu.list_users)",
                walker=walker
            )
        
        Link with permissions::
        
            result = nav.handle_zLink(
                "zLink(admin.settings, {role: 'admin'})",
                walker=walker
            )
        
        Notes
        -----
        - Parses zLink expression (zParser integration)
        - Checks RBAC permissions if specified
        - Loads target file (zLoader integration)
        - Updates session context (zVaFolder, zVaFile, zBlock)
        - Delegates to Linking.handle()
        """
        return self.linking.handle(walker=walker, zHorizontal=zHorizontal)


# ============================================================================
# Standalone Functions (Backward Compatibility)
# ============================================================================

def handle_zLink(zHorizontal: str, walker: Optional[Any] = None) -> str:
    """
    Standalone link handler function for Walker compatibility.
    
    Provides backward compatibility with legacy Walker code by maintaining
    the standalone function interface while delegating to the modern facade.
    
    Args
    ----
    zHorizontal : str
        zLink expression to handle
    walker : Optional[Any], default=None
        Walker instance (required)
    
    Returns
    -------
    str
        Result of link navigation
    
    Raises
    ------
    ValueError
        If walker parameter is not provided
    
    Examples
    --------
    Legacy Walker usage::
    
        from zOS.L2_Handling.h_zNavigation import handle_zLink
        result = handle_zLink("zLink(path)", walker)
    
    Notes
    -----
    - Backward compatibility for Walker integration
    - Delegates to walker.zcli.navigation.handle_zLink()
    - Modern code should use facade directly (zcli.navigation.handle_zLink)
    """
    if not walker:
        raise ValueError(f"handle_zLink {_ERROR_MSG_NO_WALKER}")

    return walker.zcli.navigation.handle_zLink(zHorizontal=zHorizontal, walker=walker)


def handle_zCrumbs(
    zKey: str,
    walker: Optional[Any] = None,
    operation: str = "APPEND"
) -> Any:
    """
    Standalone breadcrumbs handler function for Walker compatibility.
    
    Self-aware: reads session state to determine active block path.
    Delegates to the modern facade for actual breadcrumb handling.
    
    Args
    ----
    zKey : str
        Key identifier for breadcrumb
    walker : Optional[Any], default=None
        Walker instance (required)
    operation : str, default="APPEND"
        Breadcrumb operation: "APPEND" or "REPLACE"
    
    Returns
    -------
    Any
        Breadcrumb operation result
    
    Raises
    ------
    ValueError
        If walker parameter is not provided
    
    Examples
    --------
    Walker usage::
    
        from zOS.L2_Handling.h_zNavigation import handle_zCrumbs
        handle_zCrumbs("key", walker)
    
    Notes
    -----
    - Delegates to walker.zcli.navigation.handle_zCrumbs()
    - Breadcrumbs reads session state for block path (Delta link support)
    - Modern code should use facade directly (zcli.navigation.handle_zCrumbs)
    - Supports APPEND (default) and REPLACE operations
    """
    if not walker:
        raise ValueError(f"handle_zCrumbs {_ERROR_MSG_NO_WALKER}")

    return walker.zcli.navigation.handle_zCrumbs(zKey=zKey, walker=walker, operation=operation)
