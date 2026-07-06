# zOS/core/L2_Core/c_zDisplay/zDisplay_modules/c_basic/outputs/text_renderer.py

"""
Text Renderer - Helper module for BasicOutputs
===============================================

Provides text rendering logic:
- Text rendering with indentation and pause
- Variable and function resolution
- Semantic rendering

Note: rich_text has been moved to e_advanced/markdown/rich_text_renderer.py
"""

from zOS import Any, Optional

from ...display_constants import (  # pylint: disable=relative-beyond-top-level
    DEFAULT_BREAK_MESSAGE,
    _EVENT_NAME_TEXT,
    _KEY_CONTENT,
    _KEY_INDENT,
    _KEY_BREAK,
    _KEY_BREAK_MESSAGE,
    TERMINAL_MODES,
)
from .rendering_utilities import wrap_with_color


class TextRenderer:
    """Text rendering logic for BasicOutputs (rich_text moved to e_advanced)."""

    def __init__(self, display_instance: Any) -> None:
        """Initialize TextRenderer with display reference.
        
        Args:
            display_instance: Parent zDisplay instance
        """
        self.display = display_instance
        self.zPrimitives = display_instance.zPrimitives
        self.zColors = display_instance.zColors

    def render_text(
        self,
        content: str,
        indent: int,
        pause: bool,
        break_message: Optional[str],
        break_after: Optional[bool],
        semantic: Optional[str],
        _context: Optional[dict],
        color: Optional[str],
        kwargs: dict,
        content_transformers: Any,
    ) -> None:
        """Render text with optional indentation and pause.
        
        Args:
            content: Text content to display
            indent: Indentation level
            pause: Pause for user acknowledgment
            break_message: Custom break message
            break_after: Legacy parameter (backward compatibility)
            semantic: DEPRECATED - Use _zHTML instead (backward compatibility)
            _context: Context for variable resolution
            kwargs: Additional parameters (including _zHTML)
            content_transformers: ContentTransformers instance
        """
        # Handle backward compatibility: break_after overrides pause if provided
        should_break = break_after if break_after is not None else pause

        # Unified semantic element type: _zHTML takes precedence over legacy semantic
        element_type = kwargs.get('_zHTML') or semantic

        # Resolve %variable references
        content = content_transformers.resolve_variables(content, _context)

        # Resolve &function calls
        content = content_transformers.resolve_functions(content)

        # Apply semantic rendering if specified (terminal mode only)
        if element_type and self.display.mode in TERMINAL_MODES:
            content = content_transformers.apply_semantic(content, element_type)

        # Convert emojis to [description] for terminal accessibility
        content = content_transformers.convert_emojis_for_terminal(content)

        # Build event dict with all parameters (AFTER variable resolution)
        event_data = {
            _KEY_CONTENT: content,
            _KEY_INDENT: indent,
            _KEY_BREAK: should_break,
            _KEY_BREAK_MESSAGE: break_message,
            **kwargs
        }

        # Add _zHTML to event_data for Bifrost (if provided)
        if element_type:
            event_data["_zHTML"] = element_type

        # Add color to event_data for Bifrost (if provided)
        if color:
            event_data["color"] = color

        # Try GUI mode first - send clean event with break metadata
        if self.zPrimitives.send_gui_event(_EVENT_NAME_TEXT, event_data):
            return  # GUI event sent successfully

        # zCLI mode - output text and optionally pause
        # Decode escape sequences for terminal UNLESS _zHTML="code"
        if element_type != "code":
            try:
                from zlsp.parser.basic.escape_processors import decode_unicode_escapes
                content = decode_unicode_escapes(content)
            except ImportError:
                pass  # zlsp optional — leave escapes literal rather than crash

        # Apply ANSI color for terminal mode
        if color:
            content = wrap_with_color(content, color.upper(), self.zColors)

        # Apply indentation
        if indent > 0:
            indent_str = content_transformers.build_indent(indent)
            # Apply indent to each line
            content = '\n'.join(indent_str + line if line else line for line in content.split('\n'))

        # Display text using primitive
        self.zPrimitives.line(content)

        # Auto-break if enabled (pause for user input)
        if should_break:
            # Build break message
            message = break_message or DEFAULT_BREAK_MESSAGE
            if indent > 0:
                indent_str = content_transformers.build_indent(indent)
                message = f"{indent_str}{message}"

            # Display message and wait for Enter using primitives
            self.zPrimitives.line(message)
            self.zPrimitives.read_string("")  # Wait for Enter (discard result)
