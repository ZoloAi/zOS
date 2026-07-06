"""
navigation_helpers.py

Shared helper functions for the zNavigation subsystem.

This module provides common utility functions used across multiple navigation
modules to eliminate code duplication and centralize navigation logic.

Architecture:
- DRY helpers extracted during refactoring phases
- Shared across navigation_linking, navigation_breadcrumbs, menu modules, etc.
- Single source of truth for common patterns

Dependencies:
- typing (Python standard library)
- zOS.L1_Foundation.a_zConfig (session keys)

Updated: Navigation subsystem refactoring (Week 1 - Phase 1)
"""

from zOS import Any, Dict, List, Optional
# zPath grammar — Layer-0 SSOT for sigil/segment decomposition.
from zSys import zpath
from zOS.L1_Foundation.a_zConfig.zConfig_modules.config_constants import (
    SESSION_KEY_ZVAFOLDER,
    SESSION_KEY_ZVAFILE,
    SESSION_KEY_ZBLOCK,
)


# ============================================================================
# Display Adapter Helpers
# ============================================================================

def get_display(walker: Optional[Any], zos: Any) -> Any:
    """
    Get appropriate display instance (walker.display or zos.display).
    
    This helper eliminates the repeated pattern of checking for walker and
    falling back to zos.display. Used across navigation modules.
    
    Args:
        walker: Optional walker instance with display attribute
        zos: zOS framework instance
    
    Returns:
        Display instance (walker.display if walker exists, else zos.display)
    
    Example:
        display = get_display(walker, self.zos)
        display.zDeclare("Navigation", color="MENU")
    
    Pattern Replaced:
        walker.display if walker else self.zos.display
    
    Usage Locations:
    - navigation_breadcrumbs.py: _get_display() - 3 call sites
    - navigation_menu_system.py: _get_display() - 5 call sites
    - navigation_linking.py: inline pattern - 4 call sites
    """
    return walker.display if walker else zos.display


# ============================================================================
# Session Management Helpers
# ============================================================================

def get_session_key(session: Dict[str, Any], key: str, default: Any = None) -> Any:
    """
    Safely get a value from session with default fallback.
    
    Provides type-safe session access with consistent default handling.
    
    Args:
        session: Session dictionary from zos.session
        key: Session key to retrieve
        default: Default value if key not found
    
    Returns:
        Value from session or default
    
    Example:
        folder = get_session_key(session, SESSION_KEY_ZVAFOLDER, "@")
        file = get_session_key(session, SESSION_KEY_ZVAFILE, "")
    """
    return session.get(key, default)


def update_session_path(
    session: Dict[str, Any],
    folder: str,
    file: str,
    block: str
) -> None:
    """
    Update session with new file/block path context.
    
    Centralizes the pattern of updating all three path-related session keys
    (folder, file, block) in a single atomic operation.
    
    Args:
        session: Session dictionary to update
        folder: Folder path (e.g., "@", "@.zUI")
        file: File name without extension (e.g., "zUI.main")
        block: Block name (e.g., "MainMenu")
    
    Example:
        update_session_path(session, "@.zUI", "zUI.settings", "NetworkSettings")
    
    Pattern Replaced:
        session[SESSION_KEY_ZVAFOLDER] = folder
        session[SESSION_KEY_ZVAFILE] = file
        session[SESSION_KEY_ZBLOCK] = block
    
    Usage Locations:
    - navigation_linking.py: _update_session_path() - 2 call sites
    - navigation_breadcrumbs.py: _parse_crumb_and_update_session() - 1 call site
    """
    session[SESSION_KEY_ZVAFOLDER] = folder
    session[SESSION_KEY_ZVAFILE] = file
    session[SESSION_KEY_ZBLOCK] = block


# ============================================================================
# Path Formatting Helpers
# ============================================================================

def format_crumb_path(parts: List[str]) -> Dict[str, str]:
    """
    Parse crumb path parts into folder/file/block components.
    
    Handles the common pattern of parsing breadcrumb scope paths like
    "@.zUI.main.MainMenu" into their constituent parts.
    
    Args:
        parts: List of path components split by "."
    
    Returns:
        Dict with keys: folder, file, block
    
    Example:
        parts = "@.zUI.main.MainMenu".split(".")
        result = format_crumb_path(parts)
        # {"folder": "@.zUI", "file": "main", "block": "MainMenu"}
    
    Pattern Replaced:
        # Manual parsing with hardcoded indices
        base_path_parts = parts[:-3]
        folder = ".".join(base_path_parts) if base_path_parts else ""
        file = ".".join(parts[-3:-1])
        block = parts[-1]
    
    Usage Locations:
    - navigation_breadcrumbs.py: _parse_crumb_and_update_session() - 1 call site
    - navigation_linking.py: parse_zLink_expression() - 1 call site
    """
    if len(parts) < 3:
        return {"folder": "", "file": "", "block": parts[-1] if parts else ""}

    # Extract components: base_path.file1.file2.BlockName
    # Last part is block, second-to-last two parts are file
    base_path_parts = parts[:-3]
    folder = ".".join(base_path_parts) if base_path_parts else ""
    file = ".".join(parts[-3:-1])
    block = parts[-1]

    return {"folder": folder, "file": file, "block": block}


def get_active_crumb(session: Dict[str, Any]) -> str:
    """
    Get active breadcrumb from session.
    
    Args
    ----
    session : Dict[str, Any]
        Session dictionary containing breadcrumb state
    
    Returns
    -------
    str
        Active breadcrumb key (last key in reversed trails dict)
    
    Examples
    --------
    Get active crumb::
    
        active = get_active_crumb(session)
        # Returns: "@.zUI.main.MainMenu"
    
    Notes
    -----
    - Returns last key from trails dict (most recent scope)
    - Returns empty string if no trails exist
    - Used by breadcrumb navigation to track current scope
    """
    from zOS.L1_Foundation.a_zConfig.zConfig_modules.config_constants import SESSION_KEY_ZCRUMBS

    crumbs_dict = session.get(SESSION_KEY_ZCRUMBS, {})
    trails = crumbs_dict.get('trails', crumbs_dict)
    return next(reversed(trails)) if trails else ""


def get_crumbs_dict(session: Dict[str, Any]) -> Dict[str, List[str]]:
    """
    Get breadcrumb trails dict from session.
    
    Args
    ----
    session : Dict[str, Any]
        Session dictionary containing breadcrumb state
    
    Returns
    -------
    Dict[str, List[str]]
        Breadcrumb trails dictionary mapping scopes to key lists
    
    Examples
    --------
    Get trails::
    
        trails = get_crumbs_dict(session)
        # Returns: {
        #     "@.zUI.main.MainMenu": ["Dashboard", "Settings"],
        #     "@.zUI.settings.Network": ["Wi-Fi"]
        # }
    
    Notes
    -----
    - Returns trails from enhanced format or legacy format
    - Returns empty dict if no crumbs exist
    - Used by breadcrumb operations for trail management
    """
    from zOS.L1_Foundation.a_zConfig.zConfig_modules.config_constants import SESSION_KEY_ZCRUMBS

    crumbs_dict = session.get(SESSION_KEY_ZCRUMBS, {})
    return crumbs_dict.get('trails', crumbs_dict)


def construct_block_path(folder: str, file: str, block: str) -> str:
    """
    Construct full block path from folder/file/block components.
    
    Inverse operation of format_crumb_path(). Builds a scope path string
    from its constituent parts with proper "@" prefix handling.
    
    Args:
        folder: Folder path (e.g., "@", "@.zUI")
        file: File name without extension
        block: Block name
    
    Returns:
        Full path string (e.g., "@.zUI.main.MainMenu")
    
    Example:
        path = construct_block_path("@.zUI", "main", "MainMenu")
        # Returns: "@.zUI.main.MainMenu"
        
        path = construct_block_path("@", "zUI.test", "zBlock_1")
        # Returns: "@.zUI.test.zBlock_1"
    
    Usage Locations:
    - navigation_breadcrumbs.py: _get_active_block_path() - 3 call sites
    """
    if folder and file:
        if folder.startswith(zpath.SIGIL_WORKSPACE):
            # Folder already carries the workspace sigil ("@" or "@.<folder>").
            return f"{folder}.{file}.{block}"
        else:
            return f"@.{folder}.{file}.{block}"
    elif file:
        return f"{file}.{block}"
    else:
        return block


# ============================================================================
# File Loading Helpers
# ============================================================================

def reload_current_file(walker: Any) -> Dict[str, Any]:
    """
    Reload the current file from session using zLoader.
    
    This helper encapsulates the common pattern of reloading a file based
    on the current session state (zFolder, zFile, zBlock). It handles both
    walker.loader and walker.zcli.loader access patterns.
    
    The loader.handle(None) call triggers session-based file resolution,
    which loads the file currently referenced in the session variables
    (SESSION_KEY_ZVAFOLDER, SESSION_KEY_ZVAFILE).
    
    Args:
        walker: The zWalker instance with loader and session access
    
    Returns:
        Parsed file dictionary with zBlocks as keys
    
    Example:
        # After updating session to point to a new file
        walker.session[SESSION_KEY_ZVAFILE] = 'zUI.zVaF'
        
        # Reload the file to get its parsed content
        zFile_parsed = reload_current_file(walker)
        block_dict = zFile_parsed.get('Hero_Section', {})
    
    Usage Locations:
    - navigation_linking.py: _restore_bounce_back() - reload source after bounce-back
    - navigation_breadcrumbs.py: _reload_file_after_back() - reload after zBack navigation
    
    Pattern Replaced:
        if hasattr(walker, "loader"):
            zFile_parsed = walker.loader.handle(None)
        else:
            zFile_parsed = walker.zcli.loader.handle(None)
    """
    # Handle both walker.loader and walker.zcli.loader access patterns
    if hasattr(walker, "loader"):
        return walker.loader.handle(None)
    else:
        return walker.zcli.loader.handle(None)


# ============================================================================
# Validation Helpers
# ============================================================================

def validate_path_parts(parts: List[str], min_parts: int = 3) -> bool:
    """
    Validate that path parts meet minimum requirements.
    
    Args:
        parts: List of path components
        min_parts: Minimum number of parts required
    
    Returns:
        True if valid, False otherwise
    
    Example:
        parts = "@.zUI.main.MainMenu".split(".")
        if validate_path_parts(parts, 4):
            # Process valid path
    """
    return len(parts) >= min_parts


# Export public API
__all__ = [
    'get_display',
    'get_session_key',
    'update_session_path',
    'format_crumb_path',
    'construct_block_path',
    'reload_current_file',
    'validate_path_parts',
]
