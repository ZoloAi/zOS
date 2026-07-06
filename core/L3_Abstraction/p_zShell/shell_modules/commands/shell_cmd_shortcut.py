# zOS/core/L3_Abstraction/p_zShell/shell_modules/commands/shell_cmd_shortcut.py

"""
Shell Command Shortcut Management System - Unified Aliasing.

This module provides functionality for creating, managing, and persisting two types
of shortcuts within the zCLI framework:

TWO TYPES OF SHORTCUTS:
    1. **zVars** (User Variables): Store user-defined values
       Syntax: `shortcut myvar="value"`
       Stored in: session["zVars"]
       Use case: Configuration values, temporary data
       
    2. **File Shortcuts**: References to cached files
       Syntax: `shortcut cache` → Interactive menu to select cached file
       Stored in: session["zShortcuts"]
       Use case: Quick access to loaded schemas, UI files, configs

UNIFIED ALIASING ARCHITECTURE:
    Both types are stored in the session dictionary, making them accessible across
    all subsystems (zShell, zWalker, zBifrost, zData, etc.). This centralized
    approach ensures consistency and simplifies cross-subsystem data sharing.

Core Features:
    • Create shortcuts with memorable names
    • List all defined shortcuts with formatted display
    • Remove individual shortcuts or clear all
    • Save shortcuts to JSON file for persistence
    • Load shortcuts from JSON file
    • Validate shortcut names against reserved words
    • Prevent recursive shortcut definitions
    • Cross-platform path resolution via zConfig

Shortcut Format:
    shortcut <name>="<command>"
    
    Examples:
        shortcut gs="git status"
        shortcut ll="ls --long"
        shortcut dev="cd ~/projects/dev"

Storage:
    Shortcuts are stored in the session dictionary under SESSION_KEY_SHORTCUTS
    and can be persisted to JSON files in the user data directory.

Session Integration:
    Uses centralized session constants from zConfig:
        - SESSION_KEY_SHORTCUTS: "zShortcuts"
        - SESSION_KEY_ZUSERDATA: "zUserData"

Architecture:
    • execute_shortcut(): Main entry point, delegates to action handlers
    • _list_shortcuts(): Display all shortcuts in formatted table
    • _create_shortcut(): Create/update shortcut with validation
    • _remove_shortcut(): Remove individual shortcut
    • _clear_shortcuts(): Remove all shortcuts
    • _save_shortcuts(): Persist shortcuts to JSON file
    • _load_shortcuts(): Load shortcuts from JSON file
    • _get_default_shortcut_file(): DRY helper for path resolution
    • _validate_shortcut_name(): Validation helper for shortcut names

Type Safety:
    All functions include comprehensive type hints using types imported from
    the zCLI namespace for consistency.

Error Handling:
    Uses specific exceptions (IOError, PermissionError, json.JSONDecodeError)
    rather than broad Exception catches for precise error reporting.

Cross-Subsystem Dependencies:
    • zDisplay: User feedback via info(), error(), success(), warning()
    • zConfig: Session constants, user data paths
    • zParser: (Future) zPath resolution for file paths

Related:
    • zLoader PinnedCache: $alias system for data references
    • zParser: Command parsing infrastructure
    • zAuth: (Future) Per-user shortcut persistence

Author: zOS Framework
Version: 1.5.4
"""

from zOS import json, Path, Any, Dict, List, Optional

from ..executor_constants import KEY_ARGS, KEY_OPTIONS

# Import session constants from zConfig
from zOS.L1_Foundation.a_zConfig.zConfig_modules.config_constants import (
    SESSION_KEY_ZVARS,
    SESSION_KEY_ZSHORTCUTS
)

# ============================================================================
# MODULE CONSTANTS
# ============================================================================

# Session Keys (use imported constants for consistency)
SESSION_KEY_SHORTCUTS: str = SESSION_KEY_ZSHORTCUTS  # File shortcuts (cached files)
SESSION_KEY_VARS: str = SESSION_KEY_ZVARS  # User variables
SESSION_KEY_ZUSERDATA: str = "zUserData"  # TODO: Move to zConfig/config_session.py

# Action Constants
ACTION_LIST: str = "list"
ACTION_CREATE: str = "create"
ACTION_REMOVE: str = "remove"
ACTION_SAVE: str = "save"
ACTION_LOAD: str = "load"
ACTION_CLEAR: str = "clear"

# Option Flags
OPTION_REMOVE: str = "remove"
OPTION_RM: str = "rm"
OPTION_SAVE: str = "save"
OPTION_LOAD: str = "load"
OPTION_CLEAR: str = "clear"

# Status Codes
STATUS_SUCCESS: str = "success"
STATUS_CREATED: str = "created"
STATUS_REMOVED: str = "removed"
STATUS_SAVED: str = "saved"
STATUS_LOADED: str = "loaded"
STATUS_CLEARED: str = "cleared"
STATUS_EMPTY: str = "empty"

# Error Codes
ERROR_NO_SHORTCUT_NAME: str = "no_shortcut_name"
ERROR_INVALID_SYNTAX: str = "invalid_syntax"
ERROR_EMPTY_NAME_OR_COMMAND: str = "empty_name_or_command"
ERROR_INVALID_NAME: str = "invalid_name"
ERROR_RESERVED_WORD: str = "reserved_word"
ERROR_RECURSIVE_SHORTCUT: str = "recursive_shortcut"
ERROR_NAME_TOO_LONG: str = "name_too_long"
ERROR_NOT_FOUND: str = "not_found"
ERROR_FILE_NOT_FOUND: str = "file_not_found"
ERROR_INVALID_FORMAT: str = "invalid_format"
ERROR_INVALID_JSON: str = "invalid_json"
ERROR_PERMISSION_DENIED: str = "permission_denied"
ERROR_IO_ERROR: str = "io_error"
ERROR_PATH_NOT_ALLOWED: str = "path_not_allowed"

# Display Constants — SSOT: zshell_constants
from ..zshell_constants import (
    COLOR_INFO as DISPLAY_COLOR_INFO,
    STYLE_FULL as DISPLAY_STYLE_FULL,
)
DISPLAY_INDENT_ZERO: int = 0
DISPLAY_INDENT_ONE: int = 1

# Validation Constants
CHAR_EQUALS: str = "="
CHAR_SPACE: str = " "
CHAR_QUOTE_DOUBLE: str = '"'
CHAR_QUOTE_SINGLE: str = "'"
MAX_SHORTCUT_NAME_LENGTH: int = 50

# File Constants
FILE_EXTENSION_JSON: str = ".json"
FILE_DEFAULT_SHORTCUTS: str = "shortcuts.json"
FILE_ENCODING_UTF8: str = "utf-8"
JSON_INDENT: int = 2

# Reserved Words (zCLI commands that cannot be used as shortcut names)
RESERVED_WORDS: List[str] = [
    "data", "func", "session", "walker", "open", "test", "auth", "load",
    "export", "utils", "config", "comm", "wizard", "plugin", "history",
    "echo", "print", "ls", "dir", "cd", "pwd", "shortcut", "help", "exit"
]

# User Messages
MSG_NO_SHORTCUTS: str = "No shortcuts defined"
MSG_NO_SHORTCUTS_TO_SAVE: str = "No shortcuts to save"
MSG_SPECIFY_SHORTCUT_NAME: str = "Please specify shortcut name to remove"
MSG_INVALID_SYNTAX: str = 'Invalid shortcut syntax. Use: shortcut name="command"'
MSG_EMPTY_NAME_OR_COMMAND: str = "Shortcut name and command cannot be empty"
MSG_NAME_CONTAINS_SPACES: str = "Shortcut name cannot contain spaces"
MSG_RESERVED_WORD: str = "Cannot use reserved word '{word}' as shortcut name"
MSG_RECURSIVE_SHORTCUT: str = "Recursive shortcut detected: {name} cannot reference itself"
MSG_NAME_TOO_LONG: str = "Shortcut name too long (max {max} characters)"
MSG_OVERWRITING: str = "Overwriting existing shortcut: {name}"
MSG_CREATED: str = "Shortcut created: {name} => {command}"
MSG_REMOVED: str = "Shortcut removed: {name} (was: {command})"
MSG_CLEARED: str = "All shortcuts cleared ({count} removed)"
MSG_SAVED: str = "Shortcuts saved to: {filepath}"
MSG_LOADED: str = "Shortcuts loaded from: {filepath}"
MSG_COUNT_INFO: str = "({count} shortcuts)"
MSG_COUNT_ADDED: str = "({count} shortcuts added)"
MSG_NOT_FOUND: str = "Shortcut not found: {name}"
MSG_FILE_NOT_FOUND: str = "Shortcut file not found: {filepath}"
MSG_INVALID_FORMAT: str = "Invalid shortcut file format"
MSG_INVALID_JSON: str = "Invalid JSON in shortcut file: {filename}"
MSG_SAVE_FAILED: str = "Failed to save shortcuts: {error}"
MSG_LOAD_FAILED: str = "Failed to load shortcuts: {error}"
MSG_PERMISSION_DENIED: str = "Permission denied: {error}"
MSG_PATH_NOT_ALLOWED: str = (
    "Refusing path '{name}': shortcut files must be a .json under the shortcuts "
    "directory (no absolute paths or '..' traversal)."
)
MSG_SKIPPED_ENTRIES: str = "Ignored {count} invalid entr{suffix} (shortcuts must be name->command strings)"

# Dictionary Keys
DICT_KEY_STATUS: str = "status"
DICT_KEY_ERROR: str = "error"
DICT_KEY_COUNT: str = "count"
DICT_KEY_NAME: str = "name"
DICT_KEY_COMMAND: str = "command"
DICT_KEY_FILE: str = "file"
DICT_KEY_TOTAL: str = "total"
DICT_KEY_ARGS: str = KEY_ARGS  # SSOT: executor_constants
DICT_KEY_OPTIONS: str = KEY_OPTIONS  # SSOT: executor_constants


# ============================================================================
# PUBLIC API
# ============================================================================

def execute_shortcut(zos: Any, parsed: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute shortcut commands (create, list, remove, save, load, clear).
    
    Main entry point for shortcut command execution. Delegates to specific
    action handlers based on provided arguments and options.
    
    Args:
        zos: zOS framework instance with session, config, display access
        parsed: Parsed command dictionary with 'args' and 'options'
    
    Returns:
        Dict[str, Any]: Result dictionary with status/error and metadata
        
    Command Syntax:
        shortcut                      # List all shortcuts
        shortcut name="command"       # Create shortcut
        shortcut --remove name        # Remove shortcut
        shortcut --save [file]        # Save shortcuts to file
        shortcut --load [file]        # Load shortcuts from file
        shortcut --clear              # Clear all shortcuts
    
    Examples:
        >>> execute_shortcut(zos, {"args": [], "options": {}})
        {"status": "empty"}  # No shortcuts defined
        
        >>> execute_shortcut(zos, {"args": ['gs="git status"'], "options": {}})
        {"status": "created", "name": "gs", "command": "git status"}
        
        >>> execute_shortcut(zos, {"args": ["gs"], "options": {"remove": True}})
        {"status": "removed", "name": "gs", "command": "git status"}
    
    Session Integration:
        Initializes SESSION_KEY_SHORTCUTS in session if not present.
        All shortcuts are stored in session[SESSION_KEY_SHORTCUTS] as a dict.
    
    Related:
        _list_shortcuts(), _create_shortcut(), _remove_shortcut(),
        _save_shortcuts(), _load_shortcuts(), _clear_shortcuts()
    """
    args: List[str] = parsed.get(DICT_KEY_ARGS, [])
    options: Dict[str, Any] = parsed.get(DICT_KEY_OPTIONS, {})
    
    # Initialize shortcuts and zVars dicts in session if not exist
    if SESSION_KEY_SHORTCUTS not in zos.session:
        zos.session[SESSION_KEY_SHORTCUTS] = {}
    if SESSION_KEY_ZVARS not in zos.session:
        zos.session[SESSION_KEY_ZVARS] = {}
    
    shortcuts: Dict[str, str] = zos.session[SESSION_KEY_SHORTCUTS]
    zvars: Dict[str, str] = zos.session[SESSION_KEY_ZVARS]
    
    # Check for 'cache' subcommand (interactive shortcut creation from cache)
    if args and args[0] == "cache":
        zos.logger.info("Launching interactive shortcut creation from cache...")
        from zOS.L1_Foundation.c_zLoader.loader_modules.cache_utils import create_shortcut_from_cache
        result = create_shortcut_from_cache(zos)
        return result
    
    # Route to action handler based on args/options
    if not args and not options:
        return _list_shortcuts(zos, shortcuts, zvars)
    
    if options.get(OPTION_REMOVE) or options.get(OPTION_RM):
        if not args:
            zos.display.error(MSG_SPECIFY_SHORTCUT_NAME)
            return {DICT_KEY_ERROR: ERROR_NO_SHORTCUT_NAME}
        return _remove_shortcut(zos, shortcuts, zvars, args[0])
    
    if options.get(OPTION_SAVE):
        return _save_shortcuts(zos, shortcuts, args)
    
    if options.get(OPTION_LOAD):
        return _load_shortcuts(zos, args)
    
    if options.get(OPTION_CLEAR):
        return _clear_shortcuts(zos)
    
    if args:
        return _create_shortcut(zos, shortcuts, zvars, args)
    
    return {DICT_KEY_ERROR: ERROR_INVALID_SYNTAX}


# ============================================================================
# LISTING SHORTCUTS
# ============================================================================

def _list_shortcuts(zos: Any, shortcuts: Dict[str, str], zvars: Dict[str, str]) -> Dict[str, Any]:
    """
    List all defined shortcuts and zVars in formatted table display.
    
    Displays two sections:
    1. User Variables (zVars) - for storing values
    2. File Shortcuts - for cached file references
    
    Each section displays items in alphabetical order with aligned columns:
        name1     => value1
        name2     => value2
        longname  => value3
    
    Args:
        zos: zOS framework instance for display access
        shortcuts: Dictionary of file shortcut name -> path mappings
        zvars: Dictionary of zVar name -> value mappings
    
    Returns:
        Dict[str, Any]: {"status": "success", "count": N} or {"status": "empty"}
    
    Display:
        Uses zDisplay.zDeclare() for headers and zDisplay.text() for rows.
        Automatically calculates column width for clean alignment.
    
    Examples:
        >>> _list_shortcuts(zos, {}, {})
        # Displays: "No shortcuts or variables defined"
        {"status": "empty"}
        
        >>> _list_shortcuts(zos, {"myui": "load @.zUI.main"}, {"env": "dev"})
        # Displays:
        # User Variables (zVars) - 1
        #   env  => dev
        # File Shortcuts - 1
        #   myui => load @.zUI.main
        {"status": "success", "count": 2}
    """
    if not shortcuts and not zvars:
        zos.display.info("No shortcuts or variables defined")
        return {DICT_KEY_STATUS: STATUS_EMPTY}
    
    total_count = len(shortcuts) + len(zvars)
    
    # Display zVars section
    if zvars:
        zos.display.text("")  # Empty line for spacing
        zos.display.zDeclare(
            f"User Variables (zVars) - {len(zvars)}",
            color=DISPLAY_COLOR_INFO,
            indent=DISPLAY_INDENT_ZERO,
            style=DISPLAY_STYLE_FULL
        )
        
        max_len: int = max(len(name) for name in zvars.keys())
        
        for name, value in sorted(zvars.items()):
            zos.display.text(
                f"  {name:<{max_len}} => {value}",
                indent=DISPLAY_INDENT_ONE
            )
    
    # Display file shortcuts section
    if shortcuts:
        zos.display.text("")  # Empty line for spacing
        zos.display.zDeclare(
            f"File Shortcuts - {len(shortcuts)}",
            color=DISPLAY_COLOR_INFO,
            indent=DISPLAY_INDENT_ZERO,
            style=DISPLAY_STYLE_FULL
        )
        
        max_len: int = max(len(name) for name in shortcuts.keys())
        
        for name, command in sorted(shortcuts.items()):
            zos.display.text(
                f"  {name:<{max_len}} => {command}",
                indent=DISPLAY_INDENT_ONE
            )
    
    return {
        DICT_KEY_STATUS: STATUS_SUCCESS,
        DICT_KEY_COUNT: total_count
    }


# ============================================================================
# CREATING SHORTCUTS
# ============================================================================

def _is_zvar_syntax(args: List[str]) -> bool:
    """
    Check if shortcut syntax is for zVar (user variable).
    
    Distinguishes between:
    - zVar: Simple name="value" assignment
    - File Shortcut: Interactive cache menu (no = sign, triggers menu)
    
    Args:
        args: List of command arguments
    
    Returns:
        bool: True if creating a zVar, False if creating a file shortcut
    
    Examples:
        >>> _is_zvar_syntax(['myvar="value"'])
        True
        
        >>> _is_zvar_syntax(['myui'])  # Will trigger cache menu
        False
        
        >>> _is_zvar_syntax([])
        False
    
    Notes:
        This function uses a simple heuristic: presence of '=' indicates zVar.
        File shortcuts are created via the interactive cache menu (no = sign).
    """
    if not args:
        return False
    
    full_arg = " ".join(args)
    return "=" in full_arg


def _create_shortcut(
    zos: Any,
    shortcuts: Dict[str, str],
    zvars: Dict[str, str],
    args: List[str]
) -> Dict[str, Any]:
    """
    Create a new shortcut or zVar with comprehensive validation.
    
    Parses definition, validates name and value, and stores in appropriate session dict.
    Automatically detects if creating a zVar (simple value) or file shortcut (command).
    
    Args:
        zos: zOS framework instance for display and session access
        shortcuts: Dictionary of existing file shortcuts (modified in place)
        zvars: Dictionary of existing zVars (modified in place)
        args: List of command arguments (e.g., ['name="value"'])
    
    Returns:
        Dict[str, Any]: Result with status/error and shortcut/zVar metadata
        
    Syntax:
        name="value"      # Creates zVar (user variable)
        name='value'      # Alternative (single quotes)
        
    Validation:
        • Name and value must not be empty
        • Name cannot contain spaces
        • Name cannot be a reserved word (zCLI command)
        • Name cannot be longer than MAX_SHORTCUT_NAME_LENGTH
        • Value cannot recursively reference same name
    
    Examples:
        >>> _create_shortcut(zos, {}, {}, ['myvar="hello"'])
        {"status": "created", "name": "myvar", "value": "hello", "type": "zvar"}
        
        >>> _create_shortcut(zos, {}, {}, ['data="test"'])
        {"error": "reserved_word"}  # 'data' is a zCLI command
        
        >>> _create_shortcut(zos, {}, {"env": "old"}, ['env="new"'])
        # Displays warning: "Overwriting existing zVar: env"
        {"status": "created", "name": "env", "value": "new", "type": "zvar"}
    
    Side Effects:
        Updates zvars or shortcuts dict (passed by reference) and session state.
    
    Notes:
        File shortcuts are created via interactive cache menu (`shortcut cache`),
        not through this function.
    """
    full_arg: str = CHAR_SPACE.join(args)
    
    # Parse: name="value" or name='value'
    if CHAR_EQUALS not in full_arg:
        zos.display.error(MSG_INVALID_SYNTAX)
        return {DICT_KEY_ERROR: ERROR_INVALID_SYNTAX}
    
    parts: List[str] = full_arg.split(CHAR_EQUALS, 1)
    name: str = parts[0].strip()
    value: str = parts[1].strip()
    
    # Remove quotes if present
    if value.startswith(CHAR_QUOTE_DOUBLE) and value.endswith(CHAR_QUOTE_DOUBLE):
        value = value[1:-1]
    elif value.startswith(CHAR_QUOTE_SINGLE) and value.endswith(CHAR_QUOTE_SINGLE):
        value = value[1:-1]
    
    # Validate name
    validation_error: Optional[Dict[str, Any]] = _validate_shortcut_name(
        zos, name, value
    )
    if validation_error:
        return validation_error
    
    # Validate value is not empty
    if not value:
        zos.display.error(MSG_EMPTY_NAME_OR_COMMAND)
        return {DICT_KEY_ERROR: ERROR_EMPTY_NAME_OR_COMMAND}
    
    # Detect if creating a zVar (always true in current implementation since we check for =)
    # zVars are simple name=value assignments
    # File shortcuts are created via `shortcut cache` command
    is_zvar = _is_zvar_syntax(args)
    
    if is_zvar:
        # Warn if overwriting existing zVar
        if name in zvars:
            zos.display.warning(f"Overwriting existing zVar: {name}")
        
        # Create zVar
        zvars[name] = value
        
        zos.display.success(f"zVar '{name}' created: {value}")
        
        return {
            DICT_KEY_STATUS: STATUS_CREATED,
            DICT_KEY_NAME: name,
            "value": value,
            "type": "zvar"
        }
    else:
        # This branch is for file shortcuts (if we ever allow direct creation)
        # Currently, file shortcuts are created via `shortcut cache`
        # Warn if overwriting existing shortcut
        if name in shortcuts:
            zos.display.warning(MSG_OVERWRITING.format(name=name))
        
        # Create file shortcut
        shortcuts[name] = value
        
        zos.display.success(MSG_CREATED.format(name=name, command=value))
        
        return {
            DICT_KEY_STATUS: STATUS_CREATED,
            DICT_KEY_NAME: name,
            DICT_KEY_COMMAND: value,
            "type": "shortcut"
        }


def _validate_shortcut_name(
    zos: Any,
    name: str,
    command: str
) -> Optional[Dict[str, Any]]:
    """
    Validate shortcut name against all rules.
    
    Validation Rules:
        1. Name must not be empty
        2. Name cannot contain spaces
        3. Name cannot exceed MAX_SHORTCUT_NAME_LENGTH
        4. Name cannot be a reserved word (zCLI command)
        5. Name cannot recursively reference itself in command
    
    Args:
        zos: zOS framework instance for display access
        name: Proposed shortcut name
        command: Shortcut command (checked for recursion)
    
    Returns:
        Optional[Dict[str, Any]]: Error dict if validation fails, None if valid
    
    Examples:
        >>> _validate_shortcut_name(zos, "", "git status")
        {"error": "empty_name_or_command"}
        
        >>> _validate_shortcut_name(zos, "my shortcut", "git status")
        {"error": "invalid_name"}
        
        >>> _validate_shortcut_name(zos, "data", "git status")
        {"error": "reserved_word"}
        
        >>> _validate_shortcut_name(zos, "gs", "gs status")
        {"error": "recursive_shortcut"}
        
        >>> _validate_shortcut_name(zos, "gs", "git status")
        None  # Valid
    """
    # Check empty name
    if not name:
        zos.display.error(MSG_EMPTY_NAME_OR_COMMAND)
        return {DICT_KEY_ERROR: ERROR_EMPTY_NAME_OR_COMMAND}
    
    # Check for spaces in name
    if CHAR_SPACE in name:
        zos.display.error(MSG_NAME_CONTAINS_SPACES)
        return {DICT_KEY_ERROR: ERROR_INVALID_NAME}
    
    # Check name length
    if len(name) > MAX_SHORTCUT_NAME_LENGTH:
        zos.display.error(
            MSG_NAME_TOO_LONG.format(max=MAX_SHORTCUT_NAME_LENGTH)
        )
        return {DICT_KEY_ERROR: ERROR_NAME_TOO_LONG}
    
    # Check reserved words
    if name in RESERVED_WORDS:
        zos.display.error(MSG_RESERVED_WORD.format(word=name))
        return {DICT_KEY_ERROR: ERROR_RESERVED_WORD}
    
    # Check for recursive shortcut (name appears in command)
    if name in command.split():
        zos.display.error(MSG_RECURSIVE_SHORTCUT.format(name=name))
        return {DICT_KEY_ERROR: ERROR_RECURSIVE_SHORTCUT}
    
    return None


# ============================================================================
# REMOVING SHORTCUTS
# ============================================================================

def _remove_shortcut(
    zos: Any,
    shortcuts: Dict[str, str],
    zvars: Dict[str, str],
    name: str
) -> Dict[str, Any]:
    """
    Remove an individual shortcut or zVar by name.
    
    Checks both zVars and file shortcuts dicts to find and remove the item.
    
    Args:
        zos: zOS framework instance for display access
        shortcuts: Dictionary of existing file shortcuts (modified in place)
        zvars: Dictionary of existing zVars (modified in place)
        name: Shortcut/zVar name to remove
    
    Returns:
        Dict[str, Any]: Result with status/error and removed item metadata
    
    Examples:
        >>> _remove_shortcut(zos, {"myui": "load..."}, {"env": "dev"}, "env")
        # Displays: "zVar removed: env (was: dev)"
        {"status": "removed", "name": "env", "value": "dev", "type": "zvar"}
        
        >>> _remove_shortcut(zos, {"myui": "load..."}, {}, "myui")
        # Displays: "Shortcut removed: myui (was: load...)"
        {"status": "removed", "name": "myui", "command": "load...", "type": "shortcut"}
        
        >>> _remove_shortcut(zos, {}, {}, "missing")
        # Displays: "Shortcut or zVar not found: missing"
        {"error": "not_found", "name": "missing"}
    
    Side Effects:
        Removes item from zvars or shortcuts dict and updates session state.
    """
    # Check zVars first
    if name in zvars:
        value: str = zvars[name]
        del zvars[name]
        
        zos.display.success(f"zVar removed: {name} (was: {value})")
        
        return {
            DICT_KEY_STATUS: STATUS_REMOVED,
            DICT_KEY_NAME: name,
            "value": value,
            "type": "zvar"
        }
    
    # Check file shortcuts
    if name in shortcuts:
        command: str = shortcuts[name]
        del shortcuts[name]
        
        zos.display.success(MSG_REMOVED.format(name=name, command=command))
        
        return {
            DICT_KEY_STATUS: STATUS_REMOVED,
            DICT_KEY_NAME: name,
            DICT_KEY_COMMAND: command,
            "type": "shortcut"
        }
    
    # Not found in either
    zos.display.error(f"Shortcut or zVar not found: {name}")
    return {DICT_KEY_ERROR: ERROR_NOT_FOUND, DICT_KEY_NAME: name}


def _clear_shortcuts(zos: Any) -> Dict[str, Any]:
    """
    Clear all shortcuts from session.
    
    Args:
        zos: zOS framework instance for session and display access
    
    Returns:
        Dict[str, Any]: Result with status and count of cleared shortcuts
    
    Examples:
        >>> _clear_shortcuts(zos)
        # Displays: "All shortcuts cleared (3 removed)"
        {"status": "cleared", "count": 3}
    
    Side Effects:
        Resets session[SESSION_KEY_SHORTCUTS] to empty dict.
    """
    count: int = len(zos.session.get(SESSION_KEY_SHORTCUTS, {}))
    zos.session[SESSION_KEY_SHORTCUTS] = {}
    
    zos.display.success(MSG_CLEARED.format(count=count))
    return {DICT_KEY_STATUS: STATUS_CLEARED, DICT_KEY_COUNT: count}


# ============================================================================
# PERSISTING SHORTCUTS
# ============================================================================

def _save_shortcuts(
    zos: Any,
    shortcuts: Dict[str, str],
    args: List[str]
) -> Dict[str, Any]:
    """
    Save shortcuts to JSON file for persistence.
    
    Writes shortcuts dictionary to JSON file with pretty-printing (indent=2).
    Creates parent directories if needed. Uses UTF-8 encoding.
    
    Args:
        zos: zOS framework instance for session, config, display access
        shortcuts: Dictionary of shortcuts to save
        args: Optional filename argument [filename]
    
    Returns:
        Dict[str, Any]: Result with status/error, file path, and count
    
    File Path Resolution (V2 contained):
        If no args: default path (SESSION_KEY_ZUSERDATA / "shortcuts.json")
        If args[0]: treated as a *.json filename inside the shortcuts dir.
        Absolute paths / ".." traversal / non-.json names are refused.
        
    Examples:
        >>> _save_shortcuts(zos, {"gs": "git status"}, [])
        # Saves to: ~/.zcli/shortcuts.json (or platform-specific user data dir)
        {"status": "saved", "file": "/home/user/.zcli/shortcuts.json", "count": 1}
        
        >>> _save_shortcuts(zos, {"gs": "git status"}, ["my-shortcuts.json"])
        {"status": "saved", "file": "/home/user/.zcli/my-shortcuts.json", "count": 1}
        
        >>> _save_shortcuts(zos, {"gs": "git status"}, ["../../etc/evil.json"])
        {"error": "path_not_allowed"}  # traversal refused
        
        >>> _save_shortcuts(zos, {}, [])
        # Displays: "No shortcuts to save"
        {"status": "empty"}
    
    Error Handling:
        Catches specific exceptions (PermissionError, IOError) for precise feedback.
    
    Related:
        _get_default_shortcut_file(), _load_shortcuts()
    """
    if not shortcuts:
        zos.display.warning(MSG_NO_SHORTCUTS_TO_SAVE)
        return {DICT_KEY_STATUS: STATUS_EMPTY}
    
    # Determine file path (custom or default) — contained to shortcuts dir
    filepath = _resolve_shortcut_path(zos, args)
    if filepath is None:
        return {DICT_KEY_ERROR: ERROR_PATH_NOT_ALLOWED}
    
    try:
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath, 'w', encoding=FILE_ENCODING_UTF8) as f:
            json.dump(shortcuts, f, indent=JSON_INDENT)
        
        zos.display.success(MSG_SAVED.format(filepath=filepath))
        zos.display.info(MSG_COUNT_INFO.format(count=len(shortcuts)))
        
        return {
            DICT_KEY_STATUS: STATUS_SAVED,
            DICT_KEY_FILE: str(filepath),
            DICT_KEY_COUNT: len(shortcuts)
        }
    except PermissionError as e:
        zos.display.error(MSG_PERMISSION_DENIED.format(error=str(e)))
        return {DICT_KEY_ERROR: ERROR_PERMISSION_DENIED}
    except (IOError, OSError) as e:
        zos.display.error(MSG_SAVE_FAILED.format(error=str(e)))
        return {DICT_KEY_ERROR: ERROR_IO_ERROR}


def _load_shortcuts(zos: Any, args: List[str]) -> Dict[str, Any]:
    """
    Load shortcuts from JSON file and merge with existing shortcuts.
    
    Reads shortcuts from JSON file, validates format, and merges with existing
    shortcuts in session (new shortcuts overwrite existing with same name).
    
    Args:
        zos: zOS framework instance for session, config, display access
        args: Optional filename argument [filename]
    
    Returns:
        Dict[str, Any]: Result with status/error, file path, counts
    
    File Path Resolution (V2 contained):
        If no args: default path (SESSION_KEY_ZUSERDATA / "shortcuts.json")
        If args[0]: treated as a *.json filename inside the shortcuts dir.
        Absolute paths / ".." traversal / non-.json names are refused.
    
    Examples:
        >>> _load_shortcuts(zos, [])
        # Loads from: ~/.zcli/shortcuts.json
        {"status": "loaded", "file": "...", "count": 5, "total": 5}
        
        >>> _load_shortcuts(zos, ["my-shortcuts.json"])
        {"status": "loaded", "file": "/home/user/.zcli/my-shortcuts.json", "count": 3, "total": 8}
        
        >>> _load_shortcuts(zos, ["nonexistent.json"])
        # Displays: "Shortcut file not found: nonexistent.json"
        {"error": "file_not_found"}
    
    Error Handling:
        • Path outside shortcuts dir → ERROR_PATH_NOT_ALLOWED
        • FileNotFoundError → ERROR_FILE_NOT_FOUND
        • json.JSONDecodeError → ERROR_INVALID_JSON
        • Invalid format (not dict) → ERROR_INVALID_FORMAT
        • PermissionError → ERROR_PERMISSION_DENIED
        • Other IOError → ERROR_IO_ERROR
    
    Side Effects:
        Updates session[SESSION_KEY_SHORTCUTS] with validated name->command
        string pairs (merge). Malformed entries are dropped, not merged.
    
    Related:
        _get_default_shortcut_file(), _save_shortcuts()
    """
    # Determine file path (custom or default) — contained to shortcuts dir
    filepath = _resolve_shortcut_path(zos, args)
    if filepath is None:
        return {DICT_KEY_ERROR: ERROR_PATH_NOT_ALLOWED}
    
    try:
        if not filepath.exists():
            zos.display.error(MSG_FILE_NOT_FOUND.format(filepath=filepath))
            return {DICT_KEY_ERROR: ERROR_FILE_NOT_FOUND}
        
        with open(filepath, 'r', encoding=FILE_ENCODING_UTF8) as f:
            loaded_shortcuts: Any = json.load(f)
        
        # Validate format
        if not isinstance(loaded_shortcuts, dict):
            zos.display.error(MSG_INVALID_FORMAT)
            return {DICT_KEY_ERROR: ERROR_INVALID_FORMAT}
        
        # Security (V2): only accept well-formed name->command string pairs.
        # A loaded file is untrusted input; reject non-string keys/values,
        # spaces/oversized names, so it can't inject arbitrary session state.
        clean_shortcuts = {
            k: v for k, v in loaded_shortcuts.items()
            if isinstance(k, str) and isinstance(v, str)
            and k and CHAR_SPACE not in k and len(k) <= MAX_SHORTCUT_NAME_LENGTH
        }
        skipped = len(loaded_shortcuts) - len(clean_shortcuts)
        
        # Initialize shortcuts in session if not exists
        if SESSION_KEY_SHORTCUTS not in zos.session:
            zos.session[SESSION_KEY_SHORTCUTS] = {}
        
        # Merge validated shortcuts with existing
        zos.session[SESSION_KEY_SHORTCUTS].update(clean_shortcuts)
        
        zos.display.success(MSG_LOADED.format(filepath=filepath))
        zos.display.info(MSG_COUNT_ADDED.format(count=len(clean_shortcuts)))
        if skipped:
            zos.display.warning(
                MSG_SKIPPED_ENTRIES.format(count=skipped, suffix="y" if skipped == 1 else "ies")
            )
        
        return {
            DICT_KEY_STATUS: STATUS_LOADED,
            DICT_KEY_FILE: str(filepath),
            DICT_KEY_COUNT: len(clean_shortcuts),
            DICT_KEY_TOTAL: len(zos.session[SESSION_KEY_SHORTCUTS])
        }
    except json.JSONDecodeError:
        zos.display.error(MSG_INVALID_JSON.format(filename=str(filepath)))
        return {DICT_KEY_ERROR: ERROR_INVALID_JSON}
    except PermissionError as e:
        zos.display.error(MSG_PERMISSION_DENIED.format(error=str(e)))
        return {DICT_KEY_ERROR: ERROR_PERMISSION_DENIED}
    except (IOError, OSError) as e:
        zos.display.error(MSG_LOAD_FAILED.format(error=str(e)))
        return {DICT_KEY_ERROR: ERROR_IO_ERROR}


def _get_default_shortcut_file(zos: Any) -> Path:
    """
    Get default shortcut file path (DRY helper).
    
    Resolves to: <user_data_dir>/shortcuts.json
    Creates parent directory if it doesn't exist.
    
    Args:
        zos: zOS framework instance for session and config access
    
    Returns:
        Path: Resolved path to default shortcuts JSON file
    
    Path Resolution:
        1. Check session[SESSION_KEY_ZUSERDATA] (if set)
        2. Fallback to zos.config.sys_paths.user_data_dir
        3. Append FILE_DEFAULT_SHORTCUTS ("shortcuts.json")
    
    Examples:
        >>> _get_default_shortcut_file(zos)
        Path('/home/user/.zcli/shortcuts.json')  # Linux
        
        >>> _get_default_shortcut_file(zos)
        Path('C:/Users/user/AppData/Local/zcli/shortcuts.json')  # Windows
    
    Side Effects:
        Creates user data directory if it doesn't exist.
    
    Related:
        _save_shortcuts(), _load_shortcuts()
    """
    user_data: Path = _shortcut_base_dir(zos)
    user_data.mkdir(parents=True, exist_ok=True)
    return user_data / FILE_DEFAULT_SHORTCUTS


def _shortcut_base_dir(zos: Any) -> Path:
    """Return the single directory shortcut files are allowed to live in.

    This is the containment boundary for ``--save``/``--load``: a custom
    filename is resolved *inside* this directory and may never escape it.
    """
    return Path(
        zos.session.get(
            SESSION_KEY_ZUSERDATA,
            zos.config.sys_paths.user_data_dir,
        )
    )


def _resolve_shortcut_path(zos: Any, args: List[str]) -> Optional[Path]:
    """Resolve a save/load target, contained to the shortcuts directory.

    Security (V2): a custom ``args[0]`` is treated as a *filename within* the
    shortcuts dir — absolute paths, ``..`` traversal, or non-``.json`` names are
    refused (returns ``None`` after displaying an error). No args => default file.
    """
    if not args:
        return _get_default_shortcut_file(zos)

    name = args[0]
    base = _shortcut_base_dir(zos)
    base.mkdir(parents=True, exist_ok=True)
    base = base.resolve()
    candidate = (base / name).resolve()

    contained = candidate == base or base in candidate.parents
    if Path(name).is_absolute() or not contained or candidate.suffix != FILE_EXTENSION_JSON:
        zos.display.error(MSG_PATH_NOT_ALLOWED.format(name=name))
        zos.logger.warning("shortcut path refused (outside shortcuts dir): %s", name)
        return None
    return candidate
