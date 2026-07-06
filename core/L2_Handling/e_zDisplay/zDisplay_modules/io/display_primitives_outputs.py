# zOS/core/L2_Core/c_zDisplay/zDisplay_modules/b_primitives/display_primitives_outputs.py

"""
Primitive Output Operations - Foundation Layer Facade
======================================================

This module provides the output primitives facade for the zDisplay subsystem.
It delegates to specialized output primitive modules in the outputs/ subdirectory.

Architecture:
    - Facade: PrimitivesOutputs (this file) - unified output interface
    - Outputs: outputs/output_*.py - individual output implementations
    - Each primitive is self-contained in its own file

⚠️ CRITICAL: DO NOT ADD COMPOUND OPERATIONS TO THIS TIER ⚠️

Output Primitives:
    - raw(content, flush): Raw output, no formatting
    - line(content): Single line with newline
    - block(content): Multi-line block with final newline

Exclusive Mode I/O:
    - Terminal Mode (zCLI): Direct console output via print (synchronous)
    - Bifrost Mode: WebSocket events via zComm (asynchronous)
    - Mode is resolved once at init (not per-call)

Dependencies:
    - outputs/: Output primitive implementations
    - a_infrastructure: is_bifrost_mode helper
"""

from zOS import Any

# Import primitive output modules
from .outputs import (
    RawOutput,
    LineOutput,
    BlockOutput,
)


class PrimitivesOutputs:
    """Output primitives facade - delegates to specialized output modules.
    
    Architecture:
        This class uses the Facade pattern to provide a unified interface to
        all primitive output operations. Each operation is implemented in its own
        module under outputs/ for scalability and management.
        
        Output Primitives (outputs/):
            - raw() → RawOutput
            - line() → LineOutput
            - block() → BlockOutput
    """

    # Type hints for instance attributes
    display: Any  # Parent zDisplay instance

    # Primitive module instances
    _raw_output: RawOutput
    _line_output: LineOutput
    _block_output: BlockOutput

    def __init__(self, display_instance: Any) -> None:
        """Initialize PrimitivesOutputs facade with specialized output modules.
        
        Args:
            display_instance: Parent zDisplay instance (provides mode, zcli access)
        """
        self.display = display_instance

        # Instantiate output primitive modules with pre-computed mode flag
        is_bifrost = display_instance._is_bifrost
        self._raw_output = RawOutput(display_instance, is_bifrost)
        self._line_output = LineOutput(display_instance, is_bifrost)
        self._block_output = BlockOutput(display_instance, is_bifrost)

    # Output Primitives - Delegate to specialized modules

    def raw(self, content: str, flush: bool = True) -> None:
        """Write raw content with no formatting or newline.
        
        Delegates to: outputs.output_raw.RawOutput
        """
        self._raw_output.raw(content, flush)

    def line(self, content: str) -> None:
        """Write single line, ensuring newline.
        
        Delegates to: outputs.output_line.LineOutput
        """
        self._line_output.line(content)

    def block(self, content: str) -> None:
        """Write multi-line block, ensuring final newline.
        
        Delegates to: outputs.output_block.BlockOutput
        """
        self._block_output.block(content)

    # Legacy / Backward-Compatible Aliases

    @property
    def write_raw(self):
        """Backward-compatible alias for raw().
        
        Note: Prefer using .raw() for cleaner API calls.
        
        Returns:
            Callable: The raw method
        """
        return self.raw

    @property
    def write_line(self):
        """Backward-compatible alias for line().
        
        Note: Prefer using .line() for cleaner API calls.
        
        Returns:
            Callable: The line method
        """
        return self.line

    @property
    def write_block(self):
        """Backward-compatible alias for block().
        
        Note: Prefer using .block() for cleaner API calls.
        
        Returns:
            Callable: The block method
        """
        return self.block
