# zOS/core/L2_Handling/g_zParser/parser_modules/file/format_parsers/yaml_parser.py

"""
YAML file parsing for file package.

Provides YAML parsing for standard YAML files (.yaml, .yml) using PyYAML library.

Public API:
    - parse_yaml: Main YAML parser

Dependencies:
    - yaml: PyYAML library (standard YAML)

Created: Phase 1.1 - Extract Format Parsers from parser_file.py
Updated: Phase 1.2 - Separated ZLSP parser into zlsp_parser.py
"""

from zOS import yaml, Any, Dict, List, Optional, Union

# Import constants from shared
from ...shared.file_constants import (
    LOG_MSG_YAML_PARSED,
    LOG_MSG_YAML_PARSE_ERROR,
    LOG_MSG_YAML_UNEXPECTED_ERROR,
    STR_N_A
)


def parse_yaml(
    raw_content: Union[str, bytes],
    logger: Any
) -> Optional[Union[Dict[str, Any], List[Any], str, int, float, bool]]:
    """
    Parse YAML content into Python objects with robust error handling.
    
    Uses yaml.safe_load() for secure parsing (prevents code execution).
    Handles all YAML data types: scalars, sequences, mappings.
    
    Args:
        raw_content: Raw YAML content (string or bytes)
        logger: Logger instance for diagnostic output
    
    Returns:
        Optional[Union[Dict, List, str, int, float, bool]]: Parsed YAML object, or None on error
        - Dict: YAML mapping (most common)
        - List: YAML sequence
        - Scalar: str, int, float, bool
        - None: Parse error
    
    Raises:
        No exceptions raised - all errors logged and return None
    
    Examples:
        >>> # .yaml file (standard YAML parsing)
        >>> parse_yaml("port: 8080", logger)
        {"port": 8080}  # int (YAML native)
    
    Error Handling:
        - yaml.YAMLError: Malformed YAML syntax
        - Exception: Unexpected errors (broad catch for safety)
    
    Notes:
        - Uses PyYAML (yaml.safe_load)
        - Logs success with type/keys info
        - Returns None on any parse error
        - For .zolo files, use parse_zlsp instead
    
    Performance:
        O(n) where n = content size
    
    Thread Safety:
        Thread-safe (no shared state)
    
    See Also:
        - parse_file_content: Calls this for YAML files
        - parse_zlsp: ZLSP/Zolo equivalent
        - parse_json: JSON equivalent
    """
    try:
        parsed = yaml.safe_load(raw_content)
        logger.debug(LOG_MSG_YAML_PARSED,
                    type(parsed).__name__,
                    list(parsed.keys()) if isinstance(parsed, dict) else STR_N_A)
        return parsed
    except yaml.YAMLError as e:
        logger.error(LOG_MSG_YAML_PARSE_ERROR, e)
        return None
    except Exception as e:  # pylint: disable=broad-except
        logger.error(LOG_MSG_YAML_UNEXPECTED_ERROR, e)
        return None
