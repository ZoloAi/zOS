# zOS/core/L3_Abstraction/p_zShell/shell_modules/__init__.py

"""
Shell Modules Package - Core REPL infrastructure components.

This package serves as the aggregator for Level 3 shell modules, providing
the core infrastructure for the zShell REPL (Read-Eval-Print Loop) system.
These modules form the foundation of zOS interactive shell mode (zCLI).

────────────────────────────────────────────────────────────────────────────────
ARCHITECTURE: REFACTORED MODULE PATTERN (v1.6.0)
────────────────────────────────────────────────────────────────────────────────

    ┌──────────────────────────────────────────────────────────────┐
    │               SHELL MODULES PACKAGE                          │
    ├──────────────────────────────────────────────────────────────┤
    │                                                              │
    │  Core Infrastructure (Level 3):                             │
    │                                                              │
    │    ┌─────────────────────────────────────────┐              │
    │    │  ShellRunner (shell_runner.py)          │              │
    │    │  - REPL loop management                 │              │
    │    │  - Command history (readline)           │              │
    │    │  - Dynamic prompts                      │              │
    │    │  - Special commands (exit, clear, tips) │              │
    │    └─────────────────────────────────────────┘              │
    │                      ↓                                       │
    │    ┌─────────────────────────────────────────┐              │
    │    │  CommandExecutor (shell_executor.py)    │              │
    │    │  - Command routing (18 types)           │ ────────┐    │
    │    │  - Delegates wizard to WizardCanvas     │         │    │
    │    └─────────────────────────────────────────┘         ↓    │
    │                                                              │
    │    ┌─────────────────────────────────────────┐              │
    │    │  WizardCanvasManager (wizard_canvas.py) │              │
    │    │  - Multi-step workflow builder          │              │
    │    │  - Buffer management (show/clear/run)   │              │
    │    │  - YAML/shell format detection          │              │
    │    └─────────────────────────────────────────┘              │
    │                      ↓                                       │
    │    ┌─────────────────────────────────────────┐              │
    │    │  HelpSystem (shell_help.py)             │              │
    │    │  - Command help display                 │              │
    │    │  - Welcome messages                     │              │
    │    │  - Quick tips                           │              │
    │    └─────────────────────────────────────────┘              │
    │                      ↓                                       │
    │              Command Executors (21 modules)                 │
    │                                                              │
    └──────────────────────────────────────────────────────────────┘

────────────────────────────────────────────────────────────────────────────────
CORE COMPONENTS
────────────────────────────────────────────────────────────────────────────────

**ShellRunner** (formerly InteractiveShell)
    - Purpose: REPL session manager
    - Responsibilities:
        • Main input loop (while running)
        • Readline history (~/.zolo/.zcli_history)
        • Dynamic prompt generation (normal/wizard/zPath)
        • Special commands (exit, quit, clear, tips)
        • Error handling (KeyboardInterrupt, EOFError)
    - Lines: 829
    - Key Features: Persistent history, wizard canvas aware, mode-agnostic

**CommandExecutor**
    - Purpose: Command routing with wizard delegation
    - Responsibilities:
        • Routes commands to specific executors (18 types)
        • Delegates wizard operations to WizardCanvasManager
        • Command type detection (data, func, config, etc.)
        • Single Responsibility: routing only
    - Lines: 238 (75% reduction from refactoring)
    - Key Features: O(1) command map, clean delegation, SRP compliant

**WizardCanvasManager** (NEW in v1.6.0)
    - Purpose: Interactive wizard canvas mode manager
    - Responsibilities:
        • Canvas lifecycle (start, stop, buffer management)
        • Multi-line workflow building (YAML or shell commands)
        • Format detection and conversion
        • Transaction support via zWizard delegation
    - Lines: 362
    - Key Features: Smart format detection, isolated responsibility

**HelpSystem**
    - Purpose: Help and documentation display
    - Responsibilities:
        • Welcome message generation
        • Command-specific help
        • Quick tips display
        • Walker launch integration
    - Lines: 368
    - Key Features: Dynamic help, walker-aware, graceful fallbacks

**executor_constants.py** (NEW in v1.6.0)
    - Purpose: Centralized constant definitions
    - Contents: Wizard commands, state keys, command types, messages
    - Lines: 131

**launch_shell()** - Utility function for launching shell from UI menu

────────────────────────────────────────────────────────────────────────────────
PACKAGE METADATA
────────────────────────────────────────────────────────────────────────────────

**Version:** 1.6.0
**Status:** REFACTORED - Full modernization with SRP compliance
**Total Components:** 6 (4 classes + 1 constants module + 1 utility function)
**Backward Compatibility:** InteractiveShell alias for ShellRunner (DEPRECATED)
**Lines (Total):** 1,928 lines (ShellRunner: 829, CommandExecutor: 238, 
                    WizardCanvas: 362, HelpSystem: 368, Constants: 131)

────────────────────────────────────────────────────────────────────────────────
USAGE
────────────────────────────────────────────────────────────────────────────────

**From zShell.py (Facade):**
    ```python
    from .shell_modules import ShellRunner, CommandExecutor, HelpSystem
    
    # Initialize shell components
    self.interactive = ShellRunner(zos)
    self.executor = CommandExecutor(zos)
    self.help_system = HelpSystem(display=self.display)
    
    # Run REPL
    self.interactive.run()
    ```

**Direct Launch from UI:**
    ```python
    from zOS.L3_Abstraction.p_zShell.shell_modules import launch_shell
    
    # Launch shell from menu
    launch_shell(zos)
    ```

**Backward Compatibility (DEPRECATED):**
    ```python
    from .shell_modules import InteractiveShell  # Old name
    
    # Still works, but use ShellRunner instead
    shell = InteractiveShell(zos)  # Redirects to ShellRunner
    ```

────────────────────────────────────────────────────────────────────────────────
REFACTORING NOTES (v1.6.0)
────────────────────────────────────────────────────────────────────────────────

**Full Modernization with SRP Compliance:**
    - Extracted WizardCanvasManager from CommandExecutor (75% size reduction)
    - Created executor_constants.py for centralized constants
    - CommandExecutor: 942 lines → 238 lines (routing only)
    - Single Responsibility Principle: Each class has one clear purpose
    - Improved testability: Wizard canvas can be tested independently
    - Maintained backward compatibility: All existing code works unchanged

**Deprecation (InteractiveShell → ShellRunner):**
    - Deprecated: v1.5.4, Removal: v1.7.0 (extended due to refactoring)
    - Reason: "Interactive" is redundant (all shells are interactive)
    - Migration: Replace `InteractiveShell` with `ShellRunner`
    - Backward Compatibility: Alias maintained until v1.7.0

────────────────────────────────────────────────────────────────────────────────
DEPENDENCIES
────────────────────────────────────────────────────────────────────────────────

**Internal:**
- shell_runner: ShellRunner, launch_shell
- shell_executor: CommandExecutor
- wizard_canvas: WizardCanvasManager (NEW in v1.6.0)
- executor_constants: Shared constants (NEW in v1.6.0)
- shell_help: HelpSystem
- commands/: 21 command executor modules (imported by CommandExecutor)

**External (zOS Framework):**
- zConfig: Session management, wizard mode state
- zDisplay: Mode-agnostic output (zCLI + Bifrost)
- zParser: Command parsing and zPath resolution
- zWizard: Wizard workflow execution with transaction support
- zLogger: Framework and application logging

────────────────────────────────────────────────────────────────────────────────
NOTES
────────────────────────────────────────────────────────────────────────────────

- v1.6.0: Full refactoring with SRP compliance (75% reduction in executor size)
- Total 1,928 lines of production code (down from 2,340 lines)
- 100% type hint coverage across all components
- Comprehensive docstrings optimized for clarity
- UI adapter pattern compliance (zCLI + Bifrost)
- Clean architecture: Single Responsibility Principle enforced
- File history: shell_interactive.py → shell_runner.py (v1.5.4)
- Class history: InteractiveShell → ShellRunner (v1.5.4)
- Architecture: Monolithic → Delegated (v1.6.0)
"""

from zOS import List

# ============================================================
# PACKAGE METADATA CONSTANTS
# ============================================================
PACKAGE_VERSION = "1.6.0"
PACKAGE_STATUS = "REFACTORED"
TOTAL_CORE_MODULES = 4
TOTAL_COMPONENTS = 6  # 4 classes + 1 constants module + 1 function
TOTAL_LINES = 1928  # ShellRunner(829) + CommandExecutor(238) + WizardCanvas(362) + HelpSystem(368) + Constants(131)

# ============================================================
# MODULE METRICS
# ============================================================
LINES_SHELL_RUNNER = 829
LINES_COMMAND_EXECUTOR = 238  # Reduced from 942 (75% reduction)
LINES_WIZARD_CANVAS = 362  # NEW in v1.6.0
LINES_HELP_SYSTEM = 368
LINES_CONSTANTS = 131  # NEW in v1.6.0

# ============================================================
# REFACTORING INFO (v1.6.0)
# ============================================================
REFACTORING_VERSION = "1.6.0"
REFACTORING_TYPE = "Single Responsibility Principle (SRP)"
EXECUTOR_REDUCTION = "75%"  # From 942 to 238 lines
TOTAL_REDUCTION = "18%"  # From 2340 to 1928 lines

# ============================================================
# DEPRECATION INFO
# ============================================================
DEPRECATED_CLASS_OLD = "InteractiveShell"
DEPRECATED_CLASS_NEW = "ShellRunner"
DEPRECATED_VERSION = "1.5.4"
REMOVAL_VERSION = "1.7.0"  # Extended due to refactoring
DEPRECATION_REASON = "Interactive is redundant (all shells are interactive)"

# ============================================================
# BACKWARD COMPATIBILITY
# ============================================================
BACKWARD_COMPAT_ENABLED = True

# ============================================================
# IMPORT CORE MODULES (LEVEL 3)
# ============================================================

# REPL Session Manager
from .shell_runner import ShellRunner, launch_shell

# Command Router
from .shell_executor import CommandExecutor

# Wizard Canvas Manager
from .wizard_canvas import WizardCanvasManager

# Help System
from .shell_help import HelpSystem

# Shared Constants
from .executor_constants import (
    WIZARD_CMD_START, WIZARD_CMD_STOP, WIZARD_CMD_RUN, 
    WIZARD_CMD_SHOW, WIZARD_CMD_CLEAR
)

# ============================================================
# BACKWARD COMPATIBILITY ALIAS
# ============================================================
# DEPRECATED in v1.5.4, removal planned for v1.6.0
# Use ShellRunner instead
InteractiveShell = ShellRunner

# ============================================================
# PUBLIC API
# ============================================================
__all__: List[str] = [
    # Core Components
    "ShellRunner",
    "CommandExecutor",
    "WizardCanvasManager",
    "HelpSystem",
    "launch_shell",
    
    # Constants
    "WIZARD_CMD_START",
    "WIZARD_CMD_STOP",
    "WIZARD_CMD_RUN",
    "WIZARD_CMD_SHOW",
    "WIZARD_CMD_CLEAR",
    
    # Backward Compatibility (DEPRECATED)
    "InteractiveShell",  # Alias for ShellRunner, removal v1.6.0
]
