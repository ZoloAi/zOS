# zOS/core/L2_Core/c_zDisplay/zDisplay_modules/d_compounds/display_event_data.py

"""
CompoundData - Structured List Display with Recursive Rendering
================================================================

Provides compound list display with recursive rendering, navigation signals,
and variable resolution. Built on BasicOutputs foundation.

Features:
- Display styles: numbered, bullet, letter, roman, circle, square, dash, none
- Recursive rendering: nested arrays and zDisplay events
- Navigation signals: propagates {zLink: href} up the stack
- Variable resolution: %variable references via zParser
- Description lists: HTML <dl>/<dt>/<dd> style rendering

Usage:
    events.CompoundData.list(["A", "B", "C"], style="number")
    # Output: 1. A  2. B  3. C
    
    events.CompoundData.list(["Error 1", "Error 2"], style="bullet")
    # Output: - Error 1  - Error 2

Architecture:
    Layer 2 compound operation built on BasicOutputs foundation.
    Composes with BasicOutputs.text() for terminal display.
"""

from zOS import Any, Optional, Union, List, Dict

# Import constants from centralized module
from ...display_constants import (  # pylint: disable=relative-beyond-top-level
    _EVENT_NAME_LIST,
    STYLE_BULLET,
    STYLE_NUMBER,
    STYLE_LETTER,
    STYLE_ROMAN,
    _KEY_ITEMS,
    _KEY_STYLE,
    _KEY_INDENT,
    DEFAULT_INDENT,
    _INDENT_STRING,
    MODE_ZCLI,
    MODE_BIFROST,
    TERMINAL_MODES,
)
from zOS.zVocabulary import SESSION_KEY_ZMODE

# Import list formatting helpers
from ...utils.list_helpers import generate_prefix, number_to_letter, number_to_roman

# Local constants
MARKER_BULLET: str = "- "
DEFAULT_STYLE = STYLE_BULLET

# CompoundData Class

class CompoundData:
    """Compound list display with recursive rendering and navigation signals.
    
    Builds on BasicOutputs (A+ foundation) to provide compound list operations
    with recursive rendering, variable resolution, and navigation propagation.
    
    **Composition:**
    - Depends on BasicOutputs (A+ grade)
    - Pattern: BasicOutputs.text() for display + zPrimitives for events
    - Benefits: Reuses BasicOutputs logic (indent, I/O, dual-mode)
    
    **Display Styles:**
    - list(style="number") - Numbered lists (1. item, 2. item)
    - list(style="bullet") - Bullet lists (- item, - item)
    - list(style="letter") - Letter lists (a. item, b. item)
    - list(style="roman") - Roman lists (i. item, ii. item)
    - list(style=["bullet", "circle"]) - Cascading styles for nested lists
    
    **Compound Behaviors:**
    - Recursive rendering: Nested arrays and zDisplay events
    - Navigation signals: Propagates {zLink: href} up the stack
    - Variable resolution: %variable references via zParser
    - Description lists: HTML <dl>/<dt>/<dd> style rendering
    
    **Usage:**
    - ~27 references across 14 files
    - Used by: display_delegates, zOpen, zFunc, zShell, zAuth
    
    **Pattern:**
    All methods implement dual-mode I/O (GUI-first, terminal fallback).
    """

    # Type hints for instance attributes
    display: Any  # Parent zDisplay instance
    zPrimitives: Any  # Primitives instance for I/O operations
    zColors: Any  # Colors instance for terminal styling
    BasicOutputs: Optional[Any]  # BasicOutputs instance for composition (wired after init)

    def __init__(self, display_instance: Any) -> None:
        """Initialize BasicData with parent display reference.
        
        Args:
            display_instance: Parent zDisplay instance providing primitives and colors
            
        Note:
            BasicOutputs is set to None initially and wired after initialization
            by display_events.py to avoid circular dependencies. The fallback
            logic handles the rare edge case where BasicOutputs is not yet set.
        """
        self.display = display_instance
        self.zPrimitives = display_instance.zPrimitives
        self.zColors = display_instance.zColors
        # Get reference to BasicOutputs for composition
        self.BasicOutputs = None  # Will be set after zEvents initialization
        # Lazy zMD inline parser — a list item is an inline context (like a table
        # cell), so item text delegates to MarkdownParser.parse_inline (SSOT).
        self._md_parser = None

    # Helper Methods - Output & GUI Event Handling (DRY Fixes)

    def _output_text(self, content: str, indent: int = DEFAULT_INDENT, break_after: bool = False, _compact: bool = False) -> None:
        """Output text via BasicOutputs with fallback (DRY helper).
        
        Args:
            content: Text content to output
            indent: Indentation level (default: 0)
            break_after: Whether to pause after output (default: False)
            _compact: Suppress trailing paragraph \\n (used inside list loops)
            
        Note:
            This helper eliminates 3 duplicate BasicOutputs check + fallback patterns
            (lines 38-42, 75-80 in original). The fallback handles the rare edge
            case where BasicOutputs is not yet wired (initialization race condition).
        """
        if self.BasicOutputs:
            self.BasicOutputs.text(content, indent=indent, break_after=break_after, _compact=_compact)
        else:
            # Fallback if BasicOutputs not set (shouldn't happen)
            indented_content = self._build_indent(indent) + content
            self.zPrimitives.line(indented_content)

    def _build_indent(self, indent: int) -> str:
        """Build indentation string (DRY helper).
        
        Args:
            indent: Indentation level (number of indent units)
            
        Returns:
            str: Indentation string (e.g., "    " for indent=2)
            
        Note:
            This helper eliminates 2 duplicate indent calculation patterns
            (lines 42, 66-68 in original).
        """
        return _INDENT_STRING * indent

    def _send_gui_event(self, event_name: str, event_data: Dict[str, Any]) -> bool:
        """Send GUI event via primitives (DRY helper).
        
        Args:
            event_name: Name of the event (e.g., "list", "json")
            event_data: Event data dictionary
            
        Returns:
            bool: True if GUI event was sent, False if terminal mode
            
        Note:
            This helper eliminates 2 duplicate GUI event send patterns
            (lines 20-26, 46-52 in original).
        """
        return self.zPrimitives.send_gui_event(event_name, event_data)


    # Public Methods - List & JSON Display

    def list(
        self, items: Optional[List[Any]], style: Union[str, List[str]] = DEFAULT_STYLE,
        indent: int = DEFAULT_INDENT, **kwargs  # TODO: DEPRECATE indent - manual removal only, do not auto-fix
    ) -> Optional[Any]:
        """Display list with bullets or numbers in Terminal/GUI modes.
        
        Foundation method for list display. Implements dual-mode I/O pattern
        and composes with BasicOutputs for terminal display.
        
        NEW v1.7: Supports nested arrays and cascading styles!
        
        Supports display styles:
        - Single style: "bullet", "number", "letter", "roman", "none"
        - Cascading styles: ["bullet", "circle", "square"] for nested lists
        
        Args:
            items: List of items to display
                   - String: "Item text"
                   - List: [nested, items] - automatically indented with cascading style
                   - Dict with zDisplay: {zDisplay: {...}} - recursive event rendering
            style: Display style (default: "bullet")
                   - String: "number", "bullet", "letter", "roman", "none"
                   - List: ["bullet", "circle", "square"] - cascades through nesting levels
            indent: Base indentation level (default: 0)
            level: Internal - current nesting level for cascading (default: 0)
        
        Returns:
            None or navigation signal dict
            
        Example:
            # Numbered list (for form options, menu items)
            self.BasicData.list(["Option A", "Option B", "Option C"], style="number")
            # Output:
            #   1. Option A
            #   2. Option B
            #   3. Option C
            
            # Bullet list (for validation errors, feature lists)
            self.BasicData.list(["Error 1", "Error 2"], style="bullet", indent=1)
            # Output:
            #     - Error 1
            #     - Error 2
            
            # Plain list (for clean output like directory listings)
            self.BasicData.list(["[DIR] folder/", "[FILE] file.txt"], style="none")
            # Output:
            #   [DIR] folder/
            #   [FILE] file.txt
            
        zDialog Integration (Week 6.5):
            # Form field options
            self.list(field_options, style="number", indent=1)
            
            # Validation errors
            self.list(validation_errors, style="bullet", indent=1)
            
        zData Integration (Week 6.6):
            # Table names listing
            table_names = ops.adapter.list_tables()
            self.list(table_names, style="bullet")
            
            # Column names
            columns = list(schema[table].keys())
            self.list(columns, style="number")
        
        Note:
            Used by: display_delegates, zOpen, zFunc, zShell
            Composes with: BasicOutputs.text() for terminal display
        """
        # Handle None or empty list
        if not items:
            return

        # Handle description list style (dl/details)
        if style == 'details':
            return self._render_description_list(items, indent, **kwargs)

        # Extract internal level parameter for cascading styles
        level = kwargs.get('_level', 0)

        # Determine current style based on cascading
        if isinstance(style, list):
            # Cascading styles: cycle through list based on nesting level
            cascade_styles = style
            current_style = style[level % len(style)]
        else:
            # Single style: use for all levels
            cascade_styles = None
            current_style = style

        # NEW: In Bifrost mode, process nested zDisplay events in list items BEFORE buffering
        # This ensures nested events (like zURL inside zUL) get individually buffered
        mode = self.display.zos.session.get(SESSION_KEY_ZMODE, MODE_ZCLI)
        if mode == MODE_BIFROST:
            for item in items:
                if isinstance(item, dict) and 'zDisplay' in item:
                    # Process nested zDisplay event to trigger its buffering
                    # Don't need the result, just need the side effect of buffering
                    self.display.handle(item['zDisplay'])

        # Try GUI mode first - send clean event
        if self._send_gui_event(_EVENT_NAME_LIST, {
            _KEY_ITEMS: items,
            _KEY_STYLE: style,  # Send original style (string or list)
            _KEY_INDENT: indent
        }):
            return  # GUI event sent successfully

        # zCLI mode - format and display list
        # Use _generate_prefix() helper for DRY (reused by outline() method)
        # Extract _context from kwargs for %data.* variable resolution (v1.5.12)
        _context = kwargs.get('_context')

        ordinal = 0
        for item in items:
            # Styled-tree node (zMD path): {'text': ..., '_children': node|None}.
            # The child sublist carries its OWN style, so mixed branches render
            # correctly. Rendered inline right after its parent item.
            if isinstance(item, dict) and 'text' in item and '_children' in item:
                ordinal += 1
                content = f"{generate_prefix(current_style, ordinal)}{item['text']}"
                if "%" in content and _context:
                    from .....d_zParser.parser_modules.parser_functions import resolve_variables
                    content = resolve_variables(content, self.display.zos, _context)
                self._output_text(content, indent=indent, break_after=False, _compact=True)
                child = item['_children']
                if child:
                    result = self.list(
                        child['_items'], style=child['_style'],
                        indent=indent + 1, _level=level + 1, _context=_context,
                    )
                    if isinstance(result, dict) and 'zLink' in result:
                        return result
                continue

            # Nested sublists are containers — they must NOT consume an ordinal,
            # otherwise the parent sequence skips (e.g. "1.", sublist, "3.").
            if not isinstance(item, list):
                ordinal += 1
            prefix = generate_prefix(current_style, ordinal)

            # NEW v1.7: Handle nested arrays naturally!
            if isinstance(item, list):
                # Nested array detected - render recursively with cascading style
                # Don't render prefix for nested list (it's a container)
                # Recursively render with incremented level and indent
                result = self.list(
                    item,
                    style=cascade_styles if cascade_styles else current_style,
                    indent=indent + 1,
                    _level=level + 1,
                    _context=_context
                )
                if isinstance(result, dict) and 'zLink' in result:
                    return result

            # Check if item is a zDisplay event (recursive rendering support)
            elif isinstance(item, dict) and 'zDisplay' in item:
                # Recursively render the zDisplay event
                # Print prefix first (compact — spacing emitted once after full loop)
                self._output_text(prefix.rstrip(), indent=indent, break_after=False, _compact=True)
                # Then render the item's zDisplay event and capture result
                result = self.display.handle(item['zDisplay'])

                # If result is a navigation signal, propagate it immediately
                if isinstance(result, dict) and 'zLink' in result:
                    return result
            else:
                # Simple item — inline context: delegate to the zMD inline seam
                # (parse_inline) so **bold**/*italic*/__underline__/`code`/links
                # render exactly as in a table cell. Order: resolve %vars → parse
                # inline → prepend marker (prefix must NOT be markdown-parsed).
                # Emoji + escape decode happen downstream in render_text.
                item_text = str(item)

                # NEW v1.5.12: Resolve %variable references in list items
                if "%" in item_text and _context:
                    from .....d_zParser.parser_modules.parser_functions import resolve_variables
                    item_text = resolve_variables(item_text, self.display.zos, _context)

                if self._md_parser is None:
                    from ...advanced.markdown.markdown_parser import MarkdownParser
                    self._md_parser = MarkdownParser()
                content = f"{prefix}{self._md_parser.parse_inline(item_text)}"

                # Compact output — no per-item paragraph spacing
                self._output_text(content, indent=indent, break_after=False, _compact=True)

        # Single blank line after the full list — top-level only
        # Nested lists (level > 0) don't emit trailing spacing; parent list owns it
        if self.display.mode in TERMINAL_MODES and level == 0:
            self.zPrimitives.raw('\n')

        # Return None if no navigation occurred
        return None

    def _render_description_list(
        self, items: List[Dict[str, Any]], indent: int = DEFAULT_INDENT, **_kwargs
    ) -> Optional[Any]:
        """Render description list (HTML <dl>, <dt>, <dd> style).
        
        Args:
            items: List of dicts with 'term' and 'desc' keys
                   - term: The term being defined (rendered as <dt>)
                   - desc: Definition - string or list of strings (rendered as <dd>)
            indent: Base indentation level (default: 0)
        
        Returns:
            None or navigation signal dict
        """
        if not items:
            return None

        # Try GUI mode first - send clean event
        if self._send_gui_event(_EVENT_NAME_LIST, {
            _KEY_ITEMS: items,
            _KEY_STYLE: 'details',
            _KEY_INDENT: indent
        }):
            return  # GUI event sent successfully

        # zCLI mode rendering
        for item in items:
            if not isinstance(item, dict):
                continue

            term = item.get('term', '')
            descriptions = item.get('desc', [])

            # Normalize descriptions to list
            if not isinstance(descriptions, list):
                descriptions = [descriptions]

            # Display term in bold
            term_indent = self._build_indent(indent)
            term_text = f"{term_indent}\033[1m{term}\033[0m"
            print(term_text)

            # Display each description indented under term (compact — no per-line spacing)
            desc_indent = indent + 1  # Indent descriptions 1 level more than term
            for desc in descriptions:
                if desc:  # Skip empty descriptions
                    self._output_text(str(desc), indent=desc_indent, break_after=False, _compact=True)

            # Single blank line after each term-description group for readability
            print()

        return None
