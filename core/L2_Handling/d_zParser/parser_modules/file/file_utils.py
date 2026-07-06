# zOS/core/L2_Handling/g_zParser/parser_modules/file/file_utils.py

"""
File utility functions for file package.

Provides convenience utilities for file loading and parsing in one operation.

Public API:
    - parse_file_by_path: Load and parse file by path

Dependencies:
    - file_parser: Main parsing orchestrator

Created: Phase 1.3 - Create File Utilities from parser_file.py
"""

from zOS import os, Any, Dict, List, Optional, Union

# Import parser
from .file_parser import parse_file_content

# Import constants from shared
from ..shared.file_constants import (
    LOG_MSG_FILE_NOT_FOUND,
    LOG_MSG_FILE_READ_ERROR
)


def parse_file_by_path(
    file_path: str,
    logger: Any
) -> Optional[Union[Dict[str, Any], List[Any], str, int, float, bool]]:
    """
    Load and parse file in one convenient call.
    
    Combines file reading + parsing into a single operation.
    Automatically extracts extension and passes to parse_file_content().
    
    Args:
        file_path: Path to file to load and parse
        logger: Logger instance for diagnostic output
    
    Returns:
        Optional[Union[Dict, List, str, int, float, bool]]: Parsed file content, or None on error
        - Same return type as parse_file_content()
        - None: File not found, read error, or parse error
    
    Raises:
        No exceptions raised - all errors logged and return None
    
    Process:
        1. Check file existence
        2. Extract extension from path
        3. Read file content (UTF-8 encoding)
        4. Delegate to parse_file_content()
    
    Examples:
        >>> parse_file_by_path("/path/to/config.yaml", logger)
        {{"key": "value"}}
        
        >>> parse_file_by_path("/path/to/data.json", logger)
        {{"key": "value"}}
        
        >>> parse_file_by_path("/nonexistent.yaml", logger)
        None
    
    Error Handling:
        - File not found: Logs error, returns None
        - Read error: Logs error, returns None
        - Parse error: Delegated to parse_file_content()
    
    Notes:
        - Uses UTF-8 encoding (zOS standard)
        - Extension extracted via os.path.splitext()
        - All errors logged before returning None
    
    Performance:
        O(n) where n = file size (I/O bound)
    
    Thread Safety:
        Thread-safe (file I/O is atomic)
    
    See Also:
        - parse_file_content: Handles actual parsing
    """
    if not os.path.exists(file_path):
        logger.error(LOG_MSG_FILE_NOT_FOUND, file_path)
        return None

    # Determine extension
    _, ext = os.path.splitext(file_path)

    # Read file via zLoader's raw I/O SSOT (uniform UTF-8 + error handling).
    # Lazy import avoids an L2→L1 import cycle (zLoader imports zParser).
    from zOS.L1_Foundation.c_zLoader.loader_modules import load_file_raw
    try:
        raw_content = load_file_raw(file_path, logger)
    except RuntimeError as e:
        logger.error(LOG_MSG_FILE_READ_ERROR, file_path, e)
        return None

    # Parse content
    return parse_file_content(raw_content, logger, ext)
