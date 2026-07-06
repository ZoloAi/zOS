# zOS/core/L2_Core/c_zDisplay/zDisplay_modules/c_basic/outputs/semantic_colors.py

"""
Semantic Colors Utility
========================

Pure utility function for mapping semantic color names to ANSI codes.
"""

from zSys.formatting.colors import Colors


def get_semantic_color(color_name: str) -> str:
    """
    Get ANSI color code for a semantic color name.
    
    This is the single source of truth for Terminal-first color mapping,
    used by all zDisplay events (links, buttons, headers, text, etc.)
    
    Args:
        color_name: Semantic color name (PRIMARY, SUCCESS, DANGER, etc.)
                   Case-insensitive.
    
    Returns:
        ANSI color code string, or empty string for no color
    
    Examples:
        >>> get_semantic_color('PRIMARY')
        '\033[38;5;75m'  # Cyan (ZINFO)
        >>> get_semantic_color('success')
        '\033[38;5;78m'  # Green (ZSUCCESS)
        >>> get_semantic_color('MUTED')
        ''  # No color (plain text)
    """
    color_map = {
        'PRIMARY': Colors.PRIMARY,      # brand light green (not blue)
        'SECONDARY': Colors.SECONDARY,  # brand purple
        'SUCCESS': Colors.ZSUCCESS,     # green
        'INFO': Colors.ZINFO,           # blue
        'WARNING': Colors.ZWARNING,     # orange/yellow (foreground)
        'DANGER': Colors.ZERROR,        # red
        'ERROR': Colors.ZERROR,         # red (alias of DANGER)
        'DEFAULT': '',
        'MUTED': '',
    }
    return color_map.get(color_name.upper(), '')
