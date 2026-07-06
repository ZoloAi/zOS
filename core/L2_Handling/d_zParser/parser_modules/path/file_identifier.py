# zOS/core/L2_Handling/g_zParser/parser_modules/path/file_identifier.py

"""
File identification for path package.

Identifies file type and finds actual file path with extension for both
zVaFiles and regular files.

Public API:
    - identify_zFile: Identify file type and find actual file

Dependencies:
    - os: File operations
    - detection: Extension finding and validation

External Usage:
    - zLoader.py (CRITICAL)
    - zShell/load_executor.py

Created: Phase 3.4 - Create Main Functions from parser_path.py
"""

from zOS import os, Any, Optional, Tuple

# Import from submodules
from .detection import (
    is_zvafile_type,
    find_file_with_extension,
    validate_file_exists,
    validate_zvafile_found
)

# Import constants from shared
from ..shared.file_constants import (
    ZVAFILE_PREFIX_UI,
    ZVAFILE_PREFIX_SCHEMA,
    ZVAFILE_PREFIX_CONFIG,
    FILE_TYPE_ZUI,
    FILE_TYPE_ZSCHEMA,
    FILE_TYPE_ZCONFIG,
    FILE_TYPE_ZVAFILE,
    FILE_TYPE_ZOTHER,
    ZVAFILE_EXTENSIONS,
    COLOR_SUBLOADER,
    INDENT_PATH,
    STYLE_SINGLE,
    DISPLAY_MSG_FILE_TYPE_TEMPLATE,
    LOG_MSG_FILE_TYPE,
    LOG_MSG_FILE_TYPE_UNKNOWN,
    LOG_MSG_FILE_TYPE_OTHER
)


def identify_zFile(
    filename: str,
    full_zFilePath: str,
    logger: Any,
    display: Optional[Any] = None
) -> Tuple[str, str]:
    """
    Identify file type and find actual file path with extension.
    
    ⚠️ CRITICAL: This function is used externally by zLoader.py and zShell/load_executor.py.
    Signature must remain stable.
    
    Determines file type (zUI, zSchema, zConfig, zVaFile, zOther) and resolves
    the actual file path with extension. For zVaFiles, auto-detects extension
    by trying .json, .yaml, .yml in order. For regular files, uses provided
    extension and validates file existence.
    
    Args:
        filename: Filename to identify (may be zVaFile or regular file)
        full_zFilePath: Full path without extension (for zVaFiles) or
                       with extension (for regular files)
        logger: Logger instance for diagnostic output
        display: Optional display adapter for visual feedback
                 (CLI/Bifrost mode-agnostic)
    
    Returns:
        Tuple[str, str]: (found_path, extension)
            - found_path: Actual file path with extension
            - extension: File extension (e.g., '.yaml', '.py')
    
    Raises:
        FileNotFoundError: If file cannot be found (zVaFile with no extension
                          match, or regular file does not exist)
    
    Examples:
        >>> logger = get_logger()
        
        # zUI file (extension auto-detected)
        >>> identify_zFile('zUI.users', '/app/config/zUI.users', logger)
        ('/app/config/zUI.users.yaml', '.yaml')
        
        # zSchema file (tries .json, .yaml, .yml)
        >>> identify_zFile('zSchema.db', '/etc/zSchema.db', logger)
        ('/etc/zSchema.db.json', '.json')
        
        # Regular file (extension provided)
        >>> identify_zFile('script.py', '/app/scripts/script.py', logger)
        ('/app/scripts/script.py', '.py')
        
        # File not found
        >>> identify_zFile('missing.yaml', '/app/missing.yaml', logger)
        FileNotFoundError: File not found: /app/missing.yaml
    
    External Usage:
        zLoader.py (Week 6.9 - CRITICAL):
            file_path, ext = identify_zFile(filename, full_path, logger)
        Purpose: Identify file type and find actual file with extension
        
        zShell/load_executor.py:
            file_path, ext = identify_zFile(filename, full_path, logger)
        Purpose: Shell command file identification
    
    Notes:
        - zVaFiles: Tries extensions in order (.zolo, .json, .yaml, .yml)
        - Regular files: Extension already in filename
        - Validates file existence for all types
        - Logs file type and extension for debugging
        - Display integration allows visual feedback
        - Signature stability is CRITICAL for external usage
    
    See Also:
        - zPath_decoder: Path resolution before file identification
        - is_zvafile_type: zVaFile detection
    """
    # Detect if this is a zVaFile
    is_zvafile = is_zvafile_type(filename)

    if is_zvafile:
        # zVaFiles: Auto-detect extension
        # Determine specific type
        if filename.startswith(ZVAFILE_PREFIX_UI):
            logger.debug(LOG_MSG_FILE_TYPE, FILE_TYPE_ZUI)
            zFile_type = FILE_TYPE_ZUI
        elif filename.startswith(ZVAFILE_PREFIX_SCHEMA):
            logger.debug(LOG_MSG_FILE_TYPE, FILE_TYPE_ZSCHEMA)
            zFile_type = FILE_TYPE_ZSCHEMA
        elif filename.startswith(ZVAFILE_PREFIX_CONFIG):
            logger.debug(LOG_MSG_FILE_TYPE, FILE_TYPE_ZCONFIG)
            zFile_type = FILE_TYPE_ZCONFIG
        else:
            logger.debug(LOG_MSG_FILE_TYPE_UNKNOWN)
            zFile_type = FILE_TYPE_ZVAFILE

        # Try to find file with supported extensions
        result = find_file_with_extension(full_zFilePath, ZVAFILE_EXTENSIONS, logger)

        # If no match found, raise error
        if not result:
            validate_zvafile_found(full_zFilePath, logger)

        found_path, zFile_extension = result

    else:
        # Other files: Extension already provided in filename
        logger.debug(LOG_MSG_FILE_TYPE_OTHER)
        zFile_type = FILE_TYPE_ZOTHER

        # Extract extension from filename for display
        _, zFile_extension = os.path.splitext(filename)

        # File path already includes extension
        found_path = full_zFilePath

        # Verify file exists
        validate_file_exists(found_path, logger)

    # Display file type and extension if display available
    if display:
        display.zDeclare(
            DISPLAY_MSG_FILE_TYPE_TEMPLATE.format(zFile_type, zFile_extension),
            color=COLOR_SUBLOADER,
            indent=INDENT_PATH,
            style=STYLE_SINGLE
        )

    return found_path, zFile_extension
