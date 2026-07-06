# zOS/core/L2_Core/c_zDisplay/zDisplay_modules/c_basic/outputs/json_renderer.py

"""
JSON Renderer - Helper Module for BasicOutputs
===============================================

This module provides JSON rendering logic for the BasicOutputs facade,
including serialization, indentation, and syntax coloring.

Architecture:
    - Called by: BasicOutputs.json_data()
    - Purpose: Encapsulate JSON rendering complexity
    - Pattern: Helper module for facade (composition)

Functions:
    - try_json_gui_mode(): Attempt GUI mode JSON event
    - render_json_terminal(): Render JSON for terminal with colors
    - serialize_json(): Serialize data to JSON string
    - apply_json_indentation(): Apply base indentation
    - colorize_json(): Apply ANSI color codes to JSON

Dependencies:
    - json: JSON serialization
    - re: Regex for syntax coloring
    - display_constants: Event names and constants
    - rendering_utilities: apply_indent_to_lines helper
"""

from zOS import json, re, Any

# Import DRY helpers
from .rendering_utilities import apply_indent_to_lines

# Import constants from centralized module
from ...display_constants import (  # pylint: disable=relative-beyond-top-level
    _EVENT_NAME_JSON,
    _KEY_DATA,
    _KEY_INDENT_SIZE,
    _KEY_INDENT,
    _JSON_ENSURE_ASCII,
)


class JsonRenderer:
    """JSON rendering helper for BasicOutputs.
    
    Provides JSON serialization, formatting, and syntax coloring
    for terminal and GUI modes.
    """

    def __init__(self, display_instance: Any) -> None:
        """Initialize JsonRenderer with display reference.
        
        Args:
            display_instance: Parent zDisplay instance
        """
        self.display = display_instance
        self.zPrimitives = display_instance.zPrimitives
        self.zColors = display_instance.zColors

    def try_json_gui_mode(self, data: Any, indent_size: int, indent: int) -> bool:
        """Try to send JSON as GUI event, return True if successful.
        
        Args:
            data: Data to serialize
            indent_size: JSON indentation size
            indent: Base indentation level
            
        Returns:
            bool: True if GUI event sent, False if terminal mode
        """
        return self.zPrimitives.send_gui_event(_EVENT_NAME_JSON, {
            _KEY_DATA: data,
            _KEY_INDENT_SIZE: indent_size,
            _KEY_INDENT: indent
        })

    def render_json_terminal(
        self,
        data: Any,
        indent_size: int,
        indent: int,
        color: bool,
        output_callback: Any
    ) -> None:
        """Render JSON for terminal mode with formatting and optional colors.
        
        Args:
            data: Data to serialize
            indent_size: JSON indentation size
            indent: Base indentation level
            color: Enable syntax coloring
            output_callback: Callback to output text (BasicOutputs.text)
        """
        json_str = self.serialize_json(data, indent_size)
        json_str = self.apply_json_indentation(json_str, indent)

        if color:
            json_str = self.colorize_json(json_str)

        # Output via callback (BasicOutputs.text)
        output_callback(json_str, indent=0, break_after=False)

    def serialize_json(self, data: Any, indent_size: int) -> str:
        """Serialize data to JSON string with error handling.
        
        Args:
            data: Data to serialize
            indent_size: JSON indentation size
            
        Returns:
            str: JSON string or error message
        """
        try:
            return json.dumps(data, indent=indent_size, ensure_ascii=_JSON_ENSURE_ASCII)
        except (TypeError, ValueError) as e:
            return f"<Error serializing JSON: {e}>"

    def apply_json_indentation(self, json_str: str, indent: int) -> str:
        """Apply base indentation to each line of JSON string.
        
        Args:
            json_str: JSON string
            indent: Base indentation level
            
        Returns:
            str: Indented JSON string
        """
        return apply_indent_to_lines(json_str, indent)

    def colorize_json(self, json_str: str) -> str:
        """Apply syntax coloring to JSON string with 4-color scheme.
        
        Implements regex-based syntax coloring for professional JSON display:
        - Cyan: JSON keys (quoted strings followed by colon)
        - Green: String values (quoted strings after colon)
        - Yellow: Numeric values (integers and floats)
        - Magenta: Boolean and null values
        
        Args:
            json_str: Plain JSON string to colorize
            
        Returns:
            str: JSON string with ANSI color codes inserted
            
        Implementation:
            Uses 4 regex substitution passes in order:
            1. Color keys: r'"([^"]+)"\\s*:' → cyan
            2. Color string values: r':\\s*"([^"]*)"' → green
            3. Color numbers: r'\\b(\\d+\\.?\\d*)\\b' → yellow
            4. Color booleans/null: r'\\b(true|false|null)\\b' → magenta
            
        Note:
            The color scheme is optimized for dark terminal backgrounds.
        """
        # Color keys (quoted strings followed by colon)
        json_str = re.sub(
            r'"([^"]+)"\s*:',
            f'{self.zColors.CYAN}"\\1"{self.zColors.RESET}:',
            json_str
        )

        # Color string values (quoted strings not followed by colon)
        json_str = re.sub(
            r':\s*"([^"]*)"',
            f': {self.zColors.GREEN}"\\1"{self.zColors.RESET}',
            json_str
        )

        # Color numbers
        json_str = re.sub(
            r'\b(\d+\.?\d*)\b',
            f'{self.zColors.YELLOW}\\1{self.zColors.RESET}',
            json_str
        )

        # Color booleans and null
        json_str = re.sub(
            r'\b(true|false|null)\b',
            f'{self.zColors.MAGENTA}\\1{self.zColors.RESET}',
            json_str
        )

        return json_str
