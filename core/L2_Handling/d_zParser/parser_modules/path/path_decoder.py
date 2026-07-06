# zOS/core/L2_Handling/g_zParser/parser_modules/path/path_decoder.py

"""
Main path decoder orchestrator for path package.

Provides the primary entry point for zPath resolution, converting dot-notation
paths to OS-specific file paths with workspace support.

Public API:
    - zPath_decoder: Main path decoder

Dependencies:
    - resolvers: Symbol and zmachine resolution
    - detection: zVaFile type detection
    - extraction: Filename extraction

External Usage:
    - zLoader.py (CRITICAL)
    - zShell/load_executor.py

Created: Phase 3.4 - Create Main Functions from parser_path.py
"""

from zOS import os, Any, Dict, Optional, Tuple

# Import from submodules
from .resolvers import resolve_symbol_path
from .detection import is_zvafile_type
from .extraction import handle_ui_mode_path, extract_filename_from_parts

# Import constants from shared
from ..shared.file_constants import (
    SESSION_KEY_ZSPACE,
    PATH_SEP_DOT,
    FILE_TYPE_ZUI,
    COLOR_SUBLOADER,
    INDENT_PATH,
    STYLE_SINGLE,
    DISPLAY_MSG_PATH_DECODER,
    LOG_MSG_PARTS,
    LOG_MSG_IS_ZVAFILE,
    LOG_MSG_SYMBOL,
    LOG_MSG_ZVAFILE_FULLPATH
)


def zPath_decoder(
    zSession: Dict[str, Any],
    logger: Any,
    zPath: Optional[str] = None,
    zType: Optional[str] = None,
    display: Optional[Any] = None
) -> Tuple[str, str]:
    """
    Resolve dotted paths to file paths with workspace support.
    
    ⚠️ CRITICAL: This function is used externally by zLoader.py and zShell/load_executor.py.
    Signature must remain stable.
    
    Main path decoder that converts dot-notation paths to OS-specific file paths.
    Supports three resolution modes via symbol prefixes:
        - @ (at): Workspace-relative path
        - ~ (tilde): Absolute path from root
        - (none): Relative path from workspace
    
    Handles both zVaFiles (zUI, zSchema, zConfig) and regular files, with
    automatic filename extraction and path component resolution.
    
    Path Format Examples:
        @.config.zUI.users.main → {workspace}/config/zUI.users
        ~.etc.config.zSchema.db.users → /etc/config/zSchema.db
        config.scripts.utils.py → {workspace}/config/scripts/utils.py
    
    Args:
        zSession: Session dictionary containing workspace and file information
                  Expected keys: 'zSpace', 'zVaFolder', 'zVaFile'
        logger: Logger instance for diagnostic output
        zPath: Optional dotted path string to resolve
               If None and zType='zUI', uses session state
        zType: Optional file type hint (e.g., "zUI")
               Triggers UI mode path resolution if zPath is None
        display: Optional display adapter for visual feedback
                 (CLI/Bifrost mode-agnostic)
    
    Returns:
        Tuple[str, str]: (full_path, filename)
            - full_path: Complete OS-specific file path (without extension for zVaFiles)
            - filename: Extracted filename
    
    Examples:
        >>> zSession = {{'zSpace': '/app'}}
        >>> logger = get_logger()
        
        # Workspace-relative zVaFile
        >>> zPath_decoder(zSession, logger, zPath='@.config.zUI.users.main')
        ('/app/config/zUI.users', 'zUI.users')
        
        # Home-relative zVaFile (~ → expanduser; sibling of zMachine)
        >>> zPath_decoder(zSession, logger, zPath='~.etc.config.zSchema.db.users')
        ('/Users/me/etc/config/zSchema.db', 'zSchema.db')
        
        # Relative regular file
        >>> zPath_decoder(zSession, logger, zPath='config.scripts.utils.py')
        ('/app/config/scripts/utils.py', 'utils.py')
        
        # UI mode (from session)
        >>> zSession['zVaFolder'] = 'config.ui'
        >>> zSession['zVaFile'] = 'zUI.users'
        >>> zPath_decoder(zSession, logger, zType='zUI')
        ('/app/config/ui/zUI.users', 'zUI.users')
    
    External Usage:
        zLoader.py (Week 6.9 - CRITICAL):
            full_path, filename = zPath_decoder(zSession, logger, zPath=path)
        Purpose: Resolve file paths before loading UI/Schema/Config files
        
        zShell/load_executor.py:
            full_path, filename = zPath_decoder(zSession, logger, zPath=path)
        Purpose: Shell command path resolution
    
    Notes:
        - Returns tuple of (full_path, filename)
        - full_path does NOT include extension for zVaFiles
        - Workspace defaults to os.getcwd() if not in zSession
        - Logs detailed resolution steps for debugging
        - Display integration allows visual feedback
        - Signature stability is CRITICAL for external usage
    
    See Also:
        - identify_zFile: File identification after path resolution
        - resolve_symbol_path: Symbol-based path resolution helper
        - is_zvafile_type: zVaFile detection
    """
    if display:
        display.zDeclare(DISPLAY_MSG_PATH_DECODER, color=COLOR_SUBLOADER, indent=INDENT_PATH, style=STYLE_SINGLE)

    # Get workspace from session or fall back to current directory
    zSpace = zSession.get(SESSION_KEY_ZSPACE) or os.getcwd()

    # UI mode: resolve from session state
    if not zPath and zType == FILE_TYPE_ZUI:
        zVaFolder_basepath, zFileName = handle_ui_mode_path(zSession, zSpace, logger)
    else:
        # Standard mode: parse dotted path
        if not zPath:
            raise ValueError("zPath is required for standard mode path resolution")
        zPath_parts = zPath.lstrip(PATH_SEP_DOT).split(PATH_SEP_DOT)
        logger.framework.debug(LOG_MSG_PARTS, zPath_parts)

        # Detect if this is a zVaFile path
        is_zvafile = is_zvafile_type(zPath_parts)
        logger.framework.debug(LOG_MSG_IS_ZVAFILE, is_zvafile)

        # Extract filename and relative path components
        zFileName, zRelPath_parts = extract_filename_from_parts(zPath_parts, is_zvafile, logger)

        # Resolve path based on symbol prefix (@, ~, or none)
        symbol = zRelPath_parts[0] if zRelPath_parts else None
        logger.framework.debug(LOG_MSG_SYMBOL, symbol)

        zVaFolder_basepath = resolve_symbol_path(symbol, zRelPath_parts, zSpace, zSession, logger)

    # Combine base path and filename
    zVaFile_fullpath = os.path.join(zVaFolder_basepath, zFileName)
    logger.framework.debug(LOG_MSG_ZVAFILE_FULLPATH, zVaFile_fullpath)

    return zVaFile_fullpath, zFileName
