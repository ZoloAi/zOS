# zOS/core/L2_Handling/g_zParser/parser_modules/plugin/plugin_detection.py

"""
Plugin invocation detection for plugin package.

Provides quick detection to determine if a value should be processed as a
plugin invocation (starts with & and contains dot for plugin.function syntax).

Public API:
    - is_plugin_invocation: Quick detection function

Dependencies:
    - None (pure detection logic)

External Usage:
    - dispatch_launcher.py: Uses this to detect plugin calls

Created: Phase 2.1 - Extract Detection from parser_plugin.py
"""

from zOS import Any

# Characters
CHAR_AMPERSAND: str = '&'
CHAR_DOT: str = '.'


def is_plugin_invocation(value: Any) -> bool:
    """
    Check if value is a plugin invocation (starts with & and contains dot).
    
    Quick detection function to determine if a value should be processed as a
    plugin invocation. Used as a guard before attempting full resolution.
    
    Detection Criteria:
        1. Value must be a string
        2. Must start with the canonical plugin sigil ``&.`` (the leading dot is
           part of the sigil, exactly like ``@.`` / ``~.``)

    A bare ``&plugin.fn()`` (no leading dot) is NOT a plugin invocation — the
    hard canon is single-form ``&.``. ``&zNow`` / ``&zNow(...)`` (dot-less
    builtin tokens) are likewise not plugins; they resolve in parser_functions.

    Args:
        value: Value to check (can be any type)
    
    Returns:
        bool: True if value matches plugin invocation pattern, False otherwise
    
    Examples:
        >>> is_plugin_invocation("&.test_plugin.hello()")
        True

        >>> is_plugin_invocation("&.demos.deploy_demo.deploy()")
        True

        >>> is_plugin_invocation("&test_plugin.hello()")  # bare & — not canon
        False

        >>> is_plugin_invocation("regular_string")
        False
        
        >>> is_plugin_invocation(42)
        False
        
        >>> is_plugin_invocation("&zNow")  # dot-less builtin token, not a plugin
        False
        
        >>> is_plugin_invocation(None)
        False
    
    Notes:
        - This is a quick check, not full validation
        - Full syntax validation happens in plugin_syntax module
        - Used by dispatch_launcher.py to detect plugin calls
        - Returns False for non-string types (safe for any input)
    
    See Also:
        - plugin_resolver.resolve_plugin_invocation: Full resolution with validation
        - plugin_syntax.parse_plugin_invocation: Regex-based syntax validation
    """
    if not isinstance(value, str):
        return False

    # Canonical sigil is "&." (leading dot included). A bare "&plugin.fn()" or a
    # dot-less builtin token ("&zNow") is intentionally NOT detected here.
    return value.startswith(CHAR_AMPERSAND + CHAR_DOT)
