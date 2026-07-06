# zOS/core/L3_Abstraction/p_zShell/shell_modules/commands/shell_cmd_session.py

"""
Shell Session Management Command System.

This module provides comprehensive session state inspection and manipulation commands
within the zCLI framework. Session commands allow users to view, query, and modify
the session dictionary that maintains global state throughout the CLI session.

Core Features:
    • Display comprehensive session state (info command)
    • Query individual session key values (get command)
    • Set session key-value pairs (set command)
    • Delegates to modernized zDisplay.zSession() for consistent formatting
    • Uses centralized SESSION_KEY_* constants for refactor-proof access
    • Full type safety with comprehensive type hints

Session Structure:
    The zCLI session dictionary contains 17 standardized fields (SESSION_KEY_*):
    
    Core Fields:
        - zS_id: Session identifier
        - zMode: zCLI/zBifrost mode
        - zMachine: OS, Python, CPU, memory info
        - zAuth: Three-tier authentication state
    
    Workspace Fields:
        - zSpace: Current workspace path
        - zVaFolder: Folder containing active zVaFile
        - zVaFile: Active zVaFile name
        - zBlock: Current zBlock
    
    Navigation:
        - zCrumbs: Breadcrumb navigation trail
    
    State:
        - zCache: Cache state (system, pinned, schema, plugin)
        - wizard_mode: Wizard active/inactive + buffer
        - zSpark: zSpark context data
    
    Environment:
        - virtual_env: Virtual environment path
        - system_env: System environment variables
    
    Debug/Internal:
        - zLogger: Logger name
        - zPaginate: zData table pagination-pause on/off
        - logger_instance: Logger instance (internal)

Commands:
    session [info]      - Display core session state (8/17 fields)
                         Default action if no arguments provided
                         Delegates to zos.display.zSession()
                         
    session get <key>   - Display specific session key value
                         Shows formatted key-value pair
                         Returns None on success, uses zDisplay
                         
    session set <key> <value>
                       - Set session key to value
                         Updates session dictionary
                         Shows success confirmation via zDisplay

Usage Examples:
    # View session (default action)
    session
    
    # Explicit info command
    session info
    
    # Get specific key
    session get zMode
    session get zSpace
    
    # Set session value
    session set debug_mode true
    session set custom_key "custom value"

Session Integration:
    Uses centralized session constants from zConfig for safe, refactor-proof access:
        - All 17 SESSION_KEY_* constants imported
        - DICT_KEY_* constants for parser interaction
        - No hardcoded string access to session dictionary

Architecture:
    • execute_session(): Main entry point, delegates to action handlers
    • _show_session_info(): Display comprehensive session state
    • _get_session_key(): Display specific key-value pair
    • _set_session_key(): Update session key with validation
    • _display_key_value(): DRY helper for key-value formatting

UI Adapter Pattern:
    Shell commands act as UI adapters, not programmatic APIs:
    • All functions return None on success
    • Display output directly via zDisplay methods
    • No dict returns ({"success": ...}, {"result": ...})
    • For programmatic access, use session dict directly or subsystems

Type Safety:
    All functions include comprehensive type hints using types imported from
    the zCLI namespace for consistency.

Error Handling & Security:
    • Validates key existence for get operations
    • Protects system-managed keys from modification (PROTECTED_KEYS)
    • Prevents modification of framework-managed keys (FRAMEWORK_KEYS)
    • Shows appropriate error messages via zDisplay.error()
    • Handles missing arguments gracefully
    • No exceptions raised to user

Cross-Subsystem Dependencies:
    • zDisplay: Session display (zSession), feedback (info, success, error, warning)
    • zConfig: Session constants (SESSION_KEY_*), dict key constants
    • zParser: Command parsing (DICT_KEY_ACTION, DICT_KEY_ARGS)

Coverage Note:
    Current "session info" displays 8/17 session fields via zDisplay.zSession().
    Future enhancement (Phase 2): Add sub-commands for remaining fields:
    - session crumbs: Navigation breadcrumbs
    - session cache: Cache state
    - session wizard: Wizard mode + buffer
    - session env: Virtual/system environment
    - session debug: Logger, pagination, internal
    - session list: ALL session keys
    - session all: Comprehensive view

Related:
    • zDisplay.zSession(): Core session display method
    • zConfig.config_session: Session constant definitions
    • zParser.parser_commands: Command parsing infrastructure

Author: zOS Framework
Version: 1.5.4+
"""

from difflib import get_close_matches

from zOS import Any, Dict, List
from ..shell_paths import resolve_zpath_symbol
from ..executor_constants import KEY_ACTION, KEY_ARGS

# Import SESSION_KEY_* constants from zConfig
# NOTE: All constants are used for:
# 1. Key protection validation (PROTECTED_KEYS, FRAMEWORK_KEYS sets)
# 2. Documentation purposes
# 3. Phase 2 enhancements (session crumbs, cache, wizard, env, debug, etc.)
# Some constants appear unused but are referenced in comments and protection sets
from zOS.L1_Foundation.a_zConfig.zConfig_modules.config_constants import (  # noqa: F401
    SESSION_KEY_ZS_ID,
    SESSION_KEY_ZSPACE,
    SESSION_KEY_ZVAFOLDER,
    SESSION_KEY_ZVAFILE,
    SESSION_KEY_ZBLOCK,
    SESSION_KEY_ZMODE,
    SESSION_KEY_ZLOGGER,
    SESSION_KEY_ZPAGINATE,
    SESSION_KEY_ZMACHINE,
    SESSION_KEY_ZVISITOR,
    SESSION_KEY_ZCRUMBS,
    SESSION_KEY_ZCACHE,
    SESSION_KEY_WIZARD_MODE,
    SESSION_KEY_ZSPARK,
    SESSION_KEY_VIRTUAL_ENV,
    SESSION_KEY_SYSTEM_ENV,
    SESSION_KEY_LOGGER_INSTANCE,
    SESSION_KEY_BROWSER,
    SESSION_KEY_IDE
)

# ============================================================================
# MODULE CONSTANTS
# ============================================================================

# Action Constants
ACTION_INFO: str = "info"
ACTION_GET: str = "get"
ACTION_SET: str = "set"

# Dict Key Constants (from parser) — SSOT: executor_constants
DICT_KEY_ACTION: str = KEY_ACTION
DICT_KEY_ARGS: str = KEY_ARGS

# Message Constants
MSG_SESSION_INFO_HEADER: str = "Session Information"
MSG_KEY_VALUE_FORMAT: str = "{key}: {value}"
MSG_SESSION_UPDATED: str = "Session updated: {key} = {value}"
MSG_SESSION_KEY_SET: str = "Set {key} = {value}"
MSG_KEY_NOT_FOUND: str = "Session key '{key}' not found"
MSG_MISSING_KEY_ARG: str = "Missing required argument: key"
MSG_MISSING_VALUE_ARG: str = "Missing required argument: value"
MSG_INVALID_ARGS_GET: str = "Invalid arguments for 'get'. Usage: session get <key>"
MSG_INVALID_ARGS_SET: str = "Invalid arguments for 'set'. Usage: session set <key> <value>"
MSG_UNKNOWN_ACTION: str = "Unknown session command: {action}"

# Display Colors (from zDisplay constants)
COLOR_INFO: str = "CYAN"
COLOR_SUCCESS: str = "GREEN"
COLOR_WARNING: str = "YELLOW"
COLOR_ERROR: str = "RED"

# Minimum argument counts
MIN_ARGS_GET: int = 1
MIN_ARGS_SET: int = 2

# Session Key Protection (for session set validation)
# Protected keys: System constants that should NEVER be modified by users
PROTECTED_KEYS: set = {
    SESSION_KEY_ZS_ID,              # Session ID (auto-generated)
    SESSION_KEY_ZMACHINE,           # Machine config (auto-detected, constant)
    SESSION_KEY_LOGGER_INSTANCE,    # Internal logger object (system-managed)
    SESSION_KEY_SYSTEM_ENV,         # System environment (auto-detected, constant)
    SESSION_KEY_VIRTUAL_ENV,        # Virtual environment path (auto-detected, constant)
}

# Framework-managed keys: Require dedicated commands/subsystems (not raw session set)
FRAMEWORK_KEYS: set = {
    SESSION_KEY_ZVISITOR,              # Auth state (use zAuth commands - future)
    SESSION_KEY_ZCRUMBS,            # Navigation breadcrumbs (managed by zNavigation)
    SESSION_KEY_ZCACHE,             # Cache state (managed by zLoader)
    SESSION_KEY_WIZARD_MODE,        # Wizard mode state (managed by zWizard)
    SESSION_KEY_ZSPARK,             # zSpark context (managed by subsystems)
}

# User-configurable keys: Can be set via session set (paths auto-resolved)
# Note: zVaFolder and zVaFile are user-settable in shell for testing/navigation
# (zWalker will override as needed when active)

# User-configurable keys (allowed via session set):
# NOTE: These are documented here for reference but not enforced as a set.
# Any key NOT in PROTECTED_KEYS or FRAMEWORK_KEYS is allowed.
USER_CONFIGURABLE_KEYS_EXAMPLES: set = {
    SESSION_KEY_ZMODE,              # Execution mode (zCLI/zBifrost)
    SESSION_KEY_ZSPACE,         # Workspace root ("home base" can be changed)
    SESSION_KEY_ZLOGGER,            # Logger level
    SESSION_KEY_ZPAGINATE,          # zData table pagination-pause on/off
    # Plus any custom user-defined keys (anything not in PROTECTED_KEYS or FRAMEWORK_KEYS)
}

# Known session keys for typo detection (frequently used keys)
KNOWN_SESSION_KEYS: set = {
    "browser", "ide", "zMode", "zSpace", "zVaFolder", "zVaFile",
        "zBlock", "zLogger", "zPaginate",
}

# Validation error messages
MSG_PROTECTED_KEY: str = "Cannot modify protected system key: {key}"
MSG_PROTECTED_KEY_HINT: str = "Protected keys are auto-detected system constants and cannot be changed."
MSG_FRAMEWORK_KEY: str = "Cannot modify framework-managed key: {key}"
MSG_FRAMEWORK_KEY_HINT: str = "Use dedicated subsystem commands to manage this field."

# ============================================================================
# MAIN EXECUTION FUNCTION
# ============================================================================

def execute_session(zos: Any, parsed: Dict[str, Any]) -> None:
    """
    Execute session management commands.
    
    Main entry point for all session commands. Delegates to specialized
    action handlers based on the parsed action. Implements the UI adapter
    pattern where all output is displayed via zDisplay and None is returned.
    
    Supported Actions:
        info - Display comprehensive session state (default)
        get  - Display specific session key value
        set  - Update session key value
    
    Args:
        zos: zOS framework instance with access to session, display, logger
        parsed: Parsed command dictionary from zParser containing:
            - action (str): Action to perform (info/get/set)
            - args (List[str]): Command arguments
            - options (Dict): Command options (unused currently)
    
    Returns:
        None: All output via zDisplay (UI adapter pattern)
    
    Examples:
        # Display session info
        >>> execute_session(zos, {"action": "info", "args": [], "options": {}})
        # Displays comprehensive session state via zDisplay.zSession()
        
        # Get specific key
        >>> execute_session(zos, {"action": "get", "args": ["zMode"], "options": {}})
        # Displays: zMode: zCLI
        
        # Set session value
        >>> execute_session(zos, {"action": "set", "args": ["debug", "true"], "options": {}})
        # Displays: Session updated: debug = true
    
    Notes:
        - Uses DICT_KEY_* constants for safe dict access
        - Delegates to action-specific handlers
        - Returns None on success (UI adapter pattern)
        - All errors displayed via zos.display.error()
    """
    action: str = parsed.get(DICT_KEY_ACTION, ACTION_INFO)
    args: List[str] = parsed.get(DICT_KEY_ARGS, [])
    
    # Delegate to action handlers
    if action == ACTION_INFO:
        _show_session_info(zos)
    elif action == ACTION_GET:
        _get_session_key(zos, args)
    elif action == ACTION_SET:
        _set_session_key(zos, args)
    else:
        # Unknown action - display error
        zos.display.error(MSG_UNKNOWN_ACTION.format(action=action))


# ============================================================================
# ACTION HANDLERS
# ============================================================================

def _show_session_info(zos: Any) -> None:
    """
    Display comprehensive session state information.
    
    Delegates to zos.display.zSession() which shows 8/17 core session fields:
    - zSession ID, zMode
    - zMachine (OS, Python, CPU, memory)
    - zAuth (three-tier authentication aware)
    - zSpace, zVaFolder, zVaFile, zBlock
    
    Args:
        zos: zOS framework instance with session and display
    
    Returns:
        None: Output displayed via zDisplay.zSession()
    
    Example:
        >>> _show_session_info(zos)
        # Displays formatted session state in terminal or Bifrost mode
    
    Notes:
        - Uses modernized zDisplay.zSession() for consistent formatting
        - Automatically handles zCLI vs Bifrost mode
        - Shows "Press Enter to continue..." prompt by default
        - For additional session fields, see Phase 2 sub-commands:
          session crumbs, session cache, session wizard, session env,
          session debug, session list, session all
    """
    # Delegate to modernized zDisplay.zSession() for comprehensive display
    zos.display.zSession(zos.session)


def _get_session_key(zos: Any, args: List[str]) -> None:
    """
    Display specific session key value.
    
    Retrieves and displays a single session key-value pair. Shows formatted
    output via zDisplay.info() or error message if key not found.
    
    Args:
        zos: zOS framework instance with session and display
        args: Command arguments, expected: [key]
    
    Returns:
        None: Output displayed via zDisplay
    
    Examples:
        >>> _get_session_key(zos, ["zMode"])
        # Displays: zMode: zCLI
        
        >>> _get_session_key(zos, ["zSpace"])
        # Displays: zSpace: /Users/user/Projects/zolo-zcli
        
        >>> _get_session_key(zos, ["nonexistent"])
        # Displays error: Session key 'nonexistent' not found
    
    Validation:
        - Checks for minimum argument count (1)
        - Validates key existence in session
        - Shows appropriate error messages
    
    Notes:
        - Uses _display_key_value() helper for consistent formatting
        - Returns None on success (UI adapter pattern)
        - For viewing all keys, use "session list" (Phase 2)
    """
    # Validate arguments
    if len(args) < MIN_ARGS_GET:
        zos.display.error(MSG_MISSING_KEY_ARG)
        zos.display.warning(MSG_INVALID_ARGS_GET)
        return
    
    key: str = args[0]
    
    # Check if key exists in session
    if key not in zos.session:
        zos.display.error(MSG_KEY_NOT_FOUND.format(key=key))
        return
    
    # Get value and display
    value: Any = zos.session.get(key)
    _display_key_value(zos, key, value)


def _resolve_path_value(zos: Any, value: str) -> str:
    """
    Resolve zPath notation to absolute filesystem path.
    
    Converts zCLI's dot-notation paths (@., ~., ~zMachine.) to absolute
    filesystem paths. Non-zPath values are returned unchanged.
    
    Args:
        zos: zOS framework instance for session and config access
        value: Path value (may be zPath notation or regular path)
    
    Returns:
        str: Resolved absolute path or original value
    
    Supported Formats:
        @.path.to.dir     → Workspace-relative (from session zSpace)
        ~.path.to.dir     → Home-relative
        ~zMachine.subpath → User data directory paths
        zMachine.subpath  → User data directory paths
        ~                 → Home directory
        /absolute/path    → Unchanged
        regular_value     → Unchanged
    
    Examples:
        >>> _resolve_path_value(zos, "@.Demos")
        '/Users/user/Projects/zolo-zcli/Demos'
        
        >>> _resolve_path_value(zos, "~.Projects")
        '/Users/user/Projects'
        
        >>> _resolve_path_value(zos, "~zMachine.zConfigs")
        '/Users/user/Library/Application Support/zolo-zcli/zConfigs'
        
        >>> _resolve_path_value(zos, "debug_mode")
        'debug_mode'
    """
    # Delegate symbol resolution to the shell zPath SSOT (@. / ~zMachine / ~. / ~).
    # Non-zPath values (plain strings, absolute paths) are returned unchanged so
    # `session set <key> <value>` keeps storing literals verbatim.
    resolved = resolve_zpath_symbol(zos, value)
    return str(resolved) if resolved is not None else value


def _set_session_key(zos: Any, args: List[str]) -> None:
    """
    Set session key to specified value.
    
    Updates a session dictionary key with the provided value. Logs the change
    and displays success confirmation via zDisplay.
    
    Special handling for zSpace: 
    - Preserves zPath notation (@., ~., ~zMachine) for dynamic parser resolution
    - Only resolves plain paths (non-zPath) to absolute paths
    - This maintains semantic meaning (e.g., @.zUIs stays relative to zSpace)
    
    Args:
        zos: zOS framework instance with session, display, logger
        args: Command arguments, expected: [key, value]
    
    Returns:
        None: Output displayed via zDisplay
    
    Examples:
        >>> _set_session_key(zos, ["debug_mode", "true"])
        # Session updated, displays: Set debug_mode = true
        
        >>> _set_session_key(zos, ["custom_key", "custom value"])
        # Session updated, displays: Set custom_key = custom value
        
        >>> _set_session_key(zos, ["incomplete"])
        # Displays error: Missing required argument: value
    
    Validation:
        - Checks for minimum argument count (2)
        - Validates key is not protected (system constants)
        - Validates key is not framework-managed (needs special commands)
        - Shows appropriate error messages
    
    Protected Keys (Cannot be set):
        - SESSION_KEY_ZS_ID: Session ID (auto-generated)
        - SESSION_KEY_ZMACHINE: Machine config (constant)
        - SESSION_KEY_LOGGER_INSTANCE: Internal logger object
        - SESSION_KEY_SYSTEM_ENV: System environment (constant)
        - SESSION_KEY_VIRTUAL_ENV: Virtual environment (constant)
    
    Framework-Managed Keys (Cannot be set):
        - SESSION_KEY_ZVISITOR: Use zAuth commands (future)
        - SESSION_KEY_ZCRUMBS: Managed by zNavigation
        - SESSION_KEY_ZCACHE: Managed by zLoader
        - SESSION_KEY_WIZARD_MODE: Managed by zWizard
        - SESSION_KEY_ZSPARK: Managed by subsystems
    
    User-Configurable Keys (Allowed):
        - SESSION_KEY_ZMODE: Execution mode (zCLI/zBifrost)
        - SESSION_KEY_ZSPACE: Workspace root (auto-resolves zPaths)
        - SESSION_KEY_ZVAFOLDER: Folder containing VaFile (preserves zPaths)
        - SESSION_KEY_ZVAFILE: Current VaFile name
        - SESSION_KEY_ZBLOCK: Current block (can be set for walker/navigation)
        - SESSION_KEY_ZLOGGER: Logger level
        - SESSION_KEY_ZPAGINATE: zData table pagination-pause on/off
        - Custom keys: Any user-defined key not in above sets
    
    Notes:
        - Validates against PROTECTED_KEYS and FRAMEWORK_KEYS sets
        - Only user-configurable and custom keys can be set
        - Logs update via zos.logger.info()
        - Returns None on success (UI adapter pattern)
        - For viewing result, use "session get <key>"
    
    Future Enhancements (Phase 2):
        - Type validation for known SESSION_KEY_* constants
        - Value conversion (str → bool, int, etc.)
        - Special commands for framework-managed keys
    """
    # Validate arguments
    if len(args) < MIN_ARGS_SET:
        if len(args) == 0:
            zos.display.error(MSG_MISSING_KEY_ARG)
        else:
            zos.display.error(MSG_MISSING_VALUE_ARG)
        zos.display.warning(MSG_INVALID_ARGS_SET)
        return
    
    key: str = args[0]
    value: str = args[1]
    
    # Validate key is not protected
    if key in PROTECTED_KEYS:
        zos.display.error(MSG_PROTECTED_KEY.format(key=key))
        zos.display.warning(MSG_PROTECTED_KEY_HINT)
        zos.display.info(f"Protected keys: {', '.join(sorted(PROTECTED_KEYS))}")
        return
    
    # Validate key is not framework-managed
    if key in FRAMEWORK_KEYS:
        zos.display.error(MSG_FRAMEWORK_KEY.format(key=key))
        zos.display.warning(MSG_FRAMEWORK_KEY_HINT)
        zos.display.info(f"Framework-managed keys: {', '.join(sorted(FRAMEWORK_KEYS))}")
        return
    
    # Check for typos in known session keys (fuzzy matching for common mistakes)
    if key not in KNOWN_SESSION_KEYS:
        close_matches = get_close_matches(key, KNOWN_SESSION_KEYS, n=1, cutoff=0.7)
        if close_matches:
            zos.display.warning(f"Did you mean '{close_matches[0]}'? (You typed: '{key}')")
            zos.display.info("Known session keys: " + ", ".join(sorted(KNOWN_SESSION_KEYS)))
            zos.display.text("")
            confirm = input("Continue anyway? (y/n): ").strip().lower()
            if confirm not in ['y', 'yes']:
                zos.display.info("Session set cancelled")
                return
    
    # Special handling for zSpace: resolve zPath notation ONLY if not already zPath
    # (Preserve @., ~., ~zMachine notation for dynamic resolution by parser)
    if key == SESSION_KEY_ZSPACE:
        # Only resolve if it's NOT a zPath - preserve zPath notation for dynamic resolution
        if not any(value.startswith(prefix) for prefix in ["@.", "~.", "~zMachine", "zMachine"]):
            resolved_value = _resolve_path_value(zos, value)
            zos.session[key] = resolved_value
            
            if resolved_value != value:
                zos.logger.info(f"Session updated: {key} = {value} (resolved to: {resolved_value})")
                zos.display.success(f"Set {key} = {resolved_value}")
                zos.display.info(f"(Resolved from: {value})")
            else:
                zos.logger.info(MSG_SESSION_UPDATED.format(key=key, value=value))
                zos.display.success(MSG_SESSION_KEY_SET.format(key=key, value=value))
        else:
            # Store zPath as-is for dynamic resolution
            zos.session[key] = value
            zos.logger.info(MSG_SESSION_UPDATED.format(key=key, value=value))
            zos.display.success(MSG_SESSION_KEY_SET.format(key=key, value=value))
    else:
        # All other keys: store as-is (including zVaFolder with zPath notation)
        zos.session[key] = value
        
        # Log the change
        zos.logger.info(MSG_SESSION_UPDATED.format(key=key, value=value))
        
        # Display success confirmation
        zos.display.success(MSG_SESSION_KEY_SET.format(key=key, value=value))


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _display_key_value(zos: Any, key: str, value: Any) -> None:
    """
    Display session key-value pair in formatted style (DRY helper).
    
    Provides consistent formatting for displaying individual session key-value
    pairs across different commands. Handles value truncation for long values
    and uses zDisplay.info() for output.
    
    Args:
        zos: zOS framework instance with display
        key: Session key name
        value: Session key value (any type)
    
    Returns:
        None: Output displayed via zDisplay.info()
    
    Examples:
        >>> _display_key_value(zos, "zMode", "zCLI")
        # Displays: zMode: zCLI
        
        >>> _display_key_value(zos, "zSpace", "/Users/user/Projects/zolo-zcli")
        # Displays: zSpace: /Users/user/Projects/zolo-zcli
    
    Notes:
        - DRY helper to eliminate duplicate formatting logic
        - Uses MSG_KEY_VALUE_FORMAT constant for consistency
        - Converts value to string representation
        - Future: Add value truncation for very long values
    """
    # Format and display key-value pair
    message: str = MSG_KEY_VALUE_FORMAT.format(key=key, value=value)
    zos.display.info(message)
