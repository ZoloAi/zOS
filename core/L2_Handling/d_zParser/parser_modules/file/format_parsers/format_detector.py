# zOS/core/L2_Handling/g_zParser/parser_modules/file/format_parsers/format_detector.py

"""
File format detection for file package.

Provides heuristic-based format detection (JSON vs YAML) from content inspection.

Public API:
    - detect_format: Auto-detect file format from content

Created: Phase 1.1 - Extract Format Parsers from parser_file.py
"""

from zOS import Any, Union

# Import constants from shared
from ...shared.file_constants import (
    FILE_EXT_JSON,
    FILE_EXT_YAML,
    DEFAULT_FORMAT,
    CONTENT_MARKER_JSON_START_BRACE,
    CONTENT_MARKER_JSON_START_BRACKET,
    CONTENT_MARKER_YAML_COLON,
    CONTENT_MARKER_YAML_DASH,
    LOG_MSG_DETECTED_JSON,
    LOG_MSG_DETECTED_YAML,
    LOG_MSG_DEFAULT_YAML
)


def detect_format(
    raw_content: Union[str, bytes],
    logger: Any
) -> str:
    """
    Auto-detect file format (JSON vs YAML) from content inspection.
    
    Heuristic-based detection using first character analysis.
    Falls back to YAML (zOS default) if detection inconclusive.
    
    Detection Logic:
        1. JSON: Starts with {{ or [ (object/array)
        2. YAML: Contains : (mapping) or starts with - (sequence)
        3. Default: YAML (most common in zOS)
    
    Args:
        raw_content: Raw file content (string or bytes)
        logger: Logger instance for diagnostic output
    
    Returns:
        str: Detected format (".json" or ".yaml")
        - ".json": JSON detected
        - ".yaml": YAML detected or default
    
    Examples:
        >>> detect_format('{{"key": "value"}}', logger)
        ".json"
        
        >>> detect_format('key: value', logger)
        ".yaml"
        
        >>> detect_format('- item1', logger)
        ".yaml"
        
        >>> detect_format('ambiguous content', logger)  # Default
        ".yaml"
    
    Notes:
        - Heuristic (not parsing - fast)
        - Trims whitespace before detection
        - YAML is preferred default (zOS convention)
        - Detection is O(1) (first char inspection)
        - Returns extension format (not actual extension)
    
    Limitations:
        - Won't detect YAML scalars (no : or -)
        - Won't detect JSON primitives ("string", 123, true)
        - These cases default to YAML
    
    Performance:
        O(1) - constant time (first char inspection + one linear scan for :)
    
    Thread Safety:
        Thread-safe (no shared state)
    
    See Also:
        - parse_file_content: Calls this when extension not provided
    """
    if not raw_content:
        return DEFAULT_FORMAT

    # Convert bytes to string if needed
    if isinstance(raw_content, bytes):
        raw_content = raw_content.decode('utf-8', errors='ignore')

    # Trim whitespace for detection
    content = raw_content.strip()

    # JSON detection - starts with {{ or [
    if content.startswith(CONTENT_MARKER_JSON_START_BRACE) or \
       content.startswith(CONTENT_MARKER_JSON_START_BRACKET):
        logger.debug(LOG_MSG_DETECTED_JSON)
        return FILE_EXT_JSON

    # YAML detection - contains : or - patterns
    if CONTENT_MARKER_YAML_COLON in content or \
       content.startswith(CONTENT_MARKER_YAML_DASH):
        logger.debug(LOG_MSG_DETECTED_YAML)
        return FILE_EXT_YAML

    # Default to YAML (most common in zolo-zcli)
    logger.debug(LOG_MSG_DEFAULT_YAML)
    return DEFAULT_FORMAT
