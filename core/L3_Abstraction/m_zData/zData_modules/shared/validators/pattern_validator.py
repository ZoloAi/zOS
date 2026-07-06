# zOS/core/L3_Abstraction/m_zData/zData_modules/shared/validators/pattern_validator.py
"""
Pattern validation rules (Layer 3).

This module implements regex pattern matching validation for the zData validation engine.
It checks if string values match specified regex patterns.

Validation Rules:
- pattern: Regex pattern that the value must match
- pattern_message: Custom error message for pattern failures (optional)

Error message priority: pattern_message > error_message > default
"""

from zOS import Dict, Optional, Any, re

from .constants import (
    RULE_KEY_PATTERN,
    RULE_KEY_PATTERN_MESSAGE,
    RULE_KEY_ERROR_MESSAGE,
    ERR_INVALID_FORMAT,
)


def check_pattern_rules(
    field_name: str,
    value: Any,
    rules: Dict[str, Any]
) -> Optional[str]:
    """
    Check regex pattern validation rules (Layer 3).
    
    Validates:
    - pattern: Regex pattern matching
    
    Args:
        field_name: Name of field (for error messages)
        value: Value to validate (only checks if string)
        rules: Validation rules dict
    
    Returns:
        None if valid or not a string, error message string if invalid
    
    Examples:
        >>> rules = {"pattern": "^[A-Z][a-z]+$", "pattern_message": "Must start with capital"}
        >>> check_pattern_rules("name", "john", rules)
        "Must start with capital"
        
        >>> check_pattern_rules("name", "John", rules)
        None
    
    Notes:
        - Uses pattern_message if provided, otherwise error_message, otherwise default
    """
    pattern = rules.get(RULE_KEY_PATTERN)
    if pattern and isinstance(value, str) and not re.match(pattern, value):
        # Priority: pattern_message > error_message > default
        return (
            rules.get(RULE_KEY_PATTERN_MESSAGE) or
            rules.get(RULE_KEY_ERROR_MESSAGE) or
            ERR_INVALID_FORMAT.format(field_name=field_name)
        )
    return None
