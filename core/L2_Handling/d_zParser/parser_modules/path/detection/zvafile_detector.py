# zOS/core/L2_Handling/g_zParser/parser_modules/path/detection/zvafile_detector.py

"""
zVaFile detection for path package.

Detects zVaFile prefixes (zUI., zSchema., zConfig.) in filenames and path parts.

Public API:
    - is_zvafile_type: Check if filename indicates a zVaFile

Created: Phase 3.2 - Extract Detection from parser_path.py
"""

from zOS import List, Union

# Import constants from shared
from ...shared.file_constants import ZVAFILE_PREFIXES


def is_zvafile_type(filename_or_parts: Union[str, List[str]]) -> bool:
    """
    Check if a filename indicates a zVaFile (zUI., zSchema., zConfig.).
    
    Detects zVaFile prefixes in either a filename string or a list of path parts.
    zVaFiles are special declarative files in zOS with auto-detected extensions.
    
    Args:
        filename_or_parts: Filename string or list of path parts to check
    
    Returns:
        bool: True if filename/parts indicate a zVaFile, False otherwise
    
    Examples:
        >>> is_zvafile_type('zUI.users')
        True
        
        >>> is_zvafile_type('zSchema.database')
        True
        
        >>> is_zvafile_type('zConfig.settings')
        True
        
        >>> is_zvafile_type('script.py')
        False
        
        >>> is_zvafile_type(['config', 'zUI.users', 'main'])
        True
        
        >>> is_zvafile_type(['scripts', 'utils.py'])
        False
    
    Notes:
        - Checks for prefixes: zUI., zSchema., zConfig.
        - For lists, returns True if ANY part has a zVaFile prefix
        - Case-sensitive matching
        - Period (.) after prefix is required
    
    See Also:
        - identify_zFile: File type identification using this function
        - zPath_decoder: Path resolution using this function
    """
    if isinstance(filename_or_parts, list):
        # Check if any part starts with zVaFile prefixes
        for part in filename_or_parts:
            if part.startswith(ZVAFILE_PREFIXES):
                return True
        return False

    # Check filename string
    return filename_or_parts.startswith(ZVAFILE_PREFIXES)
