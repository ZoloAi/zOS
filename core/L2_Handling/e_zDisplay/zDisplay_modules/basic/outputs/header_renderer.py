# zOS/core/L2_Core/c_zDisplay/zDisplay_modules/c_basic/outputs/header_renderer.py

"""
Header Renderer - Helper module for BasicOutputs
=================================================

Provides header rendering logic:
- Label resolution (variables, functions, semantic, emoji)
- GUI mode event sending
- Terminal mode rendering with width-safe formatting
- Color and style application
"""

from zOS import Any, Optional, Tuple

from ...display_constants import (  # pylint: disable=relative-beyond-top-level
    DEFAULT_COLOR,
    _EVENT_NAME_HEADER,
    _KEY_LABEL,
    _KEY_COLOR,
    _KEY_INDENT,
    _KEY_STYLE,
    TERMINAL_MODES,
)


# Style constants
DEFAULT_STYLE_FULL = "full"
DEFAULT_STYLE_SINGLE = "single"
DEFAULT_STYLE_WAVE = "wave"
DEFAULT_STYLE_STAR = "star"
DEFAULT_STYLE_HASH = "hash"
DEFAULT_STYLE_PLUS = "plus"


class HeaderRenderer:
    """Header rendering logic for BasicOutputs."""

    def __init__(self, display_instance: Any) -> None:
        """Initialize HeaderRenderer with display reference.
        
        Args:
            display_instance: Parent zDisplay instance
        """
        self.display = display_instance
        self.zPrimitives = display_instance.zPrimitives
        self.zColors = display_instance.zColors

    def render_header(
        self,
        label: str,
        color: str,
        indent: int,
        style: str,
        semantic: Optional[str],
        kwargs: dict,
        content_transformers: Any
    ) -> None:
        """Render header with styling (orchestrator method).
        
        Args:
            label: Header text to display
            color: Color name for styling
            indent: Indentation level
            style: Header line style ("full", "single", "wave", "star", "hash", "plus")
            semantic: DEPRECATED - Use _zHTML instead (backward compatibility)
            kwargs: Additional parameters for GUI mode (including _zHTML)
            content_transformers: ContentTransformers instance for label resolution
        """
        # Unified semantic element type: _zHTML takes precedence over legacy semantic
        element_type = kwargs.get('_zHTML') or semantic
        
        # Resolve dynamic content
        label = self._resolve_header_label(label, element_type, kwargs, content_transformers)

        # Try GUI mode first
        if self._try_header_gui_mode(label, color, indent, style, element_type, kwargs):
            return

        # zCLI mode - render formatted header
        self._render_header_terminal(label, color, indent, style, content_transformers)

    def _resolve_header_label(
        self,
        label: str,
        element_type: Optional[str],
        kwargs: dict,
        content_transformers: Any
    ) -> str:
        """Resolve %variables, &functions, _zHTML formatting, and emoji conversion in label."""
        # Resolve %variable references
        context = kwargs.get('_context', {})
        label = content_transformers.resolve_variables(label, context)

        # Resolve &function calls
        label = content_transformers.resolve_functions(label)

        # Apply semantic rendering for terminal mode
        if element_type and self.display.mode in TERMINAL_MODES:
            label = content_transformers.apply_semantic(label, element_type)

        # Convert emojis to [description] for terminal accessibility
        label = content_transformers.convert_emojis_for_terminal(label)

        return label

    def _try_header_gui_mode(
        self,
        label: str,
        color: str,
        indent: int,
        style: str,
        element_type: Optional[str],
        kwargs: dict
    ) -> bool:
        """Try to send header as GUI event, return True if successful."""
        if hasattr(self.display, 'logger') and self.display.logger:
            self.display.logger.info(f"[HeaderRenderer] Sending GUI header: label={label}, indent={indent}")
        
        event_data = {
            _KEY_LABEL: label,
            _KEY_COLOR: color,
            _KEY_INDENT: indent,
            _KEY_STYLE: style,
            **kwargs
        }

        if element_type:
            event_data["_zHTML"] = element_type

        return self.zPrimitives.send_gui_event(_EVENT_NAME_HEADER, event_data)

    def _render_header_terminal(
        self,
        label: str,
        color: str,
        indent: int,
        style: str,
        content_transformers: Any
    ) -> None:
        """Render header for terminal mode with width-safe formatting."""
        # ALWAYS decode escape sequences for terminal (Unicode + basic escapes like \n, \t)
        try:
            from zlsp.parser.basic.escape_processors import decode_unicode_escapes
            label = decode_unicode_escapes(label)
        except ImportError:
            # Fallback if zlsp not available
            pass

        term_width = self.zPrimitives.get_terminal_columns()
        indent_str, inner_width = self._calculate_header_dimensions(
            indent, term_width, content_transformers
        )

        if inner_width <= 0:
            self.zPrimitives.line("")
            return

        sep = self._get_header_separator(style)
        header_content = self._build_header_line(label, color, inner_width, sep)
        
        # Split multi-line header and apply indent to each line
        for line in header_content.split('\n'):
            self.zPrimitives.line(f"{indent_str}{line}")

    def _calculate_header_dimensions(
        self,
        indent: int,
        term_width: int,
        content_transformers: Any
    ) -> Tuple[str, int]:
        """Calculate indent string and inner width for header."""
        indent_str = content_transformers.build_indent(indent)
        if len(indent_str) >= term_width:
            indent_str = indent_str[: max(0, term_width - 1)]

        inner_width = term_width - len(indent_str)
        return indent_str, inner_width

    def _get_header_separator(self, style: str) -> str:
        """Get separator character based on style.
        
        Supported ANSI-safe styles:
        - full: = (equals)
        - single: - (hyphen)
        - wave: ~ (tilde)
        - star: * (asterisk)
        - hash: # (hash/pound)
        - plus: + (plus)
        """
        style_map = {
            DEFAULT_STYLE_FULL: "=",
            DEFAULT_STYLE_SINGLE: "-",
            DEFAULT_STYLE_WAVE: "~",
            DEFAULT_STYLE_STAR: "*",
            DEFAULT_STYLE_HASH: "#",
            DEFAULT_STYLE_PLUS: "+",
        }
        return style_map.get(style, "-")

    def _build_header_line(self, label: str, color: str, inner_width: int, sep: str) -> str:
        """Build the header line with title, color, and separators (above and below format)."""
        title = (label or "").strip()

        if not title:
            return sep * inner_width

        # Apply color to title if needed
        title_colored = self._apply_header_color_simple(title, color)
        
        # Calculate separator length based on title length (shorter equals signs)
        title_len = len(title)
        sep_len = min(title_len, inner_width)
        separator_line = sep * sep_len
        
        # Build three-line format: separator, title, separator
        return f"{separator_line}\n{title_colored}\n{separator_line}"

    def _apply_header_color_simple(self, title: str, color: str) -> str:
        """Apply color formatting to header title.

        Routes semantic color names (PRIMARY, WARNING, DANGER, …) through the
        SSOT mapper (get_semantic_color) so headers match zText/links exactly.
        A raw \\033 escape is passed through untouched; an unknown name yields
        no color rather than a wrong one.
        """
        if not color or color == DEFAULT_COLOR:
            return title

        try:
            if isinstance(color, str) and color.startswith('\033'):
                color_code = color
            else:
                from .semantic_colors import get_semantic_color
                color_code = get_semantic_color(color)

            if not color_code:
                return title

            reset_code = getattr(self.zColors, "RESET", "")
            return f"{color_code}{title}{reset_code}"
        except Exception:
            return title
