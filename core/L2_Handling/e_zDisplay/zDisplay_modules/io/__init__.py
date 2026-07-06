# zOS/core/L2_Core/c_zDisplay/zDisplay_modules/b_primitives/__init__.py

"""
Tier 1 Primitives - Terminal I/O Syscall Wrappers
==================================================

Public API for primitive I/O operations - direct wrappers around
terminal syscalls (print, input, getpass).

Architecture:
    - Unified Facade: zPrimitives (display_primitives.py)
    - Output Facade: PrimitivesOutputs (display_primitives_outputs.py)
    - Input Facade: PrimitivesInputs (display_primitives_inputs.py)
    - Outputs: outputs/ directory (output_raw, output_line, output_block)
    - Inputs: inputs/ directory (input_string, input_password)

⚠️ CRITICAL: This tier contains ONLY terminal syscall wrappers.
All other utilities have been relocated to appropriate tiers:
- Rendering utilities → c_basic/outputs/rendering_utilities.py
- State management → e_advanced/timebased_utilities.py
"""

from .display_primitives import zPrimitives
from .display_primitives_outputs import PrimitivesOutputs
from .display_primitives_inputs import PrimitivesInputs

__all__ = [
    'zPrimitives',
    'PrimitivesOutputs',
    'PrimitivesInputs',
]

