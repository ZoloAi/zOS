# zOS/core/L3_Abstraction/p_zShell/shell_modules/commands/shell_cmd_open.py

"""
Open Command Executor for zShell

Provides command-line interface for the zOpen subsystem, enabling users to open
files, URLs, and resources directly from zShell with automatic type detection and
platform-specific handling.

Architecture Position:
    - Tier 2c (Shell Command Executor) within zShell's 4-tier architecture
    - Bridges zShell user commands with zOpen subsystem functionality
    - Part of Group C: zCLI Subsystem Integration commands

Command Syntax:
    open <path>                     # Open file or URL
    open @.README.md                # Open workspace file
    open https://example.com        # Open URL in browser
    open ~/Documents/report.pdf     # Open absolute path file
    open ~zMachine.zUIs             # Open zMachine directory

Integration Flow:
    1. User types: `open <path>` in zShell
    2. zParser parses command → {action: "open", args: [path]}
    3. shell_executor routes to execute_open()
    4. execute_open() validates and delegates to zos.open.handle()
    5. zOpen determines file type (URL vs file) and opens appropriately
    6. Result displayed to user via zDisplay

Supported Targets:
    • URLs: http://, https:// schemes (opened in browser)
    • Files: .py, .md, .txt, .yaml, .json, etc. (opened in IDE/editor)
    • HTML: .html files (opened in browser)
    • Binaries: .pdf, .png, .jpg, etc. (opened in default app)
    • Directories: Opened in file explorer

Features:
    • zPath Notation: Full support for @., ~., ~zMachine prefixes
    • Auto-Detection: Automatic URL vs file detection
    • Platform-Aware: Uses platform-specific tools (macOS open, Linux xdg-open)
    • Browser/IDE Override: Respects session["browser"] and session["ide"]
    • Error Handling: Graceful fallback with helpful error messages
    • Comprehensive Logging: Full debug trail for troubleshooting

Error Handling:
    • Missing Arguments: Shows usage hint and examples
    • Subsystem Unavailable: Detects missing zOpen subsystem
    • Invalid Paths: Validates path format before delegation
    • Open Failures: Captures and displays zOpen subsystem errors

Cross-Subsystem Dependencies:
    • zOpen: Core integration (zos.open.handle())
    • zParser: Command parsing (args extraction)
    • zDisplay: User feedback (error, success, info messages)
    • zSession: Browser/IDE preferences (session["browser"], session["ide"])
    • zLogger: Comprehensive logging (info, warning, error)

UI Adapter Pattern:
    • Returns: None (UI adapter pattern - no return value)
    • Output: All user feedback via zos.display.* methods
    • Success: zos.display.success() with confirmation message
    • Errors: zos.display.error() with specific error details

Design Patterns:
    • Command Pattern: execute_open() as command handler
    • Adapter Pattern: Translates shell commands to zOpen calls
    • Strategy Pattern: zOpen selects appropriate opening strategy
    • Defensive Programming: Validates all inputs and subsystem availability

Reference Patterns:
    • shell_cmd_func.py: Similar validation and error handling flow
    • shell_cmd_load.py: Similar subsystem delegation pattern
    • shell_cmd_walker.py: Similar zPath handling and validation

Examples:
    >>> execute_open(zos, {"args": ["https://github.com"]})
    # Opens GitHub in configured browser (or system default)
    
    >>> execute_open(zos, {"args": ["@.README.md"]})
    # Opens workspace README in configured IDE (or system default)
    
    >>> execute_open(zos, {"args": []})
    # Displays error: "No path provided to open"

Version History:
    - v1.5.4: Initial shell command implementation (basic delegation)
    - v1.5.4+: Industry-grade modernization (full validation, logging, error handling)

Module: zShell (Command Executors - Group C: zCLI Subsystem Integration)
Author: zOS Framework
Version: 1.5.4+
"""

from zOS import Any, Dict, Optional

from ..executor_constants import KEY_ARGS, KEY_OPTIONS

# ═══════════════════════════════════════════════════════════════
# Module Constants
# ═══════════════════════════════════════════════════════════════

# Error Messages
ERROR_NO_ARGS: str = "No path provided to open"
ERROR_NO_OPEN: str = "zOpen subsystem not available"
ERROR_OPEN_FAILED: str = "Failed to open: {path}"
ERROR_INVALID_PATH: str = "Invalid path format: {path}"
ERROR_UNEXPECTED: str = "Unexpected error opening: {path}"

# Success Messages
MSG_OPENED: str = "Opened: {path}"
MSG_OPENING: str = "Opening: {path}"

# Info Messages
MSG_USAGE_HINT: str = "Usage: open <path>"
MSG_EXAMPLES: str = "Examples: open @.README.md | open https://example.com"

# Result Constants (zOpen return values)
RESULT_ZBACK: str = "zBack"    # Success return from zOpen
RESULT_STOP: str = "stop"       # Failure return from zOpen

# Format Templates
TEMPLATE_ZOPEN_CMD: str = "zOpen({path})"

# Dict Keys (parser and result dicts)
# KEY_ARGS / KEY_OPTIONS — SSOT: executor_constants (imported above)
KEY_STATUS: str = "status"
KEY_ERROR: str = "error"
KEY_SUCCESS: str = "success"
KEY_RESULT: str = "result"
KEY_PATH: str = "path"

# Logging Messages
LOG_OPENING: str = "Opening path via zOpen: %s"
LOG_OPEN_SUCCESS: str = "Successfully opened: %s"
LOG_OPEN_FAILED: str = "Failed to open %s: %s"
LOG_SUBSYSTEM_CHECK: str = "Validating zOpen subsystem availability"
LOG_ARGS_VALIDATION: str = "Validating arguments for open command"

# Validation
MIN_ARGS_COUNT: int = 1


# ═══════════════════════════════════════════════════════════════
# Helper Functions
# ═══════════════════════════════════════════════════════════════

def _validate_open_subsystem(zos: Any) -> bool:
    """
    Validate zOpen subsystem is available and functional.
    
    Checks if zos.open exists and has the required handle() method for processing
    open commands. This is defensive programming to ensure subsystem availability
    before attempting to delegate.
    
    Args:
        zos: zOS framework instance with potential open subsystem
    
    Returns:
        bool: True if zOpen is available, False otherwise
    
    Side Effects:
        Logs subsystem check status
        Displays error message if subsystem unavailable
    
    Examples:
        >>> _validate_open_subsystem(zos)
        True  # zOpen available
        
        >>> _validate_open_subsystem(broken_zcli)
        False  # zOpen missing or broken
    """
    zos.logger.debug(LOG_SUBSYSTEM_CHECK)
    
    if not hasattr(zos, "open"):
        zos.logger.error("zOpen subsystem not found in zcli instance")
        zos.display.error(ERROR_NO_OPEN)
        zos.display.info("zOpen subsystem is required for opening files and URLs")
        return False
    
    if not hasattr(zos.open, "handle"):
        zos.logger.error("zOpen subsystem exists but lacks handle() method")
        zos.display.error(ERROR_NO_OPEN)
        zos.display.info("zOpen subsystem is not properly initialized")
        return False
    
    return True


def _validate_args(zos: Any, args: list) -> Optional[str]:
    """
    Validate command arguments and extract path.
    
    Checks that at least one argument (the path to open) was provided. Returns
    the path if valid, or None if validation fails.
    
    Args:
        zos: zOS framework instance for display/logging
        args: Command arguments list from parser
    
    Returns:
        Optional[str]: Extracted path if valid, None if validation fails
    
    Side Effects:
        Logs validation status
        Displays error messages if validation fails
        Shows usage hints and examples on failure
    
    Examples:
        >>> _validate_args(zos, ["@.README.md"])
        "@.README.md"
        
        >>> _validate_args(zos, [])
        None  # Displays error and usage hint
    """
    zos.logger.debug(LOG_ARGS_VALIDATION)
    
    if not args or len(args) < MIN_ARGS_COUNT:
        zos.logger.warning("No arguments provided to open command")
        zos.display.error(ERROR_NO_ARGS)
        zos.display.info(MSG_USAGE_HINT)
        zos.display.info(MSG_EXAMPLES)
        return None
    
    path = args[0]
    
    if not path or not path.strip():
        zos.logger.warning("Empty path provided to open command")
        zos.display.error(ERROR_NO_ARGS)
        zos.display.info(MSG_USAGE_HINT)
        return None
    
    return path.strip()


def _format_zopen_command(path: str) -> str:
    """
    Format path as zOpen() command string.
    
    Constructs the zOpen command format expected by zos.open.handle(). This
    encapsulates the path in the zOpen() wrapper for subsystem processing.
    
    Args:
        path: File path or URL to format
    
    Returns:
        str: Formatted zOpen command string
    
    Examples:
        >>> _format_zopen_command("@.README.md")
        "zOpen(@.README.md)"
        
        >>> _format_zopen_command("https://example.com")
        "zOpen(https://example.com)"
    
    Notes:
        • No escaping needed - zOpen.handle() processes raw paths
        • zPath notation (@., ~., ~zMachine) preserved in formatting
        • URLs passed through unchanged
    """
    return TEMPLATE_ZOPEN_CMD.format(path=path)


def _interpret_open_result(zos: Any, result: str, path: str) -> None:
    """
    Interpret zOpen subsystem result and display appropriate feedback.
    
    Processes the return value from zos.open.handle() and provides user feedback
    via zDisplay. Handles both success (RESULT_ZBACK) and failure (other values)
    cases with appropriate logging and display messages.
    
    Args:
        zos: zOS framework instance for display/logging
        result: Return value from zos.open.handle()
        path: Original path that was opened (for logging/display)
    
    Returns:
        None: Uses UI adapter pattern (no return value)
    
    Side Effects:
        Logs result interpretation
        Displays success message if result == "zBack"
        Displays error message if result != "zBack"
    
    Result Interpretation:
        • "zBack": Open succeeded → display success message
        • "stop": Open failed → display error message
        • Other: Unexpected result → display error with details
    
    Examples:
        >>> _interpret_open_result(zos, "zBack", "@.README.md")
        # Displays: "Opened: @.README.md"
        
        >>> _interpret_open_result(zos, "stop", "invalid.txt")
        # Displays error message
    """
    if result == RESULT_ZBACK:
        zos.logger.info(LOG_OPEN_SUCCESS, path)
        zos.display.success(MSG_OPENED.format(path=path))
    elif result == RESULT_STOP:
        zos.logger.warning(LOG_OPEN_FAILED, path, "zOpen returned 'stop'")
        zos.display.error(ERROR_OPEN_FAILED.format(path=path))
        zos.display.info("The file or URL could not be opened")
    else:
        zos.logger.warning(LOG_OPEN_FAILED, path, f"Unexpected result: {result}")
        zos.display.error(ERROR_OPEN_FAILED.format(path=path))
        zos.display.info(f"zOpen returned unexpected result: {result}")


# ═══════════════════════════════════════════════════════════════
# Main Execution Function
# ═══════════════════════════════════════════════════════════════

def execute_open(zos: Any, parsed: Dict[str, Any]) -> None:
    """
    Execute open command to open files, URLs, or directories.
    
    Main entry point for the 'open' shell command. Validates subsystem availability,
    validates arguments, delegates to zOpen subsystem, and provides user feedback
    via zDisplay. Uses UI adapter pattern (returns None).
    
    Args:
        zos: zOS framework instance with access to:
            - zos.open: zOpen subsystem for opening files/URLs
            - zos.display: zDisplay for user feedback
            - zos.logger: Logger for debug/error output
        parsed: Parsed command dict from zParser containing:
            - "args": List of command arguments (expects [path])
            - "options": Optional dict of command options (future use)
    
    Returns:
        None: UI adapter pattern - all output via zDisplay
    
    Command Flow:
        1. Validate zOpen subsystem availability
        2. Validate command arguments (extract path)
        3. Format path as zOpen() command
        4. Delegate to zos.open.handle()
        5. Interpret result and display feedback
        6. Handle errors gracefully with try-except
    
    Error Handling:
        • No Args: Displays error + usage hint + examples
        • No zOpen: Displays error about missing subsystem
        • Open Failed: Displays error with path details
        • Exception: Catches unexpected errors, logs and displays
    
    Subsystem Integration:
        • zOpen: Determines file type and opening method
        • zParser: Provides parsed command structure
        • zDisplay: All user feedback and error messages
        • zSession: Indirect (zOpen reads browser/IDE preferences)
    
    Examples:
        >>> execute_open(zos, {"args": ["@.README.md"]})
        # Opens README in IDE, displays: "Opened: @.README.md"
        
        >>> execute_open(zos, {"args": ["https://github.com"]})
        # Opens GitHub in browser, displays: "Opened: https://github.com"
        
        >>> execute_open(zos, {"args": []})
        # Displays: "No path provided to open" + usage hint
    
    Notes:
        • UI Adapter Pattern: No return value (all output via zDisplay)
        • zPath Support: Full support for @., ~., ~zMachine notation
        • Type Detection: zOpen automatically detects URLs vs files
        • Platform-Aware: zOpen handles platform-specific opening
        • Browser Override: Respects session["browser"] if set
        • IDE Override: Respects session["ide"] if set
    
    Version: v1.5.4+
    """
    # Validate zOpen subsystem availability
    if not _validate_open_subsystem(zos):
        return
    
    # Extract and validate arguments
    args = parsed.get(KEY_ARGS, [])
    path = _validate_args(zos, args)
    
    if path is None:
        return  # Validation failed, error already displayed
    
    # Log the opening attempt
    zos.logger.info(LOG_OPENING, path)
    
    try:
        # Format path as zOpen command
        zopen_cmd = _format_zopen_command(path)
        
        # Delegate to zOpen subsystem
        result = zos.open.handle(zopen_cmd)
        
        # Interpret and display result
        _interpret_open_result(zos, result, path)
    
    except Exception as e:
        # Catch unexpected errors
        zos.logger.error(LOG_OPEN_FAILED, path, str(e))
        zos.display.error(ERROR_UNEXPECTED.format(path=path))
        zos.display.warning(f"Error details: {str(e)}")
