# zOS/core/L2_Handling/i_zFunc/zFunc_modules/executors/base_executor.py

"""
Base executor mixin with shared execution logic.

This module provides shared functionality for all executor types, eliminating
code duplication between Python and plugin execution. The ExecutionMixin
extracts common patterns used across multiple executors.

Architecture Position
--------------------
**Tier 1: Foundation** - Base class for executor composition

Pattern Source:
    - a_zConfig/paths/config_paths.py (mixin composition via multiple inheritance)
    - DRY principle: Extract once, use everywhere

Key Functionality
-----------------
1. **Dependency Injection**: Auto-inject parameters based on function signature
2. **Async Handling**: Detect and execute coroutines with proper event loop handling

Code Duplication Eliminated
---------------------------
This mixin eliminates 34 lines of duplicated code:
    - zFunc._execute_function() lines 203-224 (injection) + 236-252 (async)
    - plugin_executor.execute_plugin_function() lines 130-139 (injection) + 144-159 (async)

Integration Points
------------------
**Used By**:
- PythonExecutor: Python function execution (from zFunc)
- plugin_executor.py: Plugin function execution (refactored)

**Dependencies**:
- inspect: Function signature inspection
- asyncio: Coroutine detection and execution
- func_constants: Timeout values

Usage Examples
--------------
Example 1: Basic mixin usage
    >>> class MyExecutor(ExecutionMixin):
    ...     def __init__(self, zos):
    ...         self.zos = zos
    ...         self.logger = zos.logger
    ...     
    ...     def execute(self, func, args, context):
    ...         available_deps = {"zos": self.zos, "context": context}
    ...         kwargs = self._inject_dependencies(func, available_deps)
    ...         result = func(*args, **kwargs)
    ...         return self._handle_async_result(result)

Example 2: Async function handling
    >>> async def fetch_data():
    ...     return {"data": [...]}
    >>> result = executor._handle_async_result(fetch_data())
    >>> # Automatically awaited in proper event loop

Version History
---------------
- v1.6.0: Extracted from zFunc._execute_function() and plugin_executor during refactoring
"""

from zOS import inspect, asyncio, Any, Callable, Dict

from ..func_constants import (
    TIMEOUT_ASYNC_EXECUTION,
    LOG_MSG_COROUTINE_DETECTED,
    LOG_MSG_EVENT_LOOP_RUNNING,
    LOG_MSG_NO_EVENT_LOOP,
)


class ExecutionMixin:
    """
    Shared execution logic for Python and plugin executors.
    
    This mixin provides common functionality used by multiple executor types:
    - Auto-inject dependencies based on function signature
    - Handle async functions (coroutines) with proper event loop handling
    
    Attributes Required (must be provided by inheriting class):
        self.logger: Logger instance for debug messages
    
    Methods:
        _inject_dependencies: Auto-inject parameters based on function signature
        _handle_async_result: Execute coroutines with timeout and event loop handling
    
    Notes:
        - Uses inspect.signature() for parameter detection
        - Supports both CLI mode (no event loop) and Bifrost mode (running loop)
        - 300-second timeout for async execution (configurable via TIMEOUT_ASYNC_EXECUTION)
    """

    def _inject_dependencies(self, func: Callable, available_deps: Dict[str, Any]) -> Dict[str, Any]:
        """
        Auto-inject dependencies based on function signature.
        
        Inspects the function signature and builds a kwargs dict with only the
        parameters that the function accepts. This allows transparent dependency
        injection without requiring manual parameter passing.
        
        Extracted from:
            - zFunc._execute_function() lines 203-224
            - plugin_executor.execute_plugin_function() lines 130-139
        
        Parameters
        ----------
        func : Callable
            Function to inspect for parameter injection.
            
        available_deps : Dict[str, Any]
            Dictionary of available dependencies to inject.
            Keys are parameter names, values are dependency instances.
            Common keys: "zos", "session", "context"
            
        Returns
        -------
        Dict[str, Any]
            Dictionary of kwargs to pass to function.
            Only includes parameters that the function accepts.
            
        Examples
        --------
        Example 1: Function with zos parameter
            >>> def my_func(arg1, zos):
            ...     return zos.config.get("setting")
            >>> deps = {"zos": zos_instance, "session": session_instance}
            >>> kwargs = self._inject_dependencies(my_func, deps)
            >>> # Returns: {"zos": zos_instance}
            >>> result = my_func("value", **kwargs)
        
        Example 2: Function with multiple dependencies
            >>> def process_data(data, zos, context):
            ...     return zos.zdata.process(data, context)
            >>> deps = {"zos": zos, "context": ctx, "session": sess}
            >>> kwargs = self._inject_dependencies(process_data, deps)
            >>> # Returns: {"zos": zos, "context": ctx}
        
        Notes
        -----
        - Uses inspect.signature() for parameter detection
        - Only injects parameters that function actually accepts
        - Logs debug message for each injection (via self.logger)
        - Empty dict returned if no matching parameters
        """
        sig = inspect.signature(func)
        kwargs = {}

        for param_name in sig.parameters:
            if param_name in available_deps:
                self.logger.debug(f"Auto-injecting '{param_name}' parameter")
                kwargs[param_name] = available_deps[param_name]

        return kwargs

    def _handle_async_result(self, result: Any) -> Any:
        """
        Handle async coroutine execution with timeout.
        
        Detects if the result is a coroutine and executes it with proper event
        loop handling. Supports both CLI mode (no running loop) and Bifrost mode
        (running loop with thread-safe execution).
        
        Extracted from:
            - zFunc._execute_function() lines 236-252
            - plugin_executor.execute_plugin_function() lines 144-159
        
        Parameters
        ----------
        result : Any
            Function execution result. Can be:
            - Regular value: Returned immediately
            - Coroutine: Awaited with proper event loop handling
            
        Returns
        -------
        Any
            - For regular values: Returns immediately
            - For coroutines: Returns awaited result
            
        Raises
        ------
        TimeoutError
            If async execution exceeds TIMEOUT_ASYNC_EXECUTION (300 seconds)
            
        Examples
        --------
        Example 1: Regular (sync) result
            >>> result = func()  # Returns: 42
            >>> handled = self._handle_async_result(result)
            >>> # Returns immediately: 42
        
        Example 2: Async result (CLI mode)
            >>> result = async_func()  # Returns: coroutine
            >>> handled = self._handle_async_result(result)
            >>> # Awaited via asyncio.run(): {"data": [...]}
        
        Example 3: Async result (Bifrost mode with running loop)
            >>> result = async_func()  # Returns: coroutine
            >>> handled = self._handle_async_result(result)
            >>> # Awaited via run_coroutine_threadsafe(): {"data": [...]}
        
        Notes
        -----
        - **Detection**: Uses asyncio.iscoroutine() for coroutine detection
        
        - **CLI Mode** (no running loop):
            - Detected via RuntimeError from get_running_loop()
            - Executes with: asyncio.run(result)
            - Creates temporary event loop
        
        - **Bifrost Mode** (running loop):
            - Detected via asyncio.get_running_loop() success
            - Executes with: asyncio.run_coroutine_threadsafe()
            - Runs in existing event loop from separate thread
            - Uses future.result(timeout=300) for timeout
        
        - **Timeout**: 300 seconds (5 minutes) for async execution
        - **Thread-Safe**: run_coroutine_threadsafe handles cross-thread execution
        """
        if not asyncio.iscoroutine(result):
            return result

        self.logger.debug(LOG_MSG_COROUTINE_DETECTED)

        try:
            # Check if event loop is already running (Bifrost mode)
            loop = asyncio.get_running_loop()
            self.logger.debug(LOG_MSG_EVENT_LOOP_RUNNING)

            # Use run_coroutine_threadsafe to execute coroutine from sync context
            future = asyncio.run_coroutine_threadsafe(result, loop)
            return future.result(timeout=TIMEOUT_ASYNC_EXECUTION)

        except RuntimeError:
            # No event loop running - use asyncio.run (CLI mode)
            self.logger.debug(LOG_MSG_NO_EVENT_LOOP)
            return asyncio.run(result)
