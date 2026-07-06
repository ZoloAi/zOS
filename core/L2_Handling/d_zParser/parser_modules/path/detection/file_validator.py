# zOS/core/L2_Handling/g_zParser/parser_modules/path/detection/file_validator.py

"""
File validation for path package.

Validates file existence and raises appropriate errors.

Public API:
    - validate_file_exists: Check file exists
    - validate_zvafile_found: Validate zVaFile found

Dependencies:
    - os: File existence checking

Created: Phase 3.2 - Extract Detection from parser_path.py
"""

from zOS import os, Any, NoReturn

# Import constants from shared
from ...shared.file_constants import (
    ERROR_MSG_FILE_NOT_FOUND,
    ERROR_MSG_NO_ZVAFILE_FOUND
)


def validate_file_exists(file_path: str, logger: Any) -> None:
    """
    Check if file exists, raise error if not.
    
    Validates file existence and raises FileNotFoundError with
    appropriate error message if file does not exist.
    
    Args:
        file_path: Path to file to validate
        logger: Logger instance for diagnostic output
    
    Raises:
        FileNotFoundError: If file does not exist
    
    Examples:
        >>> validate_file_exists('/app/config/users.yaml', logger)
        # Returns normally if file exists
        
        >>> validate_file_exists('/app/missing.yaml', logger)
        FileNotFoundError: File not found: /app/missing.yaml
    
    Notes:
        - Uses os.path.exists for validation
        - Logs error before raising
        - Appropriate for regular files
    
    See Also:
        - validate_zvafile_found: For zVaFile validation
    """
    if not os.path.exists(file_path):
        msg = ERROR_MSG_FILE_NOT_FOUND.format(file_path)
        logger.error(msg)
        raise FileNotFoundError(msg)


def validate_zvafile_found(base_path: str, logger: Any) -> NoReturn:
    """
    Validate zVaFile found with extensions, raise error if not.
    
    Raises FileNotFoundError for zVaFile that couldn't be found
    with any supported extension (.json, .yaml, .yml).
    
    Args:
        base_path: Base path that was attempted (without extension)
        logger: Logger instance for diagnostic output
    
    Raises:
        FileNotFoundError: If zVaFile not found with any extension
    
    Examples:
        >>> validate_zvafile_found('/app/config/zUI.users', logger)
        FileNotFoundError: No zVaFile found for base path: /app/config/zUI.users (tried .json/.yaml/.yml)
    
    Notes:
        - Specialized error message for zVaFiles
        - Lists attempted extensions in error
        - Logs error before raising
    
    See Also:
        - validate_file_exists: For regular file validation
    """
    msg = ERROR_MSG_NO_ZVAFILE_FOUND.format(base_path)
    logger.error(msg)
    raise FileNotFoundError(msg)
