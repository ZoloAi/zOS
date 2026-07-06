# zOS/core/L2_Handling/g_zParser/parser_modules/vafile/ui/ui_zblock_processor.py

"""
zBlock processing for vafile/ui package.

Parses UI zBlocks (menu sections) and individual UI items with construct identification.

Public API:
    - parse_ui_zblock: Parse zBlock with RBAC
    - parse_ui_item: Parse individual UI item
    - identify_ui_construct: Identify UI construct type

Created: Phase 5.3 - Extract zBlock Processor from vafile_ui.py
"""

from zOS import Any, Dict, Optional

# Import from parent vafile package
from .. import (
    FILE_TYPE_ZBLOCK, FILE_TYPE_UNKNOWN,
    DICT_KEY_NAME, DICT_KEY_TYPE, DICT_KEY_ITEMS, DICT_KEY_CONSTRUCTS,
    DICT_KEY_FILE_RBAC, DICT_KEY_GATE, DICT_KEY_RBAC, DICT_KEY_DATA, DICT_KEY_VALIDATED,
    DICT_KEY_ERRORS, DICT_KEY_WARNINGS, DICT_KEY_VALID,
    UI_CONSTRUCT_ZFUNC, UI_CONSTRUCT_ZLINK, UI_CONSTRUCT_ZDIALOG,
    UI_CONSTRUCT_ZMENU, UI_CONSTRUCT_ZWIZARD, UI_CONSTRUCT_ZDISPLAY,
    UI_CONSTRUCTS_LIST,
    LOG_MSG_PARSING_ZBLOCK, LOG_MSG_PROCESSING_ZBLOCK_ITEMS,
    LOG_MSG_PROCESSING_ITEM, LOG_MSG_FOUND_CONSTRUCT, LOG_MSG_INLINE_RBAC_FOUND,
    LOG_MSG_INLINE_RBAC_APPLIED, LOG_MSG_PUBLIC_ACCESS, LOG_MSG_PARSING_UI_ITEM
)

# Import construct validators
from .ui_construct_validators import (
    validate_zfunc_item,
    validate_zlink_item,
    validate_zdialog_item,
    validate_zmenu_item,
    validate_zwizard_item,
    validate_zdisplay_item
)


def parse_ui_zblock(
    zblock_name: str,
    zblock_data: Dict[str, Any],
    logger: Any,
    session: Optional[Dict[str, Any]] = None,
    filezRBAC: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Parse individual UI zBlock with validation and RBAC directives (v1.5.4 Week 3.3).
    
    Parses a single zBlock (menu section) from a UI file, processing each item
    and applying RBAC directives (file-level or inline).
    
    RBAC Processing:
        - File-level RBAC is inherited by all items (unless overridden)
        - Inline zRBAC in an item overrides file-level RBAC
        - If no RBAC is specified, the item is PUBLIC (default behavior)
    
    Args:
        zblock_name: Name of the zBlock (menu section)
        zblock_data: Dictionary of items in the zBlock
        logger: Logger instance for diagnostic output
        session: Optional session dict (reserved for future use)
        filezRBAC: Optional file-level RBAC directives (inherited from parent)
    
    Returns:
        Dict[str, Any]: Parsed zBlock structure with format:
            {{
                "name": str,
                "type": "zblock",
                "items": {{
                    "item_name": {{...}}
                }},
                "constructs": {{
                    "zFunc": [list of item names],
                    "zLink": [list of item names],
                    ...
                }},
                "_filezRBAC": {{...}} or None
            }}
    
    Examples:
        >>> zblock_data = {{
        ...     "Add User": {{"zFunc": "add_user"}},
        ...     "Delete User": {{
        ...         "zRBAC": {{"require_role": "admin"}},
        ...         "zFunc": "delete_user"
        ...     }}
        ... }}
        >>> filezRBAC = {{"require_role": "user"}}
        >>> logger = get_logger()
        >>> result = parse_ui_zblock("Admin", zblock_data, logger, filezRBAC=filezRBAC)
        >>> result["_filezRBAC"]
        {{"require_role": "user"}}
        >>> "Add User" in result["items"]
        True
    
    Notes:
        - All items in zBlock are processed
        - Inline zRBAC is extracted and stored separately
        - UI construct type is identified for each dict item
        - Construct lists track which items use which constructs
    
    See Also:
        - parse_ui_file: Calls this for each zBlock
        - parse_ui_item: Parses individual items
        - identify_ui_construct: Identifies construct type
    """
    logger.debug(LOG_MSG_PARSING_ZBLOCK, zblock_name)

    parsed_zblock: Dict[str, Any] = {
        DICT_KEY_NAME: zblock_name,
        DICT_KEY_TYPE: FILE_TYPE_ZBLOCK,
        DICT_KEY_ITEMS: {},
        DICT_KEY_CONSTRUCTS: {
            UI_CONSTRUCT_ZFUNC: [],
            UI_CONSTRUCT_ZLINK: [],
            UI_CONSTRUCT_ZDIALOG: [],
            UI_CONSTRUCT_ZMENU: [],
            UI_CONSTRUCT_ZWIZARD: [],
            UI_CONSTRUCT_ZDISPLAY: []
        }
    }

    # Store file-level RBAC (inherited from parent)
    if filezRBAC:
        parsed_zblock[DICT_KEY_FILE_RBAC] = filezRBAC

    # Process each item in the zBlock
    # RBAC is now INLINE in the item data (v1.5.4 Week 3.3)
    logger.debug(LOG_MSG_PROCESSING_ZBLOCK_ITEMS, zblock_name, len(zblock_data))

    for item_name, item_data in zblock_data.items():
        logger.debug(LOG_MSG_PROCESSING_ITEM, item_name)

        # zKeys can be strings (zFunc, zLink), lists (menus), or dicts (zWizard, zDialog)
        # Accept all types - validation happens in dispatch

        # Check if item already has inline zGate (or deprecated zRBAC)
        # Both are gate verbs — protect from parse_ui_item, reattach after.
        inlinezGate = None
        if isinstance(item_data, dict) and DICT_KEY_GATE in item_data:
            inlinezGate = item_data.pop(DICT_KEY_GATE)  # Extract and remove from data
            logger.framework.debug(LOG_MSG_INLINE_RBAC_FOUND, item_name, inlinezGate)
        inlinezRBAC = None
        if isinstance(item_data, dict) and DICT_KEY_RBAC in item_data:
            inlinezRBAC = item_data.pop(DICT_KEY_RBAC)  # Extract and remove from data
            logger.framework.debug(LOG_MSG_INLINE_RBAC_FOUND, item_name, inlinezRBAC)

        # Identify UI construct type (only for dict items)
        construct_type = None
        if isinstance(item_data, dict):
            construct_type = identify_ui_construct(item_data)
            if construct_type:
                parsed_zblock[DICT_KEY_CONSTRUCTS][construct_type].append(item_name)
                logger.debug(LOG_MSG_FOUND_CONSTRUCT, construct_type, item_name)

        # Parse and validate the item
        parsed_item = parse_ui_item(item_name, item_data, construct_type, logger, session)

        # Apply gate: Default is PUBLIC ACCESS (no restrictions)
        # Only apply a gate if explicitly specified
        if inlinezGate is not None:
            # Item has explicit inline zGate - use it
            parsed_item[DICT_KEY_GATE] = inlinezGate
            logger.framework.debug(LOG_MSG_INLINE_RBAC_APPLIED, item_name, inlinezGate)
        if inlinezRBAC is not None:
            # Item has explicit inline RBAC (deprecated) - use it
            parsed_item[DICT_KEY_RBAC] = inlinezRBAC
            logger.framework.debug(LOG_MSG_INLINE_RBAC_APPLIED, item_name, inlinezRBAC)
        if inlinezGate is None and inlinezRBAC is None:
            # No inline gate = public access (default behavior)
            logger.debug(LOG_MSG_PUBLIC_ACCESS, item_name)

        parsed_zblock[DICT_KEY_ITEMS][item_name] = parsed_item

    return parsed_zblock


def identify_ui_construct(item_data: Dict[str, Any]) -> Optional[str]:
    """
    Identify the type of UI construct based on item data.
    
    Scans item data dictionary for known UI construct keys and returns the
    first match found.
    
    UI Constructs:
        - zFunc: Function invocation
        - zLink: Inter-file linking
        - zDialog: Interactive forms
        - zMenu: Menu definitions
        - zWizard: Multi-step workflows
        - zDisplay: Display events
    
    Args:
        item_data: Dictionary containing UI item data
    
    Returns:
        Optional[str]: UI construct type (e.g., "zFunc", "zLink") or None if not found
    
    Examples:
        >>> identify_ui_construct({{"zFunc": "my_function"}})
        "zFunc"
        
        >>> identify_ui_construct({{"zLink": "@.path.to.file"}})
        "zLink"
        
        >>> identify_ui_construct({{"data": "value"}})  # No construct
        None
    
    Notes:
        - Returns first construct found (if multiple, precedence by list order)
        - Returns None if no recognized constructs found
        - Used for categorization and validation
    
    See Also:
        - parse_ui_zblock: Uses this to categorize items
        - UI_CONSTRUCTS_LIST: List of recognized constructs
    """
    for construct in UI_CONSTRUCTS_LIST:
        if construct in item_data:
            return construct

    return None


def parse_ui_item(
    item_name: str,
    item_data: Any,
    construct_type: Optional[str],
    logger: Any,
    _session: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Parse individual UI item with type-specific validation.
    
    Parses a single UI item (menu entry) and performs construct-specific
    validation based on the identified type.
    
    Args:
        item_name: Name of the UI item
        item_data: Data for the item (can be str, list, or dict)
        construct_type: Type of UI construct (zFunc, zLink, etc.) or None
        logger: Logger instance for diagnostic output
        _session: Optional session dict (reserved for future use, currently unused)
    
    Returns:
        Dict[str, Any]: Parsed item structure with format:
            {{
                "name": str,
                "type": str,  # Construct type or "unknown"
                "data": Any,  # Original item data
                "validated": bool,
                "errors": List[str],
                "warnings": List[str] or None
            }}
    
    Examples:
        >>> parse_ui_item("Add", {{"zFunc": "add_user"}}, "zFunc", logger)
        {{"name": "Add", "type": "zFunc", "data": {{...}}, "validated": True, "errors": []}}
        
        >>> parse_ui_item("Bad", {{"zFunc": 123}}, "zFunc", logger)  # Invalid type
        {{"name": "Bad", "type": "zFunc", "data": {{...}}, "validated": False, "errors": [...]}}
    
    Notes:
        - Type-specific validation only for dict items with constructs
        - Non-dict items (strings, lists) are accepted without validation
        - Validation errors are collected but don't prevent parsing
    
    See Also:
        - parse_ui_zblock: Calls this for each item
        - validate_*_item: Type-specific validators
    """
    logger.debug(LOG_MSG_PARSING_UI_ITEM, item_name, construct_type or FILE_TYPE_UNKNOWN)

    parsed_item: Dict[str, Any] = {
        DICT_KEY_NAME: item_name,
        DICT_KEY_TYPE: construct_type or FILE_TYPE_UNKNOWN,
        DICT_KEY_DATA: item_data,
        DICT_KEY_VALIDATED: True,
        DICT_KEY_ERRORS: []
    }

    # Type-specific validation (only for dict items with constructs)
    if isinstance(item_data, dict) and construct_type:
        if construct_type == UI_CONSTRUCT_ZFUNC:
            validation_result = validate_zfunc_item(item_data)
        elif construct_type == UI_CONSTRUCT_ZLINK:
            validation_result = validate_zlink_item(item_data)
        elif construct_type == UI_CONSTRUCT_ZDIALOG:
            validation_result = validate_zdialog_item(item_data)
        elif construct_type == UI_CONSTRUCT_ZMENU:
            validation_result = validate_zmenu_item(item_data)
        elif construct_type == UI_CONSTRUCT_ZWIZARD:
            validation_result = validate_zwizard_item(item_data)
        elif construct_type == UI_CONSTRUCT_ZDISPLAY:
            validation_result = validate_zdisplay_item(item_data)
        else:
            validation_result = {DICT_KEY_VALID: True, DICT_KEY_ERRORS: [], DICT_KEY_WARNINGS: []}

        parsed_item[DICT_KEY_VALIDATED] = validation_result[DICT_KEY_VALID]
        parsed_item[DICT_KEY_ERRORS] = validation_result[DICT_KEY_ERRORS]
        parsed_item[DICT_KEY_WARNINGS] = validation_result.get(DICT_KEY_WARNINGS, [])

    return parsed_item
