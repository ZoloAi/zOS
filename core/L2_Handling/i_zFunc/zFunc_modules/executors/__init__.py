# zOS/core/L2_Handling/i_zFunc/zFunc_modules/executors/__init__.py

"""
Executor subpackage for zFunc subsystem.

This subpackage provides execution logic for different function types:
- Python functions (internal and external)
- Plugin functions (with auto-injection)
- JavaScript functions (via Node.js)

Architecture Pattern:
    - ExecutionMixin: Shared logic for dependency injection and async handling
    - PythonExecutor: Executes Python functions with auto-injection
    - PluginExecutor: Executes plugin functions (uses ExecutionMixin)

Pattern Source:
    - b_zComm/zComm_modules/ (separation by responsibility)
    - a_zConfig/paths/config_paths.py (mixin composition)

Version History
---------------
- v1.6.0: Created during refactoring (extracted from zFunc.py and plugin_executor.py)
"""

from .base_executor import ExecutionMixin
from .python_executor import PythonExecutor

__all__ = [
    "ExecutionMixin",
    "PythonExecutor",
]
