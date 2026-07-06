# zOS/core/L2_Handling/g_zParser/parser_modules/file/transformers/rbac_transformer.py

"""
RBAC transformation for UI file parsing.

Transforms structured UI format from vafile.parse_ui_file() into flat format
expected by zWalker, merging zRBAC metadata into item data for dispatch consumption.

Public API:
    - transform_parsed_ui_for_walker: Main transformation function

Dependencies:
    - vafile package: Produces input structure

External Usage:
    - parse_file_content: Applies transformation for UI files
    - zLoader: Consumes transformed output
    - authzRBAC: Uses zRBAC metadata for permission checks

Created: Phase 1.2 - Extract Transformers from parser_file.py
"""

from zOS import Any, Dict, Optional

# Import constants from shared
from ...shared.file_constants import (
    DICT_KEY_ZBLOCKS,
    DICT_KEY_ITEMS,
    DICT_KEY_DATA,
    DICT_KEY_GATE,
    DICT_KEY_RBAC,
    DICT_KEY_VALUE,
    LOG_MSG_TRANSFORMING_ZBLOCKS,
    LOG_MSG_PROCESSING_ZBLOCK,
    LOG_MSG_FOUND_ITEMS,
    LOG_MSG_ATTACHED_RBAC,
    LOG_MSG_WRAPPED_RBAC,
    LOG_MSG_TRANSFORM_COMPLETE,
    LOG_MSG_FINAL_RESULT_KEYS,
    LOG_MSG_NO_ZBLOCKS_STRUCTURE
)


def transform_parsed_ui_for_walker(
    parsed_ui: Dict[str, Any],
    logger: Any
) -> Optional[Dict[str, Any]]:
    """
    Transform parsed UI structure to zWalker-compatible format.
    
    This is a CRITICAL helper function that transforms the structured UI format
    returned by vafile.parse_ui_file() into the flat format expected by zWalker.
    
    Transformation:
        Input:  {{zblocks: {{block: {{items: {{item: {{data: {{...}}, zRBAC: {{...}}}}}}}}}}}}
        Output: {{block: {{item: {{... data merged with zRBAC ...}}}}}}
    
    The transformation ensures that:
    1. zRBAC metadata is properly merged into item data
    2. Non-dict values are wrapped with {{_value: value, zRBAC: {{...}}}}
    3. zWalker receives a flat structure it can navigate
    4. authzRBAC.py can access zRBAC during dispatch
    
    Args:
        parsed_ui: Structured UI data from vafile.parse_ui_file()
        logger: Logger instance for diagnostic output
    
    Returns:
        Optional[Dict[str, Any]]: Transformed structure for zWalker, or None if invalid
    
    Process:
        1. Extract zblocks from parsed_ui
        2. For each zblock, extract items
        3. For each item, merge zRBAC into data
        4. Handle both dict and non-dict values
        5. Return flat {{block: {{item: data}}}} structure
    
    Examples:
        >>> parsed_ui = {{
        ...     "zblocks": {{
        ...         "Menu": {{
        ...             "items": {{
        ...                 "Add": {{"data": {{"zFunc": "add"}}, "zRBAC": {{"require_role": "user"}}}},
        ...                 "Delete": {{"data": {{"zFunc": "delete"}}, "zRBAC": {{"require_role": "admin"}}}}
        ...             }}
        ...         }}
        ...     }}
        ... }}
        >>> result = transform_parsed_ui_for_walker(parsed_ui, logger)
        >>> result
        {{"Menu": {{"Add": {{"zFunc": "add", "zRBAC": {{...}}}}, "Delete": {{"zFunc": "delete", "zRBAC": {{...}}}}}}}}
    
    Notes:
        - This function is performance-critical (called for every UI file load)
        - Complexity is O(n) where n = total UI items across all zblocks
        - Handles edge cases: missing data key, non-dict values, missing zRBAC
        - Logs transformation steps for debugging
    
    External Dependencies:
        - Used exclusively by parse_file_content() (line ~75)
        - Result consumed by zLoader.py (line 63) for zWalker
        - zRBAC metadata used by authzRBAC.py during dispatch
    
    See Also:
        - parse_file_content: Calls this helper for UI files
        - vafile.parse_ui_file: Produces the input structure
        - zLoader: Consumes the output structure
        - authzRBAC: Uses zRBAC metadata for permission checks
    """
    if not isinstance(parsed_ui, dict) or DICT_KEY_ZBLOCKS not in parsed_ui:
        logger.warning(LOG_MSG_NO_ZBLOCKS_STRUCTURE)
        return None

    result: Dict[str, Any] = {}
    logger.debug(LOG_MSG_TRANSFORMING_ZBLOCKS, list(parsed_ui[DICT_KEY_ZBLOCKS].keys()))

    for zblock_name, zblock_data in parsed_ui[DICT_KEY_ZBLOCKS].items():
        logger.debug(LOG_MSG_PROCESSING_ZBLOCK, zblock_name)

        if not isinstance(zblock_data, dict) or DICT_KEY_ITEMS not in zblock_data:
            continue

        result[zblock_name] = {}
        logger.debug(LOG_MSG_FOUND_ITEMS, len(zblock_data[DICT_KEY_ITEMS]), zblock_name)

        for item_name, item_data in zblock_data[DICT_KEY_ITEMS].items():
            # Merge the gate (zGate, or deprecated zRBAC) into the data for dispatch
            if isinstance(item_data, dict):
                value = item_data.get(DICT_KEY_DATA, item_data)

                # zGate — the one gate verb
                if isinstance(value, dict) and DICT_KEY_GATE in item_data:
                    value[DICT_KEY_GATE] = item_data[DICT_KEY_GATE]
                    logger.debug(LOG_MSG_ATTACHED_RBAC, item_name)
                elif DICT_KEY_GATE in item_data:
                    # Wrap non-dict values with gate metadata
                    value = {DICT_KEY_VALUE: value, DICT_KEY_GATE: item_data[DICT_KEY_GATE]}
                    logger.debug(LOG_MSG_WRAPPED_RBAC, item_name)

                # zRBAC — deprecated, folded into zGate; retained until leaves migrate
                if isinstance(value, dict) and DICT_KEY_RBAC in item_data:
                    value[DICT_KEY_RBAC] = item_data[DICT_KEY_RBAC]
                    logger.debug(LOG_MSG_ATTACHED_RBAC, item_name)
                elif DICT_KEY_RBAC in item_data:
                    # Wrap non-dict values with zRBAC metadata
                    value = {DICT_KEY_VALUE: value, DICT_KEY_RBAC: item_data[DICT_KEY_RBAC]}
                    logger.debug(LOG_MSG_WRAPPED_RBAC, item_name)

                result[zblock_name][item_name] = value
            else:
                result[zblock_name][item_name] = item_data

    logger.framework.debug(LOG_MSG_TRANSFORM_COMPLETE, len(result))
    logger.debug(LOG_MSG_FINAL_RESULT_KEYS, list(result.keys()))
    return result
