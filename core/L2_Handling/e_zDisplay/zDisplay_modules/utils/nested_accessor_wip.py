# zOS/core/L2_Core/c_zDisplay/zDisplay_modules/a_infrastructure/nested_accessor.py

"""
Nested Accessor Utility
========================

Pure utility function for safely accessing nested structures.
"""

from zOS import Any


def safe_get_nested(obj: Any, *keys: str, default: Any = None) -> Any:
    """
    Safely get nested attribute/dict value with fallback.
    
    This provides safe navigation of nested structures (objects with attributes,
    dicts with keys, or mixed). Returns default if any level is missing.
    
    Args:
        obj: Root object to navigate (dict, object, or any)
        *keys: Sequence of keys/attributes to traverse
        default: Default value if any key/attribute missing (default: None)
    
    Returns:
        Any: Value at nested path, or default if not found
    
    Examples:
        >>> data = {"user": {"profile": {"name": "Alice"}}}
        >>> safe_get_nested(data, "user", "profile", "name")
        "Alice"
        
        >>> safe_get_nested(data, "user", "missing", "key", default="Unknown")
        "Unknown"
    """
    current = obj
    for key in keys:
        if current is None:
            return default

        if isinstance(current, dict):
            current = current.get(key, default)
            if current == default:
                return default
        elif hasattr(current, key):
            current = getattr(current, key, default)
        else:
            return default

    return current
