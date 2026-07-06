# zOS/core/L2_Handling/g_zParser/parser_modules/file/transformers/file_type_detector.py

"""
File type detection for file parsing.

Provides detection utilities to identify UI files and Server files from
file paths and extensions, enabling appropriate parsing transformations.

Public API:
    - detect_ui_file: Detect if file is a UI file
    - detect_server_file: Detect if file is a Server routing file

Created: Phase 1.2 - Extract Transformers from parser_file.py
"""

from zOS import Optional

# Import constants from shared
from ...shared.file_constants import (
    FILE_MARKER_ZUI,
    FILE_MARKER_UI_PATH
)


def detect_ui_file(
    file_path: Optional[str] = None,
    file_extension: Optional[str] = None
) -> bool:
    """
    Detect if a file is a UI file based on path and extension markers.
    
    A file is considered a UI file if:
    1. "zUI" appears in the file path (e.g., "zUI.users.yaml")
    2. "/UI/" appears in the directory path (e.g., "/path/to/UI/users.yaml")
    3. "zUI" appears in the file extension (e.g., ".zUI.yaml")
    
    Args:
        file_path: Optional file path for detection
        file_extension: Optional file extension for detection
    
    Returns:
        bool: True if UI file detected, False otherwise
    
    Examples:
        >>> detect_ui_file(file_path="config/zUI.users.yaml")
        True
        
        >>> detect_ui_file(file_path="/app/UI/menu.yaml")
        True
        
        >>> detect_ui_file(file_extension=".zUI.yaml")
        True
        
        >>> detect_ui_file(file_path="config/zSchema.users.yaml")
        False
    
    Notes:
        - Detection uses multiple fallbacks to ensure UI files are identified
        - Case-sensitive marker matching
        - Returns False if both parameters are None
    
    Thread Safety:
        Thread-safe (no shared state)
    
    See Also:
        - parse_file_content: Uses this to determine if RBAC transformation needed
    """
    is_ui_file = False

    if file_path and (FILE_MARKER_ZUI in str(file_path) or FILE_MARKER_UI_PATH in str(file_path)):
        is_ui_file = True
    elif file_extension and (FILE_MARKER_ZUI in file_extension):
        is_ui_file = True

    return is_ui_file


def detect_server_file(
    file_path: Optional[str] = None,
    file_extension: Optional[str] = None
) -> bool:
    """
    Detect if a file is a Server routing file based on path markers.
    
    A file is considered a Server file if:
    1. "zServer" appears in the file path
    2. "zServer" appears in the file extension
    
    Args:
        file_path: Optional file path for detection
        file_extension: Optional file extension for detection
    
    Returns:
        bool: True if Server file detected, False otherwise
    
    Examples:
        >>> detect_server_file(file_path="config/zServer.routing.yaml")
        True
        
        >>> detect_server_file(file_extension=".zServer.yaml")
        True
        
        >>> detect_server_file(file_path="config/zUI.users.yaml")
        False
    
    Notes:
        - Detection for Server routing files (v1.5.4 Phase 2)
        - Case-sensitive marker matching
        - Returns False if both parameters are None
    
    Thread Safety:
        Thread-safe (no shared state)
    
    See Also:
        - parse_file_content: Uses this to apply Server-specific parsing
    """
    is_server_file = False

    if file_path and "zServer" in str(file_path):
        is_server_file = True
    elif file_extension and "zServer" in file_extension:
        is_server_file = True

    return is_server_file
