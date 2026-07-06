# zOS/core/L2_Handling/i_zFunc/zFunc_modules/arg_processing/__init__.py

"""
Argument processing subpackage for zFunc subsystem.

This subpackage provides utilities for processing function arguments with
zCLI-specific business logic (zContext, zHat, zConv injection).

Architecture Pattern:
    - argument_splitter: Delegates to zParser's universal splitting primitive
    - context_injector: zCLI-specific special argument type injection
    - argument_processor: Main orchestrator combining splitting and injection

Clear Separation from zParser:
    - zParser: Universal parsing primitives (syntax, strings, no business logic)
    - arg_processing: zCLI-specific processing (zContext, zHat, zConv injection)

Pattern Source:
    - Extracted from func_args.py (519 lines → 3 focused modules)
    - Renamed from parsers/ to avoid confusion with zParser subsystem

Version History
---------------
- v1.6.1: Renamed from parsers/ to arg_processing/ for clarity
- v1.6.0: Created during refactoring (extracted from func_args.py)
"""

from .argument_splitter import split_arguments
from .argument_processor import process_arguments

__all__ = [
    "split_arguments",
    "process_arguments",
]
