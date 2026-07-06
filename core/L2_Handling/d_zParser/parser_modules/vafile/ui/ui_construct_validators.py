# zOS/core/L2_Handling/g_zParser/parser_modules/vafile/ui/ui_construct_validators.py

"""
UI construct validators for vafile/ui package.

Type-specific validation for the 6 declarative UI primitives.

Public API:
    - validate_zfunc_item: Validate zFunc items
    - validate_zlink_item: Validate zLink items
    - validate_zdialog_item: Validate zDialog items
    - validate_zmenu_item: Validate zMenu items
    - validate_zwizard_item: Validate zWizard items
    - validate_zdisplay_item: Validate zDisplay items

Created: Phase 5.2 - Extract Construct Validators from vafile_ui.py
"""

from zOS import Any, Dict, List

# Import from parent vafile package
from .. import (
    UI_CONSTRUCT_ZFUNC,
    UI_CONSTRUCT_ZLINK,
    UI_CONSTRUCT_ZDIALOG,
    UI_CONSTRUCT_ZMENU,
    UI_CONSTRUCT_ZWIZARD,
    UI_CONSTRUCT_ZDISPLAY,
    DICT_KEY_VALID,
    DICT_KEY_ERRORS
)

# Construct validation error messages
ERROR_MSG_MISSING_CONSTRUCT_KEY = "%s item missing '%s' key"
ERROR_MSG_INVALID_CONSTRUCT_TYPE = "%s value must be a %s"
ERROR_MSG_MISSING_EVENT_FIELD = "zDisplay item missing required 'event' field"


def validate_zfunc_item(item_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate zFunc item structure.
    
    zFunc items must have:
    - A "zFunc" key
    - The value must be a string (function name)
    
    Args:
        item_data: Dictionary containing zFunc item data
    
    Returns:
        Dict[str, Any]: Validation result {{"valid": bool, "errors": List[str]}}
    
    Examples:
        >>> validate_zfunc_item({{"zFunc": "my_function"}})
        {{"valid": True, "errors": []}}
        
        >>> validate_zfunc_item({{"zFunc": 123}})  # Invalid type
        {{"valid": False, "errors": ["zFunc value must be a string"]}}
    
    See Also:
        - parse_ui_item: Calls this for zFunc items
    """
    errors: List[str] = []

    if UI_CONSTRUCT_ZFUNC not in item_data:
        errors.append(ERROR_MSG_MISSING_CONSTRUCT_KEY % (UI_CONSTRUCT_ZFUNC, UI_CONSTRUCT_ZFUNC))
    elif not isinstance(item_data[UI_CONSTRUCT_ZFUNC], str):
        errors.append(ERROR_MSG_INVALID_CONSTRUCT_TYPE % (UI_CONSTRUCT_ZFUNC, "string"))

    return {DICT_KEY_VALID: len(errors) == 0, DICT_KEY_ERRORS: errors}


def validate_zlink_item(item_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate zLink item structure.
    
    zLink items must have:
    - A "zLink" key
    - The value must be a string (link path)
    
    Args:
        item_data: Dictionary containing zLink item data
    
    Returns:
        Dict[str, Any]: Validation result {{"valid": bool, "errors": List[str]}}
    
    Examples:
        >>> validate_zlink_item({{"zLink": "@.path.to.file"}})
        {{"valid": True, "errors": []}}
        
        >>> validate_zlink_item({{"zLink": 123}})  # Invalid type
        {{"valid": False, "errors": ["zLink value must be a string"]}}
    
    See Also:
        - parse_ui_item: Calls this for zLink items
    """
    errors: List[str] = []

    if UI_CONSTRUCT_ZLINK not in item_data:
        errors.append(ERROR_MSG_MISSING_CONSTRUCT_KEY % (UI_CONSTRUCT_ZLINK, UI_CONSTRUCT_ZLINK))
    elif not isinstance(item_data[UI_CONSTRUCT_ZLINK], str):
        errors.append(ERROR_MSG_INVALID_CONSTRUCT_TYPE % (UI_CONSTRUCT_ZLINK, "string"))

    return {DICT_KEY_VALID: len(errors) == 0, DICT_KEY_ERRORS: errors}


def validate_zdialog_item(item_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate zDialog item structure.
    
    zDialog items must have:
    - A "zDialog" key
    - The value must be a string or dictionary
    
    Args:
        item_data: Dictionary containing zDialog item data
    
    Returns:
        Dict[str, Any]: Validation result {{"valid": bool, "errors": List[str]}}
    
    Examples:
        >>> validate_zdialog_item({{"zDialog": {{"fields": [...]}}}})
        {{"valid": True, "errors": []}}
        
        >>> validate_zdialog_item({{"zDialog": 123}})  # Invalid type
        {{"valid": False, "errors": ["zDialog value must be a string or dictionary"]}}
    
    See Also:
        - parse_ui_item: Calls this for zDialog items
    """
    errors: List[str] = []

    if UI_CONSTRUCT_ZDIALOG not in item_data:
        errors.append(ERROR_MSG_MISSING_CONSTRUCT_KEY % (UI_CONSTRUCT_ZDIALOG, UI_CONSTRUCT_ZDIALOG))
    elif not isinstance(item_data[UI_CONSTRUCT_ZDIALOG], (str, dict)):
        errors.append(ERROR_MSG_INVALID_CONSTRUCT_TYPE % (UI_CONSTRUCT_ZDIALOG, "string or dictionary"))

    return {DICT_KEY_VALID: len(errors) == 0, DICT_KEY_ERRORS: errors}


def validate_zmenu_item(item_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate zMenu item structure.
    
    zMenu items must have:
    - A "zMenu" key
    - The value must be a string, dictionary, or list
    
    Args:
        item_data: Dictionary containing zMenu item data
    
    Returns:
        Dict[str, Any]: Validation result {{"valid": bool, "errors": List[str]}}
    
    Examples:
        >>> validate_zmenu_item({{"zMenu": [item1, item2]}})
        {{"valid": True, "errors": []}}
        
        >>> validate_zmenu_item({{"zMenu": 123}})  # Invalid type
        {{"valid": False, "errors": ["zMenu value must be a string, dictionary, or list"]}}
    
    See Also:
        - parse_ui_item: Calls this for zMenu items
    """
    errors: List[str] = []

    if UI_CONSTRUCT_ZMENU not in item_data:
        errors.append(ERROR_MSG_MISSING_CONSTRUCT_KEY % (UI_CONSTRUCT_ZMENU, UI_CONSTRUCT_ZMENU))
    elif not isinstance(item_data[UI_CONSTRUCT_ZMENU], (str, dict, list)):
        errors.append(ERROR_MSG_INVALID_CONSTRUCT_TYPE % (UI_CONSTRUCT_ZMENU, "string, dictionary, or list"))

    return {DICT_KEY_VALID: len(errors) == 0, DICT_KEY_ERRORS: errors}


def validate_zwizard_item(item_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate zWizard item structure.
    
    zWizard items must have:
    - A "zWizard" key
    - The value must be a dictionary
    
    Args:
        item_data: Dictionary containing zWizard item data
    
    Returns:
        Dict[str, Any]: Validation result {{"valid": bool, "errors": List[str]}}
    
    Examples:
        >>> validate_zwizard_item({{"zWizard": {{"steps": [...]}}}})
        {{"valid": True, "errors": []}}
        
        >>> validate_zwizard_item({{"zWizard": "string"}})  # Invalid type
        {{"valid": False, "errors": ["zWizard value must be a dictionary"]}}
    
    See Also:
        - parse_ui_item: Calls this for zWizard items
    """
    errors: List[str] = []

    if UI_CONSTRUCT_ZWIZARD not in item_data:
        errors.append(ERROR_MSG_MISSING_CONSTRUCT_KEY % (UI_CONSTRUCT_ZWIZARD, UI_CONSTRUCT_ZWIZARD))
    elif not isinstance(item_data[UI_CONSTRUCT_ZWIZARD], dict):
        errors.append(ERROR_MSG_INVALID_CONSTRUCT_TYPE % (UI_CONSTRUCT_ZWIZARD, "dictionary"))

    return {DICT_KEY_VALID: len(errors) == 0, DICT_KEY_ERRORS: errors}


def validate_zdisplay_item(item_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate zDisplay item structure.
    
    zDisplay items must have:
    - A "zDisplay" key
    - The value must be a dictionary
    - The dictionary must have an "event" field
    
    Args:
        item_data: Dictionary containing zDisplay item data
    
    Returns:
        Dict[str, Any]: Validation result {{"valid": bool, "errors": List[str]}}
    
    Examples:
        >>> validate_zdisplay_item({{"zDisplay": {{"event": "output", "data": {{}}}}}})
        {{"valid": True, "errors": []}}
        
        >>> validate_zdisplay_item({{"zDisplay": {{"data": {{}}}}}})  # Missing event
        {{"valid": False, "errors": ["zDisplay item missing required 'event' field"]}}
    
    See Also:
        - parse_ui_item: Calls this for zDisplay items
    """
    errors: List[str] = []

    if UI_CONSTRUCT_ZDISPLAY not in item_data:
        errors.append(ERROR_MSG_MISSING_CONSTRUCT_KEY % (UI_CONSTRUCT_ZDISPLAY, UI_CONSTRUCT_ZDISPLAY))
    elif not isinstance(item_data[UI_CONSTRUCT_ZDISPLAY], dict):
        errors.append(ERROR_MSG_INVALID_CONSTRUCT_TYPE % (UI_CONSTRUCT_ZDISPLAY, "dictionary"))
    else:
        # Check for required event field
        display_obj = item_data[UI_CONSTRUCT_ZDISPLAY]
        if "event" not in display_obj:
            errors.append(ERROR_MSG_MISSING_EVENT_FIELD)

    return {DICT_KEY_VALID: len(errors) == 0, DICT_KEY_ERRORS: errors}
