# zOS/core/L3_Abstraction/p_zShell/shell_modules/commands/shell_cmd_cd.py

"""
Change Directory (cd) and Current Working Directory (cwd/pwd) Command Executors.

This module provides shell commands for directory navigation and inspection
using zCLI's declarative zPath syntax alongside traditional filesystem paths.

OVERVIEW:
    The 'cd' command changes the current OS working directory (via os.chdir()),
    while 'cwd' (alias: 'pwd') displays the current location in both absolute
    and zPath formats. SESSION_KEY_ZSPACE remains constant as the "home base"
    workspace directory (set at shell startup), allowing 'cd @.' to always return
    to the original workspace root.

COMMAND NAMING:
    • cwd: Primary command (Current Working Directory) - modern, semantically accurate
    • pwd: Alias command (Print Working Directory) - Unix compatibility for veteran users
    Both execute the same function but 'cwd' is the preferred modern terminology.

ZPATH SYNTAX:
    zCLI uses a dot-notation path syntax (zPath) that parallels filesystem paths:
    
    • @.path.to.dir       → Workspace-relative (e.g., @.src.components)
    • ~.path.to.dir       → Home-relative (e.g., ~.Projects.zolo-zcli)
    • ~                   → Home directory
    • ..                  → Parent directory
    • .                   → Current directory
    • /absolute/path      → Standard absolute path
    • relative/path       → Standard relative path

COMMAND EXAMPLES:
    cd ~.Projects.zolo-zcli   # Navigate to ~/Projects/zolo-zcli
    cd @.src                  # Navigate to workspace/src
    cd ..                     # Go to parent directory
    cd                        # Go to home directory
    cwd                       # Show current directory in both formats (primary)
    pwd                       # Same as 'cwd' (Unix compatibility alias)

ARCHITECTURE:
    Both commands are UI adapters - they display friendly messages directly
    to the user via zDisplay and return None on success. For programmatic
    directory manipulation, use os.chdir() and os.getcwd() directly.

SESSION INTEGRATION:
    • Reads: SESSION_KEY_ZSPACE for workspace root (constant "home base")
    • Writes: NONE - SESSION_KEY_ZSPACE is immutable during shell session
    • cd command: Uses os.chdir() to change OS working directory
    • pwd/cwd command: Uses os.getcwd() to read current OS directory
    • cd @. behavior: Navigates to SESSION_KEY_ZSPACE (workspace root)
    • Pattern: Uses centralized constants from zConfig.config_session

CROSS-SUBSYSTEM DEPENDENCIES:
    • zConfig: SESSION_KEY_ZSPACE constant, session management
    • zDisplay: User feedback (success, error, info messages)
    • zParser: Future integration for standardized zPath resolution

DISPLAY MODES:
    • Terminal: Shows formatted messages with zDisplay (no JSON output)
    • Bifrost: Same display pattern (WebSocket mode-agnostic)

TYPE SAFETY:
    All functions include comprehensive type hints using types imported from
    the zCLI namespace for consistency across the framework.

ERROR HANDLING:
    Gracefully handles invalid paths, permission errors, non-existent directories,
    and attempts to cd into files. All errors display user-friendly messages.

FUTURE ENHANCEMENTS:
    • cd -: Return to previous directory (history stack)
    • cd bookmarks: Save/restore favorite locations
    • pwd -P: Show physical path (resolve symlinks)
    • Integration with zParser for standardized zPath resolution

RELATED COMMANDS:
    • shell_cmd_ls: List directory contents (uses similar zPath resolution)
    • shell_cmd_where: Toggle prompt display of current location
    • navigation_state: Manages navigation history in UI mode

Author: zOS Framework
Version: 1.5.4
Module: zShell (Command Executors - Group A: Basic Terminal Commands)
"""

from zOS import os, Path, Any, Dict, Optional
from ..shell_paths import resolve_nav_path, format_zpath, ZPATH_HOME
from ..executor_constants import KEY_ARGS

# ============================================================================
# MODULE CONSTANTS
# ============================================================================

# Error Codes
ERROR_INVALID_PATH: str = "invalid_path"
ERROR_DIR_NOT_FOUND: str = "directory_not_found"
ERROR_NOT_A_DIRECTORY: str = "not_a_directory"
ERROR_PERMISSION_DENIED: str = "permission_denied"

# Dictionary Keys
DICT_KEY_ERROR: str = "error"
DICT_KEY_PATH: str = "path"
DICT_KEY_ARGS: str = KEY_ARGS  # SSOT: executor_constants

# User Messages - cd
MSG_CD_SUCCESS: str = "Changed directory to: {path}"
MSG_CD_ERROR_INVALID: str = "Invalid path: {error}"
MSG_CD_ERROR_NOT_FOUND: str = "Directory not found: {path}"
MSG_CD_ERROR_NOT_DIR: str = "Not a directory: {path}"
MSG_CD_ERROR_PERMISSION: str = "Permission denied: {path}"

# User Messages - pwd
MSG_PWD_HEADER: str = "Current Working Directory"
MSG_PWD_ZPATH_PREFIX: str = "(as zPath: {zpath})"

# Display Constants — SSOT: zshell_constants
from ..zshell_constants import (
    COLOR_INFO as DISPLAY_COLOR_INFO,
    STYLE_FULL as DISPLAY_STYLE_FULL,
)
DISPLAY_INDENT_HEADER: int = 0
DISPLAY_INDENT_PATH: int = 1


# ============================================================================
# PUBLIC API
# ============================================================================

def execute_cd(zos: Any, parsed: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """
    Execute cd (change directory) command with zPath support.
    
    Changes the current working directory (session zSpace) to the specified
    target. Supports zPath syntax (@., ~.), traditional paths, and shortcuts
    (., .., ~). Validates the target exists and is a directory before changing.
    
    Args:
        zos: zOS framework instance with session, config, and display access
        parsed: Parsed command dictionary with 'args' and 'options'
    
    Returns:
        Optional[Dict[str, str]]: Error dict if operation fails, None on success.
        Success messages are displayed directly to the user.
    
    Command Syntax:
        cd                        # Go to home directory
        cd ~                      # Go to home directory (explicit)
        cd ~.Projects.zolo-zcli   # Go to ~/Projects/zolo-zcli
        cd @.src.components       # Go to workspace/src/components
        cd ..                     # Go to parent directory
        cd .                      # Stay in current directory
        cd /absolute/path         # Go to absolute path
        cd relative/path          # Go to relative path
    
    zPath Resolution:
        @.path.to.dir → workspace/path/to/dir
        ~.path.to.dir → ~/path/to/dir
        ~             → Home directory
        ..            → Parent of current directory
        .             → Current directory (no change)
    
    Validation:
        • Target path must exist
        • Target must be a directory (not a file)
        • Must have permission to access target
    
    Side Effects:
        Changes OS working directory via os.chdir(). Does NOT modify
        SESSION_KEY_ZSPACE (which remains constant as workspace root).
    
    Examples:
        >>> execute_cd(zos, {"args": ["~.Projects"], "options": {}})
        # Displays: "Changed directory to: /Users/name/Projects"
        # os.getcwd() now returns: /Users/name/Projects
        # Returns: None
        
        >>> execute_cd(zos, {"args": ["nonexistent"], "options": {}})
        # Displays: "Directory not found: /current/path/nonexistent"
        # Returns: {"error": "directory_not_found", "path": "..."}
    
    Note:
        Shell commands are UI adapters - they display messages directly.
        For programmatic directory changes, use os.chdir() directly.
    
    Related:
        execute_pwd(), _resolve_zpath(), shell_interactive._get_prompt()
    """
    args: list = parsed.get(DICT_KEY_ARGS, [])
    
    # Determine target (default to home if no args)
    if not args:
        target = ZPATH_HOME
    else:
        target = args[0]
    
    # Resolve zPath or standard path to absolute Path object
    try:
        resolved: Path = resolve_nav_path(zos, target)
    except (OSError, ValueError, PermissionError) as e:
        zos.display.error(MSG_CD_ERROR_INVALID.format(error=str(e)))
        return {DICT_KEY_ERROR: ERROR_INVALID_PATH}
    
    # Validate target exists
    if not resolved.exists():
        zos.display.error(MSG_CD_ERROR_NOT_FOUND.format(path=resolved))
        return {DICT_KEY_ERROR: ERROR_DIR_NOT_FOUND, DICT_KEY_PATH: str(resolved)}
    
    # Validate target is a directory
    if not resolved.is_dir():
        zos.display.error(MSG_CD_ERROR_NOT_DIR.format(path=resolved))
        return {DICT_KEY_ERROR: ERROR_NOT_A_DIRECTORY, DICT_KEY_PATH: str(resolved)}
    
    # Change OS working directory (does NOT update SESSION_KEY_ZSPACE)
    os.chdir(resolved)
    
    # Display success message
    zos.display.success(MSG_CD_SUCCESS.format(path=resolved))
    
    return None


def execute_pwd(zos: Any, parsed: Dict[str, Any]) -> None:  # pylint: disable=unused-argument
    """
    Execute cwd/pwd (current/print working directory) command with dual format display.
    
    Displays the current OS working directory (from os.getcwd()) in both absolute
    filesystem format and zPath format (if under home directory). Provides users
    with clear context about their current location.
    
    Command Naming:
        This function handles both 'cwd' (primary) and 'pwd' (alias) commands.
        They execute identically - 'cwd' is preferred for modern clarity,
        'pwd' is provided for Unix compatibility.
    
    Args:
        zos: zOS framework instance with session and display access
        parsed: Parsed command dictionary (not used, but required for interface)
    
    Returns:
        None: All output is displayed directly to user
    
    Display Format:
        Current Working Directory
          /Users/name/Projects/zolo-zcli
          (as zPath: ~.Projects.zolo-zcli)
        
        OR (if outside home directory):
        Current Working Directory
          /usr/local/bin
    
    zPath Conversion:
        If current directory is under home, shows zPath format:
        • /Users/name/Projects/zolo-zcli → ~.Projects.zolo-zcli
        • /Users/name → ~ (just home)
        
        If outside home, only shows absolute path.
    
    Session Integration:
        Reads from os.getcwd() for current OS working directory.
        Does NOT read SESSION_KEY_ZSPACE (which is workspace root).
    
    Examples:
        >>> execute_pwd(zos, {"args": [], "options": {}})
        # Works for both 'cwd' and 'pwd' commands
        # Displays formatted output with both path formats
        # Returns: None
    
    Note:
        Shell commands are UI adapters - they display messages directly.
        For programmatic access to current directory, use os.getcwd().
    
    Related:
        execute_cd(), _format_zpath_display(), shell_cmd_where.py
    """
    # Get current OS working directory
    current_dir: str = os.getcwd()
    resolved: Path = Path(current_dir).resolve()
    
    # Display header
    zos.display.zDeclare(
        MSG_PWD_HEADER,
        color=DISPLAY_COLOR_INFO,
        indent=DISPLAY_INDENT_HEADER,
        style=DISPLAY_STYLE_FULL
    )
    
    # Display absolute path
    zos.display.text(f"  {resolved}", indent=DISPLAY_INDENT_PATH)
    
    # Also show as zPath if under home directory
    zpath: Optional[str] = format_zpath(resolved)
    if zpath:
        zos.display.text(
            f"  {MSG_PWD_ZPATH_PREFIX.format(zpath=zpath)}",
            indent=DISPLAY_INDENT_PATH
        )


# Path resolution + zPath formatting now live in shell_modules/shell_paths.py
# (single source of truth shared by cd, ls, where, session, and the runner prompt).
