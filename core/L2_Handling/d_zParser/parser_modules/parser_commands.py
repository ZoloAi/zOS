# zOS/core/L2_Core/g_zParser/parser_modules/parser_commands.py

"""
BACKWARD COMPATIBILITY WRAPPER for parser_commands.py

⚠️ This file is now a thin wrapper for backward compatibility.
The actual implementation has been split into modular files:
    - commands/command_router.py: Main parse_command dispatcher (~160 LOC)
    - commands/command_utils.py: Shared utilities (~135 LOC)
    - commands/data_commands.py: Data operations (~105 LOC)
    - commands/function_commands.py: func, utils, plugin parsers (~145 LOC)
    - commands/session_commands.py: session, walker, test parsers (~150 LOC)
    - commands/file_commands.py: open, load, ls, cd, pwd parsers (~235 LOC)
    - commands/config_commands.py: export, config, persistence parsers (~245 LOC)
    - commands/system_commands.py: auth, comm parsers (~160 LOC)
    - commands/ui_commands.py: wizard, shortcut, where, help parsers (~215 LOC)

External Usage (CRITICAL):
    - zShell_executor.py (Week 6.9 - CRITICAL)
    - wizard_step_executor.py

Function signature remains stable for external compatibility:
    parse_command(command, logger) → Dict[str, Any]

Refactoring completed: Phase 4 - parser_commands.py split
    - 1419 LOC → 11 focused modules (< 250 LOC each)
    - Category modules: data, function, session, file, config, system, ui
    - Utilities: command_utils (split, extract)
    - Router: command_router (main parse_command dispatcher)

Version History:
    - v1.5.4 Week 6.8.7: Industry-grade upgrade
    - v1.5.5 Phase 4: Split into modular structure (this wrapper created)

See Also:
    - commands/ package: New modular implementation
    - shared/parser_constants.py: Centralized constants
"""

# Re-export from new modular structure for backward compatibility
from .commands import parse_command

__all__ = ['parse_command']
