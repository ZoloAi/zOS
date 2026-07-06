# zOS/core/L4_Orchestration/q_zWalker/zWalker.py

"""
zWalker Subsystem - Pure Orchestration Layer (Layer 4)

╔══════════════════════════════════════════════════════════════════════════════╗
║ CRITICAL: NO LOGIC ALLOWED IN ZWALKER - ORCHESTRATION ONLY                   ║
╚══════════════════════════════════════════════════════════════════════════════╝

This module is a PURE ORCHESTRATION LAYER following Linux From Scratch architecture.

**RULES (FOR ALL DEVELOPERS AND LLMs):**
1. PROHIBITED: NO business logic - delegate to lower layers (zDispatch, zNavigation, zWizard)
2. PROHIBITED: NO data processing - delegate to zWizard or zDispatch
3. PROHIBITED: NO validation logic - delegate to zNavigation (self-aware subsystems)
4. PROHIBITED: NO path construction - delegate to zNavigation
5. PROHIBITED: NO dispatch logic - delegate to zDispatch (Single Source of Truth)
6. PROHIBITED: NO special case handling - lower layers handle it
7. REQUIRED: ONLY coordination via callbacks and method calls
8. REQUIRED: ONLY delegation to lower layer subsystems

**VIOLATION = ARCHITECTURAL BREAKDOWN**
Any logic added to zWalker violates:
- Single Source of Truth principle
- Separation of Concerns
- Linux From Scratch layered architecture
- DRY (Don't Repeat Yourself)

────────────────────────────────────────────────────────────────────────────────
ARCHITECTURE: PURE ORCHESTRATOR PATTERN (EXTENDS ZWIZARD)
────────────────────────────────────────────────────────────────────────────────

zWalker is a PURE orchestrator that extends zWizard to add navigation callbacks.
ALL block execution, _data resolution, dispatch, and iteration logic is INHERITED
or DELEGATED - NEVER reimplemented.

    ┌──────────────────────────────────────────────────────────────┐
    │                    ZWALKER (ORCHESTRATOR)                    │
    ├──────────────────────────────────────────────────────────────┤
    │                                                              │
    │  INHERITANCE:                                                │
    │      zWalker extends zWizard                                 │
    │      - Inherits: handle(), execute_loop(), _data resolution  │
    │      - Adds: Navigation callbacks (on_back, on_exit, etc.)   │
    │                                                              │
    │  ORCHESTRATION MAP (100% DELEGATION):                        │
    │      ┌──────────────────────────────────────────────┐        │
    │      │  run() [PURE ORCHESTRATOR]                   │        │
    │      │    ├─→ session.get() [DELEGATION TO ZCONFIG] │        │
    │      │    │   └─→ "zBifrost" → bifrost.orchestrator │        │
    │      │    │                    .start() [ZBIFROST]   │        │
    │      │    ├─→ loader.handle() [DELEGATION TO ZLOADER]        │
    │      │    ├─→ display.zDeclare() [DELEGATION TO ZDISPLAY]    │
    │      │    └─→ execute_loop() [INHERITED FROM ZWIZARD]        │
    │      │        with navigation_callbacks              │        │
    │      │                                                │        │
    │      │  _create_navigation_callbacks()               │        │
    │      │    [RETURNS PURE DELEGATION CALLBACKS]        │        │
    │      │    ├─→ on_continue: navigation.handle_zCrumbs()       │
    │      │    ├─→ on_back: navigation.handle_zBack()     │        │
    │      │    ├─→ on_exit: display.zDeclare() + return   │        │
    │      │    └─→ on_stop: soft alias of on_exit (graceful)      │
    │      └──────────────────────────────────────────────┘        │
    │                                                              │
    └──────────────────────────────────────────────────────────────┘

────────────────────────────────────────────────────────────────────────────────
DUAL-MODE ARCHITECTURE
────────────────────────────────────────────────────────────────────────────────

zWalker supports two execution modes, determined by zSession's zMode:

**zCLI Mode (Default):**
    - Traditional CLI menu navigation
    - Readline-based input with history
    - ASCII-formatted display via zDisplay
    - Direct keyboard input (STDIN)
    - Synchronous execution

**zBifrost Mode (WebSocket):**
    - WebSocket-based client-server architecture
    - JSON message protocol for commands/events
    - HTML-formatted display via zDisplay
    - Remote client input (WebSocket messages)
    - Asynchronous execution via asyncio

Mode Detection (Pure Delegation):
    ```python
    if self.session.get("zMode") == "zBifrost":
        # Delegate to zBifrost subsystem - NO custom logic
        asyncio.run(self.zos.bifrost.orchestrator.start(walker=self))
    else:
        # Delegate to zWizard.execute_loop - NO custom logic
        return self.execute_loop(items_dict=..., navigation_callbacks=...)
    ```

────────────────────────────────────────────────────────────────────────────────
NAVIGATION CALLBACKS PATTERN (PURE DELEGATION)
────────────────────────────────────────────────────────────────────────────────

zWalker provides navigation callbacks to zWizard.execute_loop - ALL callbacks
are PURE DELEGATION wrappers with NO logic:

**on_continue(result, key):**
    - Delegates breadcrumb tracking to zNavigation.handle_zCrumbs()
    - NO validation - zNavigation is self-aware
    - NO path construction - zNavigation handles it
    - Pure delegation: `self.navigation.handle_zCrumbs(key, walker=self)`

**on_back(result):**
    - Delegates to zNavigation.handle_zBack() for breadcrumb pop
    - Delegates to zWizard.execute_loop() for re-execution
    - NO custom logic - pure coordination
    - Pure delegation chain

**on_exit(result):**
    - Soft exit coordination (return to caller)
    - Delegates display to zDisplay.zDeclare()
    - Returns dict for caller (zShell or script)
    - Acceptable: coordination + return value

**on_stop(result):**
    - RETIRED → soft alias of on_exit (graceful unwind, no sys.exit)
    - zOS has ONE shutdown: the graceful return. "stop" ends like "exit"

(on_error retired — zOS never crashes on a fault. A returned error/None/False
bubbles up and the walk continues; "must not fail" is the ! modifier's business.)

────────────────────────────────────────────────────────────────────────────────
BREADCRUMB TRACKING (DELEGATED TO ZNAVIGATION)
────────────────────────────────────────────────────────────────────────────────

zWalker does NOT manage breadcrumbs - it DELEGATES to zNavigation:

**Delegation Pattern:**
    - PROHIBITED: NO path construction in zWalker
    - PROHIBITED: NO validation in zWalker
    - PROHIBITED: NO breadcrumb management in zWalker
    - REQUIRED: ONLY calls: `self.navigation.handle_zCrumbs(key, walker=self)`
    - REQUIRED: ONLY calls: `self.navigation.handle_zBack(walker=self)`

**Storage (managed by zNavigation via zConfig):**
    ```python
    zSession["zCrumbs"] = {
        "@.zUI.main_menu.MainMenu": ["dashboard", "settings"],
        "@.zUI.settings_menu.SettingsMenu": ["profile"]
    }
    ```

**Note:** All breadcrumb logic (path construction, validation, storage) is in
zNavigation.breadcrumbs module - zWalker is a PASSIVE CALLER ONLY.

────────────────────────────────────────────────────────────────────────────────
ZOS INITIALIZATION ORDER (Alphabetical Prefixes Match engine.py)
────────────────────────────────────────────────────────────────────────────────

**Foundation (L1_Foundation):**
    1. a_zConfig   - Configuration, session, logging (self, logger, session)
    2. b_zComm     - Communication infrastructure (WebSocket, HTTP, PostgreSQL)
    3. c_zLoader   - File loading, caching (UI, Schema, Config, Python modules)

**Core Handling (L2_Handling) - Initialized Early:**
    4. e_zDisplay  - Display/output system (initialized before d_zParser for loader feedback)

**Core Handling (L2_Handling) - Standard Order:**
    5. d_zParser   - Path resolution, content parsing, file identification
    6. f_zAuth     - Authentication, authorization, RBAC
    7. g_zDispatch - Command routing, dispatch (Single Source of Truth)
    8. h_zNavigation - Breadcrumbs, menus, linking, back navigation
    9. i_zFunc     - Function execution, plugin invocation
   10. j_zDialog   - Dialog system, user interactions
   11. k_zOpen     - File/URL opening, external app launching

**Core Abstraction (L3_Abstraction):**
   12. l_zEngine   - Loop engine, block execution, _data resolution
   13. m_zData     - Data management, CRUD operations
   14. o_zBifrost  - WebSocket bridge, server orchestration
   15. p_zShell    - Shell interface, command executor

**Orchestration (L4_Orchestration):**
   16. q_zWalker   - Navigation orchestrator (THIS MODULE)
   17. r_zServer   - HTTP/WSGI server, route handling
   18. s_zRaven    - Automated test subsystem (zSpark-activated, off by default)

**Key Dependencies (for zWalker):**
    - zWizard: Loop engine (inherited via parent class)
    - zNavigation: Breadcrumbs, menus, inter-file linking
    - zDisplay: Mode-agnostic output (zCLI + Bifrost)
    - zDispatch: Command routing and execution
    - zLoader: Declarative file loading (zVaFiles)
    - zBifrost: WebSocket server orchestration

**External Modules:**
    - asyncio: For zBifrost server (imported inline)

────────────────────────────────────────────────────────────────────────────────
USAGE
────────────────────────────────────────────────────────────────────────────────

**zCLI Mode:**
    ```python
    from zOS.L4_Orchestration.q_zWalker import zWalker
    
    walker = zWalker(zos)
    walker.run()  # Starts terminal-based menu navigation
    ```

**zBifrost Mode (WebSocket):**
    ```python
    # Set mode before walker initialization
    zos.session["zMode"] = "zBifrost"
    
    walker = zWalker(zos)
    walker.run()  # Starts WebSocket server instead of terminal loop
    ```

**From zShell (Launch Walker from Shell):**
    ```python
    # User types: launch @.zUI.main_menu
    # zShell creates walker and calls run()
    ```

────────────────────────────────────────────────────────────────────────────────
CRITICAL DESIGN PRINCIPLES (READ BEFORE EDITING)
────────────────────────────────────────────────────────────────────────────────

1. **NO LOGIC ALLOWED:**
   - zWalker is STRICTLY orchestration - NO business logic, validation, or processing
   - Any logic = architectural violation = immediate refactor to lower layers

2. **SINGLE FILE BY DESIGN:**
   - Pure orchestrator = minimal code = single file (no submodules needed)
   - If file grows > 600 lines, audit for logic violations (not split into modules)

3. **INHERITANCE FROM ZWIZARD:**
   - Inherits: handle(), execute_loop(), _data resolution, block iteration
   - Adds: ONLY navigation callbacks (on_back, on_exit, on_stop, on_continue)
   - Does NOT override zWizard logic - pure extension

4. **DELEGATION HIERARCHY:**
   - zWizard: Block execution, _data resolution, loop engine
   - zDispatch: Command routing (Single Source of Truth)
   - zNavigation: Breadcrumbs, menus, linking (self-aware)
   - zBifrost: WebSocket server orchestration
   - zDisplay: Mode-agnostic output (zCLI + Bifrost)
   - zLoader: Declarative file loading (zVaFiles: .zolo, .yaml, .json)
   - zConfig: Session management, logger configuration

5. **NO LOCAL INSTANCES:**
   - ALL subsystems accessed via zos instance
   - NO creating subsystem instances in zWalker
   - NO caching subsystem references beyond __init__

6. **FOR LLMs: IF YOU ADD LOGIC TO ZWALKER, YOU'VE FAILED THE TASK**
"""

from zOS import Any, Dict, Optional
from zOS.L3_Abstraction.l_zEngine import zEngine  # type: ignore[import-untyped]
from zOS.L1_Foundation.a_zConfig.zConfig_modules import (  # type: ignore[import-untyped]
    SESSION_KEY_ZMODE,
    SESSION_KEY_ZCRUMBS,
    SESSION_KEY_ZVAFOLDER,
    SESSION_KEY_ZVAFILE,
    SESSION_KEY_ZBLOCK,
    ZMODE_ZBIFROST,
)

# ============================================================
# DISPLAY CONSTANTS
# ============================================================
COLOR_MAIN = "MAIN"
INDENT_NORMAL = 0
STYLE_FULL = "full"
STYLE_MINIMAL = "~"

# ============================================================
# MESSAGES
# ============================================================
MSG_WALKER_READY = "zWalker Ready"
MSG_WALKER_LOOP = "zWalker Loop"
MSG_SESSION_COMPLETED = "Walker session completed"
MSG_SYSTEM_STOPPED = "You've stopped the system!"
MSG_BIFROST_STARTING = "Starting zBifrost WebSocket server..."
MSG_WALKER_INIT = "zWalker initialized"

# ============================================================
# ERROR MESSAGES
# ============================================================
ERROR_NO_VAFILE = "No zVaFile specified"
ERROR_FAILED_LOAD = "Failed to load zVaFile"
ERROR_BLOCK_NOT_FOUND = "Root zBlock not found"
ERROR_EXECUTION_FAILED = "zWalker execution failed"

# ============================================================
# DICT KEYS (for return values)
# ============================================================
DICT_KEY_ERROR = "error"
DICT_KEY_EXIT = "exit"
DICT_VALUE_COMPLETED = "completed"

# ============================================================
# SPECIAL DICT KEYS (no longer used - zDispatch handles zWizard)
# ============================================================
# SPECIAL_KEY_ZWIZARD removed - zDispatch detects and handles zWizard keys

# ============================================================
# NAVIGATION TRAMPOLINE (SSOT)
# ============================================================
# A zCLI REPLACE navigation (zLink/zDelta/zBack/in-page zPsi) used to call
# walker.execute_loop(target) recursively, growing the Python stack by one frame
# per hop and crashing with RecursionError after ~120 navigations. Instead the
# hop now stashes its destination in session[SESSION_KEY_PENDING_NAV] and returns
# NAV_SIGNAL; the executor bubbles that straight up to the trampoline loop in
# run(), which re-enters execute_loop with the staged target — a flat stack
# regardless of navigation count. NAV_SIGNAL must equal zGuard's _SIGNAL_NAVIGATE.
NAV_SIGNAL = "navigate"
SESSION_KEY_PENDING_NAV = "_pending_nav"

# ============================================================
# NAVIGATION CALLBACK KEYS
# ============================================================
CALLBACK_ON_BACK = "on_back"
CALLBACK_ON_EXIT = "on_exit"
CALLBACK_ON_STOP = "on_stop"

# ============================================================
# LOG MESSAGES
# ============================================================
LOG_ERROR_NO_VAFILE = "No zVaFile specified in zSpark_obj"
LOG_ERROR_FAILED_LOAD = "Failed to load zVaFile: %s"
LOG_ERROR_BLOCK_NOT_FOUND = "Root zBlock '%s' not found in zVaFile"
LOG_ERROR_EXECUTION = "zWalker execution failed: %s"
LOG_DEBUG_BREADCRUMB = "Initialized breadcrumb: %s"
LOG_DEBUG_DISPATCH_EXIT = "Dispatch returned exit"
LOG_DEBUG_DISPATCH_STOP = "Dispatch returned stop"


class zWalker(zEngine):
    """
    PURE Orchestration Layer (Layer 4) - Declarative UI/Menu Navigation.
    
    ╔══════════════════════════════════════════════════════════════════════════╗
    ║ CRITICAL: NO LOGIC ALLOWED - ORCHESTRATION ONLY - DELEGATES EVERYTHING  ║
    ╚══════════════════════════════════════════════════════════════════════════╝
    
    zWalker extends zWizard to add ONLY navigation callbacks.
    ALL execution, dispatch, validation, path construction is DELEGATED.
    
    Processes zVaFiles (zVacuumFiles): Declarative UI definitions in .zolo, .yaml, or .json format.
    
    **WHAT ZWALKER DOES (ONLY):**
    ALLOWED: Detect mode (zCLI vs zBifrost) → delegate to appropriate subsystem
    ALLOWED: Load zVaFile → delegate to zLoader (.zolo, .yaml, .json)
    ALLOWED: Execute blocks → delegate to zWizard.execute_loop (inherited)
    ALLOWED: Track breadcrumbs → delegate to zNavigation via on_continue callback
    ALLOWED: Handle navigation → delegate to zNavigation via callbacks
    ALLOWED: Display messages → delegate to zDisplay
    
    **WHAT ZWALKER DOES NOT DO:**
    PROHIBITED: NO block iteration logic (inherited from zWizard)
    PROHIBITED: NO _data resolution (inherited from zWizard)
    PROHIBITED: NO dispatch logic (uses zDispatch via zWizard)
    PROHIBITED: NO breadcrumb path construction (zNavigation handles it)
    PROHIBITED: NO validation (subsystems are self-aware)
    PROHIBITED: NO special case handling (lower layers handle it)
    PROHIBITED: NO business logic of ANY kind
    
    Attributes:
        zos (Any): Main zOS instance with ALL subsystems (single source)
        zSpark_obj (Dict[str, Any]): Boot config (via zos.zspark_obj)
        session (Dict[str, Any]): Session state (via zos.session, managed by zConfig)
        display (Any): zDisplay instance (via zos.display)
        dispatch (Any): zDispatch instance (via zos.dispatch)
        navigation (Any): zNavigation instance (via zos.navigation)
        loader (Any): zLoader instance (via zos.loader)
        zfunc (Any): zFunc instance (via zos.zfunc)
        open (Any): zOpen instance (via zos.open)
        plugins (Dict[str, Any]): Plugin registry (via zos.loader.get_plugins_dict())
        logger (Any): Logger instance (inherited from zWizard via zConfig)
        block_context (Dict[str, Any]): Context for zBifrost (ephemeral state)
    
    Methods (ALL are pure orchestration):
        __init__(zos): Store subsystem references (NO logic)
        run(): Detect mode + delegate to zBifrost or zWizard (NO logic)
        _create_navigation_callbacks(): Return callback dict (pure delegation wrappers)
    
    Inheritance:
        Extends zWizard → inherits handle(), execute_loop(), _data resolution
    
    Orchestration Flow:
        run() → mode detection → delegate:
            - zBifrost mode: zos.bifrost.orchestrator.start(walker=self)
            - zCLI mode: self.execute_loop(items_dict, navigation_callbacks)
        
        Navigation callbacks → all delegate to subsystems:
            - on_continue: self.navigation.handle_zCrumbs(key, walker=self)
            - on_back: self.navigation.handle_zBack() + self.execute_loop()
            - on_exit: self.display.zDeclare() + return dict
            - on_stop: soft alias of on_exit (graceful, no sys.exit)
    
    Examples:
        >>> # zCLI mode (default)
        >>> walker = zWalker(zos)
        >>> walker.run()  # → delegates to zWizard.execute_loop
        
        >>> # zBifrost mode (WebSocket)
        >>> zos.session["zMode"] = "zBifrost"
        >>> walker = zWalker(zos)
        >>> walker.run()  # → delegates to bifrost.orchestrator.start
    
    Notes:
        - 100% orchestration - ZERO logic
        - Single file by design (pure orchestrator = minimal code)
        - NO local subsystem instances (ALL via zos)
        - If adding code, ask: "Should this be in a lower layer?" (answer: YES)
    """

    def __init__(self, zos: Any) -> None:
        """
        Initialize zWalker - PURE ORCHESTRATION (store references only).
        
        NO LOGIC - only stores subsystem references from zos instance.
        Extends zWizard parent to inherit block execution capabilities.
        
        **What this method does:**
        - Call super().__init__(zos, walker=self) to initialize zWizard parent
        - Store references to subsystems (self.zos, self.display, etc.)
        - Display ready message via zDisplay
        - Log initialization via zConfig logger
        
        **What this method does NOT do:**
        - NO logger configuration (zConfig already did it)
        - NO session initialization (zConfig already did it)
        - NO validation (not needed - subsystems are robust)
        - NO special setup (lower layers handle everything)
        
        Args:
            zos: zOS instance with ALL subsystems initialized
                  (display, dispatch, navigation, loader, session, bifrost, etc.)
        
        Returns:
            None
        
        Examples:
            >>> walker = zWalker(zos)
            # Output: "zWalker Ready" (via zDisplay)
            # Logger: "zWalker initialized"
            
        Notes:
            - Pure reference storage - NO logic
            - ALL subsystems accessed via zos (single source)
            - walker=self passed to zWizard allows callbacks to access walker context
            - Logger already configured by zConfig (DO NOT reconfigure)
        """
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # STEP 1: Initialize zWizard parent (inherit execution capabilities)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        super().__init__(zos=zos, walker=self)

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # STEP 2: Store subsystem references (NO logic, just references)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # ALL subsystems accessed via zos - NO local instances created
        self.zos: Any = zos
        self.zSpark_obj: Dict[str, Any] = zos.zspark_obj  # Boot config (zConfig)
        self.session: Dict[str, Any] = zos.session  # Session state (zConfig)
        self.display: Any = zos.display  # Output (zCLI + Bifrost)
        self.dispatch: Any = zos.dispatch  # Command routing (Single Source of Truth)
        self.navigation: Any = zos.navigation  # Breadcrumbs + menus + linking
        self.loader: Any = zos.loader  # Declarative file loading (zVaFiles: .zolo, .yaml, .json)
        self.zfunc: Any = zos.zfunc  # Function execution
        self.open: Any = zos.open  # File/URL opening
        self.plugins: Dict[str, Any] = zos.loader.get_plugins_dict()  # Plugin registry (migrated from zUtils v1.7.0)

        # Walker-specific ephemeral state (NOT configuration)
        self.block_context: Dict[str, Any] = {}  # For zBifrost message handler

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # STEP 3: Display ready message + log init (delegation to subsystems)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        self.display.zDeclare(MSG_WALKER_READY, color=COLOR_MAIN, indent=INDENT_NORMAL, style=STYLE_FULL)
        # Logger already configured by zConfig - NO reconfiguration needed
        self.logger.framework.debug(MSG_WALKER_INIT)

    def run(self) -> Dict[str, Any]:
        """
        Main entry point - PURE ORCHESTRATION (detect mode + delegate).
        
        NO LOGIC - only mode detection and delegation to subsystems.
        
        **Orchestration Flow:**
        1. Check session.get("zMode") via zConfig
        2. If "zBifrost" → delegate to bifrost.orchestrator.start()
        3. Else → load zVaFile via zLoader → delegate to zWizard.execute_loop()
        
        **What this method does:**
        - Mode detection (read from zConfig session)
        - zBifrost mode: asyncio.run(bifrost.orchestrator.start(walker=self))
        - zCLI mode: loader.handle() + execute_loop(navigation_callbacks)
        - Initialize empty breadcrumbs dict if not present
        
        **What this method does NOT do:**
        - NO block iteration (zWizard.execute_loop does it)
        - NO dispatch logic (zWizard uses zDispatch automatically)
        - NO _data resolution (zWizard handles it)
        - NO breadcrumb path construction (zNavigation via on_continue callback)
        - NO validation (subsystems are self-aware)
        
        Returns:
            Dict[str, Any]: Result dictionary:
                - zCLI mode: {"exit": "completed"} (from zWizard)
                - zBifrost mode: {} (server blocks indefinitely)
                - Error: {"error": "error message"}
        
        Notes:
            - 100% delegation - NO custom logic
            - zWizard.execute_loop inherited - NO override
            - navigation_callbacks are pure delegation wrappers
            - Empty dict init (line 428-429) is acceptable setup, NOT logic
        """
        try:
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            # ZBIFROST MODE: Delegate to zBifrost subsystem (NO custom logic)
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            if self.session.get(SESSION_KEY_ZMODE) == ZMODE_ZBIFROST:
                import asyncio
                self.logger.info(MSG_BIFROST_STARTING)
                # DELEGATION: zBifrost.orchestrator handles ALL WebSocket logic
                asyncio.run(self.zos.bifrost.orchestrator.start(
                    socket_ready=asyncio.Event(),
                    walker=self
                ))
                return {}  # Never reached (server blocks), but for type consistency

            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            # TERMINAL MODE: Load file + delegate to zWizard.execute_loop
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

            # Get zVaFile from zSpark (boot config managed by zConfig)
            zVaFile: Optional[str] = self.zSpark_obj.get(SESSION_KEY_ZVAFILE)
            if not zVaFile:
                self.logger.error(LOG_ERROR_NO_VAFILE)
                return {DICT_KEY_ERROR: ERROR_NO_VAFILE}

            # DELEGATION: zLoader handles ALL file loading (navbar injection, validation)
            raw_zFile: Optional[Dict[str, Any]] = self.loader.handle(None)
            if not raw_zFile:
                self.logger.error(LOG_ERROR_FAILED_LOAD, zVaFile)
                return {DICT_KEY_ERROR: f"{ERROR_FAILED_LOAD}: {zVaFile}"}

            # Initialize empty breadcrumbs dict (acceptable setup, not logic)
            # zNavigation handles ALL path construction and validation via callbacks
            if SESSION_KEY_ZCRUMBS not in self.session:
                self.session[SESSION_KEY_ZCRUMBS] = {}

            # DELEGATION: zDisplay handles message formatting and output
            self.display.zDeclare(MSG_WALKER_LOOP, color=COLOR_MAIN, indent=INDENT_NORMAL, style=STYLE_FULL)

            # Get block name from zSpark (if specified)
            # DELEGATION: zWizard.execute_loop handles block extraction internally
            block_name: Optional[str] = self.zSpark_obj.get(SESSION_KEY_ZBLOCK)

            # Seed the entry block's breadcrumb scope via the SSOT seeder so the
            # very first page owns a well-formed scope key ({folder}.{file}.{block})
            # instead of falling through to the empty "" scope. Without this, a
            # zBack raised after a zLink from the boot page tried to parse "" as a
            # crumb (→ "Invalid crumb format") and could not return. zNavigation is
            # the sole crumb authority; the walker only triggers the seed.
            if block_name:
                self.navigation.breadcrumbs.seed_scope(
                    walker=self,
                    folder=self.session.get(SESSION_KEY_ZVAFOLDER)
                    or self.zSpark_obj.get(SESSION_KEY_ZVAFOLDER, ""),
                    file=self.session.get(SESSION_KEY_ZVAFILE)
                    or self.zSpark_obj.get(SESSION_KEY_ZVAFILE, ""),
                    block=block_name,
                )

            # zLoom SSOT pre-render (DELEGATION): bind the file-root zSpool and
            # loop-expand the entry block BEFORE the first execute_loop — the SAME
            # seam navigation_linking runs for every subsequent hop. Without it a
            # spark booting directly into a data-bound leaf rendered empty (bindings
            # only resolved on navigation). Pure delegation: zLoom owns the binding
            # + loop logic; the walker only triggers it on the entry block.
            if block_name and isinstance(raw_zFile, dict) and isinstance(raw_zFile.get(block_name), dict):
                self.zos.zloom.prepare_block_render(raw_zFile, raw_zFile[block_name])

            # DELEGATION: zWizard.execute_loop handles ALL:
            # - Block extraction (if block_name provided)
            # - Block iteration + _data resolution
            # - RBAC enforcement
            # NO dispatch_fn provided - zWizard automatically uses walker.dispatch.handle
            # (Single Source of Truth: zDispatch for ALL command routing)
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            # NAVIGATION TRAMPOLINE (zCLI): keep the call stack flat.
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            # execute_loop runs one block to completion and returns either a
            # terminal result ({"exit": ...}, "$Block", None) OR the NAV_SIGNAL —
            # meaning a REPLACE hop staged its destination in session. Re-enter
            # execute_loop here with that destination instead of recursing inside
            # the handler, so an arbitrarily long navigation chain never grows the
            # Python stack. zBifrost never reaches this loop (its handlers keep the
            # direct call; each client hop is already a fresh top-level execute_loop).
            callbacks = self._create_navigation_callbacks()
            result = self.execute_loop(
                items_dict=raw_zFile,
                navigation_callbacks=callbacks,
                block_name=block_name
            )
            while result == NAV_SIGNAL:
                pending = self.session.pop(SESSION_KEY_PENDING_NAV, None)
                if not pending:
                    # Defensive: signal without a staged target — stop cleanly.
                    self.logger.warning("navigate signal with no pending target — halting trampoline")
                    break
                result = self.execute_loop(
                    items_dict=pending["items_dict"],
                    navigation_callbacks=callbacks,
                    start_key=pending.get("start_key"),
                    context=pending.get("context"),
                )
            return result

        except Exception as e:
            self.logger.error(LOG_ERROR_EXECUTION, e, exc_info=True)
            return {DICT_KEY_ERROR: str(e)}

    def navigate_or_recurse(
        self,
        items_dict: Dict[str, Any],
        start_key: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        navigation_callbacks: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """REPLACE-navigation entry point — trampoline in zCLI, direct in zBifrost.

        A REPLACE hop (zLink / zDelta / zBack / in-page zPsi) leaves the source
        block behind and renders ``items_dict``. In zCLI this used to recurse into
        ``execute_loop`` (one stack frame per hop → RecursionError after ~120
        navigations). Now it stages the destination in the session and returns
        ``NAV_SIGNAL``; the executor bubbles that up to run()'s trampoline, which
        re-enters ``execute_loop`` with a flat stack.

        zBifrost keeps the direct call: each client navigation is already a fresh
        top-level ``execute_loop`` (no nesting), so there is no stack to flatten and
        the chunked executor never sees ``NAV_SIGNAL``.
        """
        if self.session.get(SESSION_KEY_ZMODE) == ZMODE_ZBIFROST:
            return self.execute_loop(
                items_dict=items_dict,
                navigation_callbacks=navigation_callbacks or self._create_navigation_callbacks(),
                start_key=start_key,
                context=context,
            )
        self.session[SESSION_KEY_PENDING_NAV] = {
            "items_dict": items_dict,
            "start_key": start_key,
            "context": context,
        }
        return NAV_SIGNAL

    def _create_navigation_callbacks(self) -> Dict[str, Any]:
        """
        Create navigation callbacks - PURE DELEGATION WRAPPERS ONLY.
        
        NO LOGIC - returns dict of callback functions that ONLY delegate to subsystems.
        Each callback is a thin wrapper around subsystem method calls.
        
        **Callbacks (all are pure delegation):**
        - on_continue(result, key): → self.navigation.handle_zCrumbs(key, walker=self)
        - on_back(result): → self.navigation.handle_zBack() + self.execute_loop()
        - on_exit(result): → self.display.zDeclare() + return {"exit": "completed"}
        - on_stop(result): → soft alias of on_exit (graceful, no sys.exit)
        - on_get_trail(): → self.navigation.breadcrumbs.get_active_trail() (zBack ladder)
        - on_pop_trail(key): → self.navigation.breadcrumbs.pop_trail_to_before(key) (zBack ladder)
        
        **NO LOGIC ALLOWED:**
        - PROHIBITED: NO validation in callbacks
        - PROHIBITED: NO path construction in callbacks
        - PROHIBITED: NO dispatch logic in callbacks (zDispatch handles it via zWizard)
        - PROHIBITED: NO special case handling in callbacks
        
        Returns:
            Dict[str, Any]: Callback dictionary for zWizard.execute_loop
                Keys: "on_continue", "on_back", "on_exit", "on_stop",
                      "on_get_trail", "on_pop_trail"
                Values: Pure delegation wrapper functions
        
        Notes:
            - These callbacks are Walker's ONLY addition to zWizard
            - ALL callbacks are coordination wrappers - NO business logic
            - zNavigation is self-aware - NO validation needed in callbacks
        """
        def on_continue(result: Any, key: str) -> None:  # pylint: disable=unused-argument
            """Track breadcrumb - PURE DELEGATION to zNavigation."""
            # PROHIBITED: NO validation - zNavigation is self-aware
            # PROHIBITED: NO path construction - zNavigation handles it
            # REQUIRED: ONLY delegation - pure orchestration wrapper

            # Skip breadcrumb tracking for display directives (zCrumbs is a display event, not a navigation key)
            if key.lstrip('_') == 'zCrumbs':
                return

            self.navigation.handle_zCrumbs(key, walker=self)

        def on_back(result: Any) -> Any:  # pylint: disable=unused-argument
            """Handle zBack - PURE DELEGATION chain to zNavigation + zWizard."""
            # DELEGATION STEP 1: zNavigation.handle_zBack pops breadcrumb + loads file
            # (returns: block_dict, block_keys, start_key)
            back_result = self.navigation.handle_zBack(
                show_banner=False,
                walker=self
            )

            # Handle case where there's nowhere to go back to (standalone wizard)
            if back_result is None or (isinstance(back_result, tuple) and not back_result[0]):
                self.logger.debug("No parent context to navigate back to - treating as exit")
                return on_exit(result)

            # Unpack the tuple
            block_dict, _, start_key = back_result

            # DELEGATION STEP 2: re-execute the parent block. In zCLI this trampolines
            # (stage + NAV_SIGNAL) so a long back-chain never grows the stack; zBifrost
            # keeps the direct call. zDispatch remains the SSOT (no dispatch_fn).
            return self.navigate_or_recurse(
                items_dict=block_dict,
                start_key=start_key,
            )

        def on_exit(result: Any) -> Dict[str, Any]:  # pylint: disable=unused-argument
            """Handle soft exit - coordination wrapper (log + display + return)."""
            # Acceptable orchestration: log → display → return
            # NOT business logic - just coordination
            self.logger.debug(LOG_DEBUG_DISPATCH_EXIT)
            self.display.zDeclare(MSG_SESSION_COMPLETED, color=COLOR_MAIN, indent=INDENT_NORMAL, style=STYLE_MINIMAL)
            return {DICT_KEY_EXIT: DICT_VALUE_COMPLETED}

        def on_stop(result: Any) -> Dict[str, Any]:  # pylint: disable=unused-argument
            """Stop is RETIRED → soft graceful shutdown (aliases exit).

            zOS has ONE shutdown: the soft, graceful unwind. The old hard
            ``sys.exit()`` is gone — a stop signal now ends the session exactly
            like exit (DRY: delegates to on_exit). The only app-closers are
            ``exit`` and Ctrl+C, which share this one graceful path.
            """
            return on_exit(result)

        def on_get_trail() -> list:
            """Return active crumb trail — used by the zBack ladder to find parent menu."""
            return self.navigation.breadcrumbs.get_active_trail()

        def on_pop_trail(key: str) -> None:
            """Pop trail back to before key — called by the zBack ladder before jumping to parent menu."""
            self.navigation.breadcrumbs.pop_trail_to_before(key)

        return {
            "on_continue": on_continue,  # Track breadcrumbs after each step
            CALLBACK_ON_BACK: on_back,
            CALLBACK_ON_EXIT: on_exit,
            CALLBACK_ON_STOP: on_stop,
            "on_get_trail": on_get_trail,
            "on_pop_trail": on_pop_trail,
        }
