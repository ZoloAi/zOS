# zOS/core/L2_Handling/g_zParser/parser_modules/path/detection/extension_finder.py

"""
Extension finding for path package.

Finds files by trying supported extensions in priority order.

Public API:
    - find_file_with_extension: Try extensions until file found

Dependencies:
    - os: File existence checking

Created: Phase 3.2 - Extract Detection from parser_path.py
"""

from zOS import os, Any, List, Optional, Tuple

# Import constants from shared
from ...shared.file_constants import LOG_MSG_ZFILE_EXTENSION


def find_file_with_extension(
    base_path: str,
    extensions: List[str],
    logger: Any
) -> Optional[Tuple[str, str]]:
    """
    Try to find file with supported extensions in priority order.
    
    Attempts to locate a file by appending each extension from the list
    and checking for existence. Returns the first match found.
    
    Args:
        base_path: Base file path without extension
        extensions: List of extensions to try (e.g., ['.json', '.yaml'])
        logger: Logger instance for diagnostic output
    
    Returns:
        Optional[Tuple[str, str]]: (found_path, extension) if found, None otherwise
            - found_path: Complete file path with extension
            - extension: Extension that matched
    
    Examples:
        >>> find_file_with_extension('/app/config/zUI.users', ['.json', '.yaml'], logger)
        ('/app/config/zUI.users.yaml', '.yaml')
        
        >>> find_file_with_extension('/app/config/missing', ['.json', '.yaml'], logger)
        None
    
    Notes:
        - Tries extensions in the order provided
        - Returns first match found
        - Uses os.path.exists for validation
        - Logs the matched extension
        - Returns None if no match found
    
    See Also:
        - identify_zFile: Main function using this helper
    """
    for ext in extensions:
        candidate = base_path + ext
        if os.path.exists(candidate):
            logger.debug(LOG_MSG_ZFILE_EXTENSION, ext)
            return candidate, ext

    return None
