# zOS/core/L2_Handling/g_zParser/parser_modules/shared/display_utils.py

"""
Standardized display integration helpers for parser modules.

Provides reusable display integration patterns to eliminate duplication
of display.zDeclare() calls across parser modules. Ensures consistent
formatting and reduces boilerplate code.

Public API:
    - display_path_info: Display path resolution information
    - display_file_type: Display file type information
    - safe_display: Safely call display method if available

Usage:
    >>> from zOS.L2_Handling.d_zParser.parser_modules.shared import display_path_info
    >>> display_path_info(display, "zPath decoder", path="/app/config", indent=2)

Dependencies:
    - .file_constants: Display configuration constants
    - zOS: Typing imports, Optional

Created: Phase 1 - Extract Shared Infrastructure
"""

from zOS import Any, Dict, Optional
from .file_constants import (
    COLOR_SUBLOADER,
    INDENT_PATH,
    STYLE_SINGLE,
    DISPLAY_MSG_FILE_TYPE_TEMPLATE
)


def display_path_info(
    display: Optional[Any],
    message: str,
    path: Optional[str] = None,
    color: str = COLOR_SUBLOADER,
    indent: int = INDENT_PATH,
    style: str = STYLE_SINGLE
) -> None:
    """
    Display path resolution information using standardized formatting.
    
    Wraps display.zDeclare() with consistent parameters for path operations.
    Safely handles None display instance.
    
    Args:
        display: Display instance (zDisplay) or None
        message: Message to display
        path: Optional path to append to message
        color: Display color (default: SUBLOADER)
        indent: Indentation level (default: 2)
        style: Display style (default: single)
    
    Example:
        >>> display_path_info(display, "Resolved path", path="/app/config/zUI.users")
        # Displays: "Resolved path: /app/config/zUI.users"
    """
    if not display:
        return

    full_message = f"{message}: {path}" if path else message

    display.zDeclare(
        full_message,
        color=color,
        indent=indent,
        style=style
    )


def display_file_type(
    display: Optional[Any],
    file_type: str,
    extension: Optional[str] = None,
    color: str = COLOR_SUBLOADER,
    indent: int = INDENT_PATH,
    style: str = STYLE_SINGLE
) -> None:
    """
    Display file type information using standardized formatting.
    
    Wraps display.zDeclare() with consistent parameters for file type display.
    Formats file type with optional extension.
    
    Args:
        display: Display instance (zDisplay) or None
        file_type: File type identifier (e.g., "zUI", "zSchema")
        extension: Optional file extension (e.g., ".yaml", ".json")
        color: Display color (default: SUBLOADER)
        indent: Indentation level (default: 2)
        style: Display style (default: single)
    
    Example:
        >>> display_file_type(display, "zUI", extension=".yaml")
        # Displays: "Type: zUI|.yaml"
    """
    if not display:
        return

    if extension:
        message = DISPLAY_MSG_FILE_TYPE_TEMPLATE.format(file_type, extension)
    else:
        message = f"Type: {file_type}"

    display.zDeclare(
        message,
        color=color,
        indent=indent,
        style=style
    )


def safe_display(
    display: Optional[Any],
    message: str,
    color: Optional[str] = None,
    indent: Optional[int] = None,
    style: Optional[str] = None,
    **kwargs
) -> None:
    """
    Safely call display.zDeclare() if display instance is available.
    
    Generic wrapper for display.zDeclare() that handles None display instance
    and provides default parameters.
    
    Args:
        display: Display instance (zDisplay) or None
        message: Message to display
        color: Optional display color
        indent: Optional indentation level
        style: Optional display style
        **kwargs: Additional keyword arguments passed to zDeclare()
    
    Example:
        >>> safe_display(display, "Processing file", color="INFO", indent=1)
    """
    if not display:
        return

    params: Dict[str, Any] = {"message": message}

    if color is not None:
        params["color"] = color
    if indent is not None:
        params["indent"] = indent
    if style is not None:
        params["style"] = style

    # Merge additional kwargs
    params.update(kwargs)

    display.zDeclare(**params)
