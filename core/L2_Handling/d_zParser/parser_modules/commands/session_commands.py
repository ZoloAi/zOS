# zOS/core/L2_Handling/g_zParser/parser_modules/commands/session_commands.py

"""
Session and navigation command parsing for commands package.

Parses session, walker, and test command types.

Public API:
    - parse_session_command: Parse session management
    - parse_walker_command: Parse walker operations
    - parse_test_command: Parse test execution

Created: Phase 4.2 - Extract Command Categories from parser_commands.py
"""

from zOS import Any, Dict, List

# Import constants
from ..shared.parser_constants import (
    _CMD_TYPE_SESSION as CMD_TYPE_SESSION,
    _CMD_TYPE_WALKER as CMD_TYPE_WALKER,
    _CMD_TYPE_TEST as CMD_TYPE_TEST,
    DICT_KEY_ERROR,
    DICT_KEY_TYPE,
    DICT_KEY_ACTION,
    DICT_KEY_ARGS,
    DICT_KEY_OPTIONS,
    ERROR_MSG_WALKER_NO_ACTION,
    MIN_PARTS_SIMPLE_PARSER,
    SLICE_START_ARGS,
    ACTION_DEFAULT_INFO,
    ACTION_DEFAULT_RUN
)


def parse_session_command(parts: List[str]) -> Dict[str, Any]:
    """
    Parse session commands like 'session' or 'session set mode zGUI'.
    
    Session commands manage session state and configuration. If no action is
    provided, defaults to 'info' action (display session state).
    
    Args:
        parts: Command parts (e.g., ['session'] or ['session', 'set', 'mode', 'zGUI'])
    
    Returns:
        Dict[str, Any]: Structured command dict
    
    Examples:
        >>> parse_session_command(['session'])
        {{'type': 'session', 'action': 'info', 'args': [], 'options': {{}}}}
        
        >>> parse_session_command(['session', 'info'])
        {{'type': 'session', 'action': 'info', 'args': [], 'options': {{}}}}
        
        >>> parse_session_command(['session', 'set', 'mode', 'zGUI'])
        {{'type': 'session', 'action': 'set', 'args': ['mode', 'zGUI'], 'options': {{}}}}
        
        >>> parse_session_command(['session', 'get', 'zMode'])
        {{'type': 'session', 'action': 'get', 'args': ['zMode'], 'options': {{}}}}
    
    Notes:
        - Default action is 'info' if no action provided
        - Most common use case is viewing session state
    """
    # Default to "info" action if no action provided
    action = ACTION_DEFAULT_INFO if len(parts) < MIN_PARTS_SIMPLE_PARSER else parts[1]
    args = parts[SLICE_START_ARGS:] if len(parts) > SLICE_START_ARGS else []

    return {
        DICT_KEY_TYPE: CMD_TYPE_SESSION,
        DICT_KEY_ACTION: action,
        DICT_KEY_ARGS: args,
        DICT_KEY_OPTIONS: {}
    }


def parse_walker_command(parts: List[str]) -> Dict[str, Any]:
    """
    Parse walker commands like 'walker load ui.zCloud.yaml'.
    
    Walker commands manage UI file loading and navigation.
    
    Args:
        parts: Command parts (e.g., ['walker', 'load', 'ui.zCloud.yaml'])
    
    Returns:
        Dict[str, Any]: Structured command dict or error dict
    
    Examples:
        >>> parse_walker_command(['walker', 'load', 'ui.zCloud.yaml'])
        {{'type': 'walker', 'action': 'load', 'args': ['ui.zCloud.yaml'], 'options': {{}}}}
    """
    if len(parts) < MIN_PARTS_SIMPLE_PARSER:
        return {DICT_KEY_ERROR: ERROR_MSG_WALKER_NO_ACTION}

    action = parts[1]
    args = parts[SLICE_START_ARGS:] if len(parts) > SLICE_START_ARGS else []

    return {
        DICT_KEY_TYPE: CMD_TYPE_WALKER,
        DICT_KEY_ACTION: action,
        DICT_KEY_ARGS: args,
        DICT_KEY_OPTIONS: {}
    }


def parse_test_command(parts: List[str]) -> Dict[str, Any]:
    """
    Parse test commands like 'test run' or 'test session'.
    
    Test commands execute test suites. Default action is "run" if not specified.
    
    Args:
        parts: Command parts (e.g., ['test', 'run'] or ['test'])
    
    Returns:
        Dict[str, Any]: Structured command dict
    
    Examples:
        >>> parse_test_command(['test', 'run'])
        {{'type': 'test', 'action': 'run', 'args': [], 'options': {{}}}}
        
        >>> parse_test_command(['test'])
        {{'type': 'test', 'action': 'run', 'args': [], 'options': {{}}}}
        
        >>> parse_test_command(['test', 'session'])
        {{'type': 'test', 'action': 'session', 'args': [], 'options': {{}}}}
    """
    action = ACTION_DEFAULT_RUN if len(parts) < MIN_PARTS_SIMPLE_PARSER else parts[1]
    args = parts[SLICE_START_ARGS:] if len(parts) > SLICE_START_ARGS else []

    return {
        DICT_KEY_TYPE: CMD_TYPE_TEST,
        DICT_KEY_ACTION: action,
        DICT_KEY_ARGS: args,
        DICT_KEY_OPTIONS: {}
    }
