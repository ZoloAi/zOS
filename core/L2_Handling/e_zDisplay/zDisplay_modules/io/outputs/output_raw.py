# zOS/core/L2_Handling/c_zDisplay/zDisplay_modules/b_primitives/primitives/output_raw.py

"""
Raw Output Primitive - No formatting, no newline.

Provides the most basic output operation - write content exactly as-is
with no modifications, formatting, or automatic newlines.
"""

from zOS import Any
from ...display_constants import (
    _DEFAULT_FLUSH,
    _WRITE_TYPE_RAW,
)


class RawOutput:
    """Raw output primitive - write content with no formatting or newline."""

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

    def raw(self, content: str, flush: bool = _DEFAULT_FLUSH) -> None:
        """Write raw content with no formatting or newline.
        
        Exclusive mode behavior:
            - zCLI mode: outputs to terminal (print)
            - Bifrost mode: sends via WebSocket to zComm
        
        Args:
            content: Text to write (no newline added)
            flush: Whether to flush terminal output immediately
            
        Example:
            z.display.raw("Loading")
            z.display.raw("...")
            z.display.raw(" Done!\n")
        """
        if self._is_bifrost:
            self.display.zPrimitives._send_to_bifrost(content, _WRITE_TYPE_RAW)
        else:
            print(content, end='', flush=flush)
