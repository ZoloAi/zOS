# zOS/core/L2_Handling/g_zParser/parser_modules/commands/file_commands.py

"""
File operation command parsing for commands package.

Parses open, load, ls, cd, and pwd/cwd command types.

Public API:
    - parse_open_command: Parse file/URL opening
    - parse_load_command: Parse file loading
    - parse_ls_command: Parse directory listing
    - parse_cd_command: Parse directory change
    - parse_pwd_command: Parse current directory display

Created: Phase 4.2 - Extract Command Categories from parser_commands.py
"""

from zOS import Any, Dict, List
from .command_utils import extract_args_and_options

# Import constants
from ..shared.parser_constants import (
    _CMD_TYPE_OPEN as CMD_TYPE_OPEN,
    _CMD_TYPE_LOAD as CMD_TYPE_LOAD,
    _CMD_TYPE_LS as CMD_TYPE_LS,
    _CMD_TYPE_CD as CMD_TYPE_CD,
    _CMD_TYPE_CWD as CMD_TYPE_CWD,
    _CMD_TYPE_PWD as CMD_TYPE_PWD,
    DICT_KEY_ERROR,
    DICT_KEY_TYPE,
    DICT_KEY_ACTION,
    DICT_KEY_ARGS,
    DICT_KEY_OPTIONS,
    ERROR_MSG_OPEN_NO_PATH,
    ERROR_MSG_LOAD_NO_ARGS,
    MIN_PARTS_SIMPLE_PARSER,
    SLICE_START_OPTIONS,
    ACTION_DEFAULT_OPEN,
    ACTION_DEFAULT_LS,
    ACTION_DEFAULT_CD,
    ACTION_DEFAULT_PWD,
    CHAR_SPACE,
    CHAR_DASH_DOUBLE,
    CHAR_DASH_SINGLE
)


def parse_open_command(parts: List[str]) -> Dict[str, Any]:
    """
    Parse open commands like 'open @.zProducts.zTimer.index.html' or 'open https://example.com'.
    
    Open commands open files, directories, or URLs in appropriate applications.
    Path is rejoined if split (preserves spaces in paths).
    
    Args:
        parts: Command parts (e.g., ['open', '@.zProducts.zTimer.index.html'])
    
    Returns:
        Dict[str, Any]: Structured command dict or error dict
    
    Examples:
        >>> parse_open_command(['open', '@.zProducts.zTimer.index.html'])
        {{'type': 'open', 'action': 'open', 'args': ['@.zProducts.zTimer.index.html'], 'options': {{}}}}
        
        >>> parse_open_command(['open', 'https://example.com'])
        {{'type': 'open', 'action': 'open', 'args': ['https://example.com'], 'options': {{}}}}
    """
    if len(parts) < MIN_PARTS_SIMPLE_PARSER:
        return {DICT_KEY_ERROR: ERROR_MSG_OPEN_NO_PATH}

    # The path is everything after "open", rejoined if it was split
    path = CHAR_SPACE.join(parts[1:])

    return {
        DICT_KEY_TYPE: CMD_TYPE_OPEN,
        DICT_KEY_ACTION: ACTION_DEFAULT_OPEN,
        DICT_KEY_ARGS: [path],
        DICT_KEY_OPTIONS: {}
    }


def parse_load_command(parts: List[str]) -> Dict[str, Any]:
    """
    Parse load commands like 'load @.zUI.manual' or 'load @.zSchema.demo --as my_schema'.
    
    Load commands load files with optional named options (--as, etc.).
    
    Args:
        parts: Command parts (e.g., ['load', '@.zUI.manual', '--as', 'myui'])
    
    Returns:
        Dict[str, Any]: Structured command dict or error dict
    
    Examples:
        >>> parse_load_command(['load', '@.zUI.manual'])
        {{'type': 'load', 'action': 'load', 'args': ['@.zUI.manual'], 'options': {{}}}}
        
        >>> parse_load_command(['load', '@.zSchema.demo', '--as', 'my_schema'])
        {{'type': 'load', 'action': 'load', 'args': ['@.zSchema.demo'], 'options': {{'as': 'my_schema'}}}}
    """
    if len(parts) < MIN_PARTS_SIMPLE_PARSER:
        return {DICT_KEY_ERROR: ERROR_MSG_LOAD_NO_ARGS}

    # Extract arguments and options
    args, options = extract_args_and_options(parts, SLICE_START_OPTIONS)

    return {
        DICT_KEY_TYPE: CMD_TYPE_LOAD,
        DICT_KEY_ACTION: ACTION_DEFAULT_OPEN,
        DICT_KEY_ARGS: args,
        DICT_KEY_OPTIONS: options
    }


def parse_ls_command(parts: List[str]) -> Dict[str, Any]:
    """
    Parse list/ls/dir commands like 'list', 'ls @.path', 'list --sizes'.
    
    List directory commands show directory contents. Supports flags (-l, --recursive, etc.).
    
    Args:
        parts: Command parts (e.g., ['ls', '@.path', '--recursive', '-l'])
    
    Returns:
        Dict[str, Any]: Structured command dict
    
    Examples:
        >>> parse_ls_command(['ls'])
        {{'type': 'ls', 'action': 'ls', 'args': [], 'options': {{}}}}
        
        >>> parse_ls_command(['ls', '@.path', '--recursive'])
        {{'type': 'ls', 'action': 'ls', 'args': ['@.path'], 'options': {{'recursive': True}}}}
    """
    args = []
    options = {}

    for part in parts[1:]:
        if part.startswith(CHAR_DASH_DOUBLE) or part.startswith(CHAR_DASH_SINGLE):
            flag = part.lstrip(CHAR_DASH_SINGLE)
            options[flag] = True
        else:
            args.append(part)

    return {
        DICT_KEY_TYPE: CMD_TYPE_LS,
        DICT_KEY_ACTION: ACTION_DEFAULT_LS,
        DICT_KEY_ARGS: args,
        DICT_KEY_OPTIONS: options
    }


def parse_cd_command(parts: List[str]) -> Dict[str, Any]:
    """
    Parse cd commands like 'cd @.path' or 'cd ~'.
    
    Change directory commands change current working directory.
    
    Args:
        parts: Command parts (e.g., ['cd', '@.path'])
    
    Returns:
        Dict[str, Any]: Structured command dict
    
    Examples:
        >>> parse_cd_command(['cd', '@.path'])
        {{'type': 'cd', 'action': 'cd', 'args': ['@.path'], 'options': {{}}}}
        
        >>> parse_cd_command(['cd', '~'])
        {{'type': 'cd', 'action': 'cd', 'args': ['~'], 'options': {{}}}}
    """
    args = parts[1:] if len(parts) > 1 else []

    return {
        DICT_KEY_TYPE: CMD_TYPE_CD,
        DICT_KEY_ACTION: ACTION_DEFAULT_CD,
        DICT_KEY_ARGS: args,
        DICT_KEY_OPTIONS: {}
    }


def parse_pwd_command(parts: List[str]) -> Dict[str, Any]:
    """
    Parse cwd/pwd command (current/print working directory).
    
    Shows current working directory. Both 'cwd' (primary) and 'pwd' (alias) are supported.
    Takes no arguments.
    
    Args:
        parts: Command parts (e.g., ['cwd'] or ['pwd'])
    
    Returns:
        Dict[str, Any]: Structured command dict with appropriate type
    
    Examples:
        >>> parse_pwd_command(['cwd'])
        {{'type': 'cwd', 'action': 'pwd', 'args': [], 'options': {{}}}}
        
        >>> parse_pwd_command(['pwd'])
        {{'type': 'pwd', 'action': 'pwd', 'args': [], 'options': {{}}}}
    
    Note:
        Both commands execute the same function (execute_pwd), but return their
        respective type for logging/debugging purposes.
    """
    # Determine which command was used (cwd is primary, pwd is alias)
    command_type = CMD_TYPE_CWD if parts[0] == "cwd" else CMD_TYPE_PWD

    return {
        DICT_KEY_TYPE: command_type,
        DICT_KEY_ACTION: ACTION_DEFAULT_PWD,
        DICT_KEY_ARGS: [],
        DICT_KEY_OPTIONS: {}
    }
