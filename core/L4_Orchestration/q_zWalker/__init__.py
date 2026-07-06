# zOS/core/L4_Orchestration/q_zWalker/__init__.py

"""
zWalker Package - Orchestration & Navigation Engine for Declarative UI/Menu systems.

This package provides the top-level orchestration layer for zOS's interactive UI mode,
coordinating navigation, menu rendering, breadcrumb tracking, and dual-mode execution
(zCLI and zBifrost WebSocket).

Processes zVaFiles (zVacuumFiles): Declarative UI definitions in .zolo, .yaml, or .json format.

────────────────────────────────────────────────────────────────────────────────
ARCHITECTURE: PURE ORCHESTRATOR
────────────────────────────────────────────────────────────────────────────────

zWalker is a single-file orchestrator that delegates all operations to subsystems:

    ┌──────────────────────────────────────────────────────────────┐
    │                  ZWALKER PACKAGE                             │
    ├──────────────────────────────────────────────────────────────┤
    │                                                              │
    │  Files (1):                                                  │
    │      zWalker.py - Main orchestrator                          │
    │                                                              │
    │  Delegates to subsystems (all via zos instance):             │
    │      • zWizard: Loop engine (via inheritance)               │
    │      • zNavigation: Breadcrumbs, menus, linking             │
    │      • zDisplay: Mode-agnostic output                       │
    │      • zDispatch: Command routing                           │
    │      • zLoader: Declarative file loading + plugin registry   │
    │      • zConfig: Session management                          │
    │      • zComm: WebSocket server (zBifrost)                   │
    │      • zFunc: Function execution                            │
    │      • zOpen: File/URL opening                              │
    │      • zAuth: Authentication (indirect)                     │
    │                                                              │
    └──────────────────────────────────────────────────────────────┘

────────────────────────────────────────────────────────────────────────────────
ORCHESTRATION PATTERN
────────────────────────────────────────────────────────────────────────────────

**Delegation Map:**
    • run() → Detects mode → zCLI or zBifrost
    • zBlock_loop() → execute_loop() (zWizard) + navigation callbacks
    • Navigation → zNavigation.handle_zCrumbs(), handle_zBack()
    • Display → zDisplay.zDeclare() (mode-agnostic)
    • Dispatch → zDispatch.handle() (command routing)
    • Session → zConfig session dict (zMode, zCrumbs, zBlock)

**No Local Instances:**
    - All subsystems accessed via zos instance
    - No local configuration or state (pure orchestrator)
    - Single file design (no submodules needed)

────────────────────────────────────────────────────────────────────────────────
DUAL-MODE SUPPORT
────────────────────────────────────────────────────────────────────────────────

**zCLI Mode (Default):**
    - Traditional CLI menu navigation
    - Readline-based input with history
    - ASCII-formatted display
    - Synchronous execution

**zBifrost Mode (WebSocket):**
    - WebSocket-based client-server
    - JSON message protocol
    - HTML-formatted display
    - Asynchronous execution via asyncio

────────────────────────────────────────────────────────────────────────────────
PUBLIC API
────────────────────────────────────────────────────────────────────────────────

**Class: zWalker**
    - Purpose: Orchestration & navigation engine
    - Methods: run(), zBlock_loop()
    - Inheritance: Extends zWizard for loop engine

────────────────────────────────────────────────────────────────────────────────
USAGE
────────────────────────────────────────────────────────────────────────────────

**zCLI Mode:**
    ```python
    from zOS.L4_Orchestration.q_zWalker import zWalker
    
    # Initialize walker
    walker = zWalker(zos)
    
    # Run terminal-based navigation
    walker.run()
    # [User navigates menus, exits with zBack or exit action]
    ```

**zBifrost Mode (WebSocket):**
    ```python
    from zOS.L4_Orchestration.q_zWalker import zWalker
    
    # Set mode before walker initialization
    zos.session["zMode"] = "zBifrost"
    
    # Initialize walker
    walker = zWalker(zos)
    
    # Start WebSocket server
    walker.run()
    # [WebSocket server starts, waits for client connections]
    ```

**From zShell:**
    ```bash
    # User types in zShell:
    launch @.zUI.main_menu
    
    # zShell creates walker and calls run()
    # [Walker starts, user navigates menus]
    ```

────────────────────────────────────────────────────────────────────────────────
DEPENDENCIES
────────────────────────────────────────────────────────────────────────────────

**Internal:**
    - zWalker.py: Main orchestrator

**External (ALL from zos instance):**
    - zWizard: Loop engine (parent class)
    - zNavigation: Navigation system
    - zDisplay: Mode-agnostic output
    - zDispatch: Command routing
    - zLoader: Declarative file loading (zVaFiles) + plugin registry
    - zConfig: Session management
    - zComm: Communication services
    - zFunc: Function execution
    - zOpen: File/URL opening

────────────────────────────────────────────────────────────────────────────────
NOTES
────────────────────────────────────────────────────────────────────────────────

- Pure orchestrator - no local subsystem instances
- Single file design (no modular breakdown needed)
- All navigation logic centralized in zNavigation (Week 6.7)
- All display logic via mode-agnostic zDisplay (Week 6.4)
- Loop engine inherited from zWizard (Week 6.14)
- Session state managed via zConfig (Week 6.2)
- Dual-mode support (zCLI + zBifrost)
"""

from zOS import List
from zOS.L1_Foundation.a_zConfig.zConfig_modules import (  # type: ignore[import-untyped]
    ZMODE_ZCLI,
    ZMODE_ZBIFROST,
)
from .zWalker import zWalker

# ============================================================
# PACKAGE METADATA
# ============================================================
PACKAGE_VERSION = "1.5.4"
SUBSYSTEM_NAME = "zWalker"
TOTAL_FILES = 1

# ============================================================
# ARCHITECTURE METADATA
# ============================================================
ARCHITECTURE_PATTERN = "PURE_ORCHESTRATOR"
MODULAR_DESIGN = False
SINGLE_FILE = True

# ============================================================
# SUBSYSTEM DEPENDENCIES (all accessed via the zos instance)
# ============================================================
DEPENDENCIES = [
    "zWizard",      # Loop engine (via inheritance)
    "zNavigation",  # Breadcrumbs, menus, linking
    "zDisplay",     # Mode-agnostic output
    "zDispatch",    # Command routing
    "zLoader",      # Declarative file loading (zVaFiles) + plugin registry
    "zConfig",      # Session management
    "zComm",        # WebSocket server (zBifrost)
    "zFunc",        # Function execution
    "zOpen",        # File/URL opening
    "zAuth",        # Authentication (indirect)
]
DEPENDENCY_COUNT = len(DEPENDENCIES)

# ============================================================
# DUAL-MODE SUPPORT (mode literals: see zVocabulary ZMODE_*)
# ============================================================
SUPPORTED_MODES = [ZMODE_ZCLI, ZMODE_ZBIFROST]

# ============================================================
# PUBLIC API
# ============================================================
__all__: List[str] = [
    "zWalker"
]
