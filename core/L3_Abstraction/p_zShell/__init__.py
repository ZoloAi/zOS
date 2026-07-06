# zOS/core/L3_Abstraction/p_zShell/__init__.py

"""
zShell Subsystem - Interactive REPL shell for zCLI framework.

This subsystem provides a comprehensive interactive shell environment with REPL
(Read-Eval-Print Loop) capabilities, command routing, history management, and
wizard canvas mode for multi-step workflows.

────────────────────────────────────────────────────────────────────────────────
ARCHITECTURE: 6-LAYER HIERARCHY (BOTTOM-UP)
────────────────────────────────────────────────────────────────────────────────

    ┌──────────────────────────────────────────────────────────────┐
    │                    ZSHELL SUBSYSTEM                          │
    ├──────────────────────────────────────────────────────────────┤
    │                                                              │
    │  LEVEL 6: Package Root (__init__.py)                        │
    │      └─→ Exports: zShell, launch_shell                       │
    │                                                              │
    │  LEVEL 5: Facade (zShell.py)                                │
    │      └─→ Simple 3-method API hiding the core modules        │
    │                                                              │
    │  LEVEL 4: Module Aggregator (shell_modules/__init__.py)    │
    │      └─→ Exports: ShellRunner, CommandExecutor, HelpSystem │
    │                                                              │
    │  LEVEL 3: Core Modules                                      │
    │      ├─→ ShellRunner    • REPL loop, history, prompts       │
    │      ├─→ CommandExecutor • Command routing, wizard canvas   │
    │      └─→ HelpSystem      • Welcome, tips, help display       │
    │                                                              │
    │  LEVEL 2: Command Registry (commands/__init__.py)           │
    │      └─→ Exports the command executors                       │
    │                                                              │
    │  LEVEL 1: Command Executors (commands/shell_cmd_*.py)       │
    │      ├─→ Group A: Terminal   - where, cd, ls, help, …        │
    │      ├─→ Group B: zLoader    - load, data                    │
    │      ├─→ Group C: Subsystems - auth, config, comm, …         │
    │      └─→ Group D: Advanced   - export, utils                 │
    │                                                              │
    └──────────────────────────────────────────────────────────────┘

NOTE: Exact file/line/test counts are intentionally omitted here — they drift
the moment code changes. Derive such stats from the tree/CI, not the docstring.

────────────────────────────────────────────────────────────────────────────────
PUBLIC API
────────────────────────────────────────────────────────────────────────────────

**Class: zShell**
    - Purpose: Facade for zShell subsystem
    - Methods: 3 (run_shell, execute_command, show_help)
    - Usage: Primary entry point for shell functionality
    - Delegates to: ShellRunner, CommandExecutor, HelpSystem

**Function: launch_shell(zos)**
    - Purpose: Launch interactive shell from UI menu
    - Usage: Walker mode integration
    - Returns: Status message

────────────────────────────────────────────────────────────────────────────────
USAGE EXAMPLES
────────────────────────────────────────────────────────────────────────────────

**Basic Shell Usage:**
    ```python
    from zOS.L3_Abstraction.p_zShell import zShell

    # Initialize shell
    shell = zShell(zcli)
    
    # Run REPL loop
    shell.run_shell()
    # User interacts: types commands, exits with 'exit' or Ctrl+C
    ```

**Single Command Execution (Testing):**
    ```python
    from zOS.L3_Abstraction.p_zShell import zShell

    shell = zShell(zcli)
    result = shell.execute_command("data read users")
    ```

**UI Menu Integration:**
    ```python
    from zOS.L3_Abstraction.p_zShell import launch_shell

    # Launch from Walker menu
    status = launch_shell(zos)
    # Returns: "Returned from zCLI shell"
    ```

────────────────────────────────────────────────────────────────────────────────
KEY FEATURES
────────────────────────────────────────────────────────────────────────────────

**REPL Capabilities:**
    • Interactive command-line interface
    • Persistent command history (~/.zolo/.zcli_history)
    • Up/down arrow navigation via readline
    • Dynamic prompts (normal, wizard canvas, zPath display)
    • Special commands (exit, quit, clear, tips)

**Command Routing:**
    • 18 command types (data, func, config, auth, comm, etc.)
    • Automatic type detection and delegation
    • Error handling and logging
    • Mode-agnostic output (zCLI + Bifrost)

**Wizard Canvas Mode:**
    • Multi-step workflow builder
    • YAML or shell command format
    • Transaction support via zWizard
    • Buffer management (show, clear, run, stop)

**Integration:**
    • All zCLI subsystems (zAuth, zConfig, zData, zFunc, etc.)
    • UI mode (Walker) via launch_shell()
    • zCLI mode via run_shell()
    • Bifrost mode (WebSocket) via zDisplay

────────────────────────────────────────────────────────────────────────────────
DEPENDENCIES
────────────────────────────────────────────────────────────────────────────────

**Internal:**
    - zShell.py: Facade class (Level 5)
    - shell_modules/: Core infrastructure (Level 3)
    - commands/: Command executors (Level 1)

**External Subsystems:**
    - zDisplay: Mode-agnostic output
    - zParser: Command parsing
    - zConfig: Session management
    - zAuth: Authentication
    - zData: Database operations
    - zFunc: Function execution
    - zComm: Communication services
    - zLoader: Resource loading
    - zWizard: Workflow management

────────────────────────────────────────────────────────────────────────────────
NOTES
────────────────────────────────────────────────────────────────────────────────

- Package follows the 6-layer bottom-up architecture above
- Facade pattern hides complexity from consumers
- Consistent with other zCLI subsystem packages
- zShell is still expanding toward beta (more terminal commands/features planned)
"""

from zOS import List
from .zShell import zShell, launch_shell  # noqa: F401

# ============================================================
# PACKAGE METADATA
# ============================================================
# NOTE: file/line/test counts are intentionally NOT hardcoded here — they
# drift the moment code changes (they were stale by thousands of lines). Derive
# such stats from the tree/CI, not from hand-maintained constants.
SUBSYSTEM_NAME = "zShell"

# ============================================================
# PUBLIC API
# ============================================================
__all__: List[str] = [
    "zShell",
    "launch_shell"
]
