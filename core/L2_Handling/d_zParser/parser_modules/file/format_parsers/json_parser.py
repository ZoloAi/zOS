# zOS/core/L2_Handling/g_zParser/parser_modules/file/format_parsers/json_parser.py

"""
JSON file parsing for file package.

Provides standard JSON parsing with robust error handling.

Public API:
    - parse_json: Main JSON parser

Dependencies:
    - json: Python standard library

Created: Phase 1.1 - Extract Format Parsers from parser_file.py
"""

from zOS import json, Any, Dict, List, Optional, Union

# Import constants from shared
from ...shared.file_constants import (
    LOG_MSG_JSON_PARSED,
    LOG_MSG_JSON_PARSE_ERROR,
    LOG_MSG_JSON_UNEXPECTED_ERROR,
    STR_N_A
)


def parse_json(
    raw_content: Union[str, bytes],
    logger: Any,
    file_extension: Optional[str] = None  # pylint: disable=unused-argument
) -> Optional[Union[Dict[str, Any], List[Any], str, int, float, bool]]:
    """
    Parse JSON content into Python objects with robust error handling.
    
    Uses json.loads() for standard JSON parsing.
    Handles all JSON data types: objects, arrays, strings, numbers, booleans, null.
    
    Args:
        raw_content: Raw JSON content (string or bytes)
        logger: Logger instance for diagnostic output
        file_extension: File extension (.json) - currently unused, for API consistency
    
    Returns:
        Optional[Union[Dict, List, str, int, float, bool]]: Parsed JSON object, or None on error
        - Dict: JSON object (most common)
        - List: JSON array
        - Scalar: str, int, float, bool, None
        - None: Parse error
    
    Raises:
        No exceptions raised - all errors logged and return None
    
    Examples:
        >>> parse_json('{"key": "value"}', logger)
        {"key": "value"}
        
        >>> parse_json('[1, 2, 3]', logger)
        [1, 2, 3]
        
        >>> parse_json('{"invalid": }', logger)  # Parse error
        None
    
    Error Handling:
        - json.JSONDecodeError: Malformed JSON syntax
        - Exception: Unexpected errors (broad catch for safety)
    
    Notes:
        - Standard JSON parsing (no format-specific processing)
        - Logs success with type/keys info
        - Returns None on any parse error
    
    Performance:
        O(n) where n = content size
    
    Thread Safety:
        Thread-safe (no shared state)
    
    See Also:
        - parse_file_content: Calls this for JSON files
        - parse_yaml: YAML/Zolo equivalent
    """
    try:
        # Use standard JSON parsing (no format-specific processing)
        parsed = json.loads(raw_content)
        logger.debug(LOG_MSG_JSON_PARSED,
                    type(parsed).__name__,
                    list(parsed.keys()) if isinstance(parsed, dict) else STR_N_A)

        return parsed
    except json.JSONDecodeError as e:
        logger.error(LOG_MSG_JSON_PARSE_ERROR, e)
        return None
    except Exception as e:  # pylint: disable=broad-except
        logger.error(LOG_MSG_JSON_UNEXPECTED_ERROR, e)
        return None
