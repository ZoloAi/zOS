# zOS/core/L2_Handling/g_zParser/parser_modules/commands/config_commands.py

"""
Configuration command parsing for commands package.

Parses export, config, and config_persistence command types.

Public API:
    - parse_export_command: Parse export operations
    - parse_config_command: Parse config operations
    - parse_config_persistence_command: Parse legacy config persistence

Created: Phase 4.2 - Extract Command Categories from parser_commands.py
"""

from zOS import Any, Dict, List

# Import constants
from ..shared.parser_constants import (
    _CMD_TYPE_EXPORT as CMD_TYPE_EXPORT,
    _CMD_TYPE_CONFIG as CMD_TYPE_CONFIG,
    _CMD_TYPE_CONFIG_PERSISTENCE as CMD_TYPE_CONFIG_PERSISTENCE,
    DICT_KEY_ERROR,
    DICT_KEY_TYPE,
    DICT_KEY_ACTION,
    DICT_KEY_ARGS,
    DICT_KEY_OPTIONS,
    ERROR_MSG_EXPORT_NO_TARGET,
    ERROR_MSG_EXPORT_INVALID_TARGET,
    ERROR_MSG_CONFIG_NO_ACTION,
    ERROR_MSG_CONFIG_INVALID_ACTION,
    ERROR_MSG_CONFIG_PERSIST_NO_TARGET,
    ERROR_MSG_CONFIG_PERSIST_INVALID_TARGET,
    MIN_PARTS_SIMPLE_PARSER,
    SLICE_START_ARGS,
    CHAR_DASH_DOUBLE
)

# Config actions
ACTION_CONFIG_CHECK = "check"
ACTION_CONFIG_SHOW = "show"
ACTION_CONFIG_GET = "get"
ACTION_CONFIG_SET = "set"
ACTION_CONFIG_RESET = "reset"
ACTION_CONFIG_LIST = "list"
ACTION_CONFIG_RELOAD = "reload"
ACTION_CONFIG_VALIDATE = "validate"
ACTION_CONFIG_MACHINE = "machine"
ACTION_CONFIG_CONFIG = "config"

VALID_EXPORT_TARGETS = ["machine", "config"]

VALID_CONFIG_ACTIONS = [
    ACTION_CONFIG_CHECK, ACTION_CONFIG_SHOW, ACTION_CONFIG_GET,
    ACTION_CONFIG_SET, ACTION_CONFIG_RESET, ACTION_CONFIG_LIST,
    ACTION_CONFIG_RELOAD, ACTION_CONFIG_VALIDATE,
    ACTION_CONFIG_MACHINE, ACTION_CONFIG_CONFIG
]

VALID_CONFIG_PERSISTENCE_TARGETS = ["machine", "config"]


def parse_export_command(parts: List[str]) -> Dict[str, Any]:
    """
    Parse export commands like 'export machine text_editor cursor'.
    
    Export commands export configuration to persistent storage. Validates target
    against VALID_EXPORT_TARGETS. Supports flags (--show, --reset).
    
    Args:
        parts: Command parts (e.g., ['export', 'machine', 'text_editor', 'cursor', '--show'])
    
    Returns:
        Dict[str, Any]: Structured command dict or error dict
    
    Examples:
        >>> parse_export_command(['export', 'machine', 'text_editor', 'cursor'])
        {{'type': 'export', 'action': 'machine', 'args': ['text_editor', 'cursor'], 'options': {{}}}}
        
        >>> parse_export_command(['export', 'config', '--show'])
        {{'type': 'export', 'action': 'config', 'args': [], 'options': {{'show': True}}}}
    """
    if len(parts) < MIN_PARTS_SIMPLE_PARSER:
        return {DICT_KEY_ERROR: ERROR_MSG_EXPORT_NO_TARGET}

    target = parts[1].lower()

    if target not in VALID_EXPORT_TARGETS:
        valid_list = ", ".join(VALID_EXPORT_TARGETS)
        return {DICT_KEY_ERROR: ERROR_MSG_EXPORT_INVALID_TARGET.format(target, valid_list)}

    # Check for flags (--show, --reset)
    options = {}
    args = []

    for part in parts[SLICE_START_ARGS:]:
        if part.startswith(CHAR_DASH_DOUBLE):
            flag = part[2:]
            options[flag] = True
        else:
            args.append(part)

    return {
        DICT_KEY_TYPE: CMD_TYPE_EXPORT,
        DICT_KEY_ACTION: target,
        DICT_KEY_ARGS: args,
        DICT_KEY_OPTIONS: options
    }


def parse_config_command(parts: List[str]) -> Dict[str, Any]:
    """
    Parse config commands (unified config system).
    
    Supports:
        - Diagnostics: 'config check', 'config show'
        - Get: 'config get machine text_editor', 'config get env deployment'
        - Set: 'config set machine text_editor cursor', 'config set env deployment prod'
        - Reset: 'config reset machine text_editor', 'config reset env deployment'
    
    Config commands manage configuration state. Validates action against VALID_CONFIG_ACTIONS.
    Delegates to parse_config_persistence_command for legacy machine/config actions.
    
    Args:
        parts: Command parts (e.g., ['config', 'check'], ['config', 'set', 'machine', 'browser', 'Chrome'])
    
    Returns:
        Dict[str, Any]: Structured command dict or error dict
    
    Examples:
        >>> parse_config_command(['config', 'check'])
        {{'type': 'config', 'action': 'check', 'args': [], 'options': {{}}}}
        
        >>> parse_config_command(['config', 'get', 'machine', 'text_editor'])
        {{'type': 'config', 'action': 'get', 'args': ['machine', 'text_editor'], 'options': {{}}}}
        
        >>> parse_config_command(['config', 'set', 'machine', 'text_editor', 'cursor'])
        {{'type': 'config', 'action': 'set', 'args': ['machine', 'text_editor', 'cursor'], 'options': {{}}}}
        
        >>> parse_config_command(['config', 'reset', 'env', 'deployment'])
        {{'type': 'config', 'action': 'reset', 'args': ['env', 'deployment'], 'options': {{}}}}
        
        >>> parse_config_command(['config', 'machine', 'browser', 'Chrome'])
        {{'type': 'config_persistence', 'action': 'machine', 'args': ['browser', 'Chrome'], 'options': {{}}}}
    """
    if len(parts) < MIN_PARTS_SIMPLE_PARSER:
        return {DICT_KEY_ERROR: ERROR_MSG_CONFIG_NO_ACTION}

    action = parts[1].lower()

    if action not in VALID_CONFIG_ACTIONS:
        valid_list = ", ".join(VALID_CONFIG_ACTIONS)
        return {DICT_KEY_ERROR: ERROR_MSG_CONFIG_INVALID_ACTION.format(action, valid_list)}

    # Handle persistence commands (machine, config)
    if action in [ACTION_CONFIG_MACHINE, ACTION_CONFIG_CONFIG]:
        return parse_config_persistence_command(parts)

    # Extract arguments and options for other commands
    args = parts[SLICE_START_ARGS:] if len(parts) > SLICE_START_ARGS else []
    options = {}

    return {
        DICT_KEY_TYPE: CMD_TYPE_CONFIG,
        DICT_KEY_ACTION: action,
        DICT_KEY_ARGS: args,
        DICT_KEY_OPTIONS: options
    }


def parse_config_persistence_command(parts: List[str]) -> Dict[str, Any]:
    """
    Parse config persistence commands like 'config machine browser Chrome' or 'config machine --reset browser'.
    
    Config persistence commands save configuration to disk. Validates target against
    VALID_CONFIG_PERSISTENCE_TARGETS. Supports flags (--show, --reset).
    
    Args:
        parts: Command parts (e.g., ['config', 'machine', 'browser', 'Chrome', '--reset'])
    
    Returns:
        Dict[str, Any]: Structured command dict or error dict
    
    Examples:
        >>> parse_config_persistence_command(['config', 'machine', 'browser', 'Chrome'])
        {{'type': 'config_persistence', 'action': 'machine', 'args': ['browser', 'Chrome'], 'options': {{}}}}
        
        >>> parse_config_persistence_command(['config', 'machine', '--reset', 'browser'])
        {{'type': 'config_persistence', 'action': 'machine', 'args': ['browser'], 'options': {{'reset': True}}}}
    """
    if len(parts) < MIN_PARTS_SIMPLE_PARSER:
        return {DICT_KEY_ERROR: ERROR_MSG_CONFIG_PERSIST_NO_TARGET}

    target = parts[1].lower()

    if target not in VALID_CONFIG_PERSISTENCE_TARGETS:
        valid_list = ", ".join(VALID_CONFIG_PERSISTENCE_TARGETS)
        return {DICT_KEY_ERROR: ERROR_MSG_CONFIG_PERSIST_INVALID_TARGET.format(target, valid_list)}

    # Check for flags (--show, --reset)
    options = {}
    args = []

    for part in parts[SLICE_START_ARGS:]:
        if part.startswith(CHAR_DASH_DOUBLE):
            flag = part[2:]
            options[flag] = True
        else:
            args.append(part)

    return {
        DICT_KEY_TYPE: CMD_TYPE_CONFIG_PERSISTENCE,
        DICT_KEY_ACTION: target,
        DICT_KEY_ARGS: args,
        DICT_KEY_OPTIONS: options
    }
