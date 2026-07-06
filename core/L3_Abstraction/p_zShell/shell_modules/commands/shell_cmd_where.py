# zOS/core/L3_Abstraction/p_zShell/shell_modules/commands/shell_cmd_where.py

"""
Contextual Shell Prompt Display Management.

This module provides functionality to toggle the display of the current working
directory (zSpace) in the shell prompt using zPath syntax. This gives users
visual context of "where" they are in long interactive sessions.

FEATURE OVERVIEW:
    The 'where' command allows users to control whether their current location
    is displayed in the shell prompt. When enabled, the prompt shows the zPath
    representation of the current working directory, making it easier to maintain
    context during navigation.

PROMPT FORMATS:
    • Default (off):  zOS> 
    • Enabled (on):   zCLI [~.Projects.zolo-zcli]> 

WHY "WHERE"?
    The command name 'where' is intentionally chosen as a natural question word
    that immediately communicates its purpose: "where am I?". It avoids conflicts
    with existing subsystems (zNavigation) and is short, memorable, and intuitive.

ZPATH DISPLAY:
    The location is shown using zPath syntax, which is zCLI's declarative path
    format that replaces filesystem separators with dots:
    
    • Under Home Directory:  ~.Projects.zolo-zcli
    • Workspace Relative:    @.src.components (future enhancement)
    • Absolute Fallback:     /absolute/path/to/dir (if outside home)

COMMAND SYNTAX:
    where [action]
    
    Actions:
        • (no args) or status - Display current mode and settings
        • on                  - Enable zPath display in prompt
        • off                 - Disable zPath display (default)
        • toggle              - Switch between on/off states

SESSION PERSISTENCE:
    The setting is stored in the session dictionary using SESSION_KEY_SHOW_ZPATH_IN_PROMPT
    and persists for the duration of the interactive shell session.

PROMPT FORMAT SPECIFICATION:
    When enabled, the prompt follows this format:
        [PREFIX] [zPath]> 
    
    Example: zCLI [~.Projects.zolo-zcli]> 
    
    Components:
        • PREFIX: "zCLI" (configurable)
        • Brackets: " [" and "]" for clean separation
        • zPath: Current workspace in zPath format
        • Suffix: "> " for command entry

SHELL INTEGRATION:
    This module works in conjunction with shell_interactive.py, which reads
    the session flag to dynamically build the appropriate prompt string.

FUTURE ENHANCEMENTS:
    • Multiple display modes (short, absolute, workspace-relative)
    • Color customization for different path segments
    • Truncation for very long paths
    • Git branch display integration
    • Custom prompt templates

CROSS-SUBSYSTEM DEPENDENCIES:
    • zConfig: SESSION_KEY_ZSPACE for current directory
    • zDisplay: User feedback (info, success, warning messages)
    • shell_interactive.py: Prompt building logic

TYPE SAFETY:
    All functions include comprehensive type hints using types imported from
    the zCLI namespace for consistency across the framework.

ERROR HANDLING:
    Gracefully handles edge cases such as invalid paths, permissions issues,
    and paths outside the home directory.

RELATED COMMANDS:
    • pwd: Displays current working directory (complementary, shows location once)
    • cd: Changes current working directory (updates what 'where' displays)

EXAMPLES:
    >>> where
    # Displays: "Prompt display: OFF (zOS> )"
    
    >>> where on
    # Displays: "Prompt display enabled: zCLI [~.Projects.zolo-zcli]> "
    # Prompt changes from "zOS> " to "zCLI [~.Projects.zolo-zcli]> "
    
    >>> where toggle
    # Switches state and displays new mode
    
    >>> where off
    # Displays: "Prompt display disabled"
    # Prompt returns to "zOS> "

Author: zOS Framework
Version: 1.5.4
Module: zShell (Command Executors - Group A: Basic Terminal Commands)
"""

from zOS import Any, Dict, Optional
from ..shell_paths import format_zpath
from ..executor_constants import KEY_ACTION, KEY_ARGS

# ============================================================================
# MODULE CONSTANTS
# ============================================================================

# Session Keys
SESSION_KEY_SHOW_ZPATH_IN_PROMPT: str = "zShowZPathInPrompt"
SESSION_KEY_ZSPACE: str = "zSpace"

# Actions
ACTION_STATUS: str = "status"
ACTION_ON: str = "on"
ACTION_OFF: str = "off"
ACTION_TOGGLE: str = "toggle"

# Status Codes
STATUS_SUCCESS: str = "success"
STATUS_ENABLED: str = "enabled"
STATUS_DISABLED: str = "disabled"
STATUS_TOGGLED: str = "toggled"

# Error Codes
ERROR_INVALID_ACTION: str = "invalid_action"
ERROR_INVALID_PATH: str = "invalid_path"

# Display Format Constants
PROMPT_PREFIX: str = "zCLI"
PROMPT_SUFFIX: str = "> "
PROMPT_ZPATH_OPEN: str = " ["
PROMPT_ZPATH_CLOSE: str = "]"
ZPATH_HOME_PREFIX: str = "~."
ZPATH_WORKSPACE_PREFIX: str = "@."
ZPATH_SEPARATOR: str = "."

# User Messages
MSG_STATUS_ON: str = "Prompt display: ON"
MSG_STATUS_OFF: str = "Prompt display: OFF"
MSG_CURRENT_FORMAT: str = "Current prompt: {prompt}"
MSG_ENABLED: str = "Prompt display enabled"
MSG_NEW_PROMPT: str = "New prompt: {prompt}"
MSG_DISABLED: str = "Prompt display disabled"
MSG_TOGGLED_ON: str = "Prompt display toggled ON"
MSG_TOGGLED_OFF: str = "Prompt display toggled OFF"
MSG_INVALID_ACTION: str = "Invalid action: {action}. Use: on, off, toggle, or status"

# Dictionary Keys
DICT_KEY_STATUS: str = "status"
DICT_KEY_ERROR: str = "error"
DICT_KEY_ACTION: str = KEY_ACTION  # SSOT: executor_constants
DICT_KEY_MODE: str = "mode"
DICT_KEY_PROMPT: str = "prompt"
DICT_KEY_ZPATH: str = "zpath"
DICT_KEY_ARGS: str = KEY_ARGS  # SSOT: executor_constants


# ============================================================================
# PUBLIC API
# ============================================================================

def execute_where(zos: Any, parsed: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """
    Execute the 'where' command to toggle prompt display of current location.
    
    Main entry point for the where command. Handles four actions:
    - status (default): Show current mode and prompt format
    - on: Enable zPath display in prompt
    - off: Disable zPath display (return to simple prompt)
    - toggle: Switch between on/off states
    
    Args:
        zos: zOS framework instance with session, config, and display access
        parsed: Parsed command dictionary with 'args' and 'options'
    
    Returns:
        Optional[Dict[str, str]]: Error dict if invalid action, None otherwise.
        All success messages are displayed directly to the user.
    
    Command Syntax:
        where           # Show current status
        where status    # Same as no args
        where on        # Enable zPath display
        where off       # Disable zPath display
        where toggle    # Switch current state
    
    Display Output:
        Displays user-friendly messages directly via zos.display.
        See individual action handlers for specific output formats.
    
    Session Integration:
        Reads and writes SESSION_KEY_SHOW_ZPATH_IN_PROMPT boolean flag.
        Reads SESSION_KEY_ZSPACE for current directory path.
    
    Note:
        Shell commands are UI adapters - they display messages directly.
        For programmatic control of the prompt, use session keys directly:
        - Get: zos.session.get("zShowZPathInPrompt", False)
        - Set: zos.session["zShowZPathInPrompt"] = True
    
    Related:
        shell_interactive._get_prompt() reads the session flag to build prompt
    """
    args: list = parsed.get(DICT_KEY_ARGS, [])
    
    # Determine action (default to status if no args)
    action: str = args[0].lower() if args else ACTION_STATUS
    
    # Validate action
    if action not in [ACTION_STATUS, ACTION_ON, ACTION_OFF, ACTION_TOGGLE]:
        zos.display.error(MSG_INVALID_ACTION.format(action=action))
        return {DICT_KEY_ERROR: ERROR_INVALID_ACTION, DICT_KEY_ACTION: action}
    
    # Route to appropriate handler (all return None on success)
    if action == ACTION_STATUS:
        _show_status(zos)
    elif action == ACTION_ON:
        _enable_display(zos)
    elif action == ACTION_OFF:
        _disable_display(zos)
    elif action == ACTION_TOGGLE:
        _toggle_display(zos)
    
    return None


# ============================================================================
# STATUS DISPLAY
# ============================================================================

def _show_status(zos: Any) -> None:
    """
    Display current prompt display mode and preview prompt format.
    
    Shows whether zPath display is currently enabled or disabled, along with
    a preview of what the prompt looks like in the current mode.
    
    Args:
        zos: zOS framework instance for session and display access
    
    Returns:
        None: All output is displayed directly to user
    
    Display Output:
        Prompt display: ON
        Current prompt: zCLI [~.Projects.zolo-zcli]> 
        
        OR
        
        Prompt display: OFF
        Current prompt: zOS> 
    
    Note:
        Shell commands are UI adapters - they display messages directly.
        For programmatic access, use zos.session["zShowZPathInPrompt"] directly.
    """
    current_mode: bool = _get_current_mode(zos)
    prompt_preview: str = _format_prompt_preview(zos, current_mode)
    
    # Display status
    if current_mode:
        zos.display.info(MSG_STATUS_ON)
    else:
        zos.display.info(MSG_STATUS_OFF)
    
    zos.display.text(MSG_CURRENT_FORMAT.format(prompt=prompt_preview), indent=1)


# ============================================================================
# ENABLE/DISABLE ACTIONS
# ============================================================================

def _enable_display(zos: Any) -> None:
    """
    Enable zPath display in the shell prompt.
    
    Sets the session flag to enable zPath display and shows a confirmation
    message with a preview of the new prompt format.
    
    Args:
        zos: zOS framework instance for session and display access
    
    Returns:
        None: All output is displayed directly to user
    
    Side Effects:
        Sets session[SESSION_KEY_SHOW_ZPATH_IN_PROMPT] = True
    
    Display Output:
        Prompt display enabled
        New prompt: zCLI [~.Projects.zolo-zcli]> 
    
    Note:
        Shell commands are UI adapters - they display messages directly.
        For programmatic access, set zos.session["zShowZPathInPrompt"] = True.
    """
    zos.session[SESSION_KEY_SHOW_ZPATH_IN_PROMPT] = True
    
    prompt_preview: str = _format_prompt_preview(zos, enabled=True)
    
    zos.display.success(MSG_ENABLED)
    zos.display.text(MSG_NEW_PROMPT.format(prompt=prompt_preview), indent=1)


def _disable_display(zos: Any) -> None:
    """
    Disable zPath display in the shell prompt.
    
    Clears the session flag to disable zPath display and shows a confirmation
    message with the simple prompt format.
    
    Args:
        zos: zOS framework instance for session and display access
    
    Returns:
        None: All output is displayed directly to user
    
    Side Effects:
        Sets session[SESSION_KEY_SHOW_ZPATH_IN_PROMPT] = False
    
    Display Output:
        Prompt display disabled
        New prompt: zOS> 
    
    Note:
        Shell commands are UI adapters - they display messages directly.
        For programmatic access, set zos.session["zShowZPathInPrompt"] = False.
    """
    zos.session[SESSION_KEY_SHOW_ZPATH_IN_PROMPT] = False
    
    prompt_preview: str = _format_prompt_preview(zos, enabled=False)
    
    zos.display.success(MSG_DISABLED)
    zos.display.text(MSG_NEW_PROMPT.format(prompt=prompt_preview), indent=1)


def _toggle_display(zos: Any) -> None:
    """
    Toggle zPath display between on and off states.
    
    Switches the current mode and displays appropriate confirmation message
    with the new prompt format.
    
    Args:
        zos: zOS framework instance for session and display access
    
    Returns:
        None: All output is displayed directly to user
    
    Side Effects:
        Inverts session[SESSION_KEY_SHOW_ZPATH_IN_PROMPT] boolean value
    
    Display Output:
        Prompt display toggled ON
        New prompt: zCLI [~.Projects.zolo-zcli]> 
        
        OR
        
        Prompt display toggled OFF
        New prompt: zOS> 
    
    Note:
        Shell commands are UI adapters - they display messages directly.
        For programmatic access, toggle zos.session["zShowZPathInPrompt"] directly.
    """
    current_mode: bool = _get_current_mode(zos)
    new_mode: bool = not current_mode
    
    zos.session[SESSION_KEY_SHOW_ZPATH_IN_PROMPT] = new_mode
    
    prompt_preview: str = _format_prompt_preview(zos, enabled=new_mode)
    
    # Display appropriate message
    if new_mode:
        zos.display.success(MSG_TOGGLED_ON)
    else:
        zos.display.success(MSG_TOGGLED_OFF)
    
    zos.display.text(MSG_NEW_PROMPT.format(prompt=prompt_preview), indent=1)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _get_current_mode(zos: Any) -> bool:
    """
    Get current prompt display mode from session.
    
    Args:
        zos: zOS framework instance for session access
    
    Returns:
        bool: True if zPath display is enabled, False otherwise
    
    Examples:
        >>> _get_current_mode(zos)
        False  # Default is disabled
        
        >>> zos.session[SESSION_KEY_SHOW_ZPATH_IN_PROMPT] = True
        >>> _get_current_mode(zos)
        True
    """
    return zos.session.get(SESSION_KEY_SHOW_ZPATH_IN_PROMPT, False)


def _format_prompt_preview(zos: Any, enabled: bool) -> str:
    """
    Format a preview of what the prompt will look like.
    
    Generates the complete prompt string based on the enabled state, including
    the zPath if enabled. This is used for displaying to the user what their
    prompt will look like.
    
    Args:
        zos: zOS framework instance for session access
        enabled: Whether zPath display should be shown
    
    Returns:
        str: Formatted prompt string
    
    Format:
        Disabled: "zOS> "
        Enabled:  "zCLI [~.Projects.zolo-zcli]> "
    
    Examples:
        >>> _format_prompt_preview(zos, enabled=False)
        "zOS> "
        
        >>> _format_prompt_preview(zos, enabled=True)
        "zCLI [~.Projects.zolo-zcli]> "
    """
    if not enabled:
        return PROMPT_PREFIX + PROMPT_SUFFIX
    
    zpath: Optional[str] = format_zpath(fallback_absolute=True)
    if zpath:
        return f"{PROMPT_PREFIX}{PROMPT_ZPATH_OPEN}{zpath}{PROMPT_ZPATH_CLOSE}{PROMPT_SUFFIX}"
    else:
        return PROMPT_PREFIX + PROMPT_SUFFIX


# zPath formatting now lives in shell_modules/shell_paths.format_zpath (SSOT).

