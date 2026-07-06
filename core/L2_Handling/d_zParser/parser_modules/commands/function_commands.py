# zOS/core/L2_Handling/g_zParser/parser_modules/commands/function_commands.py

"""
Function-related command parsing for commands package.

Parses func, utils, and plugin command types.

Public API:
    - parse_func_command: Parse func invocations
    - parse_utils_command: Parse utility function calls
    - parse_plugin_command: Parse plugin operations

Created: Phase 4.2 - Extract Command Categories from parser_commands.py
"""

from zOS import Any, Dict, List

# Import constants
from ..shared.parser_constants import (
    _CMD_TYPE_FUNC as CMD_TYPE_FUNC,
    _CMD_TYPE_UTILS as CMD_TYPE_UTILS,
    _CMD_TYPE_PLUGIN as CMD_TYPE_PLUGIN,
    DICT_KEY_ERROR,
    DICT_KEY_TYPE,
    DICT_KEY_ACTION,
    DICT_KEY_ARGS,
    DICT_KEY_OPTIONS,
    ERROR_MSG_FUNC_NO_NAME,
    ERROR_MSG_UTILS_NO_NAME,
    ERROR_MSG_PLUGIN_NO_SUBCOMMAND,
    MIN_PARTS_SIMPLE_PARSER,
    SLICE_START_ARGS
)


def parse_func_command(parts: List[str]) -> Dict[str, Any]:
    """
    Parse function commands like 'func generate_id zU'.
    
    Function commands invoke zFunc functions with positional arguments.
    
    Args:
        parts: Command parts (e.g., ['func', 'generate_id', 'zU'])
    
    Returns:
        Dict[str, Any]: Structured command dict or error dict
    
    Examples:
        >>> parse_func_command(['func', 'generate_id', 'zU'])
        {{'type': 'func', 'action': 'generate_id', 'args': ['zU'], 'options': {{}}}}
        
        >>> parse_func_command(['func', 'hash_password', 'secret123'])
        {{'type': 'func', 'action': 'hash_password', 'args': ['secret123'], 'options': {{}}}}
    """
    if len(parts) < MIN_PARTS_SIMPLE_PARSER:
        return {DICT_KEY_ERROR: ERROR_MSG_FUNC_NO_NAME}

    func_name = parts[1]
    args = parts[SLICE_START_ARGS:] if len(parts) > SLICE_START_ARGS else []

    return {
        DICT_KEY_TYPE: CMD_TYPE_FUNC,
        DICT_KEY_ACTION: func_name,
        DICT_KEY_ARGS: args,
        DICT_KEY_OPTIONS: {}
    }


def parse_utils_command(parts: List[str]) -> Dict[str, Any]:
    """
    Parse utility commands like 'utils hash_password mypass'.
    
    Utility commands invoke utility functions with positional arguments.
    
    Args:
        parts: Command parts (e.g., ['utils', 'hash_password', 'mypass'])
    
    Returns:
        Dict[str, Any]: Structured command dict or error dict
    
    Examples:
        >>> parse_utils_command(['utils', 'hash_password', 'secret'])
        {{'type': 'utils', 'action': 'hash_password', 'args': ['secret'], 'options': {{}}}}
    """
    if len(parts) < MIN_PARTS_SIMPLE_PARSER:
        return {DICT_KEY_ERROR: ERROR_MSG_UTILS_NO_NAME}

    util_name = parts[1]
    args = parts[SLICE_START_ARGS:] if len(parts) > SLICE_START_ARGS else []

    return {
        DICT_KEY_TYPE: CMD_TYPE_UTILS,
        DICT_KEY_ACTION: util_name,
        DICT_KEY_ARGS: args,
        DICT_KEY_OPTIONS: {}
    }


def parse_plugin_command(parts: List[str]) -> Dict[str, Any]:
    """
    Parse plugin commands like 'plugin exec', 'plugin load', or 'plugin show'.
    
    Plugin commands handle both plugin execution (exec/run) and plugin cache
    management (load/show/clear/reload).
    
    Args:
        parts: Command parts (e.g., ['plugin', 'exec', 'hash_password', 'arg1'])
    
    Returns:
        Dict[str, Any]: Structured command dict or error dict
    
    Examples:
        >>> parse_plugin_command(['plugin', 'exec', 'hash_password', 'mypass'])
        {{'type': 'plugin', 'action': 'exec', 'args': ['hash_password', 'mypass'], 'options': {{}}}}
        
        >>> parse_plugin_command(['plugin', 'load', '@.utils.my_plugin'])
        {{'type': 'plugin', 'action': 'load', 'args': ['@.utils.my_plugin'], 'options': {{}}}}
        
        >>> parse_plugin_command(['plugin', 'show'])
        {{'type': 'plugin', 'action': 'show', 'args': [], 'options': {{}}}}
    """
    if len(parts) < MIN_PARTS_SIMPLE_PARSER:
        return {DICT_KEY_ERROR: ERROR_MSG_PLUGIN_NO_SUBCOMMAND}

    action = parts[1]
    args = parts[SLICE_START_ARGS:] if len(parts) > SLICE_START_ARGS else []

    return {
        DICT_KEY_TYPE: CMD_TYPE_PLUGIN,
        DICT_KEY_ACTION: action,
        DICT_KEY_ARGS: args,
        DICT_KEY_OPTIONS: {}
    }
