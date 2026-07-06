# zOS/core/L3_Abstraction/m_zData/zData_modules/shared/validators/string_validator.py
"""
String validation rules (Layer 1).

This module implements string length validation for the zData validation engine.
It checks min_length and max_length constraints on string values.

Validation Rules:
- min_length: Minimum character count required
- max_length: Maximum character count allowed

Custom error messages can be provided via the error_message rule key.
"""

from zOS import Dict, Optional, Any

from .constants import (
    RULE_KEY_MIN_LENGTH,
    RULE_KEY_MAX_LENGTH,
    RULE_KEY_ERROR_MESSAGE,
    ERR_MIN_LENGTH,
    ERR_MAX_LENGTH,
)


def check_string_rules(
    field_name: str,
    value: Any,
    rules: Dict[str, Any]
) -> Optional[str]:
    """
    Check string length validation rules (Layer 1).
    
    Validates:
    - min_length: Minimum character count
    - max_length: Maximum character count
    
    Args:
        field_name: Name of field (for error messages)
        value: Value to validate (only checks if string)
        rules: Validation rules dict
    
    Returns:
        None if valid or not a string, error message string if invalid
    
    Examples:
        >>> rules = {"min_length": 3, "max_length": 50}
        >>> check_string_rules("username", "ab", rules)
        "username must be at least 3 characters"
        
        >>> check_string_rules("username", "valid_name", rules)
        None
    """
    if not isinstance(value, str):
        return None

    min_length = rules.get(RULE_KEY_MIN_LENGTH)
    if min_length and len(value) < min_length:
        custom_error = rules.get(RULE_KEY_ERROR_MESSAGE)
        return custom_error or ERR_MIN_LENGTH.format(
            field_name=field_name,
            min_length=min_length
        )

    max_length = rules.get(RULE_KEY_MAX_LENGTH)
    if max_length and len(value) > max_length:
        custom_error = rules.get(RULE_KEY_ERROR_MESSAGE)
        return custom_error or ERR_MAX_LENGTH.format(
            field_name=field_name,
            max_length=max_length
        )

    return None
