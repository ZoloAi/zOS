# zOS/core/L2_Handling/g_zParser/parser_modules/commands/command_router.py

"""
Command routing for commands package.

Main parse_command dispatcher that routes commands to specialized parsers.

Public API:
    - parse_command: Main command parser (CRITICAL - used by zShell)

External Usage:
    - zShell_executor.py: Parse all shell commands
    - wizard_step_executor.py: Parse wizard step commands

Created: Phase 4.3 - Create Command Router from parser_commands.py
"""

from zOS import Any, Dict
from .command_utils import split_command

# Import all command parsers
from .data_commands import parse_data_command
from .function_commands import parse_func_command, parse_utils_command, parse_plugin_command
from .session_commands import parse_session_command, parse_walker_command, parse_test_command
from .file_commands import parse_open_command, parse_load_command, parse_ls_command, parse_cd_command, parse_pwd_command
from .config_commands import parse_export_command, parse_config_command
from .system_commands import parse_auth_command, parse_comm_command
from .ui_commands import parse_wizard_command, parse_shortcut_command, parse_where_command, parse_help_command

# Import constants
from ..shared.parser_constants import (
    _CMD_TYPE_DATA as CMD_TYPE_DATA,
    _CMD_TYPE_FUNC as CMD_TYPE_FUNC,
    _CMD_TYPE_UTILS as CMD_TYPE_UTILS,
    _CMD_TYPE_SESSION as CMD_TYPE_SESSION,
    _CMD_TYPE_WALKER as CMD_TYPE_WALKER,
    _CMD_TYPE_OPEN as CMD_TYPE_OPEN,
    _CMD_TYPE_TEST as CMD_TYPE_TEST,
    _CMD_TYPE_AUTH as CMD_TYPE_AUTH,
    _CMD_TYPE_EXPORT as CMD_TYPE_EXPORT,
    _CMD_TYPE_CONFIG as CMD_TYPE_CONFIG,
    _CMD_TYPE_LOAD as CMD_TYPE_LOAD,
    _CMD_TYPE_COMM as CMD_TYPE_COMM,
    _CMD_TYPE_WIZARD as CMD_TYPE_WIZARD,
    _CMD_TYPE_PLUGIN as CMD_TYPE_PLUGIN,
    _CMD_TYPE_LS as CMD_TYPE_LS,
    _CMD_TYPE_CD as CMD_TYPE_CD,
    _CMD_TYPE_CWD as CMD_TYPE_CWD,
    _CMD_TYPE_PWD as CMD_TYPE_PWD,
    _CMD_TYPE_SHORTCUT as CMD_TYPE_SHORTCUT,
    _CMD_TYPE_WHERE as CMD_TYPE_WHERE,
    _CMD_TYPE_HELP as CMD_TYPE_HELP,
    DICT_KEY_ERROR,
    ERROR_MSG_UNKNOWN_COMMAND,
    ERROR_MSG_EMPTY_COMMAND
)

# Build command router dictionary
COMMAND_ROUTER = {
    CMD_TYPE_DATA: parse_data_command,
    CMD_TYPE_FUNC: parse_func_command,
    CMD_TYPE_UTILS: parse_utils_command,
    CMD_TYPE_SESSION: parse_session_command,
    CMD_TYPE_WALKER: parse_walker_command,
    CMD_TYPE_OPEN: parse_open_command,
    CMD_TYPE_TEST: parse_test_command,
    CMD_TYPE_AUTH: parse_auth_command,
    CMD_TYPE_EXPORT: parse_export_command,
    CMD_TYPE_CONFIG: parse_config_command,
    CMD_TYPE_LOAD: parse_load_command,
    CMD_TYPE_COMM: parse_comm_command,
    CMD_TYPE_WIZARD: parse_wizard_command,
    CMD_TYPE_PLUGIN: parse_plugin_command,
    CMD_TYPE_LS: parse_ls_command,
    "list": parse_ls_command,  # Modern alias for ls (beginner-friendly)
    "dir": parse_ls_command,   # Windows alias for ls
    CMD_TYPE_CD: parse_cd_command,
    CMD_TYPE_CWD: parse_pwd_command,  # Primary: Current Working Directory
    CMD_TYPE_PWD: parse_pwd_command,  # Alias: Unix compatibility (Print Working Directory)
    CMD_TYPE_SHORTCUT: parse_shortcut_command,
    CMD_TYPE_WHERE: parse_where_command,
    CMD_TYPE_HELP: parse_help_command,
}


def parse_command(command: str, logger: Any) -> Dict[str, Any]:
    """
    Main command parser dispatcher.
    
    ⚠️ CRITICAL: This function is used externally by zShell for ALL shell command parsing.
    Signature must remain stable.
    
    Parses shell commands into structured dictionaries with type, action, args, and options.
    Routes commands to specialized parsers based on command type.
    
    Command Router Pattern:
        parse_command() → command_type → parse_*_command() → structured dict
    
    Supported Command Types (20 Total):
        data, func, utils, session, walker, open, test, auth, export, config,
        load, comm, wizard, plugin, ls, cd, cwd, pwd, shortcut, where, help
    
    Args:
        command: Raw command string (e.g., "data read users --limit 10")
        logger: Logger instance for diagnostic output
    
    Returns:
        Dict[str, Any]: Structured command dict or error dict
        
        Success Format:
            {{
                "type": str,              # Command type (e.g., "data", "func")
                "action": str,            # Action to perform (e.g., "read", "generate_id")
                "args": List[str],        # Positional arguments
                "options": Dict[str, Any] # Named options/flags
            }}
        
        Error Format:
            {{
                "error": str              # Error message describing what went wrong
            }}
    
    Examples:
        >>> logger = get_logger()
        
        # Data command
        >>> parse_command("data read users --limit 10", logger)
        {{'type': 'data', 'action': 'read', 'args': ['users'], 'options': {{'limit': '10'}}}}
        
        # Function command
        >>> parse_command("func generate_id zU", logger)
        {{'type': 'func', 'action': 'generate_id', 'args': ['zU'], 'options': {{}}}}
        
        # Session command
        >>> parse_command("session info", logger)
        {{'type': 'session', 'action': 'info', 'args': [], 'options': {{}}}}
        
        # Error case
        >>> parse_command("unknown_cmd", logger)
        {{'error': 'Unknown command: unknown_cmd'}}
    
    External Usage (CRITICAL):
        zShell_executor.py:
            parsed = self.zos.zparser.parse_command(command)
        Purpose: Parse all shell commands entered by user
        
        wizard_step_executor.py:
            parsed = zos.zparser.parse_command(step_value)
        Purpose: Parse shell commands within wizard steps
    
    Notes:
        - Signature stability is CRITICAL for external compatibility
        - Returns error dict {{"error": str}} for invalid commands
        - Handles quote-preserved command splitting
        - Logs command parsing for debugging
        - Empty commands return error dict
    
    See Also:
        - split_command: Quote-aware command string splitting
        - COMMAND_ROUTER: Dictionary mapping types to parsers
    """
    # Strip whitespace
    command = command.strip()

    # Empty command check
    if not command:
        logger.debug(ERROR_MSG_EMPTY_COMMAND)
        return {DICT_KEY_ERROR: ERROR_MSG_EMPTY_COMMAND}

    # Split command into parts (handles quotes)
    parts = split_command(command)

    # Get command type (first part)
    cmd_type = parts[0].lower()

    # Route to appropriate parser
    if cmd_type in COMMAND_ROUTER:
        parser_func = COMMAND_ROUTER[cmd_type]
        return parser_func(parts)

    # Unknown command
    logger.warning(ERROR_MSG_UNKNOWN_COMMAND.format(cmd_type))
    return {DICT_KEY_ERROR: ERROR_MSG_UNKNOWN_COMMAND.format(cmd_type)}
