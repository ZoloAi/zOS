# zOS/core/L2_Handling/g_zParser/parser_modules/commands/ui_commands.py

"""
UI and helper command parsing for commands package.

Parses wizard, shortcut, where, and help command types.

Public API:
    - parse_wizard_command: Parse wizard operations
    - parse_shortcut_command: Parse shortcut management
    - parse_where_command: Parse contextual prompt display
    - parse_help_command: Parse help display

Created: Phase 4.2 - Extract Command Categories from parser_commands.py
"""

from zOS import Any, Dict, List

# Import constants
from ..shared.parser_constants import (
    _CMD_TYPE_WIZARD as CMD_TYPE_WIZARD,
    _CMD_TYPE_SHORTCUT as CMD_TYPE_SHORTCUT,
    _CMD_TYPE_WHERE as CMD_TYPE_WHERE,
    _CMD_TYPE_HELP as CMD_TYPE_HELP,
    DICT_KEY_ERROR,
    DICT_KEY_TYPE,
    DICT_KEY_ACTION,
    DICT_KEY_ARGS,
    DICT_KEY_OPTIONS,
    ERROR_MSG_WIZARD_NO_FLAGS,
    MIN_PARTS_SIMPLE_PARSER,
    ACTION_DEFAULT_WIZARD,
    ACTION_DEFAULT_LIST,
    ACTION_DEFAULT_CREATE,
    ACTION_DEFAULT_STATUS,
    ACTION_DEFAULT_SHOW,
    CHAR_DASH_DOUBLE
)


def parse_wizard_command(parts: List[str]) -> Dict[str, Any]:
    """
    Parse wizard commands with flags like 'wizard --start', 'wizard --run myfile'.
    
    Wizard commands manage wizard execution. Requires at least one flag
    (--start, --stop, --run, --show, --clear).
    
    Args:
        parts: Command parts (e.g., ['wizard', '--start', '--run', 'myfile'])
    
    Returns:
        Dict[str, Any]: Structured command dict or error dict
    
    Examples:
        >>> parse_wizard_command(['wizard', '--start'])
        {{'type': 'wizard', 'action': 'wizard', 'args': [], 'options': {{'start': True}}}}
        
        >>> parse_wizard_command(['wizard', '--run', 'myfile'])
        {{'type': 'wizard', 'action': 'wizard', 'args': ['myfile'], 'options': {{'run': True}}}}
    """
    if len(parts) < MIN_PARTS_SIMPLE_PARSER:
        return {DICT_KEY_ERROR: ERROR_MSG_WIZARD_NO_FLAGS}

    # Extract options
    options = {}
    args = []

    for part in parts[1:]:
        if part.startswith(CHAR_DASH_DOUBLE):
            flag = part[2:]
            options[flag] = True
        else:
            args.append(part)

    return {
        DICT_KEY_TYPE: CMD_TYPE_WIZARD,
        DICT_KEY_ACTION: ACTION_DEFAULT_WIZARD,
        DICT_KEY_ARGS: args,
        DICT_KEY_OPTIONS: options
    }


def parse_shortcut_command(parts: List[str]) -> Dict[str, Any]:
    """
    Parse shortcut commands like 'shortcut', 'shortcut name="command"', 'shortcut --remove name'.
    
    Shortcut commands manage command shortcuts. Default action is "list" if no args/options.
    
    Args:
        parts: Command parts (e.g., ['shortcut', 'name="command"'] or ['shortcut', '--remove', 'name'])
    
    Returns:
        Dict[str, Any]: Structured command dict
    
    Examples:
        >>> parse_shortcut_command(['shortcut'])
        {{'type': 'shortcut', 'action': 'list', 'args': [], 'options': {{}}}}
        
        >>> parse_shortcut_command(['shortcut', 'gs="git status"'])
        {{'type': 'shortcut', 'action': 'create', 'args': ['gs="git status"'], 'options': {{}}}}
        
        >>> parse_shortcut_command(['shortcut', '--remove', 'gs'])
        {{'type': 'shortcut', 'action': 'create', 'args': ['gs'], 'options': {{'remove': True}}}}
    """
    # Extract options and args
    options = {}
    args = []

    for part in parts[1:]:
        if part.startswith(CHAR_DASH_DOUBLE):
            flag = part[2:]
            options[flag] = True
        else:
            args.append(part)

    action = ACTION_DEFAULT_LIST if not args and not options else ACTION_DEFAULT_CREATE

    return {
        DICT_KEY_TYPE: CMD_TYPE_SHORTCUT,
        DICT_KEY_ACTION: action,
        DICT_KEY_ARGS: args,
        DICT_KEY_OPTIONS: options
    }


def parse_where_command(parts: List[str]) -> Dict[str, Any]:
    """
    Parse where commands like 'where', 'where on', 'where off', 'where toggle'.
    
    Where commands manage contextual prompt display. Default action is "status" if no args.
    
    Args:
        parts: Command parts (e.g., ['where'], ['where', 'on'], ['where', 'toggle'])
    
    Returns:
        Dict[str, Any]: Structured command dict
    
    Examples:
        >>> parse_where_command(['where'])
        {{'type': 'where', 'action': 'status', 'args': [], 'options': {{}}}}
        
        >>> parse_where_command(['where', 'on'])
        {{'type': 'where', 'action': 'status', 'args': ['on'], 'options': {{}}}}
        
        >>> parse_where_command(['where', 'toggle'])
        {{'type': 'where', 'action': 'status', 'args': ['toggle'], 'options': {{}}}}
        
        >>> parse_where_command(['where', 'off'])
        {{'type': 'where', 'action': 'status', 'args': ['off'], 'options': {{}}}}
    """
    # Extract args (no options needed for where command)
    args = parts[1:] if len(parts) > 1 else []

    return {
        DICT_KEY_TYPE: CMD_TYPE_WHERE,
        DICT_KEY_ACTION: ACTION_DEFAULT_STATUS,
        DICT_KEY_ARGS: args,
        DICT_KEY_OPTIONS: {}
    }


def parse_help_command(parts: List[str]) -> Dict[str, Any]:
    """
    Parse help commands like 'help', 'help ls', 'help shortcut'.
    
    Help commands show shell terminal command documentation. Optional argument
    specifies which command to show help for.
    
    Args:
        parts: Command parts (e.g., ['help'], ['help', 'ls'], ['help', 'shortcut'])
    
    Returns:
        Dict[str, Any]: Structured command dict
    
    Examples:
        >>> parse_help_command(['help'])
        {{'type': 'help', 'action': 'show', 'args': [], 'options': {{}}}}
        
        >>> parse_help_command(['help', 'ls'])
        {{'type': 'help', 'action': 'show', 'args': ['ls'], 'options': {{}}}}
        
        >>> parse_help_command(['help', 'shortcut'])
        {{'type': 'help', 'action': 'show', 'args': ['shortcut'], 'options': {{}}}}
    """
    # Extract args (command name to show help for)
    args = parts[1:] if len(parts) > 1 else []

    return {
        DICT_KEY_TYPE: CMD_TYPE_HELP,
        DICT_KEY_ACTION: ACTION_DEFAULT_SHOW,
        DICT_KEY_ARGS: args,
        DICT_KEY_OPTIONS: {}
    }
