# zOS/core/L3_Abstraction/l_zWizard/zWizard_modules/execution/__init__.py

"""
Execution strategies for zWizard subsystem.

Provides mode-specific execution strategies:
- SequentialExecutor: zCLI mode (blocking, sequential)
- ChunkedExecutor: Bifrost mode (progressive, chunked)
"""

from .wizard_execution_sequential import SequentialExecutor
from .wizard_execution_chunked import ChunkedExecutor

__all__ = [
    "SequentialExecutor",
    "ChunkedExecutor",
]
