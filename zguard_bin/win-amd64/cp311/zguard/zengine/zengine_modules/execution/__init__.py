# zguard/zengine/zengine_modules/execution/__init__.py

"""
Execution strategies for zWizard subsystem.

Provides mode-specific execution strategies:
- SequentialExecutor: zCLI mode (blocking, sequential)
- ChunkedExecutor: Bifrost mode (progressive, chunked)
"""

from .zengine_execution_sequential import SequentialExecutor
from .zengine_execution_chunked import ChunkedExecutor

__all__ = [
    "SequentialExecutor",
    "ChunkedExecutor",
]
