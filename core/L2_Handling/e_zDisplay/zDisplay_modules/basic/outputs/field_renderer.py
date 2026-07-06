# zOS/core/L2_Core/c_zDisplay/zDisplay_modules/c_basic/outputs/field_renderer.py

"""
Field Renderer - Helper module for BasicOutputs
================================================

Provides field and section rendering logic for Terminal mode:
- render_field: Labeled key-value pairs with color
- render_section_title: Section headers with color
- get_color_code: Safe color code resolution

These are Terminal-mode rendering helpers that use primitives for output.
"""

from zOS import Any


class FieldRenderer:
    """Field and section rendering logic for BasicOutputs."""

    def __init__(self, display_instance: Any) -> None:
        """Initialize FieldRenderer with display reference.
        
        Args:
            display_instance: Parent zDisplay instance
        """
        self.display = display_instance
        self.zPrimitives = display_instance.zPrimitives
        self.zColors = display_instance.zColors

    def render_field(
        self,
        label: str,
        value: Any,
        indent: int,
        color: str
    ) -> None:
        """Render a labeled field with color formatting (Terminal).
        
        This is the standard way to display key-value pairs across all
        zDisplay events. It provides consistent formatting with colored
        labels and proper indentation.
        
        Args:
            label: Field label text (e.g., "Username", "zSession_ID")
            value: Field value to display (any type, converted to string)
            indent: Indentation level (0 = no indent)
            color: Color name for label (e.g., "GREEN", "YELLOW", "CYAN")
        
        Returns:
            None
        
        Format:
            <color>label:<reset> value
        
        Example Output:
            Username: admin          (with colored "Username:")
            zSession_ID: abc123     (with colored "zSession_ID:")
        
        Usage:
            field_renderer.render_field("Username", "admin", indent=0, color="GREEN")
        """
        color_code = self.get_color_code(color)
        content = f"{color_code}{label}:{self.zColors.RESET} {value}"
        self.output_text(content, indent, break_after=False)

    def render_section_title(
        self,
        title: str,
        indent: int,
        color: str
    ) -> None:
        """Render a section title with color formatting (Terminal).
        
        This is the standard way to display section headers across all
        zDisplay events. It provides consistent formatting with colored
        titles and proper indentation.
        
        Args:
            title: Section title text (e.g., "zMachine", "Tool Preferences")
            indent: Indentation level (0 = no indent)
            color: Color name for title (e.g., "GREEN", "CYAN")
        
        Returns:
            None
        
        Format:
            <color>title:<reset>
        
        Example Output:
            zMachine:                (with colored "zMachine:")
            Tool Preferences:        (with colored "Tool Preferences:")
        
        Usage:
            field_renderer.render_section_title("zMachine", indent=0, color="GREEN")
        """
        color_code = self.get_color_code(color)
        content = f"{color_code}{title}:{self.zColors.RESET}"
        self.output_text(content, indent, break_after=False)

    def get_color_code(self, color_name: str) -> str:
        """Get ANSI color code from zColors with fallback to RESET.
        
        This is a safe wrapper for accessing color codes that ensures
        invalid color names don't crash the application.
        
        Args:
            color_name: Color attribute name (e.g., "GREEN", "YELLOW", "CYAN")
        
        Returns:
            str: ANSI color code from zColors, or RESET if not found
        
        Example:
            >>> field_renderer.get_color_code("GREEN")
            "\\033[92m"  # ANSI green
            
            >>> field_renderer.get_color_code("INVALID_COLOR")
            "\\033[0m"   # RESET (fallback)
        """
        if not self.zColors:
            return ""
        return getattr(self.zColors, color_name, getattr(self.zColors, 'RESET', ''))

    def output_text(
        self,
        content: str,
        indent: int,
        break_after: bool
    ) -> None:
        """Output text via BasicOutputs.text() helper.
        
        This is a convenience wrapper for BasicOutputs.text() that handles
        the case where BasicOutputs might not be available yet.
        
        Args:
            content: Text content to display
            indent: Indentation level (0 = no indent)
            break_after: Add line break after text (default: False)
        
        Returns:
            None
        
        Example:
            field_renderer.output_text("Hello, world!", indent=0, break_after=False)
        """
        if not self.display or not hasattr(self.display, 'zEvents'):
            return

        basic_outputs = getattr(self.display.zEvents, 'BasicOutputs', None)
        if not basic_outputs:
            return

        basic_outputs.text(content, indent=indent, break_after=break_after)
