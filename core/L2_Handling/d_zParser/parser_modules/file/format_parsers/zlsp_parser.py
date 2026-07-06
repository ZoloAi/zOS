# zOS/core/L2_Handling/g_zParser/parser_modules/file/format_parsers/zlsp_parser.py

"""
ZLSP (Zolo Library) file parsing for file package.

Provides parsing for the standalone zolo library format (.zolo) using the zlsp
library. Handles string-first parsing with optional type hints.

Public API:
    - parse_zlsp: Main ZLSP/Zolo parser

Dependencies:
    - zlsp: Standalone zolo library (optional)

Created: Phase 1.1 - Separate ZLSP from YAML parser
"""

from zOS import Any, Dict, List, Optional, Union

# Zolo library integration (optional dependency)
try:
    from zlsp import parser as zolo
    ZOLO_AVAILABLE = True
except ImportError:
    ZOLO_AVAILABLE = False
except Exception:
    ZOLO_AVAILABLE = False

# Import constants from shared
from ...shared.file_constants import (
    LOG_MSG_YAML_PARSED,
    LOG_MSG_YAML_UNEXPECTED_ERROR,
    STR_N_A
)


def parse_zlsp(
    raw_content: Union[str, bytes],
    logger: Any,
    file_path: Optional[str] = None
) -> Optional[Union[Dict[str, Any], List[Any], str, int, float, bool]]:
    """
    Parse ZLSP content into Python objects with robust error handling.
    
    Uses the standalone zolo library for .zolo file parsing with string-first
    approach and optional type hints.
    
    Args:
        raw_content: Raw ZLSP content (string or bytes)
        logger: Logger instance for diagnostic output
        file_path: Optional file path for zolo library context
    
    Returns:
        Optional[Union[Dict, List, str, int, float, bool]]: Parsed ZLSP object, or None on error
        - Dict: ZLSP mapping (most common)
        - List: ZLSP sequence
        - Scalar: str, int, float, bool
        - None: Parse error or zolo library not available
    
    Raises:
        No exceptions raised - all errors logged and return None
    
    Examples:
        >>> # .zolo file (string-first by default)
        >>> parse_zlsp("port: 8080", logger)
        {"port": "8080"}  # str (zolo string-first)
        
        >>> # .zolo file with type hint
        >>> parse_zlsp("port(int): 8080", logger)
        {"port": 8080}  # int (zolo type hint)
    
    Error Handling:
        - Returns None if zolo library not available
        - Logs errors for parse failures
        - Exception: Unexpected errors (broad catch for safety)
    
    Notes:
        - Requires zlsp library to be installed
        - Uses string-first parsing by default
        - Supports type hints for explicit type conversion
        - Logs success with type/keys info
        - Returns None on any parse error
    
    Performance:
        O(n) where n = content size
    
    Thread Safety:
        Thread-safe (no shared state)
    
    See Also:
        - parse_yaml: YAML equivalent
        - parse_file_content: Calls this for .zolo files
    """
    if not ZOLO_AVAILABLE:
        logger.error("ZLSP library not available. Install with: pip install zlsp")
        return None

    # Convert bytes to string if needed
    if isinstance(raw_content, bytes):
        raw_content = raw_content.decode('utf-8', errors='ignore')

    try:
        parsed = zolo.loads(raw_content, filename=file_path)
        logger.debug(LOG_MSG_YAML_PARSED,
                    type(parsed).__name__,
                    list(parsed.keys()) if isinstance(parsed, dict) else STR_N_A)
        return parsed
    except Exception as e:  # pylint: disable=broad-except
        logger.error(LOG_MSG_YAML_UNEXPECTED_ERROR, e)
        return None
