# zOS/core/L2_Handling/g_zParser/parser_modules/path/resolvers/symbol_resolver.py

"""
Symbol-based path resolution for path package.

Resolves paths based on symbol prefixes (@, ~, or none) for workspace-relative,
absolute, or relative path modes.

Public API:
    - resolve_symbol_path: Resolve @ or ~ symbol paths

Dependencies:
    - os: Path operations

Created: Phase 3.1 - Extract Resolvers from parser_path.py
"""

from zOS import Any, Dict, List, Optional
from zOS.zPath import resolve_base  # SSOT: the base-join rule (dependency-free leaf)

# Import constants from shared
from ...shared.file_constants import (
    SYMBOL_AT,
    SYMBOL_TILDE,
    SESSION_KEY_ZSPACE,
    LOG_MSG_SYMBOL_AT,
    LOG_MSG_SYMBOL_TILDE,
    LOG_MSG_SYMBOL_NONE,
    LOG_MSG_NO_WORKSPACE,
    LOG_MSG_NO_WORKSPACE_HELP,
    LOG_MSG_NO_WORKSPACE_FALLBACK,
    LOG_MSG_ZVAFOLDER_PATH
)


def resolve_symbol_path(
    symbol: Optional[str],
    zRelPath_parts: List[str],
    zSpace: str,
    zSession: Dict[str, Any],
    logger: Any
) -> str:
    """
    Resolve path based on symbol (@, ~, or no symbol).
    
    Internal helper that handles the three path resolution modes:
        - @ (at): Workspace-relative path
        - ~ (tilde): Home-relative path (expanduser); sibling of zMachine
        - (none): Relative path from workspace
    
    Args:
        symbol: Path symbol prefix (SYMBOL_AT, SYMBOL_TILDE, or None)
        zRelPath_parts: List of path components (including symbol if present)
        zSpace: Workspace directory path
        zSession: Session dictionary (for workspace validation)
        logger: Logger instance for diagnostic output
    
    Returns:
        str: Resolved base path
    
    Examples:
        >>> resolve_symbol_path('@', ['@', 'config', 'data'], '/app', {}, logger)
        '/app/config/data'
        
        >>> resolve_symbol_path('~', ['~', 'etc', 'config'], '/app', {}, logger)
        '/Users/me/etc/config'   # ~ → home (expanduser)
        
        >>> resolve_symbol_path(None, ['config', 'data'], '/app', {}, logger)
        '/app/config/data'
    
    Notes:
        - @ symbol: Relative to zSpace in zSession (or cwd)
        - ~ symbol: Home-relative (expanduser); sibling of zMachine, NOT root
        - No symbol: Relative to zSpace (same as @)
        - Logs warnings if @ used without configured workspace
        - Skips first part (symbol) when building path
    
    See Also:
        - zPath_decoder: Main function using this helper
        - zOS.zPath.resolve_base: the dependency-free join primitive (SSOT)
    """
    # Diagnostics + workspace validation stay here (zParser-facing contract);
    # the actual base join is delegated to zOS.zPath so the rule has ONE home.
    if symbol == SYMBOL_AT:
        logger.framework.debug(LOG_MSG_SYMBOL_AT)
        if not zSession.get(SESSION_KEY_ZSPACE):
            logger.warning(LOG_MSG_NO_WORKSPACE)
            logger.warning(LOG_MSG_NO_WORKSPACE_HELP)
            logger.warning(LOG_MSG_NO_WORKSPACE_FALLBACK, zSpace)
    elif symbol == SYMBOL_TILDE:
        logger.framework.debug(LOG_MSG_SYMBOL_TILDE)
    else:
        logger.framework.debug(LOG_MSG_SYMBOL_NONE)

    zVaFolder_basepath = resolve_base(symbol, zRelPath_parts, zSpace)

    if symbol == SYMBOL_AT:
        logger.framework.debug(LOG_MSG_ZVAFOLDER_PATH, zVaFolder_basepath)

    return zVaFolder_basepath
