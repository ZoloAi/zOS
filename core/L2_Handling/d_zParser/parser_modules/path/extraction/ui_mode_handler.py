# zOS/core/L2_Handling/g_zParser/parser_modules/path/extraction/ui_mode_handler.py

"""
UI mode path handling for path package.

Handles path resolution from session state for UI mode.

Public API:
    - handle_ui_mode_path: Extract path from session state

Dependencies:
    - os: Path operations

Created: Phase 3.3 - Extract Extraction Helpers from parser_path.py
"""

from zOS import os, Any, Dict, Tuple

# Import constants from shared
from ...shared.file_constants import (
    SESSION_KEY_ZVAFOLDER,
    SESSION_KEY_ZVAFILE,
    PATH_SEP_DOT,
    LOG_MSG_ZSPACE,
    LOG_MSG_ZRELPATH,
    LOG_MSG_ZFILENAME,
    LOG_MSG_OS_RELPATH,
    LOG_MSG_ZVAFOLDER_PATH
)


def handle_ui_mode_path(
    zSession: Dict[str, Any],
    zSpace: str,
    logger: Any
) -> Tuple[str, str]:
    """
    Handle UI mode path resolution from session state.
    
    Internal helper for zPath_decoder when no zPath is provided but zType is "zUI".
    Extracts path information from zSession and constructs base path and filename.
    
    Args:
        zSession: Session dictionary containing path information
        zSpace: Workspace directory path
        logger: Logger instance for diagnostic output
    
    Returns:
        Tuple[str, str]: (base_path, filename)
            - base_path: Directory path for the zVaFile
            - filename: Filename of the zVaFile
    
    Notes:
        - Private helper function (not for external use)
        - Extracts zVaFolder and zVaFile from zSession
        - Converts dot notation to OS path separators
        - Logs all intermediate steps for debugging
    
    See Also:
        - zPath_decoder: Main function using this helper
    """
    zVaFolder = zSession.get(SESSION_KEY_ZVAFOLDER) or ""
    zRelPath = (
        zVaFolder.lstrip(PATH_SEP_DOT).split(PATH_SEP_DOT)
        if PATH_SEP_DOT in zVaFolder
        else [zVaFolder]
    )
    zFileName = zSession[SESSION_KEY_ZVAFILE]
    logger.framework.debug(LOG_MSG_ZSPACE, zSpace)
    logger.framework.debug(LOG_MSG_ZRELPATH, zRelPath)
    logger.framework.debug(LOG_MSG_ZFILENAME, zFileName)

    os_RelPath = os.path.join(*zRelPath[1:]) if len(zRelPath) > 1 else ""
    logger.framework.debug(LOG_MSG_OS_RELPATH, os_RelPath)

    zVaFolder_basepath = os.path.join(zSpace, os_RelPath)
    logger.framework.debug(LOG_MSG_ZVAFOLDER_PATH, zVaFolder_basepath)
    return zVaFolder_basepath, zFileName
