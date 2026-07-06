# zOS/core/L2_Core/c_zDisplay/zDisplay_modules/a_infrastructure/value_formatter.py

"""
Value Formatter Utility
========================

Pure utility function for formatting values for display.
"""

from zOS import Any


def format_value_for_display(value: Any, max_length: int = 60) -> str:
    """
    Format value for display (handle bool, None, dict, list, long strings).
    
    This provides consistent formatting for different value types,
    ensuring terminal output is readable and doesn't overflow.
    
    Args:
        value: Value to format (any type)
        max_length: Maximum string length before truncation (default: 60)
    
    Returns:
        str: Formatted value string
    
    Formatting Rules:
        - bool: "True" or "False" (capitalized)
        - None: "None"
        - dict/list: str(value), truncated with "..." if > max_length
        - str: Truncated with "..." if > max_length
        - other: str(value)
    
    Examples:
        >>> format_value_for_display(True)
        "True"
        
        >>> format_value_for_display(None)
        "None"
        
        >>> format_value_for_display("A" * 100, max_length=60)
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA..."
    """
    if isinstance(value, bool):
        return "True" if value else "False"

    if value is None:
        return "None"

    if isinstance(value, (dict, list)):
        value_str = str(value)
        if len(value_str) > max_length:
            return value_str[:max_length - 3] + "..."
        return value_str

    value_str = str(value)
    if len(value_str) > max_length:
        return value_str[:max_length - 3] + "..."

    return value_str
