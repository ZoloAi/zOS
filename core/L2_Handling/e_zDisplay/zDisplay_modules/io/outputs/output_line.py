# zOS/core/L2_Handling/c_zDisplay/zDisplay_modules/b_primitives/primitives/output_line.py

"""
Line Output Primitive - Single line with newline.

Ensures content is written as a single line with proper newline handling
for both terminal and GUI modes.
"""

from zOS import Any
from ...display_constants import (
    _WRITE_TYPE_LINE,
)


class LineOutput:
    """Line output primitive - write single line with newline."""

    display: Any
    _is_bifrost: bool

    def __init__(self, display_instance: Any, is_bifrost: bool) -> None:
        """Initialize with parent display instance and mode flag.
        
        Args:
            display_instance: Parent zDisplay instance
            is_bifrost: Pre-computed mode flag (True if Bifrost mode)
        """
        self.display = display_instance
        self._is_bifrost = is_bifrost

    def line(self, content: str) -> None:
        """Write single line, ensuring newline.
        
        Exclusive mode behavior:
            - zCLI mode: outputs to terminal with newline
            - Bifrost mode: sends via WebSocket to zComm (without newline)
        
        Args:
            content: Text to write (newline added for terminal)
            
        Example:
            z.display.line("Processing complete")
        """
        if self._is_bifrost:
            self.display.zPrimitives._send_to_bifrost(content, _WRITE_TYPE_LINE)
        else:
            # Ensure content has newline for terminal
            terminal_content = content if content.endswith('\n') else content + '\n'
            print(terminal_content, end='', flush=True)
