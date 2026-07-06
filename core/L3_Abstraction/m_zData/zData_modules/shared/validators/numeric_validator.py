# zOS/core/L3_Abstraction/m_zData/zData_modules/shared/validators/numeric_validator.py
"""
Numeric validation rules (Layer 2).

This module implements numeric range validation for the zData validation engine.
It checks min and max constraints on numeric values (int/float).

Validation Rules:
- min: Minimum numeric value allowed
- max: Maximum numeric value allowed

Custom error messages can be provided via the error_message rule key.
"""

from zOS import Dict, Optional, Any

from .constants import (
    RULE_KEY_MIN,
    RULE_KEY_MAX,
    RULE_KEY_ERROR_MESSAGE,
    ERR_MIN_VALUE,
    ERR_MAX_VALUE,
)


def check_numeric_rules(
    field_name: str,
    value: Any,
    rules: Dict[str, Any]
) -> Optional[str]:
    """
    Check numeric range validation rules (Layer 2).
    
    Validates:
    - min: Minimum numeric value
    - max: Maximum numeric value
    
    Args:
        field_name: Name of field (for error messages)
        value: Value to validate (only checks if int/float)
        rules: Validation rules dict
    
    Returns:
        None if valid or not numeric, error message string if invalid
    
    Examples:
        >>> rules = {"min": 0, "max": 100}
        >>> check_numeric_rules("age", -5, rules)
        "age must be at least 0"
        
        >>> check_numeric_rules("age", 25, rules)
        None
    """
    if not isinstance(value, (int, float)):
        return None

    min_val = rules.get(RULE_KEY_MIN)
    if min_val is not None and value < min_val:
        custom_error = rules.get(RULE_KEY_ERROR_MESSAGE)
        return custom_error or ERR_MIN_VALUE.format(
            field_name=field_name,
            min_val=min_val
        )

    max_val = rules.get(RULE_KEY_MAX)
    if max_val is not None and value > max_val:
        custom_error = rules.get(RULE_KEY_ERROR_MESSAGE)
        return custom_error or ERR_MAX_VALUE.format(
            field_name=field_name,
            max_val=max_val
        )

    return None
