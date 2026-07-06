# zOS/core/L2_Handling/c_zDisplay/zDisplay_modules/b_primitives/primitives/output_block.py

"""
Block Output Primitive - Multi-line with final newline.

Handles multi-line content blocks with proper newline handling
for both terminal and GUI modes.
"""

from zOS import Any
from ...display_constants import (
    _WRITE_TYPE_BLOCK,
)


class BlockOutput:
    """Block output primitive - write multi-line block with final newline."""

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

    def block(self, content: str) -> None:
        """Write multi-line block, ensuring final newline.
        
        Exclusive mode behavior:
            - zCLI mode: outputs to terminal with final newline
            - Bifrost mode: sends via WebSocket to zComm (without trailing newlines)
        
        Args:
            content: Multi-line text to write (final newline added for terminal)
        """
        if self._is_bifrost:
            self.display.zPrimitives._send_to_bifrost(content, _WRITE_TYPE_BLOCK)
        else:
            # Ensure content has newline for terminal
            terminal_content = content if (content and content.endswith('\n')) else content + '\n'
            print(terminal_content, end='', flush=True)
