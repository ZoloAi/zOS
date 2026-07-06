# zOS/core/L2_Handling/g_zParser/parser_modules/commands/data_commands.py

"""
Data command parsing for commands package.

Parses data operations (read, create, insert, update, delete, etc.).

Public API:
    - parse_data_command: Parse data operations

Created: Phase 4.2 - Extract Command Categories from parser_commands.py
"""

from zOS import Any, Dict, List
from .command_utils import extract_args_and_options

# Import constants
from ..shared.parser_constants import (
    _CMD_TYPE_DATA as CMD_TYPE_DATA,
    DICT_KEY_ERROR,
    DICT_KEY_TYPE,
    DICT_KEY_ACTION,
    DICT_KEY_ARGS,
    DICT_KEY_OPTIONS,
    ERROR_MSG_DATA_NO_ACTION,
    ERROR_MSG_DATA_INVALID_ACTION,
    MIN_PARTS_SIMPLE_PARSER,
    SLICE_START_ARGS
)

# Data actions
ACTION_DATA_READ = "read"
ACTION_DATA_CREATE = "create"
ACTION_DATA_INSERT = "insert"
ACTION_DATA_UPDATE = "update"
ACTION_DATA_DELETE = "delete"
ACTION_DATA_DROP = "drop"
ACTION_DATA_HEAD = "head"
ACTION_DATA_SEARCH = "search"
ACTION_DATA_TABLES = "tables"

VALID_DATA_ACTIONS = [
    ACTION_DATA_READ, ACTION_DATA_CREATE, ACTION_DATA_INSERT,
    ACTION_DATA_UPDATE, ACTION_DATA_DELETE, ACTION_DATA_DROP,
    ACTION_DATA_HEAD, ACTION_DATA_SEARCH, ACTION_DATA_TABLES
]


def parse_data_command(parts: List[str]) -> Dict[str, Any]:
    """
    Parse data commands like 'data read users --limit 10' or 'data insert users --name Alice'.
    
    Data commands handle database/data operations with various actions (read, create, insert,
    update, delete, drop, head, search, tables). Supports positional args and named options.
    
    Args:
        parts: Command parts from split_command (e.g., ['data', 'read', 'users', '--limit', '10'])
    
    Returns:
        Dict[str, Any]: Structured command dict or error dict
        
        Success:
            {{
                "type": "data",
                "action": str (read/create/insert/update/delete/drop/head/search/tables),
                "args": List[str] (e.g., ["users"]),
                "options": Dict[str, Any] (e.g., {{"limit": "10"}})
            }}
        
        Error:
            {{"error": str}}
    
    Examples:
        >>> parse_data_command(['data', 'read', 'users', '--limit', '10'])
        {{'type': 'data', 'action': 'read', 'args': ['users'], 'options': {{'limit': '10'}}}}
        
        >>> parse_data_command(['data', 'insert', 'users', '--name', 'Alice', '--age', '30'])
        {{'type': 'data', 'action': 'insert', 'args': ['users'], 'options': {{'name': 'Alice', 'age': '30'}}}}
        
        >>> parse_data_command(['data'])
        {{'error': 'Data command requires action'}}
    
    Notes:
        - Requires at least 2 parts (data + action)
        - Action must be in VALID_DATA_ACTIONS
        - Options start with -- (e.g., --limit 10)
        - Boolean options: --flag (no value)
    """
    if len(parts) < MIN_PARTS_SIMPLE_PARSER:
        return {DICT_KEY_ERROR: ERROR_MSG_DATA_NO_ACTION}

    action = parts[1].lower()

    if action not in VALID_DATA_ACTIONS:
        return {DICT_KEY_ERROR: ERROR_MSG_DATA_INVALID_ACTION.format(action)}

    # Extract arguments and options
    args, options = extract_args_and_options(parts, SLICE_START_ARGS)

    return {
        DICT_KEY_TYPE: CMD_TYPE_DATA,
        DICT_KEY_ACTION: action,
        DICT_KEY_ARGS: args,
        DICT_KEY_OPTIONS: options
    }
