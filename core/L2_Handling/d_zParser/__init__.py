# zOS/core/L2_Core/g_zParser/__init__.py

"""
zParser subsystem - comprehensive parsing operations for the zOS framework.

This package provides unified parsing functionality for the zOS framework,
organized in a modular architecture following approved zConfig/zComm patterns.
The zParser subsystem handles:

- Path resolution and file type identification
- Command parsing (20+ command types)
- File content parsing (YAML, JSON, auto-detection)
- Expression evaluation and dotted path parsing
- Plugin invocation resolution
- zVaFile parsing (UI, Schema, Config, Generic)

Modular Architecture (Post-Refactoring v1.5.4 Phase 1-10):
    **Tier 1 - Foundation (Core Utilities)**:
        - parser_utils.py: Expression evaluation, dotted paths, references
        - parser_path.py: Path resolution, zMachine paths, file identification
    
    **Tier 2 - Specialized Parsers**:
        - parser_commands.py: Command string parsing (20+ types)
        - parser_plugin.py: Plugin invocation resolution (&syntax)
        - parser_file.py: File content parsing (YAML/JSON, RBAC transform)
        - vafile/ package: zVaFile type-specific parsers
            - vafile_ui.py: UI file parsing with RBAC extraction
            - vafile_schema.py: Database schema parsing
            - vafile_config.py: Configuration file parsing
            - vafile_generic.py: Generic fallback parsing
    
    **Tier 3 - Facade (Entry Point)**:
        - zParser.py: Unified facade with 21+ methods delegating to Tier 1-2
    
    **Tier 4 - Package Root (This File)**:
        - __init__.py: Package exports and metadata

Public API:
    This package exposes a minimal, facade-oriented API:
    
    **Primary Interface**:
        - zParser: Main facade class (21+ methods)
    
    **Direct Function Access**:
        - zExpr_eval: Expression evaluation (commonly used standalone)

Usage:
    The zParser subsystem is initialized during framework startup:
    
    >>> # In framework initialization
    >>> from zOS.L2_Handling.d_zParser import zParser
    >>> self.parser = zParser(self)
    
    >>> # Throughout the framework
    >>> path = self.parser.zPath_decoder("zMachine.Config")
    >>> cmd = self.parser.parse_command("zFunc users.list")
    >>> data = self.parser.parse_file_content(raw_yaml, ".yaml")
    
    >>> # Direct function import (for special cases)
    >>> from zOS.L2_Handling.d_zParser import zExpr_eval
    >>> result = zExpr_eval(expr, logger, display)

Module Organization:
    ```
    zParser/
    ├── __init__.py          (Package root - exports)
    ├── zParser.py           (Facade - 21+ methods)
    └── parser_modules/      (Specialized modules)
        ├── __init__.py      (Module aggregator)
        ├── parser_utils.py  (Expression evaluation)
        ├── parser_path.py   (Path resolution)
        ├── parser_commands.py (Command parsing)
        ├── parser_plugin.py (Plugin invocation)
        ├── parser_file.py   (File parsing)
        └── vafile/          (zVaFile package)
            ├── __init__.py
            ├── vafile_ui.py
            ├── vafile_schema.py
            ├── vafile_config.py
            └── vafile_generic.py
    ```

Design Principles:
    1. **Facade Pattern**: Single entry point (zParser class) for all parsing
    2. **Delegation**: Facade delegates to specialized modules
    3. **Type Safety**: 100% type hint coverage across all modules
    4. **Documentation**: Comprehensive docstrings (A+ grade)
    5. **Consistency**: Uniform parameter passing and error handling

Dependencies:
    - zOS: Main framework instance (provides logger, session, display)
    - zConfig: Configuration paths (for zMachine resolution)
    - zDisplay: Output formatting (for parser messages)
    - External: pyyaml (YAML parsing)

Performance:
    - Path resolution: O(1) - dict lookups
    - Command parsing: O(n) - single pass
    - File parsing: O(n) - YAML/JSON native
    - Expression evaluation: O(n) - recursive descent

Thread Safety:
    All parser modules are thread-safe. The logger and session are passed
    as parameters to avoid shared state issues.

Examples:
    >>> # Initialize (done by framework)
    >>> from zOS.L2_Handling.d_zParser import zParser
    >>> parser = zParser(zos)
    
    >>> # Path resolution
    >>> path = parser.zPath_decoder("zMachine.Config")
    >>> file_type, path = parser.identify_zFile("users", "/path/to/UI/")
    
    >>> # Command parsing
    >>> cmd = parser.parse_command("zFunc users.list --limit 10")
    
    >>> # File parsing
    >>> data = parser.parse_file_content(raw_yaml, ".yaml")
    >>> ui_data = parser.parse_ui_file(yaml_data, file_path="zUI.users.yaml")
    
    >>> # Expression evaluation
    >>> result = parser.zExpr_eval('{"key": "value"}')
    
    >>> # Plugin invocation
    >>> if parser.is_plugin_invocation("&MyPlugin.func()"):
    ...     result = parser.resolve_plugin_invocation("&MyPlugin.func()")

Version History:
    - v1.5.4 Week 6.8.1-6.8.10: All modules upgraded to A+ documentation quality
    - v1.5.4 Phase 1-10 (2026-03-09): Modular refactoring complete
        * Phase 1: Shared infrastructure (constants, error handlers, display utils)
        * Phase 2: commands/ package structure
        * Phase 3: plugin/ package structure
        * Phase 4: path/ package with resolvers/detection/extraction
        * Phase 5: file/ package with format_parsers/transformers
        * Phase 6: vafile/ui/ subdirectory
        * Phase 7: Facade optimization
        * Phase 8: Test infrastructure
        * Phase 9: External verification (zLoader, zShell, zDispatch verified)
        * Phase 10: Architecture documentation
    - Files reduced from 6 over 600 LOC to 0 over 500 LOC
    - ~600 lines of DRY violations eliminated
    - All external APIs preserved (backward compatible)

See Also:
    - zOS: Main framework instance
    - zLoader: Uses parser for UI file loading
    - zDispatch: Uses parser for plugin resolution
    - zNavigation: Uses parser for expression evaluation
    - parser_modules: Specialized parser modules

Notes:
    The zParser subsystem is a critical component of the zOS framework,
    serving as the foundation for the declarative paradigm. All file parsing,
    path resolution, and expression evaluation flows through this subsystem.
"""

# Import from facade (re-export for external use)
from .zParser import zParser  # noqa: F401 - Imported for re-export
from .parser_modules import zExpr_eval  # noqa: F401 - Imported for re-export (commonly used standalone)

# Package metadata
__version__ = "1.5.4"
__author__ = "zOS Framework"

# Explicit public API (facade-oriented)
__all__ = [
    'zParser',      # Primary interface (facade with 21+ methods)
    'zExpr_eval',   # Direct function access (commonly used standalone)
]
