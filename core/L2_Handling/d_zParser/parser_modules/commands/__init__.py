# zOS/core/L2_Handling/g_zParser/parser_modules/commands/__init__.py

"""
Command parsing package for zParser subsystem.

Provides comprehensive shell command parsing for 20+ command types with
structured argument and option extraction.

Package Structure:
    - command_router.py: Main parse_command dispatcher (~160 LOC)
    - command_utils.py: Shared utilities (~135 LOC)
    - data_commands.py: Data operations (~105 LOC)
    - function_commands.py: func, utils, plugin parsers (~145 LOC)
    - session_commands.py: session, walker, test parsers (~150 LOC)
    - file_commands.py: open, load, ls, cd, pwd parsers (~235 LOC)
    - config_commands.py: export, config, persistence parsers (~245 LOC)
    - system_commands.py: auth, comm parsers (~160 LOC)
    - ui_commands.py: wizard, shortcut, where, help parsers (~215 LOC)

Public API:
    - parse_command: Main command parser (CRITICAL - used by zShell)

External Usage:
    - zShell_executor.py: Parse all shell commands
    - wizard_step_executor.py: Parse wizard step commands

Signature Stability:
    parse_command(command, logger) must remain stable.

Created: Phase 2 - Establish Commands Package Structure
Updated: Phase 4.5 - Complete modular implementation
"""

from .command_router import parse_command

__all__ = ['parse_command']
