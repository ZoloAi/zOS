# zOS/core/L2_Handling/g_zParser/parser_modules/file/file_parser.py

"""
Main file parser orchestrator for file package.

Provides the primary entry point for file parsing throughout zOS, handling
automatic format detection, UI file detection, RBAC transformation, and
format-specific parsing delegation.

Public API:
    - parse_file_content: Main parser orchestrator

Dependencies:
    - format_parsers: Format-specific parsers (JSON, YAML, detection)
    - transformers: RBAC transformation and file type detection
    - vafile: UI and Server file parsing

External Usage (6 Files):
    - zParser.py (line 150)
    - zLoader.py (line 63)
    - authzRBAC.py
    - auth_session_persistence.py
    - func_args.py
    - load_executor.py

Created: Phase 1.3 - Create Main Orchestrator from parser_file.py
"""

from zOS import Any, Dict, List, Optional, Union

# Import format parsers
from .format_parsers import parse_yaml, parse_zlsp, parse_json, detect_format

# Import transformers
from .transformers import (
    transform_parsed_ui_for_walker,
    detect_ui_file,
    detect_server_file
)

# Import constants from shared
from ..shared.file_constants import (
    FILE_EXT_JSON,
    FILE_EXT_YAML,
    FILE_EXT_YML,
    FILE_EXT_ZOLO,
    DICT_KEY_ZBLOCKS,
    STR_N_A,
    LOG_PREFIX_PARSE,
    LOG_PREFIX_RBAC,
    LOG_MSG_PARSE_CALLED,
    LOG_MSG_EMPTY_CONTENT,
    LOG_MSG_AUTO_DETECTED,
    LOG_MSG_IS_UI_FILE,
    LOG_MSG_DETECTED_UI,
    LOG_MSG_RAW_DATA_KEYS,
    LOG_MSG_PARSED_UI_TYPE,
    LOG_MSG_PARSED_UI_KEYS,
    LOG_MSG_UNSUPPORTED_EXT
)


def parse_file_content(
    raw_content: Union[str, bytes],
    logger: Any,
    file_extension: Optional[str] = None,
    session: Optional[Dict[str, Any]] = None,
    file_path: Optional[str] = None
) -> Optional[Union[Dict[str, Any], List[Any], str, int, float, bool]]:
    """
    Parse raw file content into Python objects with format detection and RBAC transformation.
    
    ⚠️ CRITICAL: This function has 6 external usages. Signature must remain stable.
    
    Main entry point for file parsing throughout zOS. Handles:
    - Automatic format detection (JSON vs YAML vs ZLSP)
    - UI file detection and RBAC transformation
    - Format-specific parsing with error handling
    - zWalker-compatible output transformation
    
    Args:
        raw_content: Raw file content (string or bytes)
        logger: Logger instance for diagnostic output
        file_extension: Optional file extension hint (".json", ".yaml", ".yml", ".zolo")
                       If None, format is auto-detected from content
        session: Optional session dict (passed to parse_ui_file for RBAC context)
        file_path: Optional file path for UI file detection and logging
    
    Returns:
        Optional[Union[Dict, List, str, int, float, bool]]: Parsed data structure, or None on error
        - Dict/List: YAML/JSON objects
        - None: Empty content, parse error, or unsupported format
    
    Raises:
        No exceptions raised - all errors logged and return None
    
    Process Flow:
        1. Check for empty content → return None
        2. Auto-detect format if extension not provided
        3. Check if UI file (via path markers: "zUI", "/UI/")
        4. Route to format-specific parser (JSON or YAML)
        5. If UI file: Apply RBAC transformation via transform_parsed_ui_for_walker()
        6. Return parsed data (transformed if UI, raw otherwise)
    
    UI File Detection:
        A file is considered a UI file if any of:
        - file_path contains "zUI" (e.g., "zUI.users.yaml")
        - file_path contains "/UI/" (e.g., "/path/to/UI/file.yaml")
        - file_extension contains "zUI" (e.g., ".zUI.yaml")
    
    RBAC Transformation (UI Files Only):
        For UI files, the function:
        1. Delegates to vafile.parse_ui_file() for RBAC extraction
        2. Calls transform_parsed_ui_for_walker() to flatten structure
        3. Returns zWalker-compatible format with zRBAC merged
    
    Examples:
        >>> # Parse YAML file
        >>> data = parse_file_content("key: value", logger, ".yaml")
        >>> data
        {{"key": "value"}}
        
        >>> # Parse JSON file
        >>> data = parse_file_content('{{"key": "value"}}', logger, ".json")
        >>> data
        {{"key": "value"}}
        
        >>> # Auto-detect format (JSON)
        >>> data = parse_file_content('{{"key": "value"}}', logger)
        >>> data
        {{"key": "value"}}
        
        >>> # Parse UI file (with RBAC transformation)
        >>> raw = "Menu:\\n  Add: {{zFunc: add}}"
        >>> data = parse_file_content(raw, logger, ".yaml", file_path="zUI.users.yaml")
        >>> data  # Transformed for zWalker
        {{"Menu": {{"Add": {{"zFunc": "add"}}}}}}
        
        >>> # Empty content
        >>> data = parse_file_content("", logger)
        >>> data
        None
    
    External Usage (6 Files):
        1. zParser.py (line 150): parse_file_content(raw_content, self.logger, file_extension, session, file_path)
        2. zLoader.py (line 63): self.parse_file_content(zFile_raw, zFile_extension, session, file_path)
        3. authzRBAC.py: parse_file_content(raw_content, logger, ".yaml")
        4. auth_session_persistence.py: parse_file_content(raw_content, logger)
        5. func_args.py: parse_file_content(raw_content, logger, ".yaml")
        6. load_executor.py: parse_file_content(raw_content, logger, ext)
    
    Notes:
        - Empty content returns None (not an error - valid use case)
        - Unsupported extensions log error and return None
        - YAML is default format (zOS convention)
        - Format detection is heuristic (first char inspection)
        - RBAC transformation only for UI files (not schema/config)
        - Session parameter reserved for future session-aware parsing
    
    Performance:
        - O(1) for format detection
        - O(n) for YAML/JSON parsing (n = content size)
        - O(m) for RBAC transformation (m = number of UI items)
    
    Thread Safety:
        Thread-safe (no shared state, logger passed as parameter)
    
    See Also:
        - parse_yaml: YAML-specific parsing
        - parse_zlsp: ZLSP/Zolo-specific parsing
        - parse_json: JSON-specific parsing
        - detect_format: Auto-detection logic
        - transform_parsed_ui_for_walker: RBAC transformation
        - vafile.parse_ui_file: UI file RBAC extraction
    """
    logger.framework.debug(f"{LOG_PREFIX_PARSE} {LOG_MSG_PARSE_CALLED}", file_extension)

    if not raw_content:
        logger.warning(LOG_MSG_EMPTY_CONTENT)
        return None

    # Auto-detect format if no extension provided
    if not file_extension:
        file_extension = detect_format(raw_content, logger)
        logger.debug(LOG_MSG_AUTO_DETECTED, file_extension)

    # Check if this is a UI file or Server file
    is_ui_file = detect_ui_file(file_path, file_extension)
    is_server_file = detect_server_file(file_path, file_extension)

    logger.framework.debug(f"{LOG_PREFIX_PARSE} {LOG_MSG_IS_UI_FILE}", is_ui_file, file_extension, file_path)

    # Route to appropriate parser
    if file_extension == FILE_EXT_JSON:
        return parse_json(raw_content, logger, file_extension)
    elif file_extension == FILE_EXT_ZOLO:
        data = parse_zlsp(raw_content, logger, file_path)
    elif file_extension in [FILE_EXT_YAML, FILE_EXT_YML] or "yaml" in file_extension.lower():
        data = parse_yaml(raw_content, logger)
    else:
        logger.error(LOG_MSG_UNSUPPORTED_EXT, file_extension)
        return None

    # Apply UI-specific parsing (RBAC extraction) if this is a UI file
    if is_ui_file and data:
        from ..vafile import parse_ui_file
        logger.framework.debug(f"{LOG_PREFIX_RBAC} {LOG_MSG_DETECTED_UI}")
        logger.debug(f"{LOG_PREFIX_RBAC} {LOG_MSG_RAW_DATA_KEYS}",
                    list(data.keys()) if isinstance(data, dict) else STR_N_A)

        # UI files must be dictionaries
        if not isinstance(data, dict):
            logger.error(f"{LOG_PREFIX_PARSE} UI file must contain a dictionary, got {type(data).__name__}")
            return None

        parsed_ui = parse_ui_file(data, logger, file_path=file_path, session=session)

        # If UI parsing failed (returned None), stop immediately - this is a fatal error
        if parsed_ui is None:
            return None

        # Only log structure details if parsing succeeded
        logger.debug(f"{LOG_PREFIX_RBAC} {LOG_MSG_PARSED_UI_TYPE}", type(parsed_ui))
        logger.debug(f"{LOG_PREFIX_RBAC} {LOG_MSG_PARSED_UI_KEYS}",
                    list(parsed_ui.keys()) if isinstance(parsed_ui, dict) else STR_N_A)

        # Transform parsed structure back to zWalker-compatible format
        transformed = transform_parsed_ui_for_walker(parsed_ui, logger)
        if transformed is not None:
            return transformed

        # Fallback if transformation failed
        return parsed_ui.get(DICT_KEY_ZBLOCKS, data) if isinstance(parsed_ui, dict) else data

    # Apply Server-specific parsing (routing) if this is a Server file (v1.5.4 Phase 2)
    if is_server_file and data:
        from ..vafile import parse_server_file
        logger.framework.debug("[zServer] Detected server routing file")

        # Server files must be dictionaries
        if not isinstance(data, dict):
            logger.error(f"{LOG_PREFIX_PARSE} Server file must contain a dictionary, got {type(data).__name__}")
            return None

        parsed_server = parse_server_file(data, logger, file_path=file_path, _session=session)
        return parsed_server

    return data
