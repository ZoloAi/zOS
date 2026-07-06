# zOS/core/L2_Handling/g_zParser/parser_modules/path/extraction/filename_extractor.py

"""
Filename extraction for path package.

Extracts filenames and path parts from zPath components for both zVaFiles
and regular files.

Public API:
    - extract_filename_from_parts: Main dispatcher
    - extract_non_zvafile_filename: Extract regular filenames
    - find_filename_start: Find filename start by detecting extensions

Created: Phase 3.3 - Extract Extraction Helpers from parser_path.py
"""

from zOS import Any, List, Tuple

# Import constants from shared
from ...shared.file_constants import (
    SYMBOL_AT,
    SYMBOL_TILDE,
    PATH_SEP_DOT,
    FILE_EXTENSIONS,
    MIN_PARTS_FOR_ZVAFILE,
    FILENAME_PARTS_FOR_SHORT,
    FALLBACK_FILENAME_START,
    LOG_MSG_ZBLOCK,
    LOG_MSG_ZPATH_2_ZFILE,
    LOG_MSG_ZFILENAME_SHORT,
    LOG_MSG_ZRELPATH_PARTS,
    LOG_MSG_NO_ZBLOCK
)


def extract_filename_from_parts(
    zPath_parts: List[str],
    is_zvafile: bool,
    logger: Any
) -> Tuple[str, List[str]]:
    """
    Extract filename and path parts from zPath components.
    
    Internal helper that handles both zVaFile and non-zVaFile extraction logic.
    For zVaFiles, extracts block (last part) and filename (last 2 parts before block).
    For non-zVaFiles, delegates to extract_non_zvafile_filename.
    
    Args:
        zPath_parts: List of dot-separated path components
        is_zvafile: Whether this is a zVaFile path
        logger: Logger instance for diagnostic output
    
    Returns:
        Tuple[str, List[str]]: (filename, relative_path_parts)
            - filename: Extracted filename (may include dots)
            - relative_path_parts: Remaining path components
    
    Notes:
        - Private helper function (not for external use)
        - zVaFile paths have format: path.parts.zUI.filename.block
        - Non-zVaFile paths include extension in filename
        - Logs extraction steps for debugging
    
    See Also:
        - zPath_decoder: Main function using this helper
        - extract_non_zvafile_filename: Non-zVaFile extraction
    """
    if is_zvafile:
        # zVaFile: Extract block (last part) and filename (last 2 parts before block)
        zBlock = zPath_parts[-1]
        logger.framework.debug(LOG_MSG_ZBLOCK, zBlock)

        zPath_2_zFile = zPath_parts[:-1]
        logger.framework.debug(LOG_MSG_ZPATH_2_ZFILE, zPath_2_zFile)

        # Extract file name (last 2 parts, or just last part if only 2 total)
        if len(zPath_2_zFile) == FILENAME_PARTS_FOR_SHORT:
            zFileName = zPath_2_zFile[-1]
        else:
            zFileName = PATH_SEP_DOT.join(zPath_2_zFile[-2:])
        logger.framework.debug(LOG_MSG_ZFILENAME_SHORT, zFileName)

        zRelPath_parts = zPath_parts[:-2]
        logger.framework.debug(LOG_MSG_ZRELPATH_PARTS, zRelPath_parts)
        return zFileName, zRelPath_parts

    # Non-zVaFile: No block extraction, filename includes extension
    logger.framework.debug(LOG_MSG_NO_ZBLOCK)
    return extract_non_zvafile_filename(zPath_parts, logger)


def extract_non_zvafile_filename(
    zPath_parts: List[str],
    logger: Any
) -> Tuple[str, List[str]]:
    """
    Extract filename from non-zVaFile path parts.
    
    Internal helper for extracting regular file names (with extensions) from
    path components. Handles symbol prefixes (@, ~) and finds filename start
    by detecting file extensions.
    
    Args:
        zPath_parts: List of dot-separated path components
        logger: Logger instance for diagnostic output
    
    Returns:
        Tuple[str, List[str]]: (filename, relative_path_parts)
            - filename: Extracted filename with extension
            - relative_path_parts: Remaining path components (including symbols)
    
    Notes:
        - Private helper function (not for external use)
        - Handles @ and ~ symbol prefixes
        - Uses find_filename_start to detect filename boundary
        - Joins parts with dots to form filename
        - Logs extraction results for debugging
    
    See Also:
        - extract_filename_from_parts: Caller function
        - find_filename_start: Helper for finding filename start
    """
    symbol_idx = -1
    if zPath_parts and zPath_parts[0] in [SYMBOL_AT, SYMBOL_TILDE]:
        symbol_idx = 0

    if len(zPath_parts) >= MIN_PARTS_FOR_ZVAFILE:
        filename_start_idx = find_filename_start(zPath_parts, symbol_idx)
        zFileName = PATH_SEP_DOT.join(zPath_parts[filename_start_idx:])
        zRelPath_parts = zPath_parts[:filename_start_idx]
    else:
        zFileName = PATH_SEP_DOT.join(zPath_parts[symbol_idx + 1:] if symbol_idx >= 0 else zPath_parts)
        zRelPath_parts = zPath_parts[:symbol_idx + 1] if symbol_idx >= 0 else []

    logger.framework.debug(LOG_MSG_ZFILENAME_SHORT, zFileName)
    logger.framework.debug(LOG_MSG_ZRELPATH_PARTS, zRelPath_parts)
    return zFileName, zRelPath_parts


def find_filename_start(zPath_parts: List[str], symbol_idx: int) -> int:
    """
    Find where filename starts in path parts by detecting file extensions.
    
    Internal helper that scans path parts backwards to find the start of a
    filename by checking for common file extensions (.py, .js, .yaml, etc.).
    
    Args:
        zPath_parts: List of dot-separated path components
        symbol_idx: Index of symbol prefix (@ or ~), or -1 if none
    
    Returns:
        int: Index where filename starts in zPath_parts
    
    Notes:
        - Private helper function (not for external use)
        - Scans backwards from last part
        - Checks against FILE_EXTENSIONS list (11 common types)
        - Falls back to second-to-last part if no extension detected
        - Respects symbol_idx boundary (doesn't scan before symbol)
    
    See Also:
        - extract_non_zvafile_filename: Caller function
        - FILE_EXTENSIONS: List of supported extensions
    """
    filename_start_idx = -1

    # Scan backwards from the end to find extension boundary
    for i in range(len(zPath_parts) - 1, symbol_idx, -1):
        if i == len(zPath_parts) - 1:
            if i > 0:
                # Check if last 2 parts form a valid filename.extension
                potential_filename = PATH_SEP_DOT.join(zPath_parts[i-1:])
                if any(potential_filename.endswith(ext) for ext in FILE_EXTENSIONS):
                    filename_start_idx = i - 1
                    break

    # Fallback: assume filename starts 2 parts from end (or after symbol)
    if filename_start_idx == -1:
        filename_start_idx = max(symbol_idx + 1, len(zPath_parts) - FALLBACK_FILENAME_START)

    return filename_start_idx
