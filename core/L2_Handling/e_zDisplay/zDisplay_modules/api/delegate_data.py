# zOS/core/L2_Core/c_zDisplay/zDisplay_modules/delegates/delegate_data.py

"""
Data Display Delegate Methods for zDisplay.

This module provides structured data display convenience methods for common
data presentation patterns like lists, JSON output, and tables. These methods
handle formatting and rendering of complex data structures.

Methods:
    - list: Display bulleted/numbered lists
    - json_data: Display JSON-formatted data
    - json: Alias for json_data
    - zTable: Display tabular data with pagination

Pattern:
    All methods delegate to handle() with data event dictionaries.
    Data structures are serialized and formatted appropriately for display mode.

Grade: A+ (Type hints, constants, comprehensive docs)
"""

from zOS import Any, List, Dict, Optional, Union
from ..display_constants import (
    _KEY_EVENT,
    _EVENT_LIST,
    _EVENT_JSON,
    _EVENT_JSON_DATA,
    _EVENT_ZTABLE,
)

# Module-specific constants
DEFAULT_STYLE_BULLET = "bullet"
DEFAULT_INDENT = 0
DEFAULT_INDENT_SIZE = 2


class DelegateData:  # pylint: disable=no-member
    """Mixin providing data display delegate methods.
    
    These methods handle display of structured data like lists, JSON,
    and tables with appropriate formatting for the current display mode.
    
    Note:
        This is a mixin class. The handle() method is provided by the
        subclass (zDisplay). Pylint warnings about missing 'handle' member
        are expected and suppressed.
    """

    # Data Display Delegates

    def list(
        self,
        items: List[str],
        style: str = DEFAULT_STYLE_BULLET,
        indent: int = DEFAULT_INDENT
    ) -> Optional[Any]:
        """Display bulleted, numbered, or plain list.
        
        Args:
            items: List of strings to display
            style: List style - 'bullet', 'numbered', or 'none' (default: bullet)
                   - 'bullet': Prefix each item with "- "
                   - 'numbered': Prefix with "1. ", "2. ", etc.
                   - 'none': No prefix (clean output)
            indent: Indentation level (default: 0)
            
        Returns:
            Optional[Any]: Navigation signal (zLink dict) if user clicked a link, None otherwise
            
        Example:
            display.list(["Apple", "Banana"], style="numbered")
            display.list(["[DIR] folder/"], style="none")
        """
        return self.handle({
            _KEY_EVENT: _EVENT_LIST,
            "items": items,
            "style": style,
            "indent": indent,
        })


    def json_data(
        self,
        data: Dict[str, Any],
        indent_size: int = DEFAULT_INDENT_SIZE,
        indent: int = DEFAULT_INDENT,
        color: bool = False
    ) -> Any:
        """Display JSON-formatted data.
        
        Args:
            data: Dictionary to display as JSON
            indent_size: JSON indentation (default: 2)
            indent: Line indentation level (default: 0)
            color: Enable syntax coloring (default: False)
            
        Returns:
            Any: Result from handle() method
            
        Example:
            display.json_data({"name": "Alice", "age": 30}, indent_size=4)
        """
        return self.handle({
            _KEY_EVENT: _EVENT_JSON_DATA,
            "data": data,
            "indent_size": indent_size,
            "indent": indent,
            "color": color,
        })

    def json(
        self,
        data: Dict[str, Any],
        indent_size: int = DEFAULT_INDENT_SIZE,
        indent: int = DEFAULT_INDENT,
        color: bool = False
    ) -> Any:
        """Display JSON-formatted data (alias for json_data).
        
        Args:
            data: Dictionary to display as JSON
            indent_size: JSON indentation (default: 2)
            indent: Line indentation level (default: 0)
            color: Enable syntax coloring (default: False)
            
        Returns:
            Any: Result from handle() method
            
        Example:
            display.json({"status": "ok", "count": 42})
        """
        return self.handle({
            _KEY_EVENT: _EVENT_JSON,
            "data": data,
            "indent_size": indent_size,
            "indent": indent,
            "color": color,
        })

    def zTable(
        self,
        title: Optional[str] = None,
        columns: Optional[List[str]] = None,
        rows: Optional[List[List[Any]]] = None,
        limit: Optional[int] = None,
        offset: int = 0,
        show_header: bool = True,
        zPages: bool = False,
        caption: Optional[str] = None,
        truncate: Union[bool, int] = False,
        _zColumn: Optional[Any] = None,
        **passthrough: Any,
    ) -> Any:
        """Display tabular data with optional pagination.

        Pure display primitive — renders whatever columns/rows are passed in.

        Args:
            title: Table title
            columns: Column header labels
            rows: List of row data (each row is a list of cell values)
            limit: Optional row limit for pagination (default: None)
            offset: Starting row offset (default: 0)
            show_header: Show column headers (default: True)
            zPages: Enable paginated navigation controls (default: False)
            caption: Optional table caption
            truncate: Column width control (zCLI only) —
                False (default): content-fit columns;
                int (e.g. 20): fixed-width columns clipped with "..."
            _zColumn: Per-column style overrides
            **passthrough: Extra display props (_zClass, _zStyle, …) forwarded as JSON

        Returns:
            Any: Result from handle() method
        """
        event_dict = {
            _KEY_EVENT: _EVENT_ZTABLE,
            "title": title,
            "columns": columns,
            "rows": rows,
            "limit": limit,
            "offset": offset,
            "show_header": show_header,
            "zPages": zPages,
            "truncate": truncate,
        }
        if caption:
            event_dict["caption"] = caption
        if _zColumn:
            event_dict["_zColumn"] = _zColumn
        if passthrough:
            event_dict.update(passthrough)
        return self.handle(event_dict)
