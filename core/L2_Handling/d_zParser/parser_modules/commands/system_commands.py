# zOS/core/L2_Handling/g_zParser/parser_modules/commands/system_commands.py

"""
System service command parsing for commands package.

Parses auth and comm command types.

Public API:
    - parse_auth_command: Parse authentication operations
    - parse_comm_command: Parse communication service operations

Created: Phase 4.2 - Extract Command Categories from parser_commands.py
"""

from zOS import Any, Dict, List
from .command_utils import extract_args_and_options

# Import constants
from ..shared.parser_constants import (
    _CMD_TYPE_AUTH as CMD_TYPE_AUTH,
    _CMD_TYPE_COMM as CMD_TYPE_COMM,
    DICT_KEY_ERROR,
    DICT_KEY_TYPE,
    DICT_KEY_ACTION,
    DICT_KEY_ARGS,
    DICT_KEY_OPTIONS,
    ERROR_MSG_AUTH_NO_ACTION,
    ERROR_MSG_AUTH_INVALID_ACTION,
    ERROR_MSG_COMM_NO_ACTION,
    ERROR_MSG_COMM_INVALID_ACTION,
    MIN_PARTS_SIMPLE_PARSER,
    SLICE_START_ARGS
)

# Auth actions
ACTION_AUTH_LOGIN = "login"
ACTION_AUTH_LOGOUT = "logout"
ACTION_AUTH_STATUS = "status"

VALID_AUTH_ACTIONS = [
    ACTION_AUTH_LOGIN,
    ACTION_AUTH_LOGOUT,
    ACTION_AUTH_STATUS
]

# Comm actions
ACTION_COMM_START = "start"
ACTION_COMM_STOP = "stop"
ACTION_COMM_STATUS = "status"
ACTION_COMM_RESTART = "restart"
ACTION_COMM_INFO = "info"
ACTION_COMM_INSTALL = "install"

VALID_COMM_ACTIONS = [
    ACTION_COMM_START,
    ACTION_COMM_STOP,
    ACTION_COMM_STATUS,
    ACTION_COMM_RESTART,
    ACTION_COMM_INFO,
    ACTION_COMM_INSTALL
]


def parse_auth_command(parts: List[str]) -> Dict[str, Any]:
    """
    Parse auth commands like 'auth login', 'auth logout', 'auth status'.
    
    Auth commands manage authentication state. Validates action against VALID_AUTH_ACTIONS.
    
    Args:
        parts: Command parts (e.g., ['auth', 'login', 'admin'])
    
    Returns:
        Dict[str, Any]: Structured command dict or error dict
    
    Examples:
        >>> parse_auth_command(['auth', 'login', 'admin'])
        {{'type': 'auth', 'action': 'login', 'args': ['admin'], 'options': {{}}}}
        
        >>> parse_auth_command(['auth', 'logout'])
        {{'type': 'auth', 'action': 'logout', 'args': [], 'options': {{}}}}
        
        >>> parse_auth_command(['auth', 'invalid'])
        {{'error': 'Invalid auth action: invalid. Use: login, logout, status'}}
    """
    if len(parts) < MIN_PARTS_SIMPLE_PARSER:
        return {DICT_KEY_ERROR: ERROR_MSG_AUTH_NO_ACTION}

    action = parts[1].lower()

    if action not in VALID_AUTH_ACTIONS:
        valid_list = ", ".join(VALID_AUTH_ACTIONS)
        return {DICT_KEY_ERROR: ERROR_MSG_AUTH_INVALID_ACTION.format(action, valid_list)}

    # Extract any additional arguments (e.g., username, server URL)
    args = parts[SLICE_START_ARGS:] if len(parts) > SLICE_START_ARGS else []

    return {
        DICT_KEY_TYPE: CMD_TYPE_AUTH,
        DICT_KEY_ACTION: action,
        DICT_KEY_ARGS: args,
        DICT_KEY_OPTIONS: {}
    }


def parse_comm_command(parts: List[str]) -> Dict[str, Any]:
    """
    Parse comm commands like 'comm start postgresql', 'comm status'.
    
    Comm commands manage communication services (databases, servers, etc.).
    Validates action against VALID_COMM_ACTIONS. Supports args and options.
    
    Args:
        parts: Command parts (e.g., ['comm', 'start', 'postgresql', '--port', '5432'])
    
    Returns:
        Dict[str, Any]: Structured command dict or error dict
    
    Examples:
        >>> parse_comm_command(['comm', 'start', 'postgresql'])
        {{'type': 'comm', 'action': 'start', 'args': ['postgresql'], 'options': {{}}}}
        
        >>> parse_comm_command(['comm', 'start', 'postgresql', '--port', '5432'])
        {{'type': 'comm', 'action': 'start', 'args': ['postgresql'], 'options': {{'port': '5432'}}}}
    """
    if len(parts) < MIN_PARTS_SIMPLE_PARSER:
        return {DICT_KEY_ERROR: ERROR_MSG_COMM_NO_ACTION}

    action = parts[1].lower()

    if action not in VALID_COMM_ACTIONS:
        valid_list = ", ".join(VALID_COMM_ACTIONS)
        return {DICT_KEY_ERROR: ERROR_MSG_COMM_INVALID_ACTION.format(action, valid_list)}

    # Extract arguments and options
    args, options = extract_args_and_options(parts, SLICE_START_ARGS)

    return {
        DICT_KEY_TYPE: CMD_TYPE_COMM,
        DICT_KEY_ACTION: action,
        DICT_KEY_ARGS: args,
        DICT_KEY_OPTIONS: options
    }
