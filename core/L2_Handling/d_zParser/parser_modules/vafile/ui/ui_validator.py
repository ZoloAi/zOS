# zOS/core/L2_Handling/g_zParser/parser_modules/vafile/ui/ui_validator.py

"""
UI structure validation for vafile/ui package.

Validates UI and schema file structure including zBlocks, constructs, and fields.

Public API:
    - validate_ui_structure: Validate UI file structure
    - validate_schema_structure: Validate schema file structure

Created: Phase 5.1 - Extract Validators from vafile_ui.py
"""

from zOS import Any, Dict, Optional

# Import from parent vafile package
from .. import (
    DICT_KEY_VALID, DICT_KEY_ERRORS, DICT_KEY_WARNINGS, DICT_KEY_TYPE,
    UI_CONSTRUCTS_LIST,
    LOG_MSG_VALIDATING_UI, LOG_MSG_VALIDATING_SCHEMA,
    SCHEMA_KEY_DB_PATH, SCHEMA_KEY_META
)

# UI-specific constants
ERROR_MSG_UI_EMPTY = "UI file cannot be empty"
ERROR_MSG_NO_ZBLOCKS = "UI file must contain at least one zBlock (menu section)"
ERROR_MSG_NO_RECOGNIZED_CONSTRUCTS = (
    "zBlock '%s' contains no recognized UI constructs "
    "(zFunc, zLink, zDialog, zMenu, zWizard)"
)
ERROR_MSG_RESERVED_KEYS_UI = "UI file contains reserved keys that may conflict with schema files: %s"

ERROR_MSG_SCHEMA_EMPTY = "Schema file cannot be empty"
ERROR_MSG_NO_TABLES = "Schema file must contain at least one table definition"
ERROR_MSG_NO_FIELD_DEFS = "Table '%s' has no field definitions"
ERROR_MSG_NO_FIELD_TYPE = "Field '%s' in table '%s' missing 'type' attribute"
ERROR_MSG_INVALID_FIELD_TYPE = "Invalid field definition for '%s' in table '%s': expected dict or string"
ERROR_MSG_UI_KEYS_IN_SCHEMA = "Schema file contains UI-specific keys that may be misplaced: %s"

RESERVED_UI_KEYS = ["db_path", "meta", "schema", "table"]
RESERVED_SCHEMA_KEYS = ["zFunc", "zLink", "zDialog", "zMenu", "zWizard"]


def validate_ui_structure(
    data: Dict[str, Any],
    logger: Any,
    _file_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Validate UI file structure.
    
    Validates that a UI file has the correct structure:
    - At least one zBlock (menu section)
    - Each zBlock contains recognized UI constructs
    - No reserved schema keys that might cause conflicts
    
    Args:
        data: Parsed UI file data
        logger: Logger instance for diagnostic output
        _file_path: Optional file path for error messages (reserved, currently unused)
    
    Returns:
        Dict[str, Any]: Validation result {{"valid": bool, "errors": List, "warnings": List}}
    
    Examples:
        >>> data = {{"Menu": {{"Item": {{"zFunc": "func"}}}}}}
        >>> logger = get_logger()
        >>> result = validate_ui_structure(data, logger)
        >>> result["valid"]
        True
        
        >>> data = {{}}  # Empty
        >>> result = validate_ui_structure(data, logger)
        >>> result["valid"]
        False
    
    Notes:
        - Checks for at least one zBlock
        - Warns if zBlocks contain no recognized UI constructs
        - Warns if reserved schema keys are found
    
    See Also:
        - validate_zva_structure: Calls this for UI files
        - parse_ui_file: Uses validation results
    """
    logger.debug(LOG_MSG_VALIDATING_UI)

    validation_result: Dict[str, Any] = {
        DICT_KEY_VALID: True,
        DICT_KEY_ERRORS: [],
        DICT_KEY_WARNINGS: []
    }

    # Check for required UI structure elements
    if not data:
        validation_result[DICT_KEY_ERRORS].append(ERROR_MSG_UI_EMPTY)
        return validation_result

    # Validate zBlock structure (menu sections)
    zblock_count = 0
    for zblock_name, zblock_data in data.items():
        # Skip RBAC directives (they start with "!")
        if zblock_name.startswith("!"):
            continue

        if isinstance(zblock_data, dict):
            zblock_count += 1

            # Check if zBlock contains recognized UI constructs
            has_constructs = False
            for _item_name, item_data in zblock_data.items():
                if isinstance(item_data, dict):
                    for construct in UI_CONSTRUCTS_LIST:
                        if construct in item_data:
                            has_constructs = True
                            break
                    if has_constructs:
                        break

            if not has_constructs:
                validation_result[DICT_KEY_WARNINGS].append(
                    ERROR_MSG_NO_RECOGNIZED_CONSTRUCTS % zblock_name
                )

    if zblock_count == 0:
        validation_result[DICT_KEY_ERRORS].append(ERROR_MSG_NO_ZBLOCKS)

    # Check for reserved schema keys that shouldn't be in UI files
    found_reserved_keys = [key for key in data.keys() if key in RESERVED_UI_KEYS]
    if found_reserved_keys:
        validation_result[DICT_KEY_WARNINGS].append(
            ERROR_MSG_RESERVED_KEYS_UI % found_reserved_keys
        )

    validation_result[DICT_KEY_VALID] = len(validation_result[DICT_KEY_ERRORS]) == 0
    return validation_result


def validate_schema_structure(
    data: Dict[str, Any],
    logger: Any,
    _file_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Validate schema file structure.
    
    Validates that a schema file has the correct structure:
    - At least one table definition
    - Each table has field definitions
    - Fields have required attributes
    - No UI-specific keys that might cause conflicts
    
    Args:
        data: Parsed schema file data
        logger: Logger instance for diagnostic output
        _file_path: Optional file path for error messages (reserved, currently unused)
    
    Returns:
        Dict[str, Any]: Validation result {{"valid": bool, "errors": List, "warnings": List}}
    
    Examples:
        >>> data = {{"users": {{"id": "int!", "name": "str"}}}}
        >>> logger = get_logger()
        >>> result = validate_schema_structure(data, logger)
        >>> result["valid"]
        True
        
        >>> data = {{}}  # Empty
        >>> result = validate_schema_structure(data, logger)
        >>> result["valid"]
        False
    
    Notes:
        - Checks for at least one table definition
        - Validates field definitions (dict or string)
        - Warns if fields are missing type attribute
        - Warns if UI-specific keys are found
    
    See Also:
        - validate_zva_structure: Calls this for schema files
        - parse_schema_file: Uses validation results
    """
    logger.debug(LOG_MSG_VALIDATING_SCHEMA)

    validation_result: Dict[str, Any] = {
        DICT_KEY_VALID: True,
        DICT_KEY_ERRORS: [],
        DICT_KEY_WARNINGS: []
    }

    # Check for required schema structure elements
    if not data:
        validation_result[DICT_KEY_ERRORS].append(ERROR_MSG_SCHEMA_EMPTY)
        return validation_result

    # Validate table definitions
    table_count = 0
    for key, value in data.items():
        if key in [SCHEMA_KEY_DB_PATH, SCHEMA_KEY_META]:
            # Skip metadata keys
            continue

        if isinstance(value, dict):
            table_count += 1

            # Check for field definitions
            if not value:
                validation_result[DICT_KEY_WARNINGS].append(ERROR_MSG_NO_FIELD_DEFS % key)
                continue

            # Validate field structure
            for field_name, field_def in value.items():
                if isinstance(field_def, dict):
                    # Check for required field attributes
                    if DICT_KEY_TYPE not in field_def:
                        validation_result[DICT_KEY_WARNINGS].append(
                            ERROR_MSG_NO_FIELD_TYPE % (field_name, key)
                        )
                elif isinstance(field_def, str):
                    # String field definition (shorthand)
                    pass
                else:
                    validation_result[DICT_KEY_ERRORS].append(
                        ERROR_MSG_INVALID_FIELD_TYPE % (field_name, key)
                    )

    if table_count == 0:
        validation_result[DICT_KEY_ERRORS].append(ERROR_MSG_NO_TABLES)

    # Check for UI-specific keys that shouldn't be in schema files
    found_ui_keys = [key for key in data.keys() if key in RESERVED_SCHEMA_KEYS]
    if found_ui_keys:
        validation_result[DICT_KEY_WARNINGS].append(
            ERROR_MSG_UI_KEYS_IN_SCHEMA % found_ui_keys
        )

    validation_result[DICT_KEY_VALID] = len(validation_result[DICT_KEY_ERRORS]) == 0
    return validation_result
